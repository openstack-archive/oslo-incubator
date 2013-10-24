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

import fcntl
import multiprocessing
import os
import shutil
import sys
import tempfile
import threading

import eventlet
from eventlet import greenpool
from eventlet import greenthread
from eventlet import semaphore
from oslo.config import cfg

from openstack.common.fixture import config
from openstack.common.fixture import lockutils as fixtures
from openstack.common import lockutils
from openstack.common import test


class TestFileLocks(test.BaseTestCase):

    def test_concurrent_green_lock_succeeds(self):
        """Verify spawn_n greenthreads with two locks run concurrently."""
        tmpdir = tempfile.mkdtemp()
        try:
            self.completed = False

            def locka(wait):
                a = lockutils.InterProcessLock(os.path.join(tmpdir, 'a'))
                with a:
                    wait.wait()
                self.completed = True

            def lockb(wait):
                b = lockutils.InterProcessLock(os.path.join(tmpdir, 'b'))
                with b:
                    wait.wait()

            wait1 = eventlet.event.Event()
            wait2 = eventlet.event.Event()
            pool = greenpool.GreenPool()
            pool.spawn_n(locka, wait1)
            pool.spawn_n(lockb, wait2)
            wait2.send()
            eventlet.sleep(0)
            wait1.send()
            pool.waitall()

            self.assertTrue(self.completed)

        finally:
            if os.path.exists(tmpdir):
                shutil.rmtree(tmpdir)


class LockTestCase(test.BaseTestCase):

    def setUp(self):
        super(LockTestCase, self).setUp()
        self.config = self.useFixture(config.Config()).config

    def test_synchronized_wrapped_function_metadata(self):
        @lockutils.synchronized('whatever', 'test-')
        def foo():
            """Bar"""
            pass

        self.assertEqual(foo.__doc__, 'Bar', "Wrapped function's docstring "
                                             "got lost")
        self.assertEqual(foo.__name__, 'foo', "Wrapped function's name "
                                              "got mangled")

    def test_lock_internally(self):
        """We can lock across multiple green threads."""
        saved_sem_num = len(lockutils._semaphores)
        seen_threads = list()

        def f(_id):
            with lockutils.lock('testlock2', 'test-', external=False):
                for x in range(10):
                    seen_threads.append(_id)
                    greenthread.sleep(0)

        threads = []
        pool = greenpool.GreenPool(10)
        for i in range(10):
            threads.append(pool.spawn(f, i))

        for thread in threads:
            thread.wait()

        self.assertEqual(len(seen_threads), 100)
        # Looking at the seen threads, split it into chunks of 10, and verify
        # that the last 9 match the first in each chunk.
        for i in range(10):
            for j in range(9):
                self.assertEqual(seen_threads[i * 10],
                                 seen_threads[i * 10 + 1 + j])

        self.assertEqual(saved_sem_num, len(lockutils._semaphores),
                         "Semaphore leak detected")

    def test_nested_synchronized_external_works(self):
        """We can nest external syncs."""
        tempdir = tempfile.mkdtemp()
        try:
            self.config(lock_path=tempdir)
            sentinel = object()

            @lockutils.synchronized('testlock1', 'test-', external=True)
            def outer_lock():

                @lockutils.synchronized('testlock2', 'test-', external=True)
                def inner_lock():
                    return sentinel
                return inner_lock()

            self.assertEqual(sentinel, outer_lock())

        finally:
            if os.path.exists(tempdir):
                shutil.rmtree(tempdir)

    def _do_test_lock_externally(self):
        """We can lock across multiple processes."""

        def lock_files(handles_dir):

            with lockutils.lock('external', 'test-', external=True):
                # Open some files we can use for locking
                handles = []
                for n in range(50):
                    path = os.path.join(handles_dir, ('file-%s' % n))
                    handles.append(open(path, 'w'))

                # Loop over all the handles and try locking the file
                # without blocking, keep a count of how many files we
                # were able to lock and then unlock. If the lock fails
                # we get an IOError and bail out with bad exit code
                count = 0
                for handle in handles:
                    try:
                        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        count += 1
                        fcntl.flock(handle, fcntl.LOCK_UN)
                    except IOError:
                        os._exit(2)
                    finally:
                        handle.close()

                # Check if we were able to open all files
                self.assertEqual(50, count)

        handles_dir = tempfile.mkdtemp()
        try:
            children = []
            for n in range(50):
                pid = os.fork()
                if pid:
                    children.append(pid)
                else:
                    try:
                        lock_files(handles_dir)
                    finally:
                        os._exit(0)

            for i, child in enumerate(children):
                (pid, status) = os.waitpid(child, 0)
                if pid:
                    self.assertEqual(0, status)
        finally:
            if os.path.exists(handles_dir):
                shutil.rmtree(handles_dir, ignore_errors=True)

    def test_lock_externally(self):
        lock_dir = tempfile.mkdtemp()
        self.config(lock_path=lock_dir)

        try:
            self._do_test_lock_externally()
        finally:
            if os.path.exists(lock_dir):
                shutil.rmtree(lock_dir, ignore_errors=True)

    def test_lock_externally_lock_dir_not_exist(self):
        lock_dir = tempfile.mkdtemp()
        os.rmdir(lock_dir)
        self.config(lock_path=lock_dir)

        try:
            self._do_test_lock_externally()
        finally:
            if os.path.exists(lock_dir):
                shutil.rmtree(lock_dir, ignore_errors=True)

    def test_synchronized_with_prefix(self):
        lock_name = 'mylock'
        lock_pfix = 'mypfix-'

        foo = lockutils.synchronized_with_prefix(lock_pfix)

        @foo(lock_name, external=True)
        def bar(dirpath, pfix, name):
            filepath = os.path.join(dirpath, '%s%s' % (pfix, name))
            return os.path.isfile(filepath)

        lock_dir = tempfile.mkdtemp()
        self.config(lock_path=lock_dir)

        self.assertTrue(bar(lock_dir, lock_pfix, lock_name))

    def test_synchronized_without_prefix(self):
        lock_dir = tempfile.mkdtemp()

        @lockutils.synchronized('lock', external=True, lock_path=lock_dir)
        def test_without_prefix():
            path = os.path.join(lock_dir, "lock")
            self.assertTrue(os.path.exists(path))

        try:
            test_without_prefix()
        finally:
            if os.path.exists(lock_dir):
                shutil.rmtree(lock_dir, ignore_errors=True)

    def test_synchronized_prefix_without_hypen(self):
        lock_dir = tempfile.mkdtemp()

        @lockutils.synchronized('lock', 'hypen', True, lock_dir)
        def test_without_hypen():
            path = os.path.join(lock_dir, "hypen-lock")
            self.assertTrue(os.path.exists(path))

        try:
            test_without_hypen()
        finally:
            if os.path.exists(lock_dir):
                shutil.rmtree(lock_dir, ignore_errors=True)

    def test_contextlock(self):
        lock_dir = tempfile.mkdtemp()

        try:
            # Note(flaper87): Lock is not external, which means
            # a semaphore will be yielded
            with lockutils.lock("test") as sem:
                semaphores = (semaphore.Semaphore, threading._Semaphore)
                self.assertTrue(isinstance(sem, semaphores))

                # NOTE(flaper87): Lock is external so an InterProcessLock
                # will be yielded.
                with lockutils.lock("test2", external=True,
                                    lock_path=lock_dir):
                    path = os.path.join(lock_dir, "test2")
                    self.assertTrue(os.path.exists(path))

                with lockutils.lock("test1",
                                    external=True,
                                    lock_path=lock_dir) as lock1:
                    self.assertTrue(isinstance(lock1,
                                               lockutils.InterProcessLock))
        finally:
            if os.path.exists(lock_dir):
                shutil.rmtree(lock_dir, ignore_errors=True)

    def test_contextlock_unlocks(self):
        lock_dir = tempfile.mkdtemp()

        sem = None

        try:
            with lockutils.lock("test") as sem:
                semaphores = (semaphore.Semaphore, threading._Semaphore)
                self.assertTrue(isinstance(sem, semaphores))

                with lockutils.lock("test2", external=True,
                                    lock_path=lock_dir):
                    path = os.path.join(lock_dir, "test2")
                    self.assertTrue(os.path.exists(path))

                # NOTE(flaper87): Lock should be free
                with lockutils.lock("test2", external=True,
                                    lock_path=lock_dir):
                    path = os.path.join(lock_dir, "test2")
                    self.assertTrue(os.path.exists(path))

            # NOTE(flaper87): Lock should be free
            # but semaphore should already exist.
            with lockutils.lock("test") as sem2:
                self.assertEqual(sem, sem2)
        finally:
            if os.path.exists(lock_dir):
                shutil.rmtree(lock_dir, ignore_errors=True)

    def test_synchronized_externally_without_lock_path(self):
        self.config(lock_path=None)

        @lockutils.synchronized('external', 'test-', external=True)
        def foo():
            pass

        self.assertRaises(cfg.RequiredOptError, foo)


class LockutilsModuleTestCase(test.BaseTestCase):

    def setUp(self):
        super(LockutilsModuleTestCase, self).setUp()
        self.old_env = os.environ.get('OSLO_LOCK_PATH')

    def tearDown(self):
        if self.old_env is None:
            del os.environ['OSLO_LOCK_PATH']
        else:
            os.environ['OSLO_LOCK_PATH'] = self.old_env
        super(LockutilsModuleTestCase, self).tearDown()

    def _lock_path_conf_test(self, lock_dir):
        cfg.CONF.unregister_opts(lockutils.util_opts)
        lockutils_ = reload(lockutils)
        with lockutils_.lock('test-lock', external=True):
            if not os.path.exists(lock_dir):
                os._exit(2)
            if not os.path.exists(os.path.join(lock_dir, 'test-lock')):
                os._exit(3)

    def test_lock_path_from_env(self):
        lock_dir = tempfile.mkdtemp()
        os.environ['OSLO_LOCK_PATH'] = lock_dir
        try:
            p = multiprocessing.Process(target=self._lock_path_conf_test,
                                        args=(lock_dir,))
            p.start()
            p.join()
            if p.exitcode == 2:
                self.fail("lock_path directory %s does not exist" % lock_dir)
            elif p.exitcode == 3:
                self.fail("lock file hasn't been created in expected location")
            else:
                self.assertEqual(p.exitcode, 0,
                                 "Subprocess failed with code %s" % p.exitcode)
        finally:
            if os.path.exists(lock_dir):
                shutil.rmtree(lock_dir, ignore_errors=True)

    def test_main(self):
        script = '\n'.join([
            'import os',
            'lock_path = os.environ.get("OSLO_LOCK_PATH")',
            'assert lock_path is not None',
            'assert os.path.isdir(lock_path)',
        ])
        argv = ['', sys.executable, '-c', script]
        retval = lockutils.main(argv)
        self.assertEqual(retval, 0, "Bad OSLO_LOCK_PATH has been set")


class TestLockFixture(test.BaseTestCase):

    def setUp(self):
        super(TestLockFixture, self).setUp()
        self.config = self.useFixture(config.Config()).config
        self.tempdir = tempfile.mkdtemp()

    def _check_in_lock(self):
        # Check that the lock file exists during teardown
        lock_path = os.path.join(self.tempdir, 'test-lock')
        self.assertTrue(os.path.exists(lock_path))

    def tearDown(self):
        self._check_in_lock()
        super(TestLockFixture, self).tearDown()

    def test_lock_fixture(self):
        # Setup lock fixture to test that teardown is inside the lock
        self.config(lock_path=self.tempdir)
        self.useFixture(fixtures.LockFixture('test-lock'))
