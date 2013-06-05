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

from __future__ import print_function

import functools
import glob
import os
import os.path
import re
import shutil
import sys

from oslo.config import cfg

opts = [
    cfg.ListOpt('modules',
                default=[],
                help='The list of modules to copy from oslo-incubator '
                     '(deprecated in favor of --module)'),
    cfg.MultiStrOpt('module',
                    default=[],
                    help='The list of modules to copy from oslo-incubator'),
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
    cfg.BoolOpt('nodeps',
                default=False,
                help='Discard dependencies of configured modules'),
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

    if 'rpc/' not in dest:
        _replace(dest, 'oslo', base)

    # Restore the imports for modules that are part of the oslo
    # namespace package. We can't just do something like 'oslo\..+'
    # because there are default configuration settings like
    # "oslo.sqlite" that we want to have changed to "nova.sqlite" by
    # the above call.
    for oslo_module in ['config']:
        _replace(dest, base + '.' + oslo_module,
                 'oslo.' + oslo_module)

    _replace(dest,
             '^( *)from openstack.common',
             r'\1from ' + base + '.openstack.common')

    _replace(dest,
             '\'openstack\.common',
             '\'' + base + '.openstack.common')

    _replace(dest,
             '\"openstack\.common',
             '\"' + base + '.openstack.common')

    _replace(dest,
             'possible_topdir, "oslo",$',
             'possible_topdir, "' + base + '",')


def _copy_pyfile(path, base, dest_dir):
    _copy_file(path, _dest_path(path, base, dest_dir), base)


def _copy_module(mod, base, dest_dir):
    """Copies module to project."""
    copy_pyfile = functools.partial(_copy_pyfile,
                                    base=base, dest_dir=dest_dir)

    if '.' in mod:
        path = _mod_to_path('openstack.common')
        for d in mod.split('.')[:-1]:
            path = os.path.join(path, d)
            if os.path.isdir(path):
                copy_pyfile(os.path.join(path, '__init__.py'))

    mod_path = _mod_to_path('openstack.common.%s' % mod)
    mod_file = '%s.py' % mod_path

    if os.path.isfile(mod_file):
        print("Copying %s under the %s module in %s" % (mod, base, dest_dir))
        copy_pyfile(mod_file)
    elif os.path.isdir(mod_path):
        print("Copying %s/ under the %s module in %s" % (mod, base, dest_dir))
        dest = os.path.join(dest_dir, _mod_to_path(base),
                            'openstack', 'common', mod)
        _make_dirs(dest)
        sources = filter(lambda x: x[-3:] == '.py', os.listdir(mod_path))
        for s in sources:
            copy_pyfile(os.path.join(mod_path, s))
    else:
        print("No module %s found in oslo" % mod)

    globs_to_copy = [
        os.path.join('tools', mod + '*'),
        os.path.join('etc', 'oslo', mod + '*.conf'),
        os.path.join('contrib', mod + '*'),
    ]

    for matches in [glob.glob(g) for g in globs_to_copy]:
        for match in matches:
            dest = os.path.join(dest_dir, match.replace('oslo', base))
            print("Copying %s to %s" % (match, dest))
            _copy_file(match, dest, base)


def _remove_unset_modules(dest_dir, base, necessary_modules):
    """Removes modules that are not used by project.

    Modules that are not set in configuration file, are removed from oslo
    already or do not have to be included because of dependencies have
    to be removed.
    """
    dest = os.path.join(dest_dir, _mod_to_path(base))
    base = os.path.join('openstack', 'common')
    path = os.path.join(dest, base)

    req_dirs = []
    req_files = [os.path.join(dest, base, '__init__.py')]

    removed_modules = []

    # form the files and dirs to leave
    # they have to be defined in oslo and in necessary_modules
    for mod in necessary_modules:
        mod_path = os.path.join(base, mod)
        mod_file_path = '%s.py' % mod_path

        if os.path.isfile(mod_file_path):
            req_files.append(os.path.join(dest, mod_file_path))
        elif os.path.isdir(mod_path):
            req_dirs.append(os.path.join(dest, mod_path))

    for root, dirs, files in os.walk(path):
        # current modules in the project
        cur_dirs = [os.path.join(root, _dir) for _dir in dirs]
        cur_files = [os.path.join(root, _file) for _file in files]

        # remove files if needed
        for cur_file in cur_files:
            common_pref = path
            for req_dir in req_dirs:
                pref = os.path.commonprefix([req_dir, cur_file])
                if len(pref) > len(common_pref) + 1:
                    common_pref = pref
            if cur_file not in req_files and common_pref == path:
                os.remove(cur_file)
                removed_modules.append(cur_file)

        # remove directories if needed
        for cur_dir in cur_dirs:
            common_file_pref = path
            for req_file in req_files:
                pref = os.path.commonprefix([cur_dir, req_file])
                if len(pref) > len(common_file_pref) + 1:
                    common_file_pref = pref

            common_pref = path
            for req_dir in req_dirs:
                pref = os.path.commonprefix([cur_dir, req_dir])
                if len(pref) > len(common_pref) + 1:
                    common_pref = pref

            if (cur_dir not in req_dirs and common_pref == path
                    and common_file_pref == path):
                removed_modules.append(cur_dir)

                for _root, _dirs, _files in os.walk(cur_dir, topdown=False):
                    for name in _files:
                        os.remove(os.path.join(_root, name))
                    for name in _dirs:
                        os.rmdir(os.path.join(_root, name))

    if removed_modules:
        print('\nRemoved modules\n    %s' % '\n    '.join(removed_modules))


def _create_module_init(base, dest_dir, *sub_paths):
    """Create module __init__ files."""
    init_path = _dest_path('openstack', base, dest_dir)

    if sub_paths:
        init_path = os.path.join(init_path, *sub_paths)

    init_path = os.path.join(init_path, '__init__.py')

    if not os.path.exists(init_path):
        _make_dirs(init_path)
        open(init_path, 'w').close()


def _find_import_modules(srcfile):
    oslo_import_pattern = re.compile(r"\s*from\sopenstack\.common"
                                     "(\simport\s|\.)(\w+)($|.+)")
    with open(srcfile, 'r') as f:
        for line in f:
            result = oslo_import_pattern.match(line)
            if result:
                yield result.group(2)


def _build_dependency_tree():
    dep_tree = {}
    base_path = os.path.join('openstack', 'common')
    for dirpath, _, filenames in os.walk(base_path):
        for filename in [x for x in filenames if x.endswith('.py')]:
            if dirpath == base_path:
                mod_name = filename.split('.')[0]
            else:
                mod_name = dirpath.split(os.sep)[2]
            if mod_name == '__init__':
                continue
            filepath = os.path.join(dirpath, filename)
            dep_list = dep_tree.setdefault(mod_name, [])
            dep_list.extend([x for x in _find_import_modules(filepath)
                             if x != mod_name and x not in dep_list])
    return dep_tree


def _dfs_dependency_tree(dep_tree, mod_name, mod_list=[]):
    mod_list.append(mod_name)
    for mod in dep_tree.get(mod_name, []):
        if mod not in mod_list:
            mod_list = _dfs_dependency_tree(dep_tree, mod, mod_list)
    return mod_list


def _complete_module_list(mod_list, nodeps):
    if nodeps:
        return mod_list
    addons = []
    dep_tree = _build_dependency_tree()
    for mod in mod_list:
        addons.extend([x for x in _dfs_dependency_tree(dep_tree, mod)
                       if x not in mod_list and x not in addons])
    mod_list.extend(addons)
    return mod_list


def main(argv):
    conf = _parse_args(argv)

    dest_dir = conf.dest_dir
    if not dest_dir and conf.config_file:
        dest_dir = os.path.dirname(conf.config_file[-1])

    if not dest_dir or not os.path.isdir(dest_dir):
        print("A valid destination dir is required", file=sys.stderr)
        sys.exit(1)

    if not conf.module and not conf.modules:
        print("A list of modules to copy is required", file=sys.stderr)
        sys.exit(1)

    if not conf.base:
        print("A destination base module is required", file=sys.stderr)
        sys.exit(1)

    _create_module_init(conf.base, dest_dir)
    _create_module_init(conf.base, dest_dir, 'common')

    modules = _complete_module_list(conf.module + conf.modules, conf.nodeps)
    for mod in modules:
        _copy_module(mod, conf.base, dest_dir)

    _remove_unset_modules(dest_dir, conf.base, modules)


if __name__ == "__main__":
    main(sys.argv[1:])
