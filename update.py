# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2012 Red Hat, Inc.
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

r"""
A simple script to update openstack-common modules which have been copied
into other projects. See:

  http://wiki.openstack.org/CommonLibrary#Incubation

The script can be called the following ways:

  $> python update.py ../myproj
  $> python update.py --config-file ../myproj/openstack-common.conf

Where ../myproj is a project directory containing openstack-common.conf which
might look like:

  [DEFAULT]
  modules = wsgi,utils
  base = myproj

Or:

  $> python update.py ../myproj/myconf.conf
  $> python update.py --config-file ../myproj/myconf.conf

Where ../myproj is a project directory which contains a differently named
configuration file, or:

  $> python update.py --config-file ../myproj/myproj/openstack/common.conf \
                      --dest-dir ../myproj

Where ../myproject is a project directory, but the configuration file is
stored in a sub-directory, or:

  $> python update.py --modules wsgi,utils --base myproj ../myproj
  $> python update.py --modules wsgi,utils --base myproj --dest-dir ../myproj

Where ../myproject is a project directory, but we explicitly specify
the modules to copy and the base destination module

Obviously, the first way is the easiest!
"""

import os
import os.path
import re
import shutil
import sys

from openstack.common import cfg

opts = [
    cfg.ListOpt('modules',
                default=[],
                help='The list of modules to copy from openstack-common'),
    cfg.StrOpt('base',
               default=None,
               help='The base module to hold the copy of openstack.common'),
    cfg.StrOpt('dest-dir',
               default=None,
               help='Destination project directory'),
    ]

conf = cfg.ConfigOpts(usage='Usage: %prog [config-file|dest-dir]')
conf.register_cli_opts(opts)
args = conf()

if len(args) == 1:
    def def_config_file(dest_dir):
        return os.path.join(dest_dir, 'openstack-common.conf')

    argv = sys.argv[1:]
    i = argv.index(args[0])

    config_file = None
    if os.path.isfile(argv[i]):
        config_file = argv[i]
    elif os.path.isdir(argv[i]) and os.path.isfile(def_config_file(argv[i])):
        config_file = def_config_file(argv[i])

    if config_file:
        argv[i:i+1] = ['--config-file', config_file]
        args = conf(argv)


if args:
    conf.print_usage(file=sys.stderr)
    sys.exit(1)

dest_dir = conf.dest_dir
if not dest_dir:
    dest_dir = os.path.dirname(conf.config_file[-1])

if not dest_dir or not os.path.isdir(dest_dir):
    print >> sys.stderr, "A valid destination dir is required"
    sys.exit(1)

if not conf.modules:
    print >> sys.stderr, "A list of modules to copy is required"
    sys.exit(1)

if not conf.base:
    print >> sys.stderr, "A destination base module is required"
    sys.exit(1)

print "Copying the %s modules under the %s module in %s" % \
    (','.join(conf.modules), conf.base, dest_dir)

for mod in conf.modules:

    def mod_to_path(mod):
        return os.path.join(*mod.split('.'))

    def dest_path(path):
        return os.path.join(dest_dir, mod_to_path(conf.base), path)

    def replace(path, pattern, replacement):
        with open(path, "r+") as f:
            lines = f.readlines()
            f.seek(0)
            f.truncate()
            for line in lines:
                f.write(re.sub(pattern, replacement, line))

    def copy_file(path):
        dest = dest_path(path)

        if not os.path.isdir(os.path.dirname(dest)):
            os.makedirs(os.path.dirname(dest))

        shutil.copy2(path, dest)

        replace(dest,
                '^from openstack.common',
                'from ' + conf.base + '.openstack.common')

    if '.' in mod:
        path = mod_to_path('openstack.common')
        for d in mod.split('.')[:-1]:
            path = os.path.join(path, d)
            copy_file(os.path.join(path, '__init__.py'))

    copy_file(mod_to_path('openstack.common.' + mod) + '.py')
