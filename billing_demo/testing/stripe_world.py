"""Synthetic Stripe SDK fixture. No external payments or network calls."""
import copy
import time
from unittest.mock import MagicMock
from uuid import uuid4
from billing_backend.db import Account
from billing_backend.stripe_provider import ProviderUnavailable


class Page:
    def __init__(self, values):
        self.values = copy.deepcopy(values)
    def auto_paging_iter(self):
        return iter(self.values)


class World:
    def __init__(self, settings):
        self.settings, self.now = settings, int(time.time())
        self.subscriptions, self.invoices, self.payments, self.charges, self.sessions = {}, {}, {}, {}, {}
        self.idempotency = {}
        self.timeout_after_create = False
        self.client = MagicMock()
        v = self.client.v1
        v.accounts.retrieve_current.return_value = {'id':settings.stripe_account_id}
        self.price = {'id':settings.billing.price_id,'livemode':False,'active':True,
            'product':settings.product_id,'type':'recurring','currency':'usd','unit_amount':1000,
            'recurring':{'interval':'month','interval_count':1,'usage_type':'licensed'}}
        v.prices.retrieve.side_effect = lambda _:copy.deepcopy(self.price)
        v.customers.create.side_effect = lambda p,o:{'livemode':False,'id':'cus_'+p['metadata']['internal_user_id'].replace('-','')}
        v.subscriptions.list.side_effect = lambda p:Page([s for s in self.subscriptions.values() if s['customer']==p['customer']])
        v.invoices.retrieve.side_effect = lambda key:copy.deepcopy(self.invoices[key])
        v.payment_intents.retrieve.side_effect = lambda key:copy.deepcopy(self.payments[key])
        v.charges.retrieve.side_effect = lambda key:copy.deepcopy(self.charges[key])
        v.checkout.sessions.create.side_effect = self.create_checkout
        v.checkout.sessions.retrieve.side_effect = lambda key:copy.deepcopy(self.sessions[key])
        v.checkout.sessions.list.side_effect = lambda p:Page([s for s in self.sessions.values() if s['customer']==p['customer']])
        v.billing_portal.configurations.retrieve.return_value = {'livemode':False,'active':True,
            'features':{'subscription_cancel':{'enabled':True,'mode':'at_period_end'},
                'subscription_update':{'enabled':False},'payment_method_update':{'enabled':True}}}
        v.billing_portal.sessions.create.side_effect = lambda p:{'url':'https://billing.stripe.com/p/session/test-only'}

    def create_checkout(self, params, options):
        key = options['idempotency_key']
        if key not in self.idempotency:
            sid = 'cs_test_'+uuid4().hex
            self.sessions[sid] = {**copy.deepcopy(params),'id':sid,'livemode':False,'status':'open',
                'url':'https://checkout.stripe.com/c/pay/'+sid}
            self.idempotency[key] = sid
            if self.timeout_after_create:
                self.timeout_after_create = False
                raise ProviderUnavailable('SIMULATED transport timeout')
        return copy.deepcopy(self.sessions[self.idempotency[key]])

    def paid(self, service, user_id):
        with service.db.transaction() as s:
            account = s.get(Account,user_id)
            if not account.customer_id:
                account.customer_id = service.provider.customer(user_id)
            customer = account.customer_id
        sid = 'sub_'+uuid4().hex
        inv, pi, charge = 'in_'+uuid4().hex, 'pi_'+uuid4().hex, 'ch_'+uuid4().hex
        start,end = self.now-100,self.now+30*86400
        sub = {'id':sid,'customer':customer,'livemode':False,'status':'active',
            'metadata':{'internal_user_id':user_id},'items':{'data':[{'quantity':1,'price':copy.deepcopy(self.price)}]},
            'current_period_start':start,'current_period_end':end,'latest_invoice':inv,
            'cancel_at_period_end':False,'cancel_at':None,'pause_collection':None}
        invoice = {'id':inv,'customer':customer,'livemode':False,'status':'paid','currency':'usd',
            'amount_paid':1000,'subscription':sid,'payment_intent':pi,
            'lines':{'has_more':False,'data':[{'subscription':sid,'price':{'id':self.price['id']},
                'quantity':1,'proration':False,'period':{'start':start,'end':end}}]}}
        self.subscriptions[sid], self.invoices[inv] = sub,invoice
        self.payments[pi] = {'id':pi,'invoice':inv,'customer':customer,'livemode':False,
            'status':'succeeded','currency':'usd','amount_received':1000,'latest_charge':charge}
        self.charges[charge] = {'id':charge,'customer':customer,'livemode':False,'payment_intent':pi,
            'paid':True,'captured':True,'refunded':False,'amount_refunded':0,'disputed':False,'currency':'usd','amount':1000}
        return sub,invoice,self.payments[pi],self.charges[charge]
