# Copyright 2014 Mirantis.inc
# All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

"""Tests for common utilities used in testing"""

from openstack.common import test


class TestBaseTestCase(test.BaseTestCase):
    def setUp(self):
        super(TestBaseTestCase, self).setUp()
        self.arg = 'test_arg'

    def _some_function(self, arg):
            raise SyntaxError("There is a syntax error with %s" % arg)

    def test_assert_raises_regexp(self):
        self.assertRaisesRegexp(SyntaxError,
                                "There is a syntax error with %s" % self.arg,
                                self._some_function, self.arg)

    def test_assert_raises_regexp_failure(self):
        def _some_function(arg):
            pass

        self.assertRaises(self.failureException, self.assertRaisesRegexp,
                          ValueError,
                          "There is a syntax error with %s" % self.arg,
                          _some_function, self.arg)

    def test_assert_raises_regexp_wrong_msg(self):
        self.assertRaises(self.failureException, self.assertRaisesRegexp,
                          SyntaxError, "Wrong error message",
                          self._some_function, self.arg)
