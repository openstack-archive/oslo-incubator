# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2012 Red Hat, Inc.
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

import unittest

from openstack.common import loopingcall


class LoopingCallTestCase(unittest.TestCase):

    def setUp(self):
        self.num_runs = 0

    def test_return_true(self):
        def _raise_it():
            raise loopingcall.LoopingCallDone(True)

        timer = loopingcall.LoopingCall(_raise_it)
        self.assertTrue(timer.start(interval=0.5).wait())

    def test_return_false(self):
        def _raise_it():
            raise loopingcall.LoopingCallDone(False)

        timer = loopingcall.LoopingCall(_raise_it)
        self.assertFalse(timer.start(interval=0.5).wait())

    def test_repeat(self):
        self.num_runs = 2

        def _wait_for_zero():
            """Called at an interval until num_runs == 0."""
            if self.num_runs == 0:
                raise loopingcall.LoopingCallDone(False)
            else:
                self.num_runs = self.num_runs - 1

        timer = loopingcall.LoopingCall(_wait_for_zero)
        self.assertFalse(timer.start(interval=0.5).wait())
