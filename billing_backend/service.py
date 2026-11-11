"""Transactional billing use cases; authorization never trusts browser IDs."""
from hashlib import sha256
import time
from uuid import uuid4
from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError
from .db import Account, Entitlement, Subscription, CheckoutAttempt, EventReceipt, RateBucket
from .policy import Decision


class AccessDenied(RuntimeError):
    pass


class Conflict(RuntimeError):
    pass


class RateLimited(RuntimeError):
    def __init__(self, retry_after):
        self.retry_after = retry_after
        super().__init__('Request limit exceeded')


class BillingService:
    def __init__(self, db, provider, settings, clock=None):
        self.db, self.provider, self.settings = db, provider, settings
        self.clock = clock or (lambda:int(time.time()))

    def rate_limit(self, scope, limit, seconds):
        key = sha256(scope.encode()).hexdigest()
        now = self.clock()
        # A conflict on a new bucket is retried after the competing insert
        # commits. Existing buckets are updated under a DB row lock.
        for attempt in range(3):
            try:
                with self.db.transaction() as s:
                    row = s.get(RateBucket, key, with_for_update=True)
                    window = now // seconds
                    if row is None:
                        row = RateBucket(key=key, window=window, count=0, expires_at=now+seconds+3600)
                        s.add(row)
                    if row.window != window:
                        row.window, row.count = window, 0
                    row.count += 1
                    row.expires_at = now+seconds+3600
                    exceeded = row.count > limit
                if exceeded:
                    raise RateLimited(max(1, (window+1)*seconds-now))
                return
            except IntegrityError:
                if attempt == 2:
                    raise

    def account(self, identity):
        for attempt in range(3):
            try:
                with self.db.transaction() as s:
                    account = s.scalar(select(Account).where(
                        Account.issuer == identity.issuer, Account.subject == identity.subject))
                    if account is None:
                        account = Account(id=str(uuid4()), issuer=identity.issuer,
                            subject=identity.subject, created_at=self.clock(), disabled=False)
                        s.add(account)
                        s.flush()
                        s.add(Entitlement(user_id=account.id))
                    if account.disabled:
                        raise AccessDenied('Account disabled')
                    return account
            except IntegrityError:
                if attempt == 2:
                    raise

    @staticmethod
    def _locked(s, user_id):
        account = s.get(Account, user_id, with_for_update=True)
        if account is None or account.disabled:
            raise AccessDenied('Account unavailable')
        return account

    def _sync(self, s, account, now):
        if account.customer_id:
            decision, states = self.provider.snapshot(account.id, account.customer_id, now)
        else:
            decision, states = Decision(), []
        for sub, item in states:
            row = s.get(Subscription, sub['id'])
            if row is not None and row.user_id != account.id:
                raise Conflict('Subscription ownership mismatch')
            if row is None:
                row = Subscription(id=sub['id'], user_id=account.id)
                s.add(row)
            row.customer_id, row.status = account.customer_id, str(sub.get('status') or 'invalid')
            items = (sub.get('items') or {}).get('data') or []
            row.price_id = str((items[0].get('price') or {}).get('id') or 'unknown') if items else 'unknown'
            row.paid_until, row.checked_at = item.paid_until, now
        grant = s.get(Entitlement, account.id)
        if grant is None:
            grant = Entitlement(user_id=account.id)
            s.add(grant)
        grant.granted, grant.status = decision.granted, decision.status
        grant.paid_until, grant.checked_at = decision.paid_until, now
        grant.subscription_id = decision.subscription_id
        grant.cancel_at_period_end = decision.cancel_at_period_end
        return grant

    def entitlement(self, user_id, force=False):
        now = self.clock()
        with self.db.transaction() as s:
            account = self._locked(s, user_id)
            grant = s.get(Entitlement, user_id)
            if force or grant is None or now - grant.checked_at >= self.settings.freshness_seconds:
                grant = self._sync(s, account, now)
            # Never return cached allow after expiry, even without webhooks.
            allowed = bool(grant.granted and grant.paid_until > now
                and 0 <= now - grant.checked_at < self.settings.freshness_seconds)
            return {'premium':allowed, 'status':grant.status, 'paid_until':grant.paid_until,
                'cancel_at_period_end':grant.cancel_at_period_end}

    def require_premium(self, user_id):
        if not self.entitlement(user_id)['premium']:
            raise AccessDenied('Verified paid Premium subscription required')

    def checkout(self, user_id, *, accept_terms, acknowledge_recurring, terms_version):
        if accept_terms is not True or acknowledge_recurring is not True or terms_version != self.settings.terms_version:
            raise Conflict('Explicit acceptance of the current notice required')
        self.rate_limit('checkout:'+user_id, 5, 600)
        now = self.clock()
        # Commit the attempt BEFORE creating the remote session. A timeout or
        # crash therefore reuses the same server-generated idempotency key.
        with self.db.transaction() as s:
            account = self._locked(s, user_id)
            self.provider.validate_price()
            if not account.customer_id:
                account.customer_id = self.provider.customer(account.id)
                s.flush()  # customer_id is unique across all accounts
            attempt = s.scalar(select(CheckoutAttempt).where(
                CheckoutAttempt.user_id == user_id, CheckoutAttempt.closed.is_(False)))
            if attempt and (attempt.terms_version != terms_version or attempt.price_id != self.settings.billing.price_id):
                raise Conflict('Existing Checkout notice changed; review required')
            if attempt and not attempt.session_id and attempt.expires_at <= now:
                attempt.session_id = self.provider.find_checkout(account.customer_id, attempt.id)
                if not attempt.session_id:
                    attempt.closed = True
            if attempt and attempt.session_id:
                existing = self.provider.existing_checkout(attempt.session_id)
                if existing.get('customer') != account.customer_id:
                    raise Conflict('Checkout ownership mismatch')
                if existing.get('status') == 'open':
                    return self.provider.hosted_url(existing['url'], 'checkout.stripe.com')
                if existing.get('status') != 'expired':
                    raise Conflict('Existing Checkout completed; refresh subscription status')
                attempt.closed = True
            if attempt is None or attempt.closed:
                if self.provider.has_unfinished_subscription(account.customer_id):
                    raise Conflict('Subscription already exists; use the Customer Portal')
                s.flush()  # release the unique open-attempt constraint
                attempt = CheckoutAttempt(id=str(uuid4()), user_id=user_id, created_at=now,
                    expires_at=now+3600, closed=False, terms_version=self.settings.terms_version,
                    price_id=self.settings.billing.price_id, consent_at=now)
                s.add(attempt)
            attempt_id = attempt.id
        with self.db.transaction() as s:
            account = self._locked(s, user_id)
            attempt = s.get(CheckoutAttempt, attempt_id)
            if attempt.session_id:
                existing = self.provider.existing_checkout(attempt.session_id)
                if existing.get('customer') != account.customer_id or existing.get('status') != 'open':
                    raise Conflict('Checkout no longer open')
                return self.provider.hosted_url(existing['url'], 'checkout.stripe.com')
            session_id, url = self.provider.checkout(account.id, account.customer_id, attempt)
            attempt.session_id = session_id
            return url

    def portal(self, user_id):
        self.rate_limit('portal:'+user_id, 10, 600)
        with self.db.transaction() as s:
            account = self._locked(s, user_id)
            if not account.customer_id:
                raise Conflict('No billing customer for this account')
            return self.provider.portal(account.customer_id)

    def webhook(self, raw, signature):
        event = self.provider.verify_event(raw, signature)
        if event is None:
            return 'ignored'
        digest, now = sha256(raw).hexdigest(), self.clock()
        with self.db.transaction() as s:
            old = s.get(EventReceipt, event.event_id)
            if old:
                if old.payload_hash != digest:
                    raise Conflict('Event ID payload mismatch')
                return 'duplicate'
        customer_id = event.customer_id
        if event.charge_id:
            customer_id = self.provider.charge_customer(event.charge_id)
        account_id = None
        try:
            with self.db.transaction() as s:
                account = s.scalar(select(Account).where(Account.customer_id == customer_id).with_for_update()) if customer_id else None
                account_id = account.id if account else None
                # Claim the event and change the grant in ONE transaction.
                # A provider failure rolls both changes back for Stripe retry.
                s.add(EventReceipt(id=event.event_id, payload_hash=digest, kind=event.kind,
                    user_id=account.id if account else None,
                    outcome='processed' if account and not account.disabled else 'unmapped', processed_at=now))
                s.flush()
                if account and not account.disabled:
                    self._sync(s, account, now)
            return 'processed' if account else 'ignored'
        except IntegrityError:
            with self.db.transaction() as s:
                old = s.get(EventReceipt, event.event_id)
                if old is None or old.payload_hash != digest:
                    raise Conflict('Concurrent event payload mismatch')
            return 'duplicate'
        except Exception:
            # A verified notification signals that the cached lease may be
            # stale. If the authoritative read fails, invalidate that lease
            # without recording success; Stripe can retry the entire event.
            if account_id is not None:
                with self.db.transaction() as s:
                    self._locked(s, account_id)
                    grant = s.get(Entitlement, account_id)
                    if grant:
                        grant.checked_at = 0
            raise

    def reconcile(self):
        # Also invoked periodically by the explicit CLI, covering lost events.
        with self.db.transaction() as s:
            ids = list(s.scalars(select(Account.id).where(
                Account.customer_id.is_not(None), Account.disabled.is_(False))))
        failures = 0
        for user_id in ids:
            try:
                self.entitlement(user_id, force=True)
            except Exception:
                failures += 1  # do not log provider bodies, emails or secrets
        with self.db.transaction() as s:
            s.execute(delete(RateBucket).where(RateBucket.expires_at < self.clock()))
        return {'checked':len(ids), 'failed':failures}
