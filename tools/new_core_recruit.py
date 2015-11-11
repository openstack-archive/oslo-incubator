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

import random
import sys

import jinja2
import parawrap


def expand_template(contents, params):
    if not params:
        params = {}
    tpl = jinja2.Template(source=contents, undefined=jinja2.StrictUndefined)
    return tpl.render(**params)


chosen_how = [
    'selected',
    'picked',
    'targeted',
]
new_oslo_core_tpl = """
Hi {{firstname}} {{lastname}},

You have been {{chosen_how}} to be a new {{project}} core (if you are
willing to accept this mission). We have been watching your commits and
reviews and have noticed that you may be interested in a core position
that would be granted to you (if you are willing to accept the
responsibility of being a new core member[1] in project {{project}}).

What do you think, are you able (and willing) to accept?

If you have any questions, please feel free to respond or jump on
freenode and chat with the team on channel #openstack-oslo (one of the
other cores in oslo usually around).

This message will self-destruct in 5 seconds.

Sincerely,

The Oslo Team

[1] http://docs.openstack.org/infra/manual/core.html
"""
firstname = sys.argv[1]
lastname = sys.argv[2]
tpl_args = {
    'firstname': firstname,
    'project': sys.argv[3],
    'lastname': lastname,
    'firstname_title': firstname.title(),
    'lastname_title': lastname.title(),
    'chosen_how': random.choice(chosen_how),
}

tpl_value = expand_template(new_oslo_core_tpl.lstrip(), tpl_args)
tpl_value = parawrap.fill(tpl_value)
print(tpl_value)
