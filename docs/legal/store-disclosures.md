# Store privacy disclosures

Draft answers for the Google Play Data Safety form and the Apple App
Privacy questionnaire, derived from the Privacy Policy and the app's actual
data flows. Keep this file in sync with `docs/legal/README.md` whenever data
practices change.

Privacy policy URL for both stores:
`https://siutindei.com/privacy`

## What the app actually collects

| Data | When | Purpose | Linked to identity? |
|---|---|---|---|
| Email address | Email OTP sign-in | Account management | Yes |
| Name + email | Google / Apple federated sign-in | Account management | Yes |
| User-submitted content | Feedback, place suggestions, manager requests | App functionality | Yes |
| IP address / server logs | All API calls | Security, anti-abuse (90-day retention) | No (ops logs) |
| Device integrity signals | Firebase App Check / Play Integrity on API calls | Security, anti-abuse | No |

The app does **not** collect: location (search areas are user-selected
filters, not GPS), contacts, photos, health data, financial data, browsing
history outside the app, advertising identifiers. There are no ads and no
third-party analytics SDKs in the mobile app (web analytics are
consent-gated on the website only). No data is sold or shared for
advertising.

## Google Play Data Safety form

- Does your app collect or share any of the required user data types? — Yes
- Is all of the user data collected by your app encrypted in transit? — Yes
- Do you provide a way for users to request that their data is deleted? —
  Yes (email `support@siutindei.com`; PDPO access/correction/deletion)

Data types:

| Category | Type | Collected | Shared | Optional | Purpose |
|---|---|---|---|---|---|
| Personal info | Email address | Yes | No | Yes (browse works signed-out) | Account management |
| Personal info | Name | Yes (federated sign-in only) | No | Yes | Account management |
| Messages | Other in-app messages (feedback/suggestions) | Yes | No | Yes | App functionality |
| App info and performance | Diagnostics (integrity checks) | Yes | No | No | Fraud prevention, security |

## Apple App Privacy (App Store Connect)

Privacy practices: "Data Linked to You"

- Contact Info → Email Address — App Functionality (account)
- Contact Info → Name — App Functionality (federated sign-in only)
- User Content → Other User Content — App Functionality (feedback,
  suggestions)

"Data Not Linked to You"

- Diagnostics → Other Diagnostic Data — App Functionality (device
  integrity / anti-abuse signals)

Tracking: the app does **not** track users across apps/websites owned by
other companies (no ATT prompt required).

## Age rating / children

The app is directed at parents and guardians (18+), not at children. It is
not a "designed for families" / kids-category app. Listings describe
children's activities but contain no personal data about children.
