# -*- coding: utf-8 -*-
"""One-click enrolment, from inside the customer's own Odoo.

The whole point of this module is that it already knows what a person would otherwise have to go and find:

    web address   ir.config_parameter 'web.base.url'
    database      the cursor's own dbname
    login         the user pressing the button
    API key       res.users.apikeys._generate — no password prompt, because this is trusted server code
    datasets      whether crm.lead exists in THIS instance, rather than assuming it does

That last one is not a nicety. Odoo ships without the CRM app installed, and a connection configured to read
crm.lead on an instance that has no CRM authenticates perfectly and then syncs nothing — a support ticket
that looks like a broken integration. Asking the registry costs one query and removes the whole class.
"""
import json
import logging
import urllib.error
import urllib.request

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Where the enrolment is posted. Overridable because customers of a self-hosted RealEstateApp have their own
# address; this default is ASICO's own, which is the address every current installation uses.
DEFAULT_ENDPOINT = 'https://www.dubailuxuryhomes.ae'
TIMEOUT = 20

PARAM_ENDPOINT = 'realestateapp.endpoint'
PARAM_CONNECTED = 'realestateapp.connected_at'
PARAM_ACCOUNT = 'realestateapp.account'

# Every dataset RealEstateApp understands, and the Odoo models each one genuinely needs.
#
# Declarative on purpose. The old version hardcoded 'contacts' and appended 'leads' if crm.lead existed,
# which meant adding a dataset required editing three places and forgetting one of them was silent. Here a
# dataset that names a model this database does not have simply does not appear — on the wire or on the
# screen — rather than producing a connection that authenticates perfectly and then syncs nothing.
#
# The keys must match src/lib/connectors/registry.ts in RealEstateApp exactly. A key this side invents is
# dropped by the enrolment route, which is the safe direction, but it will not sync and nobody is told why.
#
#   (key, direction, models that must ALL exist, the sentence a person reads on the screen)
REAX_DATASETS = (
    ('contacts', 'pull', ('res.partner',),
     'Contacts — names, emails and phone numbers from Odoo Contacts.'),
    ('leads', 'pull', ('crm.lead',),
     'CRM leads — opportunities from Odoo CRM, if that app is installed.'),
    ('tenants', 'push', ('res.partner',),
     'Tenants — sent to Odoo as customer contacts.'),
    ('lessors', 'push', ('res.partner',),
     'Landlords — sent as supplier contacts, the side of Odoo that can pay them.'),
    ('lessors_realestate', 'push', ('realestate.lessor',),
     'Landlords — also sent to the Real Estate app in this Odoo, if you have it.'),
    ('vendors', 'push', ('res.partner',),
     'Vendors and contractors — sent to Odoo as supplier contacts.'),
    ('people', 'push', ('res.partner',),
     'Agents, facilitators and property administrators — sent to Odoo as contacts.'),
    # The rent schedule. Listed here so the settings page reports it like every other data set — it was
    # added on the RealEstateApp side after this table was written and was the one push the Odoo end
    # never mentioned. account.move only exists where Accounting is installed, which _reax_present_models
    # already handles: absent, and the row simply is not offered.
    ('invoices', 'push', ('account.move',),
     'Rent schedule — each instalment sent as a customer invoice Odoo can post and reconcile.'),
)


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    reax_endpoint = fields.Char(
        string='RealEstateApp address',
        config_parameter=PARAM_ENDPOINT,
        default=DEFAULT_ENDPOINT,
        help='Leave this as it is unless you were given a different address.',
    )
    reax_pairing_code = fields.Char(
        string='Pairing code',
        help='Copy this from Connectors in RealEstateApp. It is valid for 30 minutes and can be used once.',
    )
    # Read-only status, so somebody opening this screen can see where they stand without pressing anything.
    reax_connected_at = fields.Char(string='Connected', config_parameter=PARAM_CONNECTED, readonly=True)
    reax_account = fields.Char(string='Connected as', config_parameter=PARAM_ACCOUNT, readonly=True)
    # Computed rather than written into the view, so the list on screen is the same list that goes on the
    # wire. A hand-written list drifts the first time somebody adds a dataset and forgets this file.
    reax_shares = fields.Text(string='What gets shared', compute='_compute_reax_shares', readonly=True)

    # ---- what this instance can actually offer ----------------------------------------------------
    def _reax_present_models(self):
        """Which of the models we care about exist in THIS database. One query, not one per dataset."""
        wanted = sorted({m for _k, _d, models, _t in REAX_DATASETS for m in models})
        rows = self.env['ir.model'].sudo().search_read([('model', 'in', wanted)], ['model'])
        return {r['model'] for r in rows}

    def _reax_can_use(self, model, operation):
        """Existing is not the same as usable.

        The sync runs as THIS login, over an API key minted for it — so a model the login cannot read (or
        create) is a dataset that will 403 on every single record at run time. Hiding a dataset somebody
        could have served is a far smaller failure than offering one that silently fails all night.

        Odoo 18 renamed check_access_rights() to has_access(); both are handled so this also installs on 17.
        Any surprise counts as 'no' — an access probe must never be the thing that breaks the Settings page.
        """
        model_obj = self.env.get(model)
        if model_obj is None:
            return False
        try:
            if hasattr(model_obj, 'has_access'):
                return bool(model_obj.has_access(operation))
            return bool(model_obj.check_access_rights(operation, raise_exception=False))
        except Exception:      # noqa: BLE001
            return False

    def _reax_offer(self):
        """The datasets this instance can serve, split by direction.

        One source for three consumers: the enrolment payload, the text on the screen, and reax_status().
        They used to be three hand-written lists, which is how a screen ends up promising something the
        code will not send.
        """
        present = self._reax_present_models()
        offer = {'pull': [], 'push': [], 'lines': []}
        for key, direction, models, text in REAX_DATASETS:
            if not all(m in present for m in models):
                continue
            operation = 'read' if direction == 'pull' else 'create'
            if not all(self._reax_can_use(m, operation) for m in models):
                continue
            offer[direction].append(key)
            offer['lines'].append(
                (_('Read from Odoo') if direction == 'pull' else _('Sent to Odoo'), text))
        return offer

    def _reax_datasets(self):
        """Kept as-is for compatibility: RealEstateApp builds before push support read only this list."""
        return self._reax_offer()['pull']

    @api.depends_context('uid')
    def _compute_reax_shares(self):
        for record in self:
            try:
                groups = {}
                for heading, text in record._reax_offer()['lines']:
                    groups.setdefault(heading, []).append(u'  • %s' % text)
                record.reax_shares = u'\n\n'.join(
                    u'%s\n%s' % (heading, u'\n'.join(items)) for heading, items in groups.items()
                ) or _('This Odoo has none of the apps this connector can use.')
            except Exception:      # noqa: BLE001
                # A compute that raises takes down the WHOLE Settings page, for every app, not just ours.
                record.reax_shares = _('Could not work out what this Odoo can share.')

    def _reax_base_url(self):
        url = (self.env['ir.config_parameter'].sudo().get_param('web.base.url') or '').strip().rstrip('/')
        if not url:
            raise UserError(_('This Odoo has no web address configured, so RealEstateApp would not know '
                              'where to reach it. Set it under Settings → Technical → System Parameters '
                              '(web.base.url) and try again.'))
        if url.startswith('http://') and 'localhost' not in url and not url.startswith('http://127.'):
            raise UserError(_('Your Odoo web address is not secure (%s). RealEstateApp will only connect '
                              'over https, because an API key travels on this connection.') % url)
        return url

    # ---- the button -------------------------------------------------------------------------------
    def action_reax_connect(self):
        self.ensure_one()
        code = (self.reax_pairing_code or '').strip()
        if not code:
            raise UserError(_('Paste the pairing code from RealEstateApp first. You will find it under '
                              'Connectors → Odoo → Connect with the Odoo app.'))

        endpoint = (self.reax_endpoint or DEFAULT_ENDPOINT).strip().rstrip('/')
        base_url = self._reax_base_url()
        user = self.env.user

        # The key is minted for the user pressing the button, which is why there is no password prompt:
        # this is trusted server code, not the browser wizard. It is named so it is obvious in Account
        # Security what it belongs to, and revoking it there is a complete disconnect.
        #
        # THREE THINGS HERE ARE LOAD-BEARING, all from base/models/res_users.py:
        #
        #   sudo()  — _check_expiration_date returns early only for a system user. Called as an ordinary
        #             user it refuses a persistent key outright ("The API key must have an expiration
        #             date") and caps any date at the user's group api_key_duration. Odoo's own docstring
        #             says to sudo for a duration beyond the user's privileges. sudo() raises su, NOT the
        #             uid, so _generate still records self.env.user.id — the key belongs to the person
        #             who pressed the button, not to a superuser.
        #   False   — "For a persistent key (infinite duration), no value for expiration date." An
        #             integration key that silently expires is an outage nobody connects to a cause; this
        #             one is revoked deliberately, by Disconnect or in Account Security.
        #   'rpc'   — the scope external calls are checked against (_check_credentials(scope='rpc')). A
        #             NULL scope would work for any RPC; naming it keeps the key to the one job it has.
        try:
            api_key = self.env['res.users.apikeys'].sudo()._generate('rpc', 'RealEstateApp connector', False)
        except Exception as exc:      # noqa: BLE001 — Odoo raises several types here
            _logger.warning('RealEstateApp: could not generate an API key: %s', exc)
            raise UserError(_('Odoo would not create an API key for your user. An administrator can allow '
                              'this, or you can create one by hand under My Profile → Account Security '
                              'and connect from RealEstateApp instead.')) from exc

        # Both directions on the wire. `datasets` keeps its old meaning — the sets RealEstateApp READS from
        # this Odoo — so an app build that predates push support is unaffected. `push_datasets` is additive:
        # an app that does not know the field ignores it, and an older module that never sends it must be
        # read as "none", never as "everything".
        offer = self._reax_offer()
        payload = {
            'base_url': base_url,
            'db': self.env.cr.dbname,
            'login': user.login,
            'api_key': api_key,
            'datasets': offer['pull'],
            'push_datasets': offer['push'],
            'odoo_version': self.env['ir.module.module'].sudo().search(
                [('name', '=', 'base')], limit=1).latest_version or '',
            'module_version': self.env['ir.module.module'].sudo().search(
                [('name', '=', 'realestateapp_connector')], limit=1).latest_version or '',
        }

        url = '%s/api/connectors/enroll/%s' % (endpoint, code)
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
                body = json.loads(response.read().decode('utf-8') or '{}')
        except urllib.error.HTTPError as exc:
            # RealEstateApp answers with a plain sentence for a person; show that rather than a status code.
            detail = ''
            try:
                detail = json.loads(exc.read().decode('utf-8') or '{}').get('error') or ''
            except Exception:      # noqa: BLE001
                pass
            raise UserError(detail or _('RealEstateApp refused the connection (error %s).') % exc.code) from exc
        except urllib.error.URLError as exc:
            raise UserError(_('Could not reach RealEstateApp at %s. Check the address and that this server '
                              'can make outgoing connections.') % endpoint) from exc

        if not body.get('ok'):
            raise UserError(body.get('error') or _('RealEstateApp did not confirm the connection.'))

        params = self.env['ir.config_parameter'].sudo()
        params.set_param(PARAM_CONNECTED, fields.Datetime.to_string(fields.Datetime.now()))
        params.set_param(PARAM_ACCOUNT, user.login)
        params.set_param(PARAM_ENDPOINT, endpoint)

        # Report BOTH halves. Naming only what is read told people their tenants were not being sent when
        # they were — and the app now answers with both lists for exactly this.
        shared = ', '.join(
            (body.get('datasets') or payload['datasets'])
            + (body.get('push_datasets') or payload['push_datasets'])
        ) or _('nothing yet')
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'title': _('Connected to RealEstateApp'),
                'message': _('Sharing: %s. You can disconnect here at any time.') % shared,
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }

    def action_reax_disconnect(self):
        """Revoke the key this module made. That is the actual disconnect — not a flag.

        Only the key NAMED by this module is removed, so a key somebody created by hand for another tool is
        left alone.
        """
        self.ensure_one()
        keys = self.env['res.users.apikeys'].sudo().search([
            ('user_id', '=', self.env.user.id), ('name', '=', 'RealEstateApp connector'),
        ])
        removed = len(keys)
        keys.unlink()
        params = self.env['ir.config_parameter'].sudo()
        params.set_param(PARAM_CONNECTED, '')
        params.set_param(PARAM_ACCOUNT, '')
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'warning' if removed else 'info',
                'title': _('Disconnected'),
                'message': (_('%s API key(s) revoked. RealEstateApp can no longer read this Odoo.') % removed
                            if removed else
                            _('There was no key from this app to revoke.')),
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }

    @api.model
    def reax_status(self):
        """Small helper for support: what this instance would send, minus anything secret."""
        offer = self._reax_offer()
        return {
            'base_url': (self.env['ir.config_parameter'].sudo().get_param('web.base.url') or ''),
            'db': self.env.cr.dbname,
            'login': self.env.user.login,
            'datasets': offer['pull'],
            'push_datasets': offer['push'],
        }
