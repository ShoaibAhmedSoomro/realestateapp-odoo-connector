# -*- coding: utf-8 -*-
"""The payment schedule, ON the contract.

A contract in RealEstateApp shows its instalments as one list — four rent instalments, or rent plus a
security deposit, an administration fee and a commission. Odoo held exactly the same information and
could not show it that way: each instalment is its own customer invoice (which is right — they fall
due on different dates, book to different accounts, and are paid by different cheques), so opening
one invoice showed one line, and there was nowhere to see the set.

Reading one invoice and concluding the other charges had never arrived is the obvious mistake to
make, and it was made. The schedule below is the answer: the same account.move records, listed
against the contract that produced them, with what each is for, when it falls due and whether the
money is in.

These fields live in the ACCOUNTING bridge, not in the connector proper, because reax.contract must
keep installing on an Odoo with no accounting at all.
"""
from odoo import api, fields, models


class ReaxContract(models.Model):
    _inherit = 'reax.contract'

    invoice_ids = fields.One2many(
        'account.move', 'reax_contract_id', string='Payment Schedule',
        domain=[('move_type', '=', 'out_invoice')],
        help='Every charge RealEstateApp raised for this contract, as Odoo invoices.')
    invoice_count = fields.Integer(compute='_compute_invoice_totals', string='Instalments')
    invoice_total = fields.Monetary(compute='_compute_invoice_totals', string='Scheduled',
                                    currency_field='company_currency_id')
    invoice_paid = fields.Monetary(compute='_compute_invoice_totals', string='Settled',
                                   currency_field='company_currency_id')
    invoice_due = fields.Monetary(compute='_compute_invoice_totals', string='Outstanding',
                                  currency_field='company_currency_id')
    company_currency_id = fields.Many2one(
        'res.currency', compute='_compute_company_currency', string='Currency')

    def _compute_company_currency(self):
        for rec in self:
            rec.company_currency_id = rec.env.company.currency_id

    @api.depends('invoice_ids.amount_total', 'invoice_ids.amount_residual',
                 'invoice_ids.payment_state', 'invoice_ids.state')
    def _compute_invoice_totals(self):
        for rec in self:
            # A cancelled invoice is not part of the schedule any more; a draft still is, because it
            # is money the tenant owes even though nobody has posted it yet.
            live = rec.invoice_ids.filtered(lambda m: m.state != 'cancel')
            rec.invoice_count = len(live)
            rec.invoice_total = sum(live.mapped('amount_total'))
            # Residual is what Odoo itself says is still owed, so a PART payment counts properly
            # rather than a line being all-or-nothing.
            rec.invoice_due = sum(live.mapped('amount_residual'))
            rec.invoice_paid = rec.invoice_total - rec.invoice_due
