"""Per-instance Stripe client; all external reads remain in Sandbox."""
from urllib.parse import urlparse
import time
import stripe
from stripe_test_billing import StripeTestGateway, API_VERSION
from .policy import Decision, evaluate, expected_price


class ProviderUnavailable(RuntimeError):
    pass


class StripeProvider:
    def __init__(self, settings, client=None):
        self.settings = settings
        self.client = client or stripe.StripeClient(settings.billing.secret_key,
            stripe_version=API_VERSION, max_network_retries=2,
            http_client=stripe.RequestsClient(timeout=10), verify_ssl_certs=True)
        self.verifier = StripeTestGateway(settings.billing, stripe)
        self._account_verified = False

    def verify_event(self, body, signature):
        value = self.verifier.verify_webhook(raw_body=body, signature=signature)
        # Stripe SDK bounds old timestamps. Also reject a timestamp far in
        # the future, after signature verification and before any DB write.
        stamps = [part[2:] for part in signature.split(',') if part.startswith('t=')]
        if len(stamps) != 1 or int(stamps[0]) > time.time()+300:
            raise ValueError('Invalid signature timestamp')
        return value

    def _account(self):
        if not self._account_verified:
            account = self.client.v1.accounts.retrieve_current()
            if account['id'] != self.settings.stripe_account_id:
                raise ProviderUnavailable('Sandbox account mismatch')
            self._account_verified = True

    def _test(self, value):
        if value.get('livemode') is not False:
            raise ProviderUnavailable('Unverified Sandbox object')
        return value

    def validate_price(self):
        self._account()
        price = self.client.v1.prices.retrieve(self.settings.billing.price_id)
        if not expected_price(price, self.settings):
            raise ProviderUnavailable('Expected USD 10 monthly Sandbox Price unavailable')
        return price

    def customer(self, user_id):
        self._account()
        value = self._test(self.client.v1.customers.create(
            {'metadata':{'internal_user_id':user_id}},
            {'idempotency_key':'bestbets-sandbox-customer-'+user_id}))
        return value['id']

    def _subscriptions(self, customer_id):
        self._account()
        values = self.client.v1.subscriptions.list({'customer':customer_id, 'status':'all', 'limit':100})
        result = []
        for sub in values.auto_paging_iter():
            self._test(sub)
            if sub.get('customer') != customer_id or len(result) >= 1000:
                raise ProviderUnavailable('Subscription scope mismatch')
            result.append(sub)
        return result

    def has_unfinished_subscription(self, customer_id):
        return any(s['status'] not in ('canceled', 'incomplete_expired') for s in self._subscriptions(customer_id))

    def snapshot(self, user_id, customer_id, now):
        self.validate_price()
        decisions, subscriptions = [], self._subscriptions(customer_id)
        for sub in subscriptions:
            decision = Decision(status=str(sub.get('status') or 'invalid'))
            # Retrieve authoritative payment objects; signed event statuses are
            # deliberately never used as the entitlement source.
            if sub.get('status') == 'active' and isinstance(sub.get('latest_invoice'), str):
                invoice = self._test(self.client.v1.invoices.retrieve(sub['latest_invoice']))
                pi_id = invoice.get('payment_intent')
                if isinstance(pi_id, str):
                    payment = self._test(self.client.v1.payment_intents.retrieve(pi_id))
                    charge_id = payment.get('latest_charge')
                    if isinstance(charge_id, str):
                        charge = self._test(self.client.v1.charges.retrieve(charge_id))
                        decision = evaluate(sub, invoice, payment, charge,
                            self.settings, user_id, customer_id, now)
            decisions.append((sub, decision))
        allowed = [d for _, d in decisions if d.granted]
        best = max(allowed, key=lambda d:d.paid_until) if allowed else Decision(
            status=decisions[0][1].status if decisions else 'free')
        return best, decisions

    @staticmethod
    def hosted_url(value, host):
        if not isinstance(value, str) or any(c.isspace() for c in value):
            raise ProviderUnavailable('Invalid hosted URL')
        p = urlparse(value)
        if p.scheme != 'https' or p.hostname != host or p.username or p.password or p.port not in (None,443):
            raise ProviderUnavailable('Invalid hosted URL')
        return value

    def checkout(self, user_id, customer_id, attempt):
        self.validate_price()
        base = self.settings.billing.app_url.rstrip('/')
        result = self._test(self.client.v1.checkout.sessions.create({
            'mode':'subscription', 'customer':customer_id, 'payment_method_types':['card'],
            'line_items':[{'price':self.settings.billing.price_id, 'quantity':1}],
            'client_reference_id':user_id, 'metadata':{'internal_user_id':user_id,'checkout_attempt_id':attempt.id},
            'subscription_data':{'metadata':{'internal_user_id':user_id}},
            'success_url':base+'/?checkout=success', 'cancel_url':base+'/?checkout=cancelled',
            'expires_at':attempt.expires_at, 'allow_promotion_codes':False,
        }, {'idempotency_key':'bestbets-sandbox-checkout-'+attempt.id}))
        if result.get('customer') != customer_id or result.get('mode') != 'subscription':
            raise ProviderUnavailable('Checkout binding mismatch')
        return result['id'], self.hosted_url(result['url'], 'checkout.stripe.com')

    def existing_checkout(self, session_id):
        self._account()
        return self._test(self.client.v1.checkout.sessions.retrieve(session_id))

    def find_checkout(self, customer_id, attempt_id):
        self._account()
        sessions = self.client.v1.checkout.sessions.list({'customer':customer_id,'limit':100})
        for count, session in enumerate(sessions.auto_paging_iter()):
            if count >= 1000:
                raise ProviderUnavailable('Checkout recovery requires operator review')
            self._test(session)
            if (session.get('metadata') or {}).get('checkout_attempt_id') == attempt_id:
                if session.get('customer') != customer_id:
                    raise ProviderUnavailable('Checkout ownership mismatch')
                return session['id']
        return None

    def portal(self, customer_id):
        self._account()
        config = self._test(self.client.v1.billing_portal.configurations.retrieve(
            self.settings.portal_configuration_id))
        features = config.get('features') or {}
        cancel = features.get('subscription_cancel') or {}
        if (config.get('active') is not True or cancel.get('enabled') is not True
            or cancel.get('mode') != 'at_period_end'
            or (features.get('payment_method_update') or {}).get('enabled') is not True
            or (features.get('subscription_update') or {}).get('enabled') is not False):
            raise ProviderUnavailable('Portal must allow end-of-period cancellation without plan changes')
        # Portal Sessions have no documented livemode field. The per-instance
        # test key and checked account select the environment.
        result = self.client.v1.billing_portal.sessions.create({
            'customer':customer_id, 'return_url':self.settings.billing.app_url,
            'configuration':self.settings.portal_configuration_id})
        return self.hosted_url(result['url'], 'billing.stripe.com')

    def charge_customer(self, charge_id):
        self._account()
        return self._test(self.client.v1.charges.retrieve(charge_id)).get('customer')
