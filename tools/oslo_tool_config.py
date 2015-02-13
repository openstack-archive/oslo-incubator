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
"""Utilities functions for working with oslo.config from the tool scripts.
"""

import os

from oslo_config import cfg

DEFAULT_CONFIG_FILES = [
    './oslo.conf',
    os.path.expanduser('~/.oslo.conf'),
]


def get_config_parser():
    conf = cfg.ConfigOpts()
    conf.register_cli_opt(
        cfg.StrOpt(
            'repo_root',
            default='.',
            help='directory containing the git repositories',
        )
    )
    return conf


def parse_arguments(conf):
    # Look for a few configuration files, and load the ones we find.
    default_config_files = [
        f
        for f in DEFAULT_CONFIG_FILES
        if os.path.exists(f)
    ]
    return conf(
        project='oslo',
        default_config_files=default_config_files,
    )
