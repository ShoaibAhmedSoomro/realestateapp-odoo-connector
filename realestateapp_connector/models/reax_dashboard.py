# -*- coding: utf-8 -*-
"""The overview — RealEstateApp's dashboard, inside Odoo.

One persisted singleton whose every field is COMPUTED at read time from the mirrored records
themselves (reax.* and the stamped account.move rows), so the numbers can never disagree with the
menus they summarise: the same domain that counts a figure is the domain its drill-down opens.

sudo() on the aggregates is deliberate: a user who may open the dashboard should see the counts even
when their own groups could not read, say, account.move directly — the numbers are aggregates, not
records. account.move itself is touched only if the accounting bridge is installed, so a CRM-only
Odoo still gets everything else.
"""
from odoo import fields, models

# The app's own definition of a won lead (LeadOverview + lead-insights agree on it since 24 Aug).
WON_STATUSES = ('Request Approved', 'Contract Released')
MAINT_DONE = ('Resolved', 'Closed')
INVOICE_DOMAIN = [('move_type', '=', 'out_invoice'),
                  ('narration', 'ilike', 'Synced from RealEstateApp (installment ')]


class ReaxDashboard(models.Model):
    _name = 'reax.dashboard'
    _description = 'RealEstateApp Overview'

    name = fields.Char(default='RealEstateApp', readonly=True)
    currency_id = fields.Many2one('res.currency', compute='_compute_stats')

    # ── the estate ──
    properties_total = fields.Integer(compute='_compute_stats')
    units_total = fields.Integer(compute='_compute_stats')
    units_occupied = fields.Integer(compute='_compute_stats')
    units_vacant = fields.Integer(compute='_compute_stats')
    occupancy_pct = fields.Float(compute='_compute_stats', digits=(5, 1))

    # ── leasing ──
    leads_total = fields.Integer(compute='_compute_stats')
    leads_won = fields.Integer(compute='_compute_stats')
    requests_total = fields.Integer(compute='_compute_stats')
    bookings_total = fields.Integer(compute='_compute_stats')
    contracts_active = fields.Integer(compute='_compute_stats')
    contracts_expiring_60 = fields.Integer(compute='_compute_stats')
    renewals_total = fields.Integer(compute='_compute_stats')

    # ── the money (present only with the accounting bridge) ──
    inv_count = fields.Integer(compute='_compute_stats')
    inv_total = fields.Monetary(compute='_compute_stats', currency_field='currency_id')
    inv_open = fields.Monetary(compute='_compute_stats', currency_field='currency_id')
    inv_paid = fields.Monetary(compute='_compute_stats', currency_field='currency_id')
    inv_bounced = fields.Integer(compute='_compute_stats')

    # ── legal & operations ──
    legal_open = fields.Integer(compute='_compute_stats')
    legal_settled = fields.Integer(compute='_compute_stats')
    maintenance_open = fields.Integer(compute='_compute_stats')
    amc_active = fields.Integer(compute='_compute_stats')
    inspections_pending = fields.Integer(compute='_compute_stats')

    def _compute_stats(self):
        env = self.env
        today = fields.Date.context_today(self)
        horizon = fields.Date.add(today, days=60)
        has_account = 'account.move' in env

        units = env['reax.unit'].sudo()
        units_total = units.search_count([])
        occupied = units.search_count([('occupancy_status', '=', 'Occupied')])

        for rec in self:
            rec.currency_id = env.company.currency_id
            rec.properties_total = env['reax.property'].sudo().search_count([])
            rec.units_total = units_total
            rec.units_occupied = occupied
            rec.units_vacant = units.search_count([('occupancy_status', 'like', 'Vacant')])
            rec.occupancy_pct = (occupied / units_total * 100.0) if units_total else 0.0

            rec.leads_total = env['reax.lead'].sudo().search_count([])
            rec.leads_won = env['reax.lead'].sudo().search_count([('status', 'in', list(WON_STATUSES))])
            rec.requests_total = env['reax.leasing.request'].sudo().search_count([])
            rec.bookings_total = env['reax.booking'].sudo().search_count([])
            rec.contracts_active = env['reax.contract'].sudo().search_count([('status', '=', 'Active')])
            rec.contracts_expiring_60 = env['reax.contract'].sudo().search_count([
                ('status', '=', 'Active'), ('lease_end', '>=', today), ('lease_end', '<=', horizon)])
            rec.renewals_total = env['reax.renewal'].sudo().search_count([])

            if has_account:
                moves = env['account.move'].sudo()
                grp = moves.read_group(INVOICE_DOMAIN, ['amount_total:sum', 'amount_residual:sum'], [])
                rec.inv_count = grp and grp[0]['__count'] or 0
                rec.inv_total = grp and grp[0]['amount_total'] or 0.0
                rec.inv_open = grp and grp[0]['amount_residual'] or 0.0
                rec.inv_paid = rec.inv_total - rec.inv_open
                rec.inv_bounced = moves.search_count(INVOICE_DOMAIN + [('ref', 'ilike', 'BOUNCED')])
            else:
                rec.inv_count = 0
                rec.inv_total = rec.inv_open = rec.inv_paid = 0.0
                rec.inv_bounced = 0

            rec.legal_open = env['reax.legal.case'].sudo().search_count(
                [('status', 'in', ['Open', 'Under Termination'])])
            rec.legal_settled = env['reax.legal.case'].sudo().search_count([('status', '=', 'Settled')])
            rec.maintenance_open = env['reax.maintenance'].sudo().search_count(
                [('status', 'not in', list(MAINT_DONE))])
            rec.amc_active = env['reax.amc'].sudo().search_count([('status', '=', 'Active')])
            rec.inspections_pending = env['reax.inspection'].sudo().search_count(
                [('status', 'not in', ['Completed', 'Revoked'])])

    # ── drill-downs: each button opens the EXACT list its number counted ─────────────────────────
    def _open(self, xmlid, domain=None, name=None):
        action = self.env['ir.actions.act_window']._for_xml_id(xmlid)
        if domain is not None:
            action['domain'] = domain
        if name:
            action['name'] = name
        return action

    def action_properties(self):
        return self._open('realestateapp_connector.action_reax_properties')

    def action_units(self):
        return self._open('realestateapp_connector.action_reax_units')

    def action_units_occupied(self):
        return self._open('realestateapp_connector.action_reax_units',
                          [('occupancy_status', '=', 'Occupied')], 'Occupied Units')

    def action_units_vacant(self):
        return self._open('realestateapp_connector.action_reax_units',
                          [('occupancy_status', 'like', 'Vacant')], 'Vacant Units')

    def action_leads(self):
        return self._open('realestateapp_connector.action_reax_leads')

    def action_leads_won(self):
        return self._open('realestateapp_connector.action_reax_leads',
                          [('status', 'in', list(WON_STATUSES))], 'Won Leads')

    def action_requests(self):
        return self._open('realestateapp_connector.action_reax_requests')

    def action_bookings(self):
        return self._open('realestateapp_connector.action_reax_bookings')

    def action_contracts_active(self):
        return self._open('realestateapp_connector.action_reax_contracts',
                          [('status', '=', 'Active')], 'Active Contracts')

    def action_contracts_expiring(self):
        today = fields.Date.context_today(self)
        return self._open('realestateapp_connector.action_reax_contracts',
                          [('status', '=', 'Active'), ('lease_end', '>=', today),
                           ('lease_end', '<=', fields.Date.add(today, days=60))],
                          'Expiring in 60 days')

    def action_renewals(self):
        return self._open('realestateapp_connector.action_reax_renewals')

    def action_legal_open(self):
        return self._open('realestateapp_connector.action_reax_legal',
                          [('status', 'in', ['Open', 'Under Termination'])], 'Open Cases')

    def action_legal_settled(self):
        return self._open('realestateapp_connector.action_reax_legal',
                          [('status', '=', 'Settled')], 'Settled Cases')

    def action_maintenance_open(self):
        return self._open('realestateapp_connector.action_reax_maintenance',
                          [('status', 'not in', list(MAINT_DONE))], 'Open Tickets')

    def action_amc(self):
        return self._open('realestateapp_connector.action_reax_amc')

    def action_inspections_pending(self):
        return self._open('realestateapp_connector.action_reax_inspections',
                          [('status', 'not in', ['Completed', 'Revoked'])], 'Pending Inspections')

    def action_invoices(self):
        if 'account.move' not in self.env:
            return False
        return self._open('realestateapp_connector_account.action_reax_invoices')

    def action_collections(self):
        if 'account.move' not in self.env:
            return False
        return self._open('realestateapp_connector_account.action_reax_collections')

    def action_bounced(self):
        if 'account.move' not in self.env:
            return False
        return self._open('realestateapp_connector_account.action_reax_bounced')

    def action_paid(self):
        if 'account.move' not in self.env:
            return False
        return self._open('realestateapp_connector_account.action_reax_paid')
