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

  $> python update.py --config-file ../myproj/myproj/openstack/common.conf
                      --dest-dir ../myproj

Where ../myproject is a project directory, but the configuration file is
stored in a sub-directory, or:

  $> python update.py --modules wsgi,utils --base myproj ../myproj
  $> python update.py --modules wsgi,utils --base myproj --dest-dir ../myproj

Where ../myproject is a project directory, but we explicitly specify
the modules to copy and the base destination module

Obviously, the first way is the easiest!
"""

import glob
import os
import os.path
import re
import shutil
import sys

try:
    from openstack.common import cfg
except:
    sys.stderr.write("Try running update.sh")
    raise

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
    cfg.StrOpt('configfile_or_destdir',
               default=None,
               help='A config file or destination project directory',
               positional=True),
]


def _parse_args(argv):
    conf = cfg.ConfigOpts()
    conf.register_cli_opts(opts)
    conf(argv, usage='Usage: %(prog)s [config-file|dest-dir]')

    if conf.configfile_or_destdir:
        def def_config_file(dest_dir):
            return os.path.join(dest_dir, 'openstack-common.conf')

        config_file = None
        if os.path.isfile(conf.configfile_or_destdir):
            config_file = conf.configfile_or_destdir
        elif (os.path.isdir(conf.configfile_or_destdir)
              and os.path.isfile(def_config_file(conf.configfile_or_destdir))):
            config_file = def_config_file(conf.configfile_or_destdir)

        if config_file:
            conf(argv + ['--config-file', config_file])

    return conf


def _mod_to_path(mod):
    return os.path.join(*mod.split('.'))


def _dest_path(path, base, dest_dir):
    return os.path.join(dest_dir, _mod_to_path(base), path)


def _replace(path, pattern, replacement):
    with open(path, "rb+") as f:
        lines = f.readlines()
        f.seek(0)
        f.truncate()
        for line in lines:
            f.write(re.sub(pattern, replacement, line))


def _make_dirs(path):
    if not os.path.isdir(os.path.dirname(path)):
        os.makedirs(os.path.dirname(path))


def _copy_file(path, dest, base):
    _make_dirs(dest)
    if not os.path.isdir(os.path.dirname(dest)):
        os.makedirs(os.path.dirname(dest))

    shutil.copy2(path, dest)

    _replace(dest, 'oslo', base)

    _replace(dest,
             '^( *)from openstack.common',
             r'\1from ' + base + '.openstack.common')

    _replace(dest,
             '\'openstack\.common',
             '\'' + base + '.openstack.common')

    _replace(dest,
             '\"openstack\.common',
             '\"' + base + '.openstack.common')


def _copy_pyfile(path, base, dest_dir):
    _copy_file(path, _dest_path(path, base, dest_dir), base)


def _copy_module(mod, base, dest_dir):
    print ("Copying openstack.common.%s under the %s module in %s" %
           (mod, base, dest_dir))

    if '.' in mod:
        path = _mod_to_path('openstack.common')
        for d in mod.split('.')[:-1]:
            path = os.path.join(path, d)
            _copy_pyfile(os.path.join(path, '__init__.py'), base, dest_dir)

    mod_path = _mod_to_path('openstack.common.%s' % mod)
    mod_file = '%s.py' % mod_path
    if os.path.isfile(mod_file):
        _copy_pyfile(mod_file, base, dest_dir)
    elif os.path.isdir(mod_path):
        dest = os.path.join(dest_dir, _mod_to_path(base),
                            'openstack', 'common', mod)
        _make_dirs(dest)
        sources = filter(lambda x: x[-3:] == '.py', os.listdir(mod_path))
        for s in sources:
            _copy_pyfile(os.path.join(mod_path, s), base, dest_dir)

    globs_to_copy = [
        os.path.join('bin', 'oslo-' + mod + '*'),
        os.path.join('tools', mod + '*'),
        os.path.join('etc', 'oslo', mod + '*.conf'),
    ]

    for matches in [glob.glob(g) for g in globs_to_copy]:
        for match in matches:
            dest = os.path.join(dest_dir, match.replace('oslo', base))
            print "Copying %s to %s" % (match, dest)
            _copy_file(match, dest, base)


def _create_module_init(base, dest_dir, *sub_paths):
    """Create module __init__ files."""
    init_path = _dest_path('openstack', base, dest_dir)

    if sub_paths:
        init_path = os.path.join(init_path, *sub_paths)

    init_path = os.path.join(init_path, '__init__.py')

    if not os.path.exists(init_path):
        _make_dirs(init_path)
        open(init_path, 'w').close()


def main(argv):
    conf = _parse_args(argv)

    dest_dir = conf.dest_dir
    if not dest_dir and conf.config_file:
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

    _create_module_init(conf.base, dest_dir)
    _create_module_init(conf.base, dest_dir, 'common')

    for mod in conf.modules:
        _copy_module(mod, conf.base, dest_dir)


if __name__ == "__main__":
    main(sys.argv[1:])
