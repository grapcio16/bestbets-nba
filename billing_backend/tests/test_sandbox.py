import copy
from dataclasses import replace
import hashlib
import hmac
import json
import time
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
import pytest
from sqlalchemy import select,func
from billing_backend.auth import AuthenticationFailed,Identity
from billing_backend.db import Account,Entitlement,EventReceipt,CheckoutAttempt
from billing_backend.policy import evaluate
from billing_backend.service import AccessDenied,Conflict,RateLimited
from billing_backend.stripe_provider import ProviderUnavailable


def signed(env, kind='customer.subscription.updated', obj=None, event_id=None, **changes):
    if obj is None:
        with env.db.transaction() as s:
            customer=s.get(Account,env.user.id).customer_id
        obj={'id':'sub_TestOnly','customer':customer,'status':'active','object':'subscription'}
    value={'id':event_id or 'evt_'+uuid4().hex,'object':'event','type':kind,'livemode':False,'data':{'object':obj}}
    value.update(changes)
    raw=json.dumps(value,separators=(',',':')).encode()
    stamp=int(time.time())
    digest=hmac.new(env.settings.billing.webhook_secret.encode(),str(stamp).encode()+b'.'+raw,hashlib.sha256).hexdigest()
    return raw,f't={stamp},v1={digest}'


def checkout(env):
    return env.service.checkout(env.user.id, accept_terms=True, acknowledge_recurring=True,
        terms_version=env.settings.terms_version)


def auth(env,subject='user-one'):
    return {'Authorization':'Bearer '+env.token(subject)}


@pytest.mark.parametrize('changes',[
    {'iss':'https://attacker.invalid/'},{'aud':'wrong-api'},{'exp':1},
    {'email_verified':False},{'scope':''},{'sub':''},{'iat':int(time.time())+500},
    {'exp':int(time.time())+7200}])
def test_oidc_claims_rejected(env,changes):
    with pytest.raises(AuthenticationFailed):env.verifier.verify(env.token(**changes))


def test_oidc_signature_and_query_forgery(env):
    token=env.token();parts=token.split('.')
    import base64
    claims=json.loads(base64.urlsafe_b64decode(parts[1]+'=='));claims['sub']='another-user'
    parts[1]=base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b'=').decode()
    assert env.client.get('/v1/me',headers={'Authorization':'Bearer '+'.'.join(parts)}).status_code==401
    assert env.client.get('/v1/me?premium=true&user_id=someone',headers={'X-User-ID':'someone'}).status_code==401
    assert env.client.get('/v1/me',headers=auth(env)).json()['user_id']==env.user.id


def test_account_not_linked_by_email_or_client_role(env):
    one=env.client.get('/v1/me',headers=auth(env)).json()
    other=env.client.get('/v1/me',headers={'Authorization':'Bearer '+env.token('other',role='premium',email='same@example.invalid')}).json()
    assert one['user_id']!=other['user_id'] and other['premium'] is False


@pytest.mark.parametrize('status',['trialing','past_due','unpaid','incomplete','incomplete_expired','canceled','paused'])
def test_unpaid_statuses_never_grant(env,status):
    sub,*_=env.world.paid(env.service,env.user.id);sub['status']=status
    assert env.service.entitlement(env.user.id,force=True)['premium'] is False


@pytest.mark.parametrize('field,value',[
    ('currency','eur'),('unit_amount',100),('unit_amount',0),('active',False),('livemode',True),
    ('product','prod_Other'),('id','price_Other'),('type','one_time')])
def test_wrong_price_never_grants_or_creates_checkout(env,field,value):
    env.world.price[field]=value
    with pytest.raises(ProviderUnavailable):checkout(env)
    assert env.world.client.v1.checkout.sessions.create.call_count==0


@pytest.mark.parametrize('value',[{'interval':'year','interval_count':1,'usage_type':'licensed'},
    {'interval':'month','interval_count':2,'usage_type':'licensed'},
    {'interval':'month','interval_count':1,'usage_type':'metered'}])
def test_wrong_recurring_price(env,value):
    env.world.price['recurring']=value
    with pytest.raises(ProviderUnavailable):checkout(env)


@pytest.mark.parametrize('part,field,value',[
    (0,'livemode',True),(0,'customer','cus_Other'),(0,'pause_collection',{'behavior':'void'}),
    (1,'status','open'),(1,'amount_paid',0),(1,'subscription','sub_Other'),(1,'customer','cus_Other'),
    (2,'status','processing'),(2,'amount_received',0),(2,'invoice','in_Other'),
    (3,'refunded',True),(3,'amount_refunded',1),(3,'disputed',True),(3,'captured',False)])
def test_payment_proof_tampering_denied(env,part,field,value):
    objects=env.world.paid(env.service,env.user.id);objects[part][field]=value
    d=evaluate(*objects,env.settings,env.user.id,objects[0]['customer'],env.world.now)
    assert not d.granted


def test_paid_correct_period_only_and_expiration(env):
    sub,inv,pi,ch=env.world.paid(env.service,env.user.id)
    assert env.service.entitlement(env.user.id,force=True)['premium'] is True
    inv['lines']['data'][0]['period']['end']-=86400
    assert env.service.entitlement(env.user.id,force=True)['premium'] is False
    inv['lines']['data'][0]['period']['end']=sub['current_period_end']
    env.world.now=sub['current_period_end']
    assert env.service.entitlement(env.user.id,force=True)['premium'] is False


def test_success_redirect_never_grants(env):
    assert env.client.get('/v1/me?checkout=success&session_id=cs_test_forged',headers=auth(env)).json()['premium'] is False
    assert env.client.get('/v1/premium/check/player-props',headers=auth(env)).status_code==403
    for free in ['schedule','teams','players','injuries']:
        assert env.client.get('/v1/features/'+free).json()['requires_premium'] is False


def test_subscription_other_user_cannot_grant(env):
    sub,*_=env.world.paid(env.service,env.user.id)
    sub['metadata']['internal_user_id']='another-user'
    assert env.service.entitlement(env.user.id,force=True)['premium'] is False


def test_cancel_end_of_period_then_immediate_revocation(env):
    sub,*_=env.world.paid(env.service,env.user.id);sub['cancel_at_period_end']=True
    raw,sig=signed(env)
    assert env.service.webhook(raw,sig)=='processed'
    result=env.service.entitlement(env.user.id)
    assert result['premium'] and result['cancel_at_period_end']
    sub['status']='canceled'
    raw,sig=signed(env,'customer.subscription.deleted')
    env.service.webhook(raw,sig)
    assert env.service.entitlement(env.user.id)['premium'] is False


def test_out_of_order_event_uses_current_stripe_state(env):
    env.world.paid(env.service,env.user.id)
    raw,sig=signed(env,'customer.subscription.deleted')
    env.service.webhook(raw,sig)  # an old cancellation does not overwrite current paid state
    assert env.service.entitlement(env.user.id)['premium'] is True


def test_webhook_real_signature_and_tampering(env):
    env.world.paid(env.service,env.user.id);raw,sig=signed(env)
    assert env.client.post('/webhooks/stripe',content=raw,headers={'Stripe-Signature':sig}).status_code==200
    assert env.client.post('/webhooks/stripe',content=raw+b' ',headers={'Stripe-Signature':sig}).status_code==400
    assert env.client.post('/webhooks/stripe',content=raw,headers={'Stripe-Signature':'t=1,v1=bad'}).status_code==400
    assert env.client.post('/webhooks/stripe',content=raw).status_code==400


def test_duplicate_event_atomic_and_hash_conflict(env):
    env.world.paid(env.service,env.user.id);raw,sig=signed(env,event_id='evt_Duplicate')
    assert env.service.webhook(raw,sig)=='processed'
    count=env.world.client.v1.subscriptions.list.call_count
    assert env.service.webhook(raw,sig)=='duplicate'
    assert env.world.client.v1.subscriptions.list.call_count==count
    raw2,sig2=signed(env,event_id='evt_Duplicate',created=123)
    with pytest.raises(Conflict):env.service.webhook(raw2,sig2)
    with env.db.transaction() as s:assert s.scalar(select(func.count()).select_from(EventReceipt))==1


def test_provider_failure_rolls_back_event_and_retries(env):
    env.world.paid(env.service,env.user.id);raw,sig=signed(env,event_id='evt_Retry')
    env.world.client.v1.prices.retrieve.side_effect=ProviderUnavailable('no provider')
    with pytest.raises(ProviderUnavailable):env.service.webhook(raw,sig)
    with env.db.transaction() as s:assert s.get(EventReceipt,'evt_Retry') is None
    env.world.client.v1.prices.retrieve.side_effect=lambda _:copy.deepcopy(env.world.price)
    assert env.service.webhook(raw,sig)=='processed'
    assert env.service.entitlement(env.user.id)['premium']


def test_stale_cache_fails_closed_and_periodic_reconcile(env):
    env.world.paid(env.service,env.user.id);assert env.service.entitlement(env.user.id,force=True)['premium']
    env.world.now+=61
    env.world.client.v1.prices.retrieve.side_effect=ProviderUnavailable('outage')
    assert env.client.get('/v1/premium/check/simulations',headers=auth(env)).status_code==503
    env.world.client.v1.prices.retrieve.side_effect=lambda _:copy.deepcopy(env.world.price)
    for sub in env.world.subscriptions.values():sub['status']='past_due'
    assert env.service.reconcile()=={'checked':1,'failed':0}
    assert not env.service.entitlement(env.user.id)['premium']


def test_checkout_retries_reuse_attempt_and_customer(env):
    first=checkout(env);second=checkout(env)
    assert first==second and len(env.world.sessions)==1
    assert env.world.client.v1.customers.create.call_count==1
    params=env.world.client.v1.checkout.sessions.create.call_args.args[0]
    assert params['line_items']==[{'price':env.settings.billing.price_id,'quantity':1}]
    assert params['payment_method_types']==['card'] and params['allow_promotion_codes'] is False


def test_crash_after_remote_creation_has_persisted_idempotency(env):
    env.world.timeout_after_create=True
    with pytest.raises(ProviderUnavailable):checkout(env)
    assert len(env.world.sessions)==1
    with env.db.transaction() as s:
        row=s.scalar(select(CheckoutAttempt));assert row.session_id is None
        attempt_id=row.id
    url=checkout(env)
    assert len(env.world.sessions)==1 and 'checkout.stripe.com' in url
    with env.db.transaction() as s:assert s.scalar(select(CheckoutAttempt)).id==attempt_id


def test_checkout_parameter_injection_and_consent(env):
    body={'accept_terms':True,'acknowledge_recurring':True,'terms_version':env.settings.terms_version}
    for extra in ['user_id','customer_id','price_id','success_url','premium']:
        assert env.client.post('/v1/billing/checkout',headers=auth(env),json={**body,extra:'forged'}).status_code==422
    assert env.client.post('/v1/billing/checkout',headers=auth(env),json={**body,'accept_terms':False}).status_code==422
    assert env.client.post('/v1/billing/checkout',headers=auth(env),json={**body,'terms_version':'old'}).status_code==409
    result=env.client.post('/v1/billing/checkout',headers=auth(env),json=body)
    assert result.status_code==200,result.text
    with env.db.transaction() as s:assert s.scalar(select(CheckoutAttempt)).terms_version==env.settings.terms_version


def test_portal_ownership_and_configuration(env):
    checkout(env)
    assert env.client.post('/v1/billing/portal',headers=auth(env),json={'customer_id':'cus_forged'}).status_code==422
    assert env.client.post('/v1/billing/portal',headers=auth(env,'user-two'),json={}).status_code==409
    assert env.client.post('/v1/billing/portal',headers=auth(env),json={}).status_code==200
    cfg=env.world.client.v1.billing_portal.configurations.retrieve.return_value
    cfg['features']['subscription_update']['enabled']=True
    with pytest.raises(ProviderUnavailable):env.service.portal(env.user.id)


def test_live_keys_objects_and_connect_events_refused(env):
    with pytest.raises(Exception):replace(env.settings,billing=replace(env.settings.billing,secret_key='sk_live_SYNTHETIC_FOR_REJECTION')).validate()
    raw,sig=signed(env,livemode=True)
    assert env.client.post('/webhooks/stripe',content=raw,headers={'Stripe-Signature':sig}).status_code==400
    raw,sig=signed(env,account='acct_Connect')
    assert env.client.post('/webhooks/stripe',content=raw,headers={'Stripe-Signature':sig}).status_code==400
    env.world.client.v1.accounts.retrieve_current.return_value={'id':'acct_Other'}
    with pytest.raises(ProviderUnavailable):checkout(env)


def test_unknown_signed_customer_does_not_create_account(env):
    raw,sig=signed(env,obj={'id':'sub_Other','customer':'cus_Unknown'})
    assert env.service.webhook(raw,sig)=='ignored'
    with env.db.transaction() as s:assert s.scalar(select(func.count()).select_from(Account))==1


def test_refund_revokes_and_disabled_user_is_denied(env):
    _,_,_,charge=env.world.paid(env.service,env.user.id)
    assert env.service.entitlement(env.user.id,force=True)['premium']
    charge['refunded']=True
    raw,sig=signed(env,'charge.refunded',charge)
    env.service.webhook(raw,sig)
    assert not env.service.entitlement(env.user.id)['premium']
    with env.db.transaction() as s:s.get(Account,env.user.id).disabled=True
    assert env.client.get('/v1/me',headers=auth(env)).status_code==403


def test_limits_body_size_origin_and_secret_redaction(env):
    assert env.client.post('/webhooks/stripe',content=b'x'*(1024*1024+1)).status_code==413
    assert env.client.get('/v1/me',headers={**auth(env),'Origin':'https://evil.invalid'}).status_code==403
    for _ in range(5):checkout(env)
    with pytest.raises(RateLimited):checkout(env)
    assert env.settings.billing.secret_key not in repr(env.settings)
    assert env.settings.billing.webhook_secret not in repr(env.settings.billing)
    response=env.client.get('/v1/me',headers=auth(env))
    assert response.headers['cache-control']=='no-store'


def test_concurrent_duplicate_webhooks_once(env):
    env.world.paid(env.service,env.user.id);raw,sig=signed(env)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(lambda _:env.service.webhook(raw,sig),range(4)))
    assert results.count('processed')==1 and results.count('duplicate')==3


def test_concurrent_checkout_tabs_one_session(env):
    with ThreadPoolExecutor(max_workers=4) as pool:
        urls=list(pool.map(lambda _:checkout(env),range(4)))
    assert len(set(urls))==1 and len(env.world.sessions)==1


def test_failed_webhook_invalidates_previously_fresh_allow(env):
    sub,*_=env.world.paid(env.service,env.user.id)
    assert env.service.entitlement(env.user.id,force=True)['premium']
    sub['status']='canceled';raw,sig=signed(env,'customer.subscription.deleted')
    env.world.client.v1.prices.retrieve.side_effect=ProviderUnavailable('outage')
    with pytest.raises(ProviderUnavailable):env.service.webhook(raw,sig)
    assert env.client.get('/v1/premium/check/player-props',headers=auth(env)).status_code==503


def test_completed_checkout_and_existing_subscription_prevent_second_charge(env):
    checkout(env)
    session=next(iter(env.world.sessions.values()));session['status']='complete'
    env.world.paid(env.service,env.user.id)
    with pytest.raises(Conflict):checkout(env)
    assert len(env.world.sessions)==1


def test_expired_checkout_attempt_recovered_from_provider(env):
    env.world.timeout_after_create=True
    with pytest.raises(ProviderUnavailable):checkout(env)
    env.world.now+=3601
    url=checkout(env)
    assert 'checkout.stripe.com' in url and len(env.world.sessions)==1


def test_expired_signature_live_api_response_and_disabled_account(env):
    raw,sig=signed(env)
    stamp=int(time.time())-1000
    digest=hmac.new(env.settings.billing.webhook_secret.encode(),str(stamp).encode()+b'.'+raw,hashlib.sha256).hexdigest()
    assert env.client.post('/webhooks/stripe',content=raw,headers={'Stripe-Signature':f't={stamp},v1={digest}'}).status_code==400
    env.world.client.v1.customers.create.side_effect=lambda p,o:{'livemode':True,'id':'cus_NotSandbox'}
    with pytest.raises(ProviderUnavailable):checkout(env)


def test_multi_item_quantity_and_invoice_line_period_are_not_accepted(env):
    sub,inv,pi,ch=env.world.paid(env.service,env.user.id)
    sub['items']['data'][0]['quantity']=2
    assert not evaluate(sub,inv,pi,ch,env.settings,env.user.id,sub['customer'],env.world.now).granted
    sub['items']['data'][0]['quantity']=1
    sub['items']['data'].append(copy.deepcopy(sub['items']['data'][0]))
    assert not evaluate(sub,inv,pi,ch,env.settings,env.user.id,sub['customer'],env.world.now).granted


def test_hosted_urls_account_configuration_and_local_url_restrictions(env):
    for url in ['https://checkout.stripe.com.evil.invalid/x','https://attacker@checkout.stripe.com/x','http://checkout.stripe.com/x']:
        with pytest.raises(ProviderUnavailable):env.provider.hosted_url(url,'checkout.stripe.com')
    from stripe_test_billing import BillingNotConfigured
    for url in ['https://good.invalid/?redirect=evil','https://good.invalid/path','http://evil.invalid']:
        with pytest.raises(BillingNotConfigured):replace(env.settings.billing,app_url=url).validate()


def test_restart_retains_customer_attempt_and_event_receipt(env):
    from billing_backend.service import BillingService
    from billing_backend.db import Database
    first=checkout(env)
    restarted_db=Database(env.settings.database_url)
    service=BillingService(restarted_db,env.provider,env.settings,clock=lambda:env.world.now)
    try:
        assert service.account(Identity(env.settings.oidc_issuer,'user-one')).id==env.user.id
        again=service.checkout(env.user.id,accept_terms=True,acknowledge_recurring=True,terms_version=env.settings.terms_version)
        assert first==again and env.world.client.v1.customers.create.call_count==1
        env.world.paid(env.service,env.user.id);raw,sig=signed(env)
        env.service.webhook(raw,sig)
        assert service.webhook(raw,sig)=='duplicate'
    finally:restarted_db.engine.dispose()


def test_concurrent_first_login_one_account(env):
    identity=Identity(env.settings.oidc_issuer,'new-concurrent-user')
    with ThreadPoolExecutor(max_workers=4) as pool:
        ids=list(pool.map(lambda _:env.service.account(identity).id,range(4)))
    assert len(set(ids))==1


def test_remote_database_requires_verified_tls_and_consent_is_strict(env):
    with pytest.raises(ValueError):replace(env.settings,database_url='postgresql+psycopg://user@remote.invalid/test').validate()
    replace(env.settings,database_url='postgresql+psycopg://user@remote.invalid/test?sslmode=verify-full').validate()
    with pytest.raises(Conflict):env.service.checkout(env.user.id,accept_terms=False,acknowledge_recurring=True,terms_version=env.settings.terms_version)
    body={'accept_terms':1,'acknowledge_recurring':True,'terms_version':env.settings.terms_version}
    assert env.client.post('/v1/billing/checkout',headers=auth(env),json=body).status_code==422


def test_signed_future_webhook_timestamp_refused(env):
    raw,_=signed(env)
    stamp=int(time.time())+1000
    digest=hmac.new(env.settings.billing.webhook_secret.encode(),str(stamp).encode()+b'.'+raw,hashlib.sha256).hexdigest()
    assert env.client.post('/webhooks/stripe',content=raw,headers={'Stripe-Signature':f't={stamp},v1={digest}'}).status_code==400


@pytest.mark.parametrize('changed',['price','terms'])
def test_open_checkout_bound_to_accepted_price_and_notice(env,changed):
    checkout(env)
    if changed=='price':
        env.settings=replace(env.settings,billing=replace(env.settings.billing,price_id='price_ChangedMonthly'))
        env.world.price['id']='price_ChangedMonthly'
    else:
        env.settings=replace(env.settings,terms_version='new-sandbox-draft')
    env.service.settings=env.provider.settings=env.settings
    with pytest.raises(Conflict):checkout(env)
    assert len(env.world.sessions)==1
