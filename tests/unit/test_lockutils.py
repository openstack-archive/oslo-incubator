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
import os
import select
import shutil
import tempfile
import unittest

import eventlet
from eventlet import greenthread
from eventlet import greenpool

from openstack.common import lockutils
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
        try:
            self.config(lock_path=tempdir)
            rpipe1, wpipe1 = os.pipe()
            rpipe2, wpipe2 = os.pipe()

            @lockutils.synchronized('testlock1', 'test-', external=True)
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

        finally:
            if os.path.exists(tempdir):
                shutil.rmtree(tempdir)
