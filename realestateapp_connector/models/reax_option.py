# -*- coding: utf-8 -*-
"""The app's vocabularies, as records — so Odoo shows dropdowns instead of free text.

Every status, type and stage on these models is a CONTROLLED LIST in RealEstateApp: a contract is
'Active' or 'Booked', never 'actve'. Mirroring them into Char fields threw that away — Odoo showed a
text box, the values could not be grouped or filtered reliably, and nothing stopped a typo.

A Selection field would have been the obvious fix and is the wrong one: its values are frozen in
Python, while these lists are per-company and editable by the app's own administrators. A new status
in the app would then be a value the ORM refuses to write.

So the vocabulary is DATA. The sync resolves each value to a row here, creating it the first time it
is seen, which means the dropdown in Odoo always offers exactly what the app actually uses — and
follows the app when it changes, with no module upgrade.
"""
from odoo import fields, models


class ReaxOption(models.Model):
    _name = 'reax.option'
    _description = 'RealEstateApp Vocabulary'
    _order = 'category, sequence, name'
    _rec_name = 'name'

    category = fields.Char(
        required=True, index=True,
        help="Which list this value belongs to — e.g. contract_status, unit_type, lead_stage.")
    code = fields.Char(required=True, index=True, help='The value exactly as RealEstateApp holds it.')
    name = fields.Char(required=True, help='What a person reads. Defaults to the code.')
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('category_code_uniq', 'unique(category, code)',
         'That value already exists in this list.'),
    ]
