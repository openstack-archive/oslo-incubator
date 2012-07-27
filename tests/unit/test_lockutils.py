# vim: tabstop=4 shiftwidth=4 softtabstop=4

#    Copyright 2011 Justin Santa Barbara
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

import errno
import lockfile
import os
import os.path
import select
import socket
import shutil
import tempfile

from eventlet import greenpool
from eventlet import greenthread

from openstack.common import cfg
from openstack.common import timeutils
from openstack.common import lockutils
from openstack.common import utils
from tests import utils as test_utils


CONF = cfg.CONF


class LockTestCase(test_utils.BaseTestCase):
    def test_synchronized_wrapped_function_metadata(self):
        @lockutils.synchronized('whatever')
        def foo():
            """Bar"""
            pass
        self.assertEquals(foo.__doc__, 'Bar', "Wrapped function's docstring "
                                              "got lost")
        self.assertEquals(foo.__name__, 'foo', "Wrapped function's name "
                                               "got mangled")

    def test_synchronized_internally(self):
        """We can lock across multiple green threads"""
        saved_sem_num = len(lockutils._semaphores)
        seen_threads = list()

        @lockutils.synchronized('testlock2', external=False)
        def f(id):
            for x in range(10):
                seen_threads.append(id)
                greenthread.sleep(0)

        threads = []
        pool = greenpool.GreenPool(10)
        for i in range(10):
            threads.append(pool.spawn(f, i))

        for thread in threads:
            thread.wait()

        self.assertEquals(len(seen_threads), 100)
        # Looking at the seen threads, split it into chunks of 10, and verify
        # that the last 9 match the first in each chunk.
        for i in range(10):
            for j in range(9):
                self.assertEquals(seen_threads[i * 10],
                                  seen_threads[i * 10 + 1 + j])

        self.assertEqual(saved_sem_num, len(lockutils._semaphores),
                         "Semaphore leak detected")

    def test_nested_external_fails(self):
        """We can not nest external syncs"""

        @lockutils.synchronized('testlock1', external=True)
        def outer_lock():

            @lockutils.synchronized('testlock2', external=True)
            def inner_lock():
                pass
            inner_lock()
        try:
            self.assertRaises(lockfile.NotMyLock, outer_lock)
        finally:
            lockutils.cleanup_file_locks()

    def test_synchronized_externally(self):
        """We can lock across multiple processes"""
        rpipe1, wpipe1 = os.pipe()
        rpipe2, wpipe2 = os.pipe()

        @lockutils.synchronized('testlock1', external=True)
        def f(rpipe, wpipe):
            try:
                os.write(wpipe, "foo")
            except OSError, e:
                self.assertEquals(e.errno, errno.EPIPE)
                return

            rfds, _wfds, _efds = select.select([rpipe], [], [], 1)
            self.assertEquals(len(rfds), 0, "The other process, which was"
                                            " supposed to be locked, "
                                            "wrote on its end of the "
                                            "pipe")
            os.close(rpipe)

        pid = os.fork()
        if pid > 0:
            os.close(wpipe1)
            os.close(rpipe2)

            f(rpipe1, wpipe2)
        else:
            os.close(rpipe1)
            os.close(wpipe2)

            f(rpipe2, wpipe1)
            os._exit(0)


class TestLockCleanup(test_utils.BaseTestCase):
    """unit tests for utils.cleanup_file_locks()"""

    def setUp(self):
        super(TestLockCleanup, self).setUp()

        self.pid = os.getpid()
        self.dead_pid = self._get_dead_pid()
        self.tempdir = tempfile.mkdtemp()
        self.config(lock_path=self.tempdir)
        self.lock_name = 'nova-testlock'
        self.lock_file = os.path.join(CONF.lock_path,
                                      self.lock_name + '.lock')
        self.hostname = socket.gethostname()
        print self.pid, self.dead_pid
        try:
            os.unlink(self.lock_file)
        except OSError as (errno, strerror):
            if errno == 2:
                pass

    def tearDown(self):
        shutil.rmtree(self.tempdir)
        super(TestLockCleanup, self).tearDown()

    def _get_dead_pid(self):
        """get a pid for a process that does not exist"""

        candidate_pid = self.pid - 1
        while os.path.exists(os.path.join('/proc', str(candidate_pid))):
            candidate_pid -= 1
            if candidate_pid == 1:
                return 0
        return candidate_pid

    def _get_sentinel_name(self, hostname, pid, thread='MainThread'):
        return os.path.join(CONF.lock_path,
                            '%s-%s.%d' % (hostname, thread, pid))

    def _create_sentinel(self, hostname, pid, thread='MainThread'):
        name = self._get_sentinel_name(hostname, pid, thread)
        open(name, 'wb').close()
        return name

    def test_clean_stale_locks(self):
        """verify locks for dead processes are cleaned up"""

        # create sentinels for two processes, us and a 'dead' one
        # no active lock
        sentinel1 = self._create_sentinel(self.hostname, self.pid)
        sentinel2 = self._create_sentinel(self.hostname, self.dead_pid)

        lockutils.cleanup_file_locks()

        self.assertTrue(os.path.exists(sentinel1))
        self.assertFalse(os.path.exists(self.lock_file))
        self.assertFalse(os.path.exists(sentinel2))

        os.unlink(sentinel1)

    def test_clean_stale_locks_active(self):
        """verify locks for dead processes are cleaned with an active lock """

        # create sentinels for two processes, us and a 'dead' one
        # create an active lock for us
        sentinel1 = self._create_sentinel(self.hostname, self.pid)
        sentinel2 = self._create_sentinel(self.hostname, self.dead_pid)
        os.link(sentinel1, self.lock_file)

        lockutils.cleanup_file_locks()

        self.assertTrue(os.path.exists(sentinel1))
        self.assertTrue(os.path.exists(self.lock_file))
        self.assertFalse(os.path.exists(sentinel2))

        os.unlink(sentinel1)
        os.unlink(self.lock_file)

    def test_clean_stale_with_threads(self):
        """verify locks for multiple threads are cleaned up """

        # create sentinels for four threads in our process, and a 'dead'
        # process.  no lock.
        sentinel1 = self._create_sentinel(self.hostname, self.pid, 'Default-1')
        sentinel2 = self._create_sentinel(self.hostname, self.pid, 'Default-2')
        sentinel3 = self._create_sentinel(self.hostname, self.pid, 'Default-3')
        sentinel4 = self._create_sentinel(self.hostname, self.pid, 'Default-4')
        sentinel5 = self._create_sentinel(self.hostname, self.dead_pid,
                                          'Default-1')

        lockutils.cleanup_file_locks()

        self.assertTrue(os.path.exists(sentinel1))
        self.assertTrue(os.path.exists(sentinel2))
        self.assertTrue(os.path.exists(sentinel3))
        self.assertTrue(os.path.exists(sentinel4))
        self.assertFalse(os.path.exists(self.lock_file))
        self.assertFalse(os.path.exists(sentinel5))

        os.unlink(sentinel1)
        os.unlink(sentinel2)
        os.unlink(sentinel3)
        os.unlink(sentinel4)

    def test_clean_stale_with_threads_active(self):
        """verify locks for multiple threads are cleaned up """

        # create sentinels for four threads in our process, and a 'dead'
        # process
        sentinel1 = self._create_sentinel(self.hostname, self.pid, 'Default-1')
        sentinel2 = self._create_sentinel(self.hostname, self.pid, 'Default-2')
        sentinel3 = self._create_sentinel(self.hostname, self.pid, 'Default-3')
        sentinel4 = self._create_sentinel(self.hostname, self.pid, 'Default-4')
        sentinel5 = self._create_sentinel(self.hostname, self.dead_pid,
                                          'Default-1')

        os.link(sentinel1, self.lock_file)

        lockutils.cleanup_file_locks()

        self.assertTrue(os.path.exists(sentinel1))
        self.assertTrue(os.path.exists(sentinel2))
        self.assertTrue(os.path.exists(sentinel3))
        self.assertTrue(os.path.exists(sentinel4))
        self.assertTrue(os.path.exists(self.lock_file))
        self.assertFalse(os.path.exists(sentinel5))

        os.unlink(sentinel1)
        os.unlink(sentinel2)
        os.unlink(sentinel3)
        os.unlink(sentinel4)
        os.unlink(self.lock_file)

    def test_clean_bogus_lockfiles(self):
        """verify lockfiles are cleaned """

        lock1 = os.path.join(CONF.lock_path, 'nova-testlock1.lock')
        lock2 = os.path.join(CONF.lock_path, 'nova-testlock2.lock')
        lock3 = os.path.join(CONF.lock_path, 'testlock3.lock')

        open(lock1, 'wb').close()
        open(lock2, 'wb').close()
        open(lock3, 'wb').close()

        lockutils.cleanup_file_locks()

        self.assertFalse(os.path.exists(lock1))
        self.assertFalse(os.path.exists(lock2))
        self.assertTrue(os.path.exists(lock3))

        os.unlink(lock3)
