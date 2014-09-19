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

import os
import shutil
import tempfile

import eventlet
eventlet.monkey_patch()
from eventlet import greenpool
from oslo.concurrency import lockutils
from oslotest import base as test_base


class TestFileLocks(test_base.BaseTestCase):

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
