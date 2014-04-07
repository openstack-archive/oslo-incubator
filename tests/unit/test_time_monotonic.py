# Copyright 2014 OpenStack Foundation.
#
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

import time

from openstack.common import test
from openstack.common import time_monotonic


class TimeMonotonicTestCase(test.BaseTestCase):
    def test_time(self):
        # monotonic() should not go backward
        times = [time_monotonic.time_monotonic() for n in range(100)]
        t1 = times[0]
        for t2 in times[1:]:
            self.assertGreaterEqual(t2, t1, "times=%s" % times)
            t1 = t2

        # monotonic() includes time elapsed during a sleep
        t1 = time_monotonic.time_monotonic()
        time.sleep(0.5)
        t2 = time_monotonic.time_monotonic()
        dt = t2 - t1
        self.assertGreater(t2, t1)
        # Use 1 second for the higher bound to avoid false postive
        # on very slow systems
        self.assertTrue(0.45 <= dt <= 1.0, dt)

    def test_resolution(self):
        self.assertGreater(time_monotonic.time_monotonic_resolution, 0.0)
