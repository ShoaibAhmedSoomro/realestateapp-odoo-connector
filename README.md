# RealEstateApp Connector — free Odoo app

One-click enrolment for the Odoo connector. Free, LGPL-3, no paid tier.

## Why this exists

Connecting Odoo by hand means an administrator finds four things and copies them between two browser tabs:

| Field | Where they have to look |
|---|---|
| Web address | obvious |
| **Database name** | not shown anywhere in the UI; `db.list` is disabled on most production instances |
| Login | obvious |
| **API key** | My Profile → Account Security → New API Key, confirmed with their password, shown once |

Then they pick which datasets to sync — and if they pick CRM on an instance without the CRM app installed,
the connection authenticates successfully and syncs nothing.

This app runs *inside* their Odoo, so it already knows all of it. The customer pastes one short pairing code
and presses Connect.

## The flow

```
RealEstateApp  →  Connectors → Odoo → Get a pairing code        (30 min, single use)
Odoo           →  Settings → RealEstateApp → paste → Connect
                     ├─ reads web.base.url, cr.dbname, env.user.login
                     ├─ checks ir.model for crm.lead → offers contacts [+ leads]
                     ├─ mints its own API key (sudo, persistent, scope 'rpc')
                     └─ POST /api/connectors/enroll/<code>
RealEstateApp  →  authenticates against that Odoo for real, then stores it
```

Nothing is marked connected on the module's word: the server proves the credentials against the customer's
own instance before writing anything. See `src/pages/api/connectors/enroll/[code].ts`.

## What it does not do

- **No password is used or sent.** The module generates an API key; the customer's password never leaves Odoo.
- **No write access.** The connector only reads. There is no write path in `src/lib/connectors/odoo.ts`.
- **No new models, tables or menus.** It is a settings block and two buttons — the smallest thing that does
  this job. Uninstalling leaves nothing behind but the API key, which Disconnect revokes.

## Hosting support — read this before promising it to a customer

Odoo Online (the `*.odoo.com` SaaS) **cannot install third-party modules at all**. Its "Import Module" accepts
XML and static assets only, no Python. So this app works on:

| Hosting | Works? |
|---|---|
| Self-hosted / on-premise | Yes |
| Odoo.sh | Yes |
| Odoo Online (SaaS) | **No** — those customers use the manual form |

The manual credential form stays in the product for exactly that reason. It is not legacy.

## Installing it (customer side)

1. Copy `realestateapp_connector/` into the instance's addons path.
2. Restart Odoo, then Apps → Update Apps List.
3. Search "RealEstateApp", press Install.
4. Settings → RealEstateApp → paste the pairing code → Connect.

## Odoo version support

Built and verified against **Odoo 18.0**. The version-sensitive parts, if you port it:

- `res.users.apikeys._generate(scope, name, expiration_date)` — three positional args in 17/18. It **must**
  be called via `.sudo()` for a persistent key: `_check_expiration_date` refuses a falsy date for a
  non-system user and caps any date at the user's group `api_key_duration`. `sudo()` raises `su` but not the
  uid, so the key still belongs to the user who pressed the button.
- The settings view uses the `<app>` / `<block>` / `<setting>` widgets and `invisible="..."` expressions,
  which are 17+ syntax. On 16 and older this needs `attrs="..."` and a plain `<div>` layout.

## Before submitting to apps.odoo.com

Not done here, because they need real brand assets rather than placeholders:

- `static/description/icon.png` (140×140) and `banner.png`
- `static/description/index.html` — the listing page
- Re-add `'images': ['static/description/banner.png']` to the manifest once the file exists

Store terms worth knowing: your listed price must be the lowest anywhere, and Odoo keeps 30% of paid sales.
Neither applies while this stays free — and distributing the folder yourself needs no listing at all, which
is the faster way to get the first customers onto it.

## Tests

`scripts/odoo-enroll-check.ts` covers the server half — 27 assertions including cross-tenant isolation,
replay, expiry, refusal of unproven credentials, and that the key never appears in any response. It runs a
stub Odoo on localhost for the success path, so no real credential exists anywhere in the suite.
