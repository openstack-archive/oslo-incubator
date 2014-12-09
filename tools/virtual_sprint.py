#!/usr/bin/env python

# vi: ts=4 expandtab
#
#    Copyright (C) 2014 Yahoo! Inc.
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License version 3, as
#    published by the Free Software Foundation.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.

import sys

import delorean
import jinja2
import parawrap


def expand_template(contents, params):
    if not params:
        params = {}
    tpl = jinja2.Template(source=str(contents),
                          undefined=jinja2.StrictUndefined).render(**params)
    return tpl


TPL = """
Hi everyone,

The OpenStack {{ team }} team will be hosting a virtual sprint in
the Freenode IRC channel #{{ channel }} for the {{ for }}
on {{ when }} starting at {{ starts_at }} and going for ~{{ duration }} hours.

The goal of this sprint is to work on any open reviews, documentation or
any other integration questions, development and so-on, so that we can help
progress the {{ for }} forward at a good rate.

Live version of the current documentation is available here:

{{ docs }}

The code itself lives in the openstack/{{ project }} respository.

{{ git_tree }}

Please feel free to join if interested, curious, or able.

Much appreciated,

{{ author }}
"""

# Example:
#
# python tools/virtual_sprint.py  "taskflow" "next tuesday" "Joshua Harlow"
if len(sys.argv) != 4:
    print("%s project when author" % sys.argv[0])
    sys.exit(1)

# Something like 'next tuesday' is expected...
d = delorean.Delorean()
project = sys.argv[1]
when = getattr(d, sys.argv[2].replace(" ", "_"))
author = sys.argv[3]
params = {
    'team': 'oslo',
    'project': project,
    'channel': 'openstack-oslo',
    'docs': 'http://docs.openstack.org/developer/%s/' % project,
    'when': when().datetime.strftime('%A %m-%d-%Y'),
    'starts_at': '16:00 UTC',
    'duration': 8,
    'author': author,
    'git_tree': 'http://git.openstack.org/cgit/openstack/%s/tree' % project,
}
params['for'] = params['project'] + ' ' + 'subproject'
for line in parawrap.wrap(expand_template(TPL.strip(), params)):
    print(line)
