# -*- coding: utf-8 -*-
{
    'name': 'RealEstateApp Connector',
    'version': '18.0.1.0.0',
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
2. In Odoo, open *Settings → RealEstateApp*, paste the code, and press *Connect*.

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
""",
    'author': 'ASICO Property Management',
    'website': 'https://asico.ae',
    'category': 'Productivity',
    # Free, and licensed so it stays free. LGPL-3 is the Odoo community licence for a connector like this;
    # OPL-1 would make it a paid Enterprise-style app, which is not what this is.
    'license': 'LGPL-3',
    'depends': ['base_setup', 'contacts'],
    'data': [
        'views/res_config_settings_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
