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

import oslo_tool_config as cfg
import yaml


def main():
    conf = cfg.get_config_parser()
    cfg.parse_arguments(conf)

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
