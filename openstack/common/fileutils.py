# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2010 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
# Copyright 2011 Justin Santa Barbara
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

"""File helper functions."""

import errno
import os
import re
import socket

import lockfile

from openstack.common import cfg
from openstack.common import log as logging


LOG = logging.getLogger(__name__)
CONF = cfg.CONF
CONF.register_opt(
        cfg.BoolOpt('disable_process_locking',
                    default=False,
                    help='Whether to disable inter-process locks'))
CONF.register_opt(
        cfg.StrOpt('lock_path',
                   default='$pybasedir',
                   help='Directory to use for lock files'))


def cleanup_file_locks():
    """clean up stale locks left behind by process failures

    The lockfile module, used by @synchronized, can leave stale lockfiles
    behind after process failure. These locks can cause process hangs
    at startup, when a process deadlocks on a lock which will never
    be unlocked.

    Intended to be called at service startup.

    """

    # NOTE(mikeyp) this routine incorporates some internal knowledge
    #              from the lockfile module, and this logic really
    #              should be part of that module.
    #
    # cleanup logic:
    # 1) look for the lockfile modules's 'sentinel' files, of the form
    #    hostname.[thread-.*]-pid, extract the pid.
    #    if pid doesn't match a running process, delete the file since
    #    it's from a dead process.
    # 2) check for the actual lockfiles. if lockfile exists with linkcount
    #    of 1, it's bogus, so delete it. A link count >= 2 indicates that
    #    there are probably sentinels still linked to it from active
    #    processes.  This check isn't perfect, but there is no way to
    #    reliably tell which sentinels refer to which lock in the
    #    lockfile implementation.

    if CONF.disable_process_locking:
        return

    hostname = socket.gethostname()
    sentinel_re = hostname + r'-.*\.(\d+$)'
    lockfile_re = r'nova-.*\.lock'
    files = os.listdir(CONF.lock_path)

    # cleanup sentinels
    for filename in files:
        match = re.match(sentinel_re, filename)
        if match is None:
            continue
        pid = match.group(1)
        LOG.debug(_('Found sentinel %(filename)s for pid %(pid)s'),
                  {'filename': filename, 'pid': pid})
        try:
            os.kill(int(pid), 0)
        except OSError, e:
            # PID wasn't found
            delete_if_exists(os.path.join(CONF.lock_path, filename))
            LOG.debug(_('Cleaned sentinel %(filename)s for pid %(pid)s'),
                      {'filename': filename, 'pid': pid})

    # cleanup lock files
    for filename in files:
        match = re.match(lockfile_re, filename)
        if match is None:
            continue
        try:
            stat_info = os.stat(os.path.join(CONF.lock_path, filename))
        except OSError as e:
            if e.errno == errno.ENOENT:
                continue
            else:
                raise
        LOG.debug(_('Found lockfile %(file)s with link count %(count)d'),
                  {'file': filename, 'count': stat_info.st_nlink})
        if stat_info.st_nlink == 1:
            delete_if_exists(os.path.join(CONF.lock_path, filename))
            LOG.debug(_('Cleaned lockfile %(file)s with link count %(count)d'),
                      {'file': filename, 'count': stat_info.st_nlink})


def delete_if_exists(pathname):
    """delete a file, but ignore file not found error"""

    try:
        os.unlink(pathname)
    except OSError as e:
        if e.errno == errno.ENOENT:
            return
        else:
            raise
