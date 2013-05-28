#!/usr/bin/env python
# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2012 SINA Corporation
# All Rights Reserved.
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
#
# @author: Zhongyue Luo, SINA Corporation.
#
"""Extracts OpenStack config option info from module(s)."""

import imp
import os
import re
import socket
import sys
import textwrap

from oslo.config import cfg

from openstack.common import gettextutils
from openstack.common import importutils

gettextutils.install('oslo')

STROPT = "StrOpt"
BOOLOPT = "BoolOpt"
INTOPT = "IntOpt"
FLOATOPT = "FloatOpt"
LISTOPT = "ListOpt"
MULTISTROPT = "MultiStrOpt"

OPT_TYPES = {
    STROPT: 'string value',
    BOOLOPT: 'boolean value',
    INTOPT: 'integer value',
    FLOATOPT: 'floating point value',
    LISTOPT: 'list value',
    MULTISTROPT: 'multi valued',
}

OPTION_COUNT = 0
OPTION_REGEX = re.compile(r"(%s)" % "|".join([STROPT, BOOLOPT, INTOPT,
                                              FLOATOPT, LISTOPT,
                                              MULTISTROPT]))

PY_EXT = ".py"
BASEDIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
WORDWRAP_WIDTH = 60


def generate(srcfiles):
    mods_by_pkg = dict()
    for filepath in srcfiles:
        pkg_name = filepath.split(os.sep)[1]
        mod_str = '.'.join(['.'.join(filepath.split(os.sep)[:-1]),
                            os.path.basename(filepath).split('.')[0]])
        mods_by_pkg.setdefault(pkg_name, list()).append(mod_str)
    # NOTE(lzyeval): place top level modules before packages
    pkg_names = filter(lambda x: x.endswith(PY_EXT), mods_by_pkg.keys())
    pkg_names.sort()
    ext_names = filter(lambda x: x not in pkg_names, mods_by_pkg.keys())
    ext_names.sort()
    pkg_names.extend(ext_names)

    # opts_by_group is a mapping of group name to an options list
    # The options list is a list of (module, options) tuples
    opts_by_group = {'DEFAULT': []}

    for pkg_name in pkg_names:
        mods = mods_by_pkg.get(pkg_name)
        mods.sort()
        for mod_str in mods:
            if mod_str.endswith('.__init__'):
                mod_str = mod_str[:mod_str.rfind(".")]

            mod_obj = _import_module(mod_str)
            if not mod_obj:
                continue

            for group, opts in _list_opts(mod_obj):
                opts_by_group.setdefault(group, []).append((mod_str, opts))

    print_group_opts('DEFAULT', opts_by_group.pop('DEFAULT', []))
    for group, opts in opts_by_group.items():
        print_group_opts(group, opts)

    print "# Total option count: %d" % OPTION_COUNT


def _import_module(mod_str):
    try:
        if mod_str.startswith('bin.'):
            imp.load_source(mod_str[4:], os.path.join('bin', mod_str[4:]))
            return sys.modules[mod_str[4:]]
        else:
            return importutils.import_module(mod_str)
    except ImportError as ie:
        sys.stderr.write("%s\n" % str(ie))
        return None
    except Exception:
        return None


def _is_in_group(opt, group):
    "Check if opt is in group."
    for key, value in group._opts.items():
        if value['opt'] == opt:
            return True
    return False


def _guess_groups(opt, mod_obj):
    # is it in the DEFAULT group?
    if _is_in_group(opt, cfg.CONF):
        return 'DEFAULT'

    # what other groups is it in?
    for key, value in cfg.CONF.items():
        if isinstance(value, cfg.CONF.GroupAttr):
            if _is_in_group(opt, value._group):
                return value._group.name

    raise RuntimeError(
        "Unable to find group for option %s, "
        "maybe it's defined twice in the same group?"
        % opt.name
    )


def _list_opts(obj):
    def is_opt(o):
        return (isinstance(o, cfg.Opt) and
                not isinstance(o, cfg.SubCommandOpt))

    opts = list()
    for attr_str in dir(obj):
        attr_obj = getattr(obj, attr_str)
        if is_opt(attr_obj):
            opts.append(attr_obj)
        elif (isinstance(attr_obj, list) and
              all(map(lambda x: is_opt(x), attr_obj))):
            opts.extend(attr_obj)

    ret = {}
    for opt in opts:
        ret.setdefault(_guess_groups(opt, obj), []).append(opt)
    return ret.items()


def print_group_opts(group, opts_by_module):
    print "[%s]" % group
    print
    global OPTION_COUNT
    for mod, opts in opts_by_module:
        OPTION_COUNT += len(opts)
        print '#'
        print '# Options defined in %s' % mod
        print '#'
        print
        for opt in opts:
            _print_opt(opt)
        print


def _get_my_ip():
    try:
        csock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        csock.connect(('8.8.8.8', 80))
        (addr, port) = csock.getsockname()
        csock.close()
        return addr
    except socket.error:
        return None


def _sanitize_default(s):
    """Set up a reasonably sensible default for pybasedir, my_ip and host."""
    if s.startswith(BASEDIR):
        return s.replace(BASEDIR, '/usr/lib/python/site-packages')
    elif BASEDIR in s:
        return s.replace(BASEDIR, '')
    elif s == _get_my_ip():
        return '10.0.0.1'
    elif s == socket.getfqdn():
        return 'oslo'
    elif s.strip() != s:
        return '"%s"' % s
    return s


def _print_opt(opt):
    opt_name, opt_default, opt_help = opt.dest, opt.default, opt.help
    if not opt_help:
        sys.stderr.write('WARNING: "%s" is missing help string.\n' % opt_name)
    opt_type = None
    try:
        opt_type = OPTION_REGEX.search(str(type(opt))).group(0)
    except (ValueError, AttributeError), err:
        sys.stderr.write("%s\n" % str(err))
        sys.exit(1)
    opt_help += ' (' + OPT_TYPES[opt_type] + ')'
    print '#', "\n# ".join(textwrap.wrap(opt_help, WORDWRAP_WIDTH))
    try:
        if opt_default is None:
            print '#%s=<None>' % opt_name
        elif opt_type == STROPT:
            assert(isinstance(opt_default, basestring))
            print '#%s=%s' % (opt_name, _sanitize_default(opt_default))
        elif opt_type == BOOLOPT:
            assert(isinstance(opt_default, bool))
            print '#%s=%s' % (opt_name, str(opt_default).lower())
        elif opt_type == INTOPT:
            assert(isinstance(opt_default, int) and
                   not isinstance(opt_default, bool))
            print '#%s=%s' % (opt_name, opt_default)
        elif opt_type == FLOATOPT:
            assert(isinstance(opt_default, float))
            print '#%s=%s' % (opt_name, opt_default)
        elif opt_type == LISTOPT:
            assert(isinstance(opt_default, list))
            print '#%s=%s' % (opt_name, ','.join(opt_default))
        elif opt_type == MULTISTROPT:
            assert(isinstance(opt_default, list))
            if not opt_default:
                opt_default = ['']
            for default in opt_default:
                print '#%s=%s' % (opt_name, default)
        print
    except Exception:
        sys.stderr.write('Error in option "%s"\n' % opt_name)
        sys.exit(1)


def main():
    if len(sys.argv) < 2:
        print "usage: %s [srcfile]...\n" % sys.argv[0]
        sys.exit(0)
    generate(sys.argv[1:])

if __name__ == '__main__':
    main()
