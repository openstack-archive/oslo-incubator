# Copyright 2011 OpenStack Foundation.
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

import contextlib
import errno
import fcntl
import functools
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import weakref

from oslo.config import cfg

from openstack.common import fileutils
from openstack.common.gettextutils import _, _LE, _LI
from openstack.common import log as logging


LOG = logging.getLogger(__name__)


util_opts = [
    cfg.BoolOpt('disable_process_locking', default=False,
                help='Enables or disables inter-process locks.'),
    cfg.StrOpt('lock_path',
               default=os.environ.get("OSLO_LOCK_PATH"),
               help='Directory to use for lock files.')
]


CONF = cfg.CONF
CONF.register_opts(util_opts)


def set_defaults(lock_path):
    cfg.set_defaults(util_opts, lock_path=lock_path)


class _FileLock(object):
    """Lock implementation which allows multiple locks, working around
    issues like bugs.debian.org/cgi-bin/bugreport.cgi?bug=632857 and does
    not require any cleanup. Since the lock is always held on a file
    descriptor rather than outside of the process, the lock gets dropped
    automatically if the process crashes, even if __exit__ is not executed.

    There are no guarantees regarding usage by multiple green threads in a
    single process here. This lock works only between processes. Exclusive
    access between local threads should be achieved using the semaphores
    in the @synchronized decorator.

    Note these locks are released when the descriptor is closed, so it's not
    safe to close the file descriptor while another green thread holds the
    lock. Just opening and closing the lock file can break synchronisation,
    so lock files must be accessed only using this abstraction.
    """

    def __init__(self, name):
        self.lockfile = None
        self.fname = name

    def acquire(self):
        basedir = os.path.dirname(self.fname)

        if not os.path.exists(basedir):
            fileutils.ensure_tree(basedir)
            LOG.info(_LI('Created lock path: %s'), basedir)

        self.lockfile = open(self.fname, 'w')

        while True:
            try:
                # Using non-blocking locks since green threads are not
                # patched to deal with blocking locking calls.
                # Also upon reading the MSDN docs for locking(), it seems
                # to have a laughable 10 attempts "blocking" mechanism.
                self.trylock()
                LOG.debug('Got file lock "%s"', self.fname)
                return True
            except IOError as e:
                if e.errno in (errno.EACCES, errno.EAGAIN):
                    # external locks synchronise things like iptables
                    # updates - give it some time to prevent busy spinning
                    time.sleep(0.01)
                else:
                    raise threading.ThreadError(_("Unable to acquire lock on"
                                                  " `%(filename)s` due to"
                                                  " %(exception)s") %
                                                {
                                                    'filename': self.fname,
                                                    'exception': e,
                                                })

    def __enter__(self):
        self.acquire()
        return self

    def release(self):
        try:
            self.unlock()
            self.lockfile.close()
            LOG.debug('Released file lock "%s"', self.fname)
        except IOError:
            LOG.exception(_LE("Could not release the acquired lock `%s`"),
                          self.fname)

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()

    def exists(self):
        return os.path.exists(self.fname)

    def trylock(self):
        raise NotImplementedError()

    def unlock(self):
        raise NotImplementedError()


class _WindowsLock(_FileLock):
    def trylock(self):
        msvcrt.locking(self.lockfile.fileno(), msvcrt.LK_NBLCK, 1)

    def unlock(self):
        msvcrt.locking(self.lockfile.fileno(), msvcrt.LK_UNLCK, 1)


class _FcntlLock(_FileLock):
    def trylock(self):
        fcntl.lockf(self.lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def unlock(self):
        fcntl.lockf(self.lockfile, fcntl.LOCK_UN)


class _PosixLock(object):
    def __init__(self, name):
        # Hash the name because it's not valid to have POSIX semaphore
        # names with things like / in them. Then use base64 to encode
        # the digest() instead taking the hexdigest() because the
        # result is shorter and most systems can't have shm sempahore
        # names longer than 31 characters.
        h = hashlib.sha1()
        h.update(name.encode('ascii'))
        self.name = str((b'/' + base64.urlsafe_b64encode(
            h.digest())).decode('ascii'))

    def acquire(self, timeout=None):
        self.semaphore = posix_ipc.Semaphore(self.name,
                                             flags=posix_ipc.O_CREAT,
                                             initial_value=1)
        self.semaphore.acquire(timeout)
        return self

    def __enter__(self):
        self.acquire()
        return self

    def release(self):
        self.semaphore.release()
        self.semaphore.close()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()

    def exists(self):
        try:
            semaphore = posix_ipc.Semaphore(self.name)
        except posix_ipc.ExistentialError:
            return False
        else:
            semaphore.close()
        return True


if os.name == 'nt':
    import msvcrt
    InterProcessLock = _WindowsLock
    FileLock = _WindowsLock
else:
    import base64
    import hashlib

    import posix_ipc
    InterProcessLock = _PosixLock
    FileLock = _FcntlLock

_semaphores = weakref.WeakValueDictionary()
_semaphores_lock = threading.Lock()


def _get_lock_path(name, lock_file_prefix, lock_path=None):
    # NOTE(mikal): the lock name cannot contain directory
    # separators
    name = name.replace(os.sep, '_')
    if lock_file_prefix:
        sep = '' if lock_file_prefix.endswith('-') else '-'
        name = '%s%s%s' % (lock_file_prefix, sep, name)

    local_lock_path = lock_path or CONF.lock_path

    if not local_lock_path:
        # NOTE(bnemec): Create a fake lock path for posix locks so we don't
        # unnecessarily raise the RequiredOptError below.
        if InterProcessLock is not _PosixLock:
            raise cfg.RequiredOptError('lock_path')
        local_lock_path = 'posixlock:/'

    return os.path.join(local_lock_path, name)


def external_lock(name, lock_file_prefix=None, lock_path=None):
    LOG.debug('Attempting to grab external lock "%(lock)s"',
              {'lock': name})

    lock_file_path = _get_lock_path(name, lock_file_prefix, lock_path)

    # NOTE(bnemec): If an explicit lock_path was passed to us then it
    # means the caller is relying on file-based locking behavior, so
    # we can't use posix locks for those calls.
    if lock_path:
        return FileLock(lock_file_path)
    return InterProcessLock(lock_file_path)


def remove_external_lock_file(name, lock_file_prefix=None):
    """Remove an external lock file when it's not used anymore
    This will be helpful when we have a lot of lock files
    """
    with internal_lock(name):
        lock_file_path = _get_lock_path(name, lock_file_prefix)
        try:
            os.remove(lock_file_path)
        except OSError:
            LOG.info(_LI('Failed to remove file %(file)s'),
                     {'file': lock_file_path})


def internal_lock(name):
    with _semaphores_lock:
        try:
            sem = _semaphores[name]
        except KeyError:
            sem = threading.Semaphore()
            _semaphores[name] = sem

    LOG.debug('Got semaphore "%(lock)s"', {'lock': name})
    return sem


@contextlib.contextmanager
def lock(name, lock_file_prefix=None, external=False, lock_path=None):
    """Context based lock

    This function yields a `threading.Semaphore` instance (if we don't use
    eventlet.monkey_patch(), else `semaphore.Semaphore`) unless external is
    True, in which case, it'll yield an InterProcessLock instance.

    :param lock_file_prefix: The lock_file_prefix argument is used to provide
      lock files on disk with a meaningful prefix.

    :param external: The external keyword argument denotes whether this lock
      should work across multiple processes. This means that if two different
      workers both run a method decorated with @synchronized('mylock',
      external=True), only one of them will execute at a time.
    """
    int_lock = internal_lock(name)
    with int_lock:
        if external and not CONF.disable_process_locking:
            ext_lock = external_lock(name, lock_file_prefix, lock_path)
            with ext_lock:
                yield ext_lock
        else:
            yield int_lock
    LOG.debug('Released semaphore "%(lock)s"', {'lock': name})


def synchronized(name, lock_file_prefix=None, external=False, lock_path=None):
    """Synchronization decorator.

    Decorating a method like so::

        @synchronized('mylock')
        def foo(self, *args):
           ...

    ensures that only one thread will execute the foo method at a time.

    Different methods can share the same lock::

        @synchronized('mylock')
        def foo(self, *args):
           ...

        @synchronized('mylock')
        def bar(self, *args):
           ...

    This way only one of either foo or bar can be executing at a time.
    """

    def wrap(f):
        @functools.wraps(f)
        def inner(*args, **kwargs):
            try:
                with lock(name, lock_file_prefix, external, lock_path):
                    LOG.debug('Got semaphore / lock "%(function)s"',
                              {'function': f.__name__})
                    return f(*args, **kwargs)
            finally:
                LOG.debug('Semaphore / lock released "%(function)s"',
                          {'function': f.__name__})
        return inner
    return wrap


def synchronized_with_prefix(lock_file_prefix):
    """Partial object generator for the synchronization decorator.

    Redefine @synchronized in each project like so::

        (in nova/utils.py)
        from nova.openstack.common import lockutils

        synchronized = lockutils.synchronized_with_prefix('nova-')


        (in nova/foo.py)
        from nova import utils

        @utils.synchronized('mylock')
        def bar(self, *args):
           ...

    The lock_file_prefix argument is used to provide lock files on disk with a
    meaningful prefix.
    """

    return functools.partial(synchronized, lock_file_prefix=lock_file_prefix)


def main(argv):
    """Create a dir for locks and pass it to command from arguments

    If you run this:
    python -m openstack.common.lockutils python setup.py testr <etc>

    a temporary directory will be created for all your locks and passed to all
    your tests in an environment variable. The temporary dir will be deleted
    afterwards and the return value will be preserved.
    """

    lock_dir = tempfile.mkdtemp()
    os.environ["OSLO_LOCK_PATH"] = lock_dir
    try:
        ret_val = subprocess.call(argv[1:])
    finally:
        shutil.rmtree(lock_dir, ignore_errors=True)
    return ret_val


if __name__ == '__main__':
    sys.exit(main(sys.argv))
