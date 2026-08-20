# Working on this repo

## This is one half of a feature

The other half is the enrolment endpoint in the RealEstateApp application:

```
RealEstateApp-Astro/src/pages/api/connectors/enroll/[code].ts
```

**The JSON payload is a contract between the two.** This module sends `base_url`, `db`, `login`, `api_key`,
`datasets`, `odoo_version` and `module_version`; that endpoint validates and stores exactly those. Change the
shape on one side and the other stops working — so change both, together, or add fields in a way the older
side ignores.

`RealEstateApp-Astro/scripts/odoo-enroll-check.ts` is the test for the server half. It stands up a stub Odoo
on localhost that answers `common.authenticate`, so the success path is covered without a real credential for
anybody's instance existing in the suite. Run it after touching either side.

## Before submitting to apps.odoo.com

Odoo requires a **Git repository** — it does not accept a ZIP upload. The URL is registered in SSH form and the
branch name is read as the Odoo version:

```
ssh://git@github.com/ShoaibAhmedSoomro/realestateapp-odoo-connector#18.0
```

That is why the default branch here is `18.0` rather than `main`. Supporting another Odoo release means another
branch named for it, not a folder.

The listing assets are done, and rendered from the app's OWN brand files rather than drawn by hand:

| File | Source |
|---|---|
| `static/description/icon.png` (140×140) | `public/brand/REA-appicon.svg`, rasterised with sharp |
| `static/description/banner.png` (1200×600) | `REA-logo-white.svg` on crimson `#e11d48` |
| `static/description/index.html` | palette from `src/styles/global.css` — `#e11d48` / `#e81a47` / `#1d0e7f` |

The banner uses the wordmark WITHOUT the mark, deliberately: the mark in `REA-logo-white.svg` is a crimson
gradient, so on a crimson banner it renders as an invisible sliver. The mark carries the icon instead. If the
branding changes, regenerate rather than editing pixels.

The repository is **public**, so Odoo's builder can read it with no extra authorisation. If it is ever made
private again, authorise the `online-odoo` user on it.

## Porting to another Odoo version

Two things are version-sensitive, both verified against 18.0:

- `res.users.apikeys._generate(scope, name, expiration_date)` — three positional arguments in 17 and 18. It
  **must** be called through `.sudo()` for a persistent key: `_check_expiration_date` refuses a falsy date for a
  non-system user and caps any date at the user's group `api_key_duration`. `sudo()` raises `su` but not the uid,
  so the key still belongs to whoever pressed the button.
- The settings view uses the `<app>` / `<block>` / `<setting>` widgets and `invisible="…"` expressions, which are
  Odoo 17+ syntax. On 16 and older these need `attrs="…"` and a plain layout.
