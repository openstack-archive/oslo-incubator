# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2012 Red Hat, Inc.
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

import unittest

from openstack.common import testutils


class TestUtilsTestCase(unittest.TestCase):

    @testutils.skip_test('test should be skipped')
    def test_skip_test(self):
        raise Exception('should have been skipped')

    @testutils.skip_if(True, 'test should be skipped')
    def test_skip_if_true(self):
        raise Exception('should have been skipped')

    @testutils.skip_if(False, 'test should not be skipped')
    def test_skip_if_false(self):
        pass

    @testutils.skip_unless(True, 'test should not be skipped')
    def test_skip_unless_true(self):
        pass

    @testutils.skip_unless(False, 'test should be skipped')
    def test_skip_unless_false(self):
        raise Exception('should have been skipped')
