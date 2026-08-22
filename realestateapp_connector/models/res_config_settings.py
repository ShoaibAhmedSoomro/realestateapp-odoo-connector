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

    # ---- what this instance can actually offer ----------------------------------------------------
    def _reax_datasets(self):
        """The dataset keys RealEstateApp understands that THIS instance can serve.

        Contacts is always available — res.partner is in base. CRM is only there if the app is installed,
        and claiming it when it is not is the difference between a connection that works and one that
        authenticates and then does nothing.
        """
        datasets = ['contacts']
        if self.env['ir.model'].sudo().search_count([('model', '=', 'crm.lead')]):
            datasets.append('leads')
        return datasets

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

        payload = {
            'base_url': base_url,
            'db': self.env.cr.dbname,
            'login': user.login,
            'api_key': api_key,
            'datasets': self._reax_datasets(),
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

        shared = ', '.join(body.get('datasets') or payload['datasets'])
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
        return {
            'base_url': (self.env['ir.config_parameter'].sudo().get_param('web.base.url') or ''),
            'db': self.env.cr.dbname,
            'login': self.env.user.login,
            'datasets': self._reax_datasets(),
        }
