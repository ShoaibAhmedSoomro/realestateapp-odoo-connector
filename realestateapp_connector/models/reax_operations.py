# -*- coding: utf-8 -*-
"""The working modules — leasing, legal, operations — mirrored the same way the estate is.

Same contract as reax_estate.py: RealEstateApp is the system of record, the sync overwrites these
rows, and every link points at a record that is real on this side — a lead at its building, a
renewal at its contract, a maintenance ticket at the unit's property. Odoo-side edits of these rows
are not the workflow (the app's approval gates are); the value is that the whole business is
browsable, filterable and reportable where the accounting lives.
"""
from odoo import fields, models


class ReaxLead(models.Model):
    _name = 'reax.lead'
    _description = 'RealEstateApp Lead'
    _order = 'id desc'

    code = fields.Char(required=True, index=True)
    name = fields.Char(string='Customer', required=True)
    mobile = fields.Char()
    email = fields.Char()
    status = fields.Char(index=True)
    stage = fields.Char(index=True)
    priority = fields.Char()
    source = fields.Char()
    property_id = fields.Many2one('reax.property', index=True)
    assigned_to = fields.Char(string='Owner')
    lead_date = fields.Datetime(string='Created')

    _sql_constraints = [('code_uniq', 'unique(code)', 'A lead with this code already exists.')]


class ReaxLeasingRequest(models.Model):
    _name = 'reax.leasing.request'
    _description = 'RealEstateApp Leasing Request'
    _order = 'id desc'

    code = fields.Char(required=True, index=True)
    partner_id = fields.Many2one('res.partner', string='Tenant', index=True)
    property_id = fields.Many2one('reax.property', index=True)
    status = fields.Char(index=True)
    purpose = fields.Char()
    lease_start = fields.Date()
    lease_end = fields.Date()
    requested_rent = fields.Float()

    _sql_constraints = [('code_uniq', 'unique(code)', 'A request with this code already exists.')]


class ReaxBooking(models.Model):
    _name = 'reax.booking'
    _description = 'RealEstateApp Booking'
    _order = 'id desc'

    code = fields.Char(required=True, index=True)
    partner_id = fields.Many2one('res.partner', string='Tenant', index=True)
    property_id = fields.Many2one('reax.property', index=True)
    status = fields.Char(index=True)
    lease_from = fields.Date()
    lease_to = fields.Date()

    _sql_constraints = [('code_uniq', 'unique(code)', 'A booking with this code already exists.')]


class ReaxRenewal(models.Model):
    _name = 'reax.renewal'
    _description = 'RealEstateApp Renewal'
    _order = 'id desc'

    code = fields.Char(required=True, index=True)
    contract_id = fields.Many2one('reax.contract', index=True)
    status = fields.Char(index=True)
    current_rent = fields.Float()
    proposed_rent = fields.Float()
    approved_rent = fields.Float()
    new_lease_start = fields.Date()
    new_lease_end = fields.Date()

    _sql_constraints = [('code_uniq', 'unique(code)', 'A renewal with this code already exists.')]


class ReaxLegalCase(models.Model):
    _name = 'reax.legal.case'
    _description = 'RealEstateApp Legal Case'
    _order = 'id desc'

    name = fields.Char(string='Case Ref', required=True, index=True)
    contract_id = fields.Many2one('reax.contract', index=True)
    case_type = fields.Char()
    status = fields.Char(index=True)
    stage = fields.Char()
    workflow_status = fields.Char(string='Workflow')
    assigned_to = fields.Char(string='Assigned Legal')
    court = fields.Char()
    lawyer = fields.Char()
    case_number = fields.Char()

    _sql_constraints = [('name_uniq', 'unique(name)', 'A case with this reference already exists.')]


class ReaxMaintenance(models.Model):
    _name = 'reax.maintenance'
    _description = 'RealEstateApp Maintenance Ticket'
    _order = 'id desc'

    code = fields.Char(required=True, index=True)
    property_id = fields.Many2one('reax.property', index=True)
    unit_name = fields.Char(string='Unit')
    category = fields.Char()
    subcategory = fields.Char()
    priority = fields.Char()
    status = fields.Char(index=True)
    assigned_to = fields.Char()
    work_type = fields.Char()
    vendor = fields.Char()
    estimated_cost = fields.Float()
    actual_cost = fields.Float()
    cost_recovery = fields.Char(string='Recover From')
    scheduled_at = fields.Datetime()
    resolved_at = fields.Datetime()

    _sql_constraints = [('code_uniq', 'unique(code)', 'A ticket with this code already exists.')]


class ReaxAmc(models.Model):
    _name = 'reax.amc'
    _description = 'RealEstateApp AMC Contract'
    _order = 'end_date'

    code = fields.Char(required=True, index=True)
    property_id = fields.Many2one('reax.property', index=True)
    service_type = fields.Char()
    provider = fields.Char()
    contract_value = fields.Float()
    start_date = fields.Date()
    end_date = fields.Date()
    visit_frequency = fields.Char()
    status = fields.Char(index=True)

    _sql_constraints = [('code_uniq', 'unique(code)', 'An AMC with this code already exists.')]


class ReaxAsset(models.Model):
    _name = 'reax.asset'
    _description = 'RealEstateApp Asset'
    _order = 'name'

    code = fields.Char(required=True, index=True)
    name = fields.Char(required=True)
    asset_type = fields.Char(string='Type')
    property_id = fields.Many2one('reax.property', index=True)
    make = fields.Char()
    model_name = fields.Char(string='Model')
    serial_no = fields.Char()
    warranty_until = fields.Date()
    assigned_to = fields.Char()
    status = fields.Char(index=True)

    _sql_constraints = [('code_uniq', 'unique(code)', 'An asset with this code already exists.')]


class ReaxInspection(models.Model):
    _name = 'reax.inspection'
    _description = 'RealEstateApp Move-In/Out Inspection'
    _order = 'id desc'

    code = fields.Char(required=True, index=True)
    kind = fields.Char(string='Kind', index=True)
    property_id = fields.Many2one('reax.property', index=True)
    contract_id = fields.Many2one('reax.contract', index=True)
    status = fields.Char(index=True)
    lease_date = fields.Date()
    scheduled_at = fields.Datetime()
    completed_at = fields.Datetime()
    legal_required = fields.Boolean()
    accounts_cleared = fields.Boolean()
    legal_cleared = fields.Boolean()

    _sql_constraints = [('code_uniq', 'unique(code)', 'An inspection with this code already exists.')]
