# Copyright (c) 2012 Rackspace Hosting
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

"""
Unit Tests for thread groups
"""

import multiprocessing
import time

import eventlet
from oslotest import base as test_base

from openstack.common import threadgroup


class ThreadGroupTestCase(test_base.BaseTestCase):
    """Test cases for thread group."""
    def setUp(self):
        super(ThreadGroupTestCase, self).setUp()
        self.tg = threadgroup.ThreadGroup()
        self.addCleanup(self.tg.stop)

    def test_add_dynamic_timer(self):

        def foo(*args, **kwargs):
            pass
        initial_delay = 1
        periodic_interval_max = 2
        self.tg.add_dynamic_timer(foo, initial_delay, periodic_interval_max,
                                  'arg', kwarg='kwarg')

        self.assertEqual(1, len(self.tg.timers))

        timer = self.tg.timers[0]
        self.assertTrue(timer._running)
        self.assertEqual(('arg',), timer.args)
        self.assertEqual({'kwarg': 'kwarg'}, timer.kw)

    def test_stop_immediately(self):

        def foo(*args, **kwargs):
            time.sleep(1)
        start_time = time.time()
        self.tg.add_thread(foo, 'arg', kwarg='kwarg')
        self.tg.stop()
        end_time = time.time()

        self.assertEqual(0, len(self.tg.threads))
        self.assertTrue(end_time - start_time < 1)

    def test_stop_gracefully(self):

        def foo(*args, **kwargs):
            time.sleep(1)
        start_time = time.time()
        self.tg.add_thread(foo, 'arg', kwarg='kwarg')
        self.tg.stop(True)
        end_time = time.time()

        self.assertEqual(0, len(self.tg.threads))
        self.assertTrue(end_time - start_time >= 1)

    def test_stop_timers(self):

        def foo(*args, **kwargs):
            pass
        self.tg.add_timer('1234', foo)
        self.assertEqual(1, len(self.tg.timers))
        self.tg.stop_timers()
        self.assertEqual(0, len(self.tg.timers))

    def _test_pool_auto_expand(self, auto_expand):
        tg = threadgroup.ThreadGroup(1)

        # that's a hack to enable auto expansion while still starting
        # with only one thread in the pool
        tg.auto_expand_pool = auto_expand

        self.wait_time = None
        self.no_wait_time = None

        def wait_callback():
            # one second should be enough for another thread to spawn
            # and complete execution, unless it's blocked due to no free
            # threads in the greenthread pool (which is the case when
            # auto_resize is False)
            eventlet.greenthread.sleep(1)
            self.wait_time = time.clock()

        def no_wait_callback():
            self.no_wait_time = time.clock()

        tg.add_thread(wait_callback)
        tg.add_thread(no_wait_callback)

        tg.stop(True)

        self.assertTrue(self.no_wait_time is not None)
        self.assertTrue(self.wait_time is not None)

        self.assertEqual(self.wait_time > self.no_wait_time, auto_expand)

    def test_pool_auto_expand_negative(self):
        self._test_pool_auto_expand(False)

    def test_pool_auto_expand_positive(self):
        self._test_pool_auto_expand(True)

    def test_pool_size(self):
        tg = threadgroup.ThreadGroup(1)

        # that's a hack to enable auto expansion while still starting
        # with only one thread in the pool
        tg.auto_expand_pool = True

        ready = multiprocessing.Event()

        def wait_for_event():
            ready.wait()

        self.assertEqual(tg.pool.size, 1)

        expected_size = 1
        for i in range(100):
            tg.add_thread(wait_for_event)

            # while at it, determine the expected size that should be
            # the first power of two that will accomodate all the
            # threads, and still leaving more than 50% of the pool as
            # free for later spawns
            if expected_size < i / .5:
                expected_size *= 2
        self.assertEqual(tg.pool.size, expected_size)

        # now allow all the threads to complete execution and free pool
        # resources
        ready.set()
        tg.stop(True)

        # once all the threads are complete, the pool size is still the
        # same because there is no big reason to shrink it
        self.assertEqual(tg.pool.size, expected_size)
