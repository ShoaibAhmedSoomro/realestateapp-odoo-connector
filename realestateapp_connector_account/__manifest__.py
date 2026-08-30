# -*- coding: utf-8 -*-
{
    'name': 'RealEstateApp Connector — Accounting',
    'version': '18.0.1.3.0',
    'summary': 'The rent schedule RealEstateApp sends, on the contract that produced it.',
    'description': """
RealEstateApp Connector — Accounting
====================================

Adds a *Rent Invoices* menu to the RealEstateApp app, listing the customer invoices RealEstateApp has
sent into this Odoo.

Why this is a separate app
--------------------------
The main connector only needs Contacts, so it installs on any Odoo — including one with no accounting at
all, where the contact sync is still useful. Requiring Accounting just to connect would be wrong. This
bridge carries the accounting half and installs itself automatically wherever both the connector and
Accounting are present, which is the standard Odoo pattern for exactly this.

There is nothing to configure here. If you can see it, it is already working.

Credits
-------
Developed by Shoaib Ahmed — Developer (ASICO), for ASICO Property Management.
""",
    'author': 'ASICO Property Management',
    'maintainer': 'Shoaib Ahmed — Developer (ASICO)',
    'website': 'https://asico.ae',
    'category': 'Accounting',
    'license': 'LGPL-3',
    'depends': ['realestateapp_connector', 'account'],
    'data': [
        'views/move_views.xml',
        'views/contract_views.xml',
    ],
    'installable': True,
    # Not an application in its own right — it is a bridge, and it belongs inside the connector's app
    # tile rather than as a second tile in the grid.
    'application': False,
    # The whole point: appears by itself when the connector meets Accounting, and stays away otherwise.
    'auto_install': True,
}
