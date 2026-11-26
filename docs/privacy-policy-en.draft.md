# Hoopzaro — Privacy notice
**DRAFT FOR APPROVAL • version 0.1 • 26 November 2026**
Do not publish as an effective notice until bracketed fields, actual processing, providers and retention have been verified. Future functionality is not represented as operational.

## 1. Controller and contact
The controller for personal data associated with Hoopzaro (hoopzaro.com and its hoopzaro.streamlit.app instance) is [full legal name of the individual or business], [legal contact address and country]. Privacy contact: contact@hoopzaro.com. Technical support: support@hoopzaro.com. [Data protection officer details, if appointed.] This notice concerns service users, not NBA athletes whose sporting statistics are analysed.

## 2. Data and purposes
- Google sign-in: issuer and immutable subject identifiers (iss, sub), authentication validity information and, depending on the provider response, display name, email address and verification status. Used for authentication, account recognition and access permissions. We do not receive your Google password. Legal basis: GDPR Article 6(1)(b) where necessary to provide the requested service; Article 6(1)(f) for security and abuse prevention following a documented balancing assessment.
- Use of the service: analysis inputs, session settings and results needed to provide features. Query contents are not stored in the optional telemetry described below. Basis: Article 6(1)(b).
- Technical data: hosting and infrastructure providers may process IP addresses, browser information, connection and error logs to deliver and protect the service. Basis: Article 6(1)(b) or (f), as applicable. [Confirm the actual fields, recipients and log retention.]
- Optional usage analytics (before rollout): pseudonymous HMAC account identifier for signed-in users, last observed role, first and last observation dates, random session identifier not joined to the account identifier in the database, visited pages, approximate activity samples and aggregated feature usage, errors and execution times. Purpose: improving the application, identifying technical problems and assessing feature usage. Basis: voluntary consent under Article 6(1)(a). This telemetry does not store email addresses, IP addresses, query contents or card details. Infrastructure services may process other data. Pseudonymisation is not anonymisation.
- Contact and support: email, correspondence and information required to address requests. Basis: Article 6(1)(b) for service/precontractual requests, (f) for other correspondence and legal claims, (c) for legal obligations where applicable.
- Payments and subscriptions (currently test environment only): Stripe hosts checkout. Before live billing launches, the service is expected to process customer, checkout and subscription identifiers, status and access periods, and billing information necessary to perform the contract. Hoopzaro does not intend to store full card details. Intended basis: Article 6(1)(b), (c) for accounting obligations and (f) for fraud prevention and legal claims. [Verify actual data flows, Stripe entities, retention and legal bases before publication.]
- Entitlements and limits: necessary account identifiers and access status may be used for service delivery and abuse prevention. Any daily quota must be independent of analytics consent. [Confirm actual implementation, retention and legal basis.]

Not signing in restricts functions that require an account. Refusing analytics does not reduce features that you are entitled to use. Required future billing fields will be identified during checkout.

## 3. Consent and withdrawal
Customer analytics is intended to be off by default. Once enabled, you can choose “Allow analytics” in Settings. Consent applies to the current session and can be withdrawn in the same place. Withdrawal stops further collection and does not affect the lawfulness of processing before withdrawal. It does not automatically erase all previously collected records. You can request erasure through our privacy contact; random sessions may not be identifiable. Do not send passwords, keys or card details. [Implement demonstrable consent, notice version, request-handling procedures and access to the full notice before consent.]

## 4. Retention
Proposed analytics retention: page samples up to 30 UTC calendar days; sessions up to 30 days since last observation, with sessions needed for unexpired samples retained; feature aggregates up to 90 UTC calendar days; pseudonymous account observations up to 90 days since last observation, except records necessary for separate purposes, including linked quotas. The retention schedule is not yet active. Retention does not delete a Google account or cancel a subscription.
[Confirm schedules, consent evidence, logs, backups, correspondence, quotas, billing and claims retention. Specify a period or clear criteria for each purpose.]

## 5. Recipients and international transfers
Depending on the feature, providers include Google (sign-in), Streamlit/Snowflake (hosting), Neon (database), Zoho (email), Stripe (test billing; future live billing) and GitHub (code and technical jobs). [Verify legal entities, controller/processor roles, processing agreements, subprocessors, actual regions and data access. Do not assume every provider receives customer data.] 
Where data is transferred outside the EEA, [state the actual destinations, applicable adequacy decisions or safeguards and how to obtain a copy]. Provider information: https://policies.google.com/privacy, https://www.snowflake.com/legal/privacy-policy/, https://neon.com/privacy-policy, https://www.zoho.com/privacy.html, https://stripe.com/privacy, https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement. These notices do not replace Hoopzaro's own obligations.

## 6. Cookies and session technologies
Streamlit sign-in uses an identity/session cookie; its documentation states the standard identity cookie can expire after 30 days and signing out removes the app's cookie. Google may use its own cookies independently. Strictly necessary technologies may be used to provide the requested service. Optional analytics should not begin without consent. [Inventory actual cookies, browser storage, purposes, durations, third parties and applicable consent rules, including Article 399 of Poland's Electronic Communications Law; verify browser and hosting behaviour.]

## 7. Your rights
Subject to the GDPR's conditions, you may request access, rectification, erasure, restriction, portability, object to legitimate-interest processing and withdraw consent. Contact contact@hoopzaro.com. Where necessary, we may request proportionate identity verification; we do not collect extra identifiers solely to attribute anonymous visits. You may lodge a complaint with a competent supervisory authority, including Poland's President of the Personal Data Protection Office (https://uodo.gov.pl/). [Establish a request-handling process.]

## 8. Security and decisions
We use server-side role checks, separated keys and restricted permissions, HTTPS and pseudonymisation of analytics. [Verify measures, backups and incident handling.] Predictions concern sporting events, not evaluations of users. [Confirm the absence of solely automated decisions with legal or similarly significant effects and user profiling; describe any exceptions.]

## 9. Children, changes and contact
[Confirm target age, age restrictions and children's consent requirements for intended markets.] We will provide updated information before introducing new processing purposes or changing analytics scope, and seek renewed consent when required. Effective date: [after approval].

### Working legal references
- GDPR Articles 5–8, 11–22, 28, 32–34, 44–49: https://eur-lex.europa.eu/eli/reg/2016/679/oj/eng
- EDPB Guidelines 05/2020 on consent: https://www.edpb.europa.eu/documents/guideline/guidelines-052020-on-consent-under-regulation-2016679_en
- Polish Electronic Communications Law, Article 399: https://eli.sejm.gov.pl/eli/DU/2024/1221/ogl/pol
- Streamlit authentication: https://docs.streamlit.io/develop/concepts/connections/authentication
