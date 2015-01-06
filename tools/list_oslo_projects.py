#!/usr/bin/env python

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

"""Print a list of the oslo project repository names.
"""

from __future__ import print_function

import os

from oslo_config import cfg
import yaml


DEFAULT_CONFIG_FILES = [
    './oslo.conf',
    os.path.expanduser('~/.oslo.conf'),
]


def main():
    conf = cfg.ConfigOpts()
    conf.register_cli_opt(
        cfg.StrOpt(
            'repo_root',
            default='.',
            help='directory containing the git repositories',
        )
    )
    # Look for a few configuration files, and load the ones we find.
    default_config_files = [
        f
        for f in DEFAULT_CONFIG_FILES
        if os.path.exists(f)
    ]
    conf(
        project='oslo',
        default_config_files=default_config_files,
    )

    # Find the governance repository.
    gov_repo = os.path.expanduser(os.path.join(conf.repo_root,
                                               'openstack/governance'))

    # Parse the program file within the repository.
    program_input = os.path.join(gov_repo, 'reference/programs.yaml')
    with open(program_input, 'r') as f:
        program = yaml.load(f.read())

    # Print the list of repositories.
    repos = [p['repo'] for p in program['Common Libraries']['projects']]
    for r in sorted(repos):
        print(r)


if __name__ == '__main__':
    import sys
    sys.exit(main())
