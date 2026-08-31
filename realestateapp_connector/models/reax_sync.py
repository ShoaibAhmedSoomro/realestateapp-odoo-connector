# -*- coding: utf-8 -*-
"""WHAT THE CONNECTOR IS DOING, AND WHAT IT HAS DONE — inside Odoo.

The synchronisation engine does not run here. It runs in RealEstateApp, against its own Postgres,
and Odoo holds no credential to call it: enrolment sends Odoo's API key TO the app, so the app can
read this Odoo, and nothing comes back the other way. Odoo therefore cannot fetch progress.

So the app WRITES it here, as ordinary Odoo records, each slice. That is better than fetching: a real
row can be listed, sorted, searched, filtered, grouped and deleted by Odoo itself, which is most of
what a progress and activity screen needs, already built and already familiar.

It also answers "close the page and come back" for free. The state is in the database, never in a
browser; a person can close Odoo, restart it, and the run is exactly where they left it.

THREE THINGS ARE DELIBERATELY ABSENT, because the honest answer is nothing rather than a plausible
number:

  · NO ETA. A run parks between slices — it checkpoints, drops its heartbeat and waits for the next
    cron tick — so most of started_at→now is idle. A rate computed from wall clock was 13x wrong on a
    measured run. Elapsed time and "6,800 of 10,000" are true; "4 minutes remaining" would not be.
  · NO PERCENTAGE WITHOUT A DENOMINATOR. Nine of the push data sets have no count() defined, so the
    total is genuinely unknown. Those lines show a running count and no bar, rather than a bar
    measured against a number nobody has.
  · NO USER. sync_runs has no user column; what is actually known is what STARTED the run — manual,
    the schedule, a retry, or an app event. That is what is shown.
"""
from odoo import api, fields, models

# The app's own status vocabulary, mapped to something a person reads. Kept as data because the app
# is the source of truth for these strings and a mismatch must show up as "Unknown", not as a crash.
RUN_STATES = [
    ('queued', 'Queued'),
    ('preparing', 'Preparing'),
    ('running', 'Syncing'),
    ('paused', 'Paused'),
    ('completed', 'Completed'),
    ('partial', 'Completed with errors'),
    ('failed', 'Failed'),
    ('cancelled', 'Cancelled'),
]


class ReaxSyncRun(models.Model):
    _name = 'reax.sync.run'
    _description = 'RealEstateApp synchronisation'
    _order = 'started_at desc, id desc'
    _rec_name = 'display_title'

    # The app's own run id. Unique, so a slice UPDATES its run rather than adding another row —
    # without this a long import would leave one row per slice and the screen would be nonsense.
    app_run_id = fields.Integer(string='Run', required=True, index=True)
    display_title = fields.Char(compute='_compute_display_title', store=True)
    state = fields.Selection(RUN_STATES, string='Status', default='queued', index=True)
    trigger = fields.Char(string='Started by', help='What started this run: by hand, the schedule, '
                                                    'a retry, or a change in RealEstateApp.')
    direction = fields.Selection(
        [('push', 'RealEstateApp → Odoo'), ('pull', 'Odoo → RealEstateApp'), ('both', 'Both ways')],
        string='Direction')

    started_at = fields.Datetime(string='Started', index=True)
    finished_at = fields.Datetime(string='Finished')
    progress_at = fields.Datetime(string='Last update')

    checked = fields.Integer(string='Processed')
    created = fields.Integer(string='Created')
    updated = fields.Integer(string='Updated')
    skipped = fields.Integer(string='Unchanged')
    failed = fields.Integer(string='Failed')
    total = fields.Integer(string='Total', help='Total records to process, where that is known.')

    message = fields.Text(string='Result')
    line_ids = fields.One2many('reax.sync.run.line', 'run_id', string='Modules')
    activity_ids = fields.One2many('reax.sync.activity', 'run_id', string='Activity')

    percent = fields.Float(string='Progress', compute='_compute_progress')
    has_total = fields.Boolean(compute='_compute_progress')
    elapsed = fields.Char(string='Running for', compute='_compute_progress')
    remaining = fields.Integer(string='Remaining', compute='_compute_progress')
    doing = fields.Char(string='Currently', compute='_compute_doing')

    _sql_constraints = [
        ('app_run_uniq', 'unique(app_run_id)', 'That synchronisation is already recorded here.'),
    ]

    @api.depends('app_run_id', 'started_at')
    def _compute_display_title(self):
        for r in self:
            when = fields.Datetime.to_string(r.started_at)[:16] if r.started_at else ''
            r.display_title = 'Sync %s%s' % (r.app_run_id, ' · %s' % when if when else '')

    @api.depends('checked', 'total', 'started_at', 'finished_at', 'progress_at')
    def _compute_progress(self):
        now = fields.Datetime.now()
        for r in self:
            r.has_total = r.total > 0
            r.percent = min(100.0, (r.checked / r.total) * 100.0) if r.total > 0 else 0.0
            r.remaining = max(0, r.total - r.checked) if r.total > 0 else 0
            end = r.finished_at or now
            if r.started_at:
                secs = int((end - r.started_at).total_seconds())
                h, rem = divmod(max(0, secs), 3600)
                m, s = divmod(rem, 60)
                r.elapsed = ('%dh %dm' % (h, m)) if h else (('%dm %ds' % (m, s)) if m else '%ds' % s)
            else:
                r.elapsed = ''

    @api.depends('line_ids.state', 'line_ids.module', 'state')
    def _compute_doing(self):
        """The sentence a person reads: what is happening right now, in words.

        Taken from the module lines rather than from the run's `message`. The app's message field
        holds the last VERDICT ("Up to date"), not what is in flight — showing it as live status
        would put a stale sentence from the previous run under a spinning progress bar.
        """
        for r in self:
            if r.state in ('completed', 'partial', 'failed', 'cancelled'):
                r.doing = dict(RUN_STATES).get(r.state, r.state)
                continue
            active = r.line_ids.filtered(lambda l: l.state == 'running')
            if active:
                r.doing = ', '.join('%s %s' % (l.action_label, l.module_label) for l in active[:3])
            elif r.state == 'queued':
                r.doing = 'Waiting to start'
            else:
                r.doing = 'Preparing'

    def action_reax_open_activity(self):
        """This run's activity, in the ordinary Odoo list — pagination and filters included."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Activity — %s' % self.display_title,
            'res_model': 'reax.sync.activity',
            'view_mode': 'list,form',
            'domain': [('run_id', '=', self.id)],
        }


class ReaxSyncRunLine(models.Model):
    _name = 'reax.sync.run.line'
    _description = 'RealEstateApp synchronisation, one module'
    _order = 'run_id, sequence, id'

    run_id = fields.Many2one('reax.sync.run', required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    module = fields.Char(required=True, help='The data set, as RealEstateApp names it.')
    module_label = fields.Char(compute='_compute_labels', store=True)
    direction = fields.Selection(
        [('push', 'RealEstateApp → Odoo'), ('pull', 'Odoo → RealEstateApp')], string='Direction')
    state = fields.Selection(
        [('waiting', 'Waiting'), ('running', 'Syncing'), ('done', 'Done')],
        default='waiting', string='Status')

    found = fields.Integer(string='Total')
    checked = fields.Integer(string='Processed')
    created = fields.Integer(string='Created')
    updated = fields.Integer(string='Updated')
    skipped = fields.Integer(string='Unchanged')
    failed = fields.Integer(string='Failed')

    percent = fields.Float(string='Progress', compute='_compute_progress')
    has_total = fields.Boolean(compute='_compute_progress')
    action_label = fields.Char(compute='_compute_labels', store=True)

    @api.depends('module', 'direction')
    def _compute_labels(self):
        for l in self:
            l.module_label = (l.module or '').replace('_', ' ').title()
            # The words under the progress line: what is being done, not just to what.
            l.action_label = 'Sending' if l.direction == 'push' else 'Fetching'

    @api.depends('checked', 'found', 'state')
    def _compute_progress(self):
        for l in self:
            # Nine push data sets have no count(), so `found` is genuinely unknown. Those show a
            # running count and NO bar — a bar needs a denominator and inventing one is a lie.
            l.has_total = l.found > 0
            if l.state == 'done' and l.found > 0:
                # FINISHED IS FINISHED. A lane can complete having touched almost nothing — the
                # invoice lane drains its frontier and reports 0 of 32,652 because every record was
                # already up to date and never needed examining. Showing that as 0% said "nothing
                # happened" about work that was done. The engine calling it done IS the fact here.
                l.percent = 100.0
            else:
                l.percent = min(100.0, (l.checked / l.found) * 100.0) if l.found > 0 else 0.0


class ReaxSyncActivity(models.Model):
    _name = 'reax.sync.activity'
    _description = 'RealEstateApp synchronisation activity'
    _order = 'occurred_at desc, id desc'
    _rec_name = 'record_name'

    run_id = fields.Many2one('reax.sync.run', string='Synchronisation', ondelete='set null', index=True)
    occurred_at = fields.Datetime(string='When', required=True, index=True)
    module = fields.Char(string='Module', index=True)
    module_label = fields.Char(compute='_compute_module_label', store=True, string='Module')
    direction = fields.Selection(
        [('push', 'RealEstateApp → Odoo'), ('pull', 'Odoo → RealEstateApp')],
        string='Direction', index=True)
    operation = fields.Selection(
        [('created', 'Created'), ('updated', 'Updated'), ('failed', 'Failed'),
         ('retried', 'Retried'), ('withdrawn', 'Withdrawn')],
        string='Operation', index=True)
    status = fields.Selection(
        [('ok', 'Successful'), ('error', 'Failed')], string='Result', index=True)
    record_name = fields.Char(string='Record')
    record_ref = fields.Char(string='RealEstateApp id')
    external_ref = fields.Char(string='Odoo id')
    trigger = fields.Char(string='Started by')
    message = fields.Text(string='Detail')

    @api.depends('module')
    def _compute_module_label(self):
        for a in self:
            a.module_label = (a.module or '').replace('_', ' ').title()

    # ---- clearing the history -----------------------------------------------------------------
    #
    # This removes the LOG and nothing else. Not one property, contract, invoice, cheque or contact
    # is touched by it, in Odoo or in RealEstateApp — these rows are a record OF work, never the
    # work. Said plainly on the button too, because "clear" next to a synchronisation screen is
    # exactly the word that makes somebody hesitate about their data.
    @api.model
    def action_reax_clear_activity(self):
        """Delete the activity history, honouring whatever the company must keep."""
        keep_days = int(self.env['ir.config_parameter'].sudo().get_param(
            'realestateapp.activity_keep_days') or 0)
        domain = []
        if keep_days > 0:
            cutoff = fields.Datetime.subtract(fields.Datetime.now(), days=keep_days)
            domain = [('occurred_at', '<', cutoff)]
        rows = self.sudo().search(domain)
        n = len(rows)
        rows.unlink()
        kept = self.sudo().search_count([])
        msg = ('%s activity record(s) cleared.' % n) if n else 'There was nothing to clear.'
        if keep_days > 0:
            msg += ' %s kept — the last %s days are retained by policy.' % (kept, keep_days)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success' if n else 'info',
                'title': 'Activity history cleared',
                'message': msg + ' No RealEstateApp or Odoo records were changed.',
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }

    @api.model
    def reax_record_activity(self, rows):
        """Where RealEstateApp writes its activity. One call carries many rows.

        Batched on purpose: a call into Odoo costs about a third of a second whatever it carries, so
        logging record by record would roughly double the time a sync takes. A slice sends its whole
        batch in one call, which costs the same as sending one.

        Anything unrecognised is dropped rather than stored: this is called by an outside system, and
        a log that accepts arbitrary keys is a log that can be filled with nonsense.
        """
        allowed = {'occurred_at', 'module', 'direction', 'operation', 'status',
                   'record_name', 'record_ref', 'external_ref', 'trigger', 'message', 'run_id'}
        clean = []
        for row in (rows or []):
            if not isinstance(row, dict):
                continue
            vals = {k: v for k, v in row.items() if k in allowed}
            if not vals.get('occurred_at'):
                vals['occurred_at'] = fields.Datetime.now()
            clean.append(vals)
        if not clean:
            return 0
        return len(self.sudo().create(clean))
