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
import functools
import os
import re
import socket
import threading

from eventlet import corolocal
from eventlet import semaphore
import lockfile

from openstack.common import cfg
from openstack.common import log as logging
from openstack.common import utils


LOG = logging.getLogger(__name__)
CONF = cfg.CONF
CONF.register_opt(
    cfg.StrOpt('pybasedir',
               default=os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                    '../')),
               help='Directory where the nova python module is installed'))
CONF.register_opt(
    cfg.BoolOpt('disable_process_locking',
                default=False,
                help='Whether to disable inter-process locks'))
CONF.register_opt(
    cfg.StrOpt('lock_path',
               default='$pybasedir',
               help='Directory to use for lock files'))


class GreenLockFile(lockfile.FileLock):
    """Implementation of lockfile that allows for a lock per greenthread.

    Simply implements lockfile:LockBase init with an addiontall suffix
    on the unique name of the greenthread identifier
    """
    def __init__(self, path, threaded=True):
        self.path = path
        self.lock_file = os.path.abspath(path) + ".lock"
        self.hostname = socket.gethostname()
        self.pid = os.getpid()
        if threaded:
            t = threading.current_thread()
            # Thread objects in Python 2.4 and earlier do not have ident
            # attrs.  Worm around that.
            ident = getattr(t, "ident", hash(t)) or hash(t)
            gident = corolocal.get_ident()
            self.tname = "-%x-%x" % (ident & 0xffffffff, gident & 0xffffffff)
        else:
            self.tname = ""
        dirname = os.path.dirname(self.lock_file)
        self.unique_name = os.path.join(dirname,
                                        "%s%s.%s" % (self.hostname,
                                                     self.tname,
                                                     self.pid))


_semaphores = {}


def synchronized(name, external=False):
    """Synchronization decorator.

    Decorating a method like so::

        @synchronized('mylock')
        def foo(self, *args):
           ...

    ensures that only one thread will execute the bar method at a time.

    Different methods can share the same lock::

        @synchronized('mylock')
        def foo(self, *args):
           ...

        @synchronized('mylock')
        def bar(self, *args):
           ...

    This way only one of either foo or bar can be executing at a time.

    The external keyword argument denotes whether this lock should work across
    multiple processes. This means that if two different workers both run a
    a method decorated with @synchronized('mylock', external=True), only one
    of them will execute at a time.

    Important limitation: you can only have one external lock running per
    thread at a time. For example the following will fail:

        @lockutils.synchronized('testlock1', external=True)
        def outer_lock():

            @lockutils.synchronized('testlock2', external=True)
            def inner_lock():
                pass
            inner_lock()

        outer_lock()

    """

    def wrap(f):
        @functools.wraps(f)
        def inner(*args, **kwargs):
            # NOTE(soren): If we ever go natively threaded, this will be racy.
            #              See http://stackoverflow.com/questions/5390569/dyn
            #              amically-allocating-and-destroying-mutexes
            if name not in _semaphores:
                _semaphores[name] = semaphore.Semaphore()
            sem = _semaphores[name]
            LOG.debug(_('Attempting to grab semaphore "%(lock)s" for method '
                        '"%(method)s"...'), {'lock': name,
                                             'method': f.__name__})
            with sem:
                LOG.debug(_('Got semaphore "%(lock)s" for method '
                            '"%(method)s"...'), {'lock': name,
                                                 'method': f.__name__})
                if external and not CONF.disable_process_locking:
                    LOG.debug(_('Attempting to grab file lock "%(lock)s" for '
                                'method "%(method)s"...'),
                              {'lock': name, 'method': f.__name__})
                    lock_file_path = os.path.join(CONF.lock_path,
                                                  'nova-%s' % name)
                    lock = GreenLockFile(lock_file_path)
                    with lock:
                        LOG.debug(_('Got file lock "%(lock)s" for '
                                    'method "%(method)s"...'),
                                  {'lock': name, 'method': f.__name__})
                        retval = f(*args, **kwargs)
                else:
                    retval = f(*args, **kwargs)

            # If no-one else is waiting for it, delete it.
            # See note about possible raciness above.
            if not sem.balance < 1:
                del _semaphores[name]

            return retval
        return inner
    return wrap


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
            utils.delete_if_exists(os.path.join(CONF.lock_path, filename))
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
            utils.delete_if_exists(os.path.join(CONF.lock_path, filename))
            LOG.debug(_('Cleaned lockfile %(file)s with link count %(count)d'),
                      {'file': filename, 'count': stat_info.st_nlink})
