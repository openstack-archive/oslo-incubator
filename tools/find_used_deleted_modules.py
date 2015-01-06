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
"""
Look through the openstack-common.conf files for projects to find
any that are using modules that have been deleted from the
incubator.
"""

from __future__ import print_function

import glob
import os
import sys

from oslo_config import cfg

# Extend sys.path to find update.py
my_dir = os.path.dirname(__file__)
incubator_root = os.path.abspath(os.path.dirname(my_dir))
sys.path.append(incubator_root)
import update


def main(argv=sys.argv[1:]):
    repodir = os.path.abspath(
        os.path.join(my_dir, os.pardir, os.pardir, os.pardir)
    )

    main_cfg = cfg.ConfigOpts()
    main_cfg.register_cli_opt(
        cfg.MultiStrOpt(
            # NOTE(dhellmann): We can't call this "project" because
            # that conflicts with another property of the ConfigOpts
            # class.
            'proj',
            default=[],
            positional=True,
            help='list of repo subdirs to scan, e.g. "openstack/nova"',
        )
    )
    main_cfg(argv)

    # If the user gave us project names, turn them into full paths to
    # the project directory. If not, build a full list of all the
    # projects we find.
    projects = main_cfg.proj
    if projects:
        projects = [os.path.join(repodir, p) for p in projects]
    else:
        projects = glob.glob(
            os.path.join(repodir, '*', '*')
        )

    base_dir = os.path.join(
        incubator_root,
        'openstack',
        'common',
    )
    tools_dir = os.path.join(incubator_root, 'tools')

    previous_project = None
    for project_path in projects:
        conf_file = os.path.join(project_path, 'openstack-common.conf')
        if not os.path.exists(conf_file):
            # This is not a directory using oslo-incubator.
            continue

        project_name = '/'.join(project_path.split('/')[-2:])

        # Use a separate parser for each configuration file.
        pcfg = cfg.ConfigOpts()
        pcfg.register_opts(update.opts)
        pcfg(['--config-file', conf_file])

        # The list of modules can come in a couple of different
        # options, so combine the results.
        modules = pcfg.module + pcfg.modules
        for mod in modules:
            # Build a few filenames and patterns for looking for
            # versions of the module being used by the project before
            # testing them all.
            mod_path = os.path.join(
                base_dir,
                mod.replace('.', os.sep),
            )
            mod_file = '%s.py' % mod_path
            tool_pattern = os.path.join(tools_dir, mod + '*')
            tool_subdir_pattern = os.path.join(tools_dir, mod, '*.sh')
            if (os.path.isfile(mod_file)
                    or
                    os.path.isdir(mod_path)
                    or
                    glob.glob(tool_pattern)
                    or
                    glob.glob(tool_subdir_pattern)):
                # Found something we would have copied in update.py.
                continue
            else:
                if project_name != previous_project:
                    previous_project = project_name
                    print()
                print('%s: %s' % (project_name, mod))

if __name__ == '__main__':
    main()
