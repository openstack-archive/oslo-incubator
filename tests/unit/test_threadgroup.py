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

import time

from openstack.common import test
from openstack.common import threadgroup


class ThreadGroupTestCase(test.BaseTestCase):
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
        self.tg.add_thread(foo, 'arg', 'kwarg')
        self.tg.stop()
        end_time = time.time()

        self.assertEqual(0, len(self.tg.threads))
        self.assertTrue(end_time - start_time < 1)

    def test_stop_gracefully(self):

        def foo(*args, **kwargs):
            time.sleep(1)
        start_time = time.time()
        self.tg.add_thread(foo, 'arg', 'kwarg')
        self.tg.stop(True)
        end_time = time.time()

        self.assertEqual(0, len(self.tg.threads))
        self.assertTrue(end_time - start_time >= 1)
