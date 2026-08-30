# -*- coding: utf-8 -*-
"""The link from a rent invoice back to the tenancy contract that produced it.

Until now that link existed only as TEXT: the connector writes `ref` as "<contract>/<seq> · chq
<no>", and the contract form's Rent Invoices button searched `ref ilike '<contract>/'`. Two problems
with that, and this module's own view comments already name the first:

  · `ref` is a business reference an accountant may legitimately edit, and the moment somebody tidies
    one the invoice silently drops out of its contract's list.
  · A text search is not a relation, so Odoo cannot show the schedule ON the contract, cannot group
    invoices by contract, and cannot follow the link in the other direction at all.

A real Many2one fixes all of that. It is written by the connector, which knows exactly which contract
an instalment came from — no parsing, no guessing. The compute exists only to adopt invoices that
were here before this field was, and it never overwrites a link that already has a value.
"""
from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    reax_contract_id = fields.Many2one(
        'reax.contract', string='Tenancy Contract', index=True, ondelete='set null', copy=False,
        compute='_compute_reax_contract_id', store=True, readonly=False,
        help='The RealEstateApp tenancy contract this instalment belongs to.')

    @api.depends('ref')
    def _compute_reax_contract_id(self):
        """Adopt older invoices from the reference they already carry.

        Every record is assigned, and an existing link always wins — `or` rather than a branch,
        because the whole reason this field exists is that `ref` cannot be trusted to stay put. One
        search for the whole batch, not one per invoice.
        """
        def code_of(move):
            return move.ref.split('/')[0].strip() if move.ref and '/' in move.ref else None

        codes = {c for c in (code_of(m) for m in self) if c}
        by_code = {}
        if codes:
            found = self.env['reax.contract'].search([('name', 'in', list(codes))])
            by_code = {c.name: c.id for c in found}
        for move in self:
            move.reax_contract_id = move.reax_contract_id.id or by_code.get(code_of(move), False)
