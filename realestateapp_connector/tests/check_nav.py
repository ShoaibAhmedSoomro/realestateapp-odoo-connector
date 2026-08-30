# -*- coding: utf-8 -*-
"""The smallest thing that fails if the navigation default breaks again.

    python realestateapp_connector/tests/check_nav.py

Runnable without Odoo, on purpose: the bug it guards was in a one-line truth test, it hid all
nineteen RealEstateApp menus on a live install, and nothing short of running it would have shown
that — the docstring above the line said the opposite of what the line did.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, '..', 'models', 'reax_nav.py')

# Imported by reading rather than by `import`, so this needs no Odoo on the path.
src = open(SRC, encoding='utf-8').read()
ns = {}
body = src[src.index('def nav_enabled('):src.index('class ReaxNav')]
exec(compile(body, SRC, 'exec'), ns)                      # noqa: S102 — our own file, read above
nav_enabled = ns['nav_enabled']

CASES = [
    # (what ir.config_parameter.get_param returns, expected, why it matters)
    (False,   True,  'NEVER SET — Odoo returns Python False, not None and not "". '
                     'This is the exact case that hid all nineteen menus.'),
    (None,    True,  'absent by another route'),
    ('',      True,  'empty string'),
    ('True',  True,  'switched on'),
    ('False', False, 'switched OFF deliberately — must NOT be confused with never-set'),
    ('true',  False, 'anything that is not exactly "True" is off, rather than guessed at'),
]

fails = 0
for raw, want, why in CASES:
    got = nav_enabled(raw)
    okay = got is want
    print('  %s  get_param -> %-8r => %-5r  %s' % ('PASS' if okay else 'FAIL', raw, got, why))
    if not okay:
        fails += 1

# The three lists that must never drift: one nav item, one settings field, one checkbox on screen.
items = re.findall(r"\('(reax_nav_\w+)',\s*'([\w.]+)',", src)
cfg = open(os.path.join(HERE, '..', 'models', 'res_config_settings.py'), encoding='utf-8').read()
view = open(os.path.join(HERE, '..', 'views', 'res_config_settings_views.xml'), encoding='utf-8').read()
fields = set(re.findall(r'(reax_nav_\w+) = fields\.Boolean', cfg))
shown = set(re.findall(r'name="(reax_nav_\w+)"', view))
names = {i[0] for i in items}
for label, got in (('settings fields', fields), ('checkboxes on screen', shown)):
    okay = got == names
    print('  %s  %d %s match the %d nav items' % ('PASS' if okay else 'FAIL', len(got), label, len(names)))
    if not okay:
        fails += 1
        print('        only in one side: %s' % (got ^ names))

# config_parameter= cannot express "off": set_param(key, False) DELETES the row.
okay = 'realestateapp.nav.' not in cfg
print('  %s  the nav fields do not use config_parameter, which cannot store "off"' % ('PASS' if okay else 'FAIL'))
if not okay:
    fails += 1

print('\n%d passed, %d failed' % (len(CASES) + 3 - fails, fails))
sys.exit(1 if fails else 0)
