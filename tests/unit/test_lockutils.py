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
import fcntl
import os
import select
import shutil
import tempfile
import time
import unittest

import eventlet
from eventlet import greenpool
from eventlet import greenthread

from openstack.common import lockutils
from openstack.common import testutils
from tests import utils as test_utils


class TestFileLocks(test_utils.BaseTestCase):
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


class LockTestCase(test_utils.BaseTestCase):
    def test_synchronized_wrapped_function_metadata(self):
        @lockutils.synchronized('whatever', 'test-')
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

        @lockutils.synchronized('testlock2', 'test-', external=False)
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

    def test_nested_external_works(self):
        """We can nest external syncs"""
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

    def test_synchronized_externally(self):
        """We can lock across multiple processes"""
        tempdir = tempfile.mkdtemp()
        self.config(lock_path=tempdir)

        @lockutils.synchronized('external', 'test-', external=True)
        def lock_files(tempdir):
            if not os.path.exists(tempdir):
                os.makedirs(tempdir)

            # Open some files we can use for locking
            handles = []
            for n in range(50):
                path = os.path.join(tempdir, ('file-%s' % n))
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

        try:
            children = []
            for n in range(50):
                pid = os.fork()
                if pid:
                    children.append(pid)
                else:
                    lock_files(tempdir)
                    os._exit(0)

            for i, child in enumerate(children):
                (pid, status) = os.waitpid(child, 0)
                if pid:
                    self.assertEqual(0, status)
        finally:
            if os.path.exists(tempdir):
                shutil.rmtree(tempdir, ignore_errors=True)
