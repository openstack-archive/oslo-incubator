# Copyright 2010 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
# Copyright 2011 Justin Santa Barbara
# Copyright (c) 2012 NTT DOCOMO, INC.
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

"""Utilities and helper functions."""

import errno
import logging
import os

from oslo_concurrency import processutils
from oslo_config import cfg
from oslo_utils import excutils

from openstack.common._i18n import _LE
from openstack.common._i18n import _LW
from openstack.common.libironic import exception

utils_opts = [
    cfg.StrOpt('rootwrap_config',
               default="/etc/ironic/rootwrap.conf",
               help='Path to the rootwrap configuration file to use for '
                    'running commands as root.'),
    cfg.StrOpt('rootwrap_helper_cmd',
               default="sudo ironic-root-wrap",
               help='Path to the rootwrap configuration file to use for '
                    'running commands as root.'),
    cfg.StrOpt('tempdir',
               help='Explicitly specify the temporary working directory.'),
]

CONF = cfg.CONF
CONF.register_opts(utils_opts)

LOG = logging.getLogger(__name__)


def _get_root_helper():
    return '%s %s' % (CONF.rootwrap_helper_cmd, CONF.rootwrap_config)


def execute(*cmd, **kwargs):
    """Convenience wrapper around oslo's execute() method.

    :param cmd: Passed to processutils.execute.
    :param use_standard_locale: True | False. Defaults to False. If set to
                                True, execute command with standard locale
                                added to environment variables.
    :returns: (stdout, stderr) from process execution
    :raises: UnknownArgumentError
    :raises: ProcessExecutionError
    """

    use_standard_locale = kwargs.pop('use_standard_locale', False)
    if use_standard_locale:
        env = kwargs.pop('env_variables', os.environ.copy())
        env['LC_ALL'] = 'C'
        kwargs['env_variables'] = env
    if kwargs.get('run_as_root') and 'root_helper' not in kwargs:
        kwargs['root_helper'] = _get_root_helper()
    result = processutils.execute(*cmd, **kwargs)
    LOG.debug('Execution completed, command line is "%s"',
              ' '.join(map(str, cmd)))
    LOG.debug('Command stdout is: "%s"' % result[0])
    LOG.debug('Command stderr is: "%s"' % result[1])
    return result


def mkfs(fs, path, label=None):
    """Format a file or block device

    :param fs: Filesystem type (examples include 'swap', 'ext3', 'ext4'
               'btrfs', etc.)
    :param path: Path to file or block device to format
    :param label: Volume label to use
    """
    if fs == 'swap':
        args = ['mkswap']
    else:
        args = ['mkfs', '-t', fs]
    # add -F to force no interactive execute on non-block device.
    if fs in ('ext3', 'ext4'):
        args.extend(['-F'])
    if label:
        if fs in ('msdos', 'vfat'):
            label_opt = '-n'
        else:
            label_opt = '-L'
        args.extend([label_opt, label])
    args.append(path)
    try:
        execute(*args, run_as_root=True, use_standard_locale=True)
    except processutils.ProcessExecutionError as e:
        with excutils.save_and_reraise_exception() as ctx:
            if os.strerror(errno.ENOENT) in e.stderr:
                ctx.reraise = False
                LOG.exception(_LE('Failed to make file system. '
                                  'File system %s is not supported.'), fs)
                raise exception.FileSystemNotSupported(fs=fs)
            else:
                LOG.exception(_LE('Failed to create a file system '
                                  'in %(path)s. Error: %(error)s'),
                              {'path': path, 'error': e})


def unlink_without_raise(path):
    try:
        os.unlink(path)
    except OSError as e:
        if e.errno == errno.ENOENT:
            return
        else:
            LOG.warn(_LW("Failed to unlink %(path)s, error: %(e)s"),
                     {'path': path, 'e': e})


def dd(src, dst, *args):
    """Execute dd from src to dst.

    :param src: the input file for dd command.
    :param dst: the output file for dd command.
    :param args: a tuple containing the arguments to be
        passed to dd command.
    :raises: processutils.ProcessExecutionError if it failed
        to run the process.
    """
    LOG.debug("Starting dd process.")
    execute('dd', 'if=%s' % src, 'of=%s' % dst, *args,
            run_as_root=True, check_exit_code=[0])


def is_http_url(url):
    url = url.lower()
    return url.startswith('http://') or url.startswith('https://')
