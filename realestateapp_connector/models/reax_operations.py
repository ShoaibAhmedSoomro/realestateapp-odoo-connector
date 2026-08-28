# -*- coding: utf-8 -*-
"""The working modules — leasing, legal, operations — mirrored the same way the estate is.

Same contract as reax_estate.py: RealEstateApp is the system of record, the sync overwrites these
rows, and every link points at a record that is real on this side — a lead at its building, a
renewal at its contract, a maintenance ticket at the unit's property. Odoo-side edits of these rows
are not the workflow (the app's approval gates are); the value is that the whole business is
browsable, filterable and reportable where the accounting lives.
"""
from odoo import fields, models


# See models/reax_option.py for why these are records rather than Selection values. Each vocabulary
# field keeps its original Char twin during the changeover so an older RealEstateApp — which still
# sends plain text — does not break against a newer addon.
def _opt(category, string):
    return fields.Many2one(
        'reax.option', string=string, index=True, ondelete='restrict',
        domain=[('category', '=', category)],
        help='Chosen from the list RealEstateApp maintains.')



class ReaxLead(models.Model):
    _name = 'reax.lead'
    _description = 'RealEstateApp Lead'
    _order = 'id desc'

    code = fields.Char(required=True, index=True)
    name = fields.Char(string='Customer', required=True)
    mobile = fields.Char()
    email = fields.Char()
    status = fields.Char(index=True, string='Status (text)')
    stage = fields.Char(index=True, string='Stage (text)')
    priority = fields.Char(string='Priority (text)')
    source = fields.Char(string='Source (text)')
    status_id = fields.Many2one('reax.option', string='Status', index=True, ondelete='restrict',
                                domain=[('category', '=', 'lead_status')])
    stage_id = fields.Many2one('reax.option', string='Stage', index=True, ondelete='restrict',
                               domain=[('category', '=', 'lead_stage')])
    priority_id = fields.Many2one('reax.option', string='Priority', ondelete='restrict',
                                  domain=[('category', '=', 'lead_priority')])
    source_id = fields.Many2one('reax.option', string='Source', ondelete='restrict',
                                domain=[('category', '=', 'lead_source')])
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
    status = fields.Char(index=True, string='Status (text)')
    purpose = fields.Char(string='Purpose (text)')
    status_id = _opt('request_status', 'Status')
    purpose_id = _opt('lease_purpose', 'Purpose')
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
    status = fields.Char(index=True, string='Status (text)')
    status_id = _opt('booking_status', 'Status')
    lease_from = fields.Date()
    lease_to = fields.Date()

    _sql_constraints = [('code_uniq', 'unique(code)', 'A booking with this code already exists.')]


class ReaxRenewal(models.Model):
    _name = 'reax.renewal'
    _description = 'RealEstateApp Renewal'
    _order = 'id desc'

    code = fields.Char(required=True, index=True)
    contract_id = fields.Many2one('reax.contract', index=True)
    status = fields.Char(index=True, string='Status (text)')
    status_id = _opt('renewal_status', 'Status')
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
    case_type = fields.Char(string='Case Type (text)')
    case_type_id = _opt('legal_case_type', 'Case Type')
    status = fields.Char(index=True, string='Status (text)')
    status_id = _opt('legal_status', 'Status')
    stage = fields.Char(string='Stage (text)')
    stage_id = _opt('legal_stage', 'Stage')
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
    category = fields.Char(string='Category (text)')
    category_id = _opt('maintenance_category', 'Category')
    subcategory = fields.Char()
    priority = fields.Char(string='Priority (text)')
    priority_id = _opt('maintenance_priority', 'Priority')
    status = fields.Char(index=True, string='Status (text)')
    status_id = _opt('maintenance_status', 'Status')
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
    status = fields.Char(index=True, string='Status (text)')
    status_id = _opt('amc_status', 'Status')

    _sql_constraints = [('code_uniq', 'unique(code)', 'An AMC with this code already exists.')]


class ReaxAsset(models.Model):
    _name = 'reax.asset'
    _description = 'RealEstateApp Asset'
    _order = 'name'

    code = fields.Char(required=True, index=True)
    name = fields.Char(required=True)
    asset_type = fields.Char(string='Type (text)')
    asset_type_id = _opt('asset_type', 'Type')
    property_id = fields.Many2one('reax.property', index=True)
    make = fields.Char()
    model_name = fields.Char(string='Model')
    serial_no = fields.Char()
    warranty_until = fields.Date()
    assigned_to = fields.Char()
    status = fields.Char(index=True, string='Status (text)')
    status_id = _opt('asset_status', 'Status')

    _sql_constraints = [('code_uniq', 'unique(code)', 'An asset with this code already exists.')]


class ReaxInspection(models.Model):
    _name = 'reax.inspection'
    _description = 'RealEstateApp Move-In/Out Inspection'
    _order = 'id desc'

    code = fields.Char(required=True, index=True)
    kind = fields.Char(string='Kind (text)', index=True)
    kind_id = _opt('inspection_kind', 'Kind')
    property_id = fields.Many2one('reax.property', index=True)
    contract_id = fields.Many2one('reax.contract', index=True)
    status = fields.Char(index=True, string='Status (text)')
    status_id = _opt('inspection_status', 'Status')
    lease_date = fields.Date()
    scheduled_at = fields.Datetime()
    completed_at = fields.Datetime()
    legal_required = fields.Boolean()
    accounts_cleared = fields.Boolean()
    legal_cleared = fields.Boolean()

    _sql_constraints = [('code_uniq', 'unique(code)', 'An inspection with this code already exists.')]
