# -*- coding: utf-8 -*-
{
    'name': 'RealEstateApp Connector',
    'version': '18.0.4.0.0',
    'summary': 'Connect this Odoo to RealEstateApp in one click — no API keys to copy by hand.',
    'description': """
RealEstateApp Connector
=======================

Connects your Odoo to RealEstateApp so your contacts and CRM leads flow into it.

Without this app, connecting means finding your database name, creating an API key, and copying four
values across two browser tabs. This app already knows all of them, because it runs inside your Odoo.

How it works
------------
1. In RealEstateApp, open Connectors and press *Connect with the Odoo app*. You get a short code.
2. In Odoo, open the *RealEstateApp* app (or *Settings → RealEstateApp*), paste the code, and press *Connect*.

That is the whole setup. The app creates its own API key, works out which of your apps it can read, and
tells RealEstateApp where to find you. Nothing is stored anywhere until your Odoo has proved the key works.

What it sends
-------------
Only what is needed to establish the connection: your Odoo web address, your database name, the login it
should connect as, and an API key it generates for that purpose. Your password is never used or sent.

Disconnecting
-------------
Press *Disconnect* here, or revoke the API key under *My Profile → Account Security*. Either one stops
access immediately.

Credits
-------
Developed by Shoaib Ahmed — Developer (ASICO), for ASICO Property Management.
""",
    'author': 'ASICO Property Management',
    'maintainer': 'Shoaib Ahmed — Developer (ASICO)',
    'website': 'https://asico.ae',
    'category': 'Productivity',
    # Free, and licensed so it stays free. LGPL-3 is the Odoo community licence for a connector like this;
    # OPL-1 would make it a paid Enterprise-style app, which is not what this is.
    'license': 'LGPL-3',
    # 'web' is only listed because menus.xml sets web_icon, a field the web module adds to ir.ui.menu.
    # It arrives transitively anyway, but an app in a store should not depend on that being true.
    'depends': ['base_setup', 'contacts', 'web'],
    'data': [
        'security/ir.model.access.csv',
        'views/res_config_settings_views.xml',
        # Before menus.xml: menus.xml references these actions, and Odoo resolves a ref at load time
        # against what it has already loaded.
        'views/partner_views.xml',
        'views/estate_views.xml',
        'views/operations_views.xml',
        'views/dashboard_views.xml',
        'views/menus.xml',
    ],
    # Two explicit paths, never a glob. A glob would sweep settings.dark.scss into the light bundle and
    # then need a ('remove', …) directive to pull it back out — and `remove` naming a path that is not in
    # the bundle is the one asset construct that raises rather than warning, which takes the page down.
    # web.assets_web_dark already includes web.assets_backend, so settings.scss loads in both modes and is
    # declared once.
    'assets': {
        'web.assets_backend': [
            'realestateapp_connector/static/src/scss/settings.scss',
        ],
        'web.assets_web_dark': [
            'realestateapp_connector/static/src/scss/settings.dark.scss',
        ],
    },
    # The cover image apps.odoo.com shows on the listing. Both this and static/description/icon.png are
    # rendered from the app's own brand files (public/brand/REA-appicon.svg and REA-logo-white.svg) in the
    # RealEstateApp repo, in the palette from its global.css — crimson #e11d48, accent #e81a47, indigo #1d0e7f.
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': True,
    'auto_install': False,
}
