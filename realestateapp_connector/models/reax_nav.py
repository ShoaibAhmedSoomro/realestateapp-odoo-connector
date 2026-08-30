# -*- coding: utf-8 -*-
"""WHICH REALESTATEAPP MODULES APPEAR IN THIS ODOO'S MENU.

Not every customer wants every part of the app inside Odoo. A firm that runs maintenance in another
system does not want a Maintenance menu that mirrors it, and a menu nobody uses is a menu somebody
opens by mistake.

HOW IT PERSISTS, which is the part that is easy to get wrong. The setting lives in
ir.config_parameter — plain rows nothing resets. The MENU's own `active` flag is only ever the
consequence: menus come from this module's data file, and Odoo REWRITES data records on every module
upgrade, so a menu switched off by hand comes back the next time somebody presses Upgrade. Storing
the intent separately and re-applying it from `_register_hook` — which runs on every registry load,
after data is loaded — is what makes the choice survive both a restart and an upgrade.

WHAT THIS IS NOT. Hiding a menu is navigation, not access control. Odoo's access control is groups
and record rules, and this deliberately does not touch them: silently stripping a user's rights from
a settings checkbox is how people get locked out of their own data. The two compose exactly as the
brief asks — a person sees a module when it is enabled here AND their Odoo groups allow it — and the
group half is still the one that decides what may be READ.
"""
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

PARAM_PREFIX = 'realestateapp.nav.'

# Every menu a person can switch, in the order they appear in Odoo. Each entry is
#   (settings field name, menu XML id, the words on the screen)
# The parents — Property Mgmt., Leasing, Operations, People — are deliberately absent: Odoo already
# hides a parent whose children are all hidden, so switching off both Properties and Units removes
# the section by itself. Listing parents as well would let somebody switch off a section while its
# children claim to be on, and then wonder which one won.
REAX_NAV_ITEMS = (
    ('reax_nav_dashboard', 'realestateapp_connector.menu_reax_dashboard', 'Dashboard'),
    ('reax_nav_properties', 'realestateapp_connector.menu_reax_properties', 'Properties'),
    ('reax_nav_units', 'realestateapp_connector.menu_reax_units', 'Units'),
    ('reax_nav_leads', 'realestateapp_connector.menu_reax_leads', 'Leads'),
    ('reax_nav_requests', 'realestateapp_connector.menu_reax_requests', 'Leasing Requests'),
    ('reax_nav_bookings', 'realestateapp_connector.menu_reax_bookings', 'Bookings'),
    ('reax_nav_contracts', 'realestateapp_connector.menu_reax_contracts', 'Contracts'),
    ('reax_nav_renewals', 'realestateapp_connector.menu_reax_renewals', 'Renewals'),
    ('reax_nav_accounts', 'realestateapp_connector.menu_reax_accounts', 'Accounts'),
    ('reax_nav_legal', 'realestateapp_connector.menu_reax_legal_cases', 'Legal Cases'),
    ('reax_nav_maintenance', 'realestateapp_connector.menu_reax_maintenance', 'Maintenance'),
    ('reax_nav_amc', 'realestateapp_connector.menu_reax_amc', 'AMC Contracts'),
    ('reax_nav_assets', 'realestateapp_connector.menu_reax_assets', 'Assets'),
    ('reax_nav_inspections', 'realestateapp_connector.menu_reax_inspections', 'Inspections'),
    ('reax_nav_contacts', 'realestateapp_connector.menu_reax_contacts', 'Contacts'),
    ('reax_nav_tenants', 'realestateapp_connector.menu_reax_tenants', 'Tenants'),
    ('reax_nav_landlords', 'realestateapp_connector.menu_reax_landlords', 'Landlords'),
    ('reax_nav_vendors', 'realestateapp_connector.menu_reax_vendors', 'Vendors'),
    ('reax_nav_staff', 'realestateapp_connector.menu_reax_staff', 'Staff'),
)


def nav_enabled(raw):
    """Is a module enabled, given whatever ir.config_parameter handed back?

    Pure, and separate from the model, so the truth table can be checked without an Odoo running —
    which is the whole reason this exists. The version before it took `raw is None or raw == ''` to
    mean "unset". Odoo returns Python **False** for an unset key, which is neither of those, so every
    unconfigured module fell through to (False == 'True') and came out hidden. Nineteen menus went
    dark on a live install.

        get_param -> False   (never set)      -> True,  show it
        get_param -> 'True'                   -> True,  show it
        get_param -> 'False' (deliberately)   -> False, hide it
    """
    return True if not raw else str(raw) == 'True'


class ReaxNav(models.AbstractModel):
    """The apply half, on its own so both the settings page and the registry hook can call it."""
    _name = 'reax.nav'
    _description = 'RealEstateApp navigation visibility'

    @api.model
    def _param(self, field):
        return PARAM_PREFIX + field[len('reax_nav_'):]

    @api.model
    def _enabled(self, field):
        """Default ON, and getting this wrong hides the entire app.

        Odoo's get_param returns Python **False** for a key that is not set — not None, not ''. An
        earlier version tested `raw is None or raw == ''`, which False satisfies neither of, so every
        unconfigured module fell through to (False == 'True') and came out HIDDEN. It switched off
        all nineteen menus on a live install. The docstring said "default ON" and the code did the
        opposite of what it said, which is why this now tests truthiness and nothing else.

        The other half of the trap: set_param(key, False) DELETES the row, so an explicit "off"
        cannot be stored as a Python False. set_values below writes the literal strings 'True' and
        'False' instead, which is what makes "never configured" and "deliberately off" different
        things rather than the same absent row.
        """
        return nav_enabled(self.env['ir.config_parameter'].sudo().get_param(self._param(field)))

    @api.model
    def reax_apply_navigation(self):
        """Public wrapper. _apply starts with an underscore, so Odoo refuses to call it over RPC —
        which is correct, and this is the door for the check that has to."""
        return self._apply()

    @api.model
    def _apply(self):
        """Make the menus match the setting. Cheap, idempotent, and safe to call on every load."""
        changed = 0
        for field, xmlid, _label in REAX_NAV_ITEMS:
            menu = self.env.ref(xmlid, raise_if_not_found=False)
            if not menu:
                continue                      # a menu from the accounting bridge, which may be absent
            want = self._enabled(field)
            if menu.active != want:
                menu.write({'active': want})
                changed += 1
        if changed:
            # The menu tree is cached per user; without this the change appears only after a reload.
            # registry.clear_cache() and not menus.clear_caches(): the model-level helper was removed
            # in Odoo 18, so the hasattr this used to guard on could only ever be false — a branch
            # that read as a compatibility shim and was in fact dead code.
            self.env.registry.clear_cache()
            _logger.info('RealEstateApp: navigation updated, %s menu(s) changed', changed)
        return changed

    def _register_hook(self):
        """Re-apply on every registry load — a restart, and every module upgrade.

        This is the load-bearing part. Menus are data records, and Odoo rewrites data records on
        upgrade, so `active` is reset to what the XML says. The parameter is the intent; this puts
        the menus back in line with it. Wrapped because a failure here would take the whole registry
        down, and a menu that is showing when it should be hidden is not worth that.
        """
        try:
            self._apply()
        except Exception:      # noqa: BLE001
            _logger.warning('RealEstateApp: could not apply navigation settings', exc_info=True)
        return super()._register_hook()
