#!/usr/bin/env python
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import sys

import delorean
import jinja2
import parawrap


def expand_template(contents, params):
    if not params:
        params = {}
    tpl = jinja2.Template(source=contents, undefined=jinja2.StrictUndefined)
    return tpl.render(**params)


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
when = getattr(d, sys.argv[2].replace(" ", "_"))
project = sys.argv[1]
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
