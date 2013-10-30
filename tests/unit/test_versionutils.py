# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright (c) 2013 OpenStack Foundation
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

from testtools import matchers

from openstack.common import test
from openstack.common import versionutils


class DeprecatedTestCase(test.BaseTestCase):

    def setUp(self):
        super(DeprecatedTestCase, self).setUp()
        self.orig_logger = versionutils.LOG
        versionutils.LOG = self

    def tearDown(self):
        super(DeprecatedTestCase, self).tearDown()
        versionutils.LOG = self.orig_logger

    def deprecated(self, message, details):
        self.deprecated_message = message % details

    def test_deprecating_a_function_returns_correct_value(self):

        @versionutils.deprecated(as_of=versionutils.deprecated.ICEHOUSE)
        def do_outdated_stuff(data):
            return data

        expected_rv = 'expected return value'
        retval = do_outdated_stuff(expected_rv)

        self.assertThat(retval, matchers.Equals(expected_rv))

    def test_deprecating_a_method_returns_correct_value(self):

        class C(object):
            @versionutils.deprecated(as_of=versionutils.deprecated.ICEHOUSE)
            def outdated_method(self, *args):
                return args

        retval = C().outdated_method(1, 'of anything')

        self.assertThat(retval, matchers.Equals((1, 'of anything')))

    def test_deprecated_with_unknown_future_release(self):

        @versionutils.deprecated(as_of=versionutils.deprecated.ICEHOUSE,
                                 in_favor_of='different_stuff()')
        def do_outdated_stuff():
            return

        do_outdated_stuff()

        expected = ('do_outdated_stuff() is deprecated as of Icehouse '
                    'in favor of different_stuff() and may be removed in K.')
        self.assertThat(self.deprecated_message,
                        matchers.Contains(expected))

    def test_deprecated_with_known_future_release(self):

        @versionutils.deprecated(as_of=versionutils.deprecated.GRIZZLY,
                                 in_favor_of='different_stuff()')
        def do_outdated_stuff():
            return

        do_outdated_stuff()

        expected = ('do_outdated_stuff() is deprecated as of Grizzly '
                    'in favor of different_stuff() and may be removed in '
                    'Icehouse.')
        self.assertThat(self.deprecated_message,
                        matchers.Contains(expected))

    def test_deprecated_without_replacement(self):

        @versionutils.deprecated(as_of=versionutils.deprecated.GRIZZLY)
        def do_outdated_stuff():
            return

        do_outdated_stuff()

        expected = ('do_outdated_stuff() is deprecated as of Grizzly '
                    'and may be removed in Icehouse. It will not be '
                    'superseded.')
        self.assertThat(self.deprecated_message,
                        matchers.Contains(expected))

    def test_deprecated_with_custom_what(self):

        @versionutils.deprecated(as_of=versionutils.deprecated.GRIZZLY,
                                 what='v2.0 API',
                                 in_favor_of='v3 API')
        def do_outdated_stuff():
            return

        do_outdated_stuff()

        expected = ('v2.0 API is deprecated as of Grizzly in favor of '
                    'v3 API and may be removed in Icehouse.')
        self.assertThat(self.deprecated_message,
                        matchers.Contains(expected))

    def test_deprecated_with_removed_next_release(self):

        @versionutils.deprecated(as_of=versionutils.deprecated.GRIZZLY,
                                 remove_in=1)
        def do_outdated_stuff():
            return

        do_outdated_stuff()

        expected = ('do_outdated_stuff() is deprecated as of Grizzly '
                    'and may be removed in Havana. It will not be '
                    'superseded.')
        self.assertThat(self.deprecated_message,
                        matchers.Contains(expected))

    def test_deprecated_with_removed_plus_3(self):

        @versionutils.deprecated(as_of=versionutils.deprecated.GRIZZLY,
                                 remove_in=+3)
        def do_outdated_stuff():
            return

        do_outdated_stuff()

        expected = ('do_outdated_stuff() is deprecated as of Grizzly '
                    'and may be removed in J. It will not '
                    'be superseded.')
        self.assertThat(self.deprecated_message,
                        matchers.Contains(expected))


class IsCompatibleTestCase(test.BaseTestCase):
    def test_same_version(self):
        self.assertTrue(versionutils.is_compatible('1', '1'))
        self.assertTrue(versionutils.is_compatible('1.0', '1.0'))
        self.assertTrue(versionutils.is_compatible('1.0.0', '1.0.0'))

    def test_requested_minor_greater(self):
        self.assertFalse(versionutils.is_compatible('1.1', '1.0'))

    def test_requested_minor_less_than(self):
        self.assertTrue(versionutils.is_compatible('1.0', '1.1'))

    def test_requested_patch_greater(self):
        self.assertFalse(versionutils.is_compatible('1.0.1', '1.0.0'))

    def test_requested_patch_less_than(self):
        self.assertTrue(versionutils.is_compatible('1.0.0', '1.0.1'))

    def test_requested_patch_not_present_same(self):
        self.assertTrue(versionutils.is_compatible('1.0', '1.0.0'))

    def test_requested_patch_not_present_less_than(self):
        self.assertTrue(versionutils.is_compatible('1.0', '1.0.1'))

    def test_current_patch_not_present_same(self):
        self.assertTrue(versionutils.is_compatible('1.0.0', '1.0'))

    def test_current_patch_not_present_less_than(self):
        self.assertFalse(versionutils.is_compatible('1.0.1', '1.0'))

    def test_same_major_true(self):
        """Even though the current version is 2.0, since `same_major` defaults
        to `True`, 1.0 is deemed incompatible.
        """
        self.assertFalse(versionutils.is_compatible('2.0', '1.0'))
        self.assertTrue(versionutils.is_compatible('1.0', '1.0'))
        self.assertFalse(versionutils.is_compatible('1.0', '2.0'))

    def test_same_major_false(self):
        """With `same_major` set to False, then major version compatibiity
        rule is not enforced, so a current version of 2.0 is deemed to satisfy
        a requirement of 1.0.
        """
        self.assertFalse(versionutils.is_compatible('2.0', '1.0',
                                                    same_major=False))
        self.assertTrue(versionutils.is_compatible('1.0', '1.0',
                                                   same_major=False))
        self.assertTrue(versionutils.is_compatible('1.0', '2.0',
                                                   same_major=False))
