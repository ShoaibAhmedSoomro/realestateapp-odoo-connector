# -*- coding: utf-8 -*-
"""The estate itself, as first-class Odoo records.

The connector's first release showed only what already had a home in Odoo's own tables — contacts
and invoices. Properties, units and tenancy contracts had nowhere to land, so "connect all modules"
stopped two menus in. These models are that home.

They are REFERENCE data, deliberately thin: RealEstateApp is the system of record and the sync
overwrites these rows on every run. Odoo-side edits of estate structure would be overwritten and are
not the point — the point is that a contract here links to the REAL res.partner Odoo can invoice, to
the property, and (through the stamp convention) back to the app record it mirrors. Money still
lives in account.move, never in a silo (see the connector README for why).
"""
from odoo import api, fields, models

# Vocabulary fields come in pairs during the changeover: the original Char (what older copies of
# RealEstateApp still write, and what existing rows already hold) and a Many2one to reax.option that
# gives Odoo a real dropdown. The sync fills whichever this Odoo has, so an app and an addon of
# different ages keep working. The Char columns go in a later release, once every connected app is
# sending ids.
def _opt(category, string):
    return fields.Many2one(
        'reax.option', string=string, index=True, ondelete='restrict',
        domain=[('category', '=', category)],
        help='Chosen from the list RealEstateApp maintains.')



class ReaxProperty(models.Model):
    _name = 'reax.property'
    _description = 'RealEstateApp Property'
    _order = 'name'
    _rec_name = 'name'

    code = fields.Char(required=True, index=True)
    name = fields.Char(required=True)
    community = fields.Char()
    property_type = fields.Char(string='Type (text)')
    status = fields.Char(string='Status (text)')
    city = fields.Char()
    emirate = fields.Char(string='Emirate (text)')
    property_type_id = _opt('property_type', 'Type')
    status_id = _opt('property_status', 'Status')
    emirate_id = _opt('emirate', 'Emirate')
    owner_name = fields.Char(string='Owner')
    active = fields.Boolean(default=True)
    unit_ids = fields.One2many('reax.unit', 'property_id', string='Units')
    unit_count = fields.Integer(compute='_compute_unit_count')
    contract_ids = fields.One2many('reax.contract', 'property_id', string='Contracts')
    contract_count = fields.Integer(compute='_compute_contract_count')

    _sql_constraints = [
        ('code_uniq', 'unique(code)', 'A property with this code already exists.'),
    ]

    @api.depends('unit_ids')
    def _compute_unit_count(self):
        for rec in self:
            rec.unit_count = len(rec.unit_ids)

    @api.depends('contract_ids')
    def _compute_contract_count(self):
        for rec in self:
            rec.contract_count = len(rec.contract_ids)


class ReaxUnit(models.Model):
    _name = 'reax.unit'
    _description = 'RealEstateApp Unit'
    _order = 'property_id, name'
    _rec_name = 'name'

    code = fields.Char(required=True, index=True, help='The app-side unit identity the sync matches on.')
    name = fields.Char(string='Unit No', required=True)
    property_id = fields.Many2one('reax.property', required=True, ondelete='cascade', index=True)
    occupancy_status = fields.Char(string='Occupancy (text)')
    unit_status = fields.Char(string='Unit Status (text)')
    unit_type = fields.Char(string='Type (text)')
    occupancy_status_id = _opt('unit_occupancy', 'Occupancy')
    unit_status_id = _opt('unit_status', 'Unit Status')
    unit_type_id = _opt('unit_type', 'Type')
    annual_rent = fields.Float()
    leasable = fields.Boolean(default=True)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('code_uniq', 'unique(code)', 'A unit with this code already exists.'),
    ]


class ReaxContract(models.Model):
    _name = 'reax.contract'
    _description = 'RealEstateApp Tenancy Contract'
    _order = 'lease_start desc'
    _rec_name = 'name'

    name = fields.Char(string='Contract No', required=True, index=True)
    partner_id = fields.Many2one('res.partner', string='Tenant', index=True,
                                 help='The same contact rent invoices are raised against.')
    # WHO the parties actually are, without leaving the contract. Related fields rather than copies:
    # the contact is the single record, so a phone number corrected on the partner is corrected here.
    tenant_email = fields.Char(related='partner_id.email', string='Tenant Email', readonly=True)
    tenant_phone = fields.Char(related='partner_id.mobile', string='Tenant Mobile', readonly=True)
    tenant_vat = fields.Char(related='partner_id.vat', string='Tenant TRN', readonly=True)
    landlord_id = fields.Many2one('res.partner', string='Landlord', index=True,
                                  help='The property owner this lease is held for.')
    landlord_email = fields.Char(related='landlord_id.email', string='Landlord Email', readonly=True)
    landlord_phone = fields.Char(related='landlord_id.mobile', string='Landlord Mobile', readonly=True)
    property_id = fields.Many2one('reax.property', index=True)
    unit_nos = fields.Char(string='Units')
    status = fields.Char(index=True, string='Status (text)')
    contract_type = fields.Char(string='Type (text)')
    status_id = _opt('contract_status', 'Status')
    contract_type_id = _opt('contract_type', 'Type')
    lease_start = fields.Date()
    lease_end = fields.Date()
    rent_payable = fields.Float(string='Annual Rent')
    vat_on_rent = fields.Float(string='VAT')
    signed = fields.Boolean()
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'A contract with this number already exists.'),
    ]

    def action_view_invoices(self):
        """The rent schedule THIS contract produced — the narration stamp carries the contract code
        in every invoice ref, and ref is what the push writes it into (contract_code/seq)."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.name,
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('move_type', '=', 'out_invoice'), ('ref', 'ilike', f'{self.name}/')],
        }
