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

import mock
from oslotest import base as test_base
from testtools import matchers

from openstack.common import versionutils


class DeprecatedTestCase(test_base.BaseTestCase):
    def assert_deprecated(self, mock_log, no_removal=False,
                          **expected_details):
        decorator = versionutils.deprecated
        if 'in_favor_of' in expected_details:
            if no_removal is False:
                expected_msg = decorator._deprecated_msg_with_alternative
            else:
                expected_msg = getattr(
                    decorator,
                    '_deprecated_msg_with_alternative_no_removal')
        else:
            if no_removal is False:
                expected_msg = decorator._deprecated_msg_no_alternative
            else:
                expected_msg = getattr(
                    decorator,
                    '_deprecated_msg_with_no_alternative_no_removal')
        mock_log.deprecated.assert_called_with(expected_msg, expected_details)

    @mock.patch('openstack.common.versionutils.LOG', mock.Mock())
    def test_deprecating_a_function_returns_correct_value(self):

        @versionutils.deprecated(as_of=versionutils.deprecated.ICEHOUSE)
        def do_outdated_stuff(data):
            return data

        expected_rv = 'expected return value'
        retval = do_outdated_stuff(expected_rv)

        self.assertThat(retval, matchers.Equals(expected_rv))

    @mock.patch('openstack.common.versionutils.LOG', mock.Mock())
    def test_deprecating_a_method_returns_correct_value(self):

        class C(object):
            @versionutils.deprecated(as_of=versionutils.deprecated.ICEHOUSE)
            def outdated_method(self, *args):
                return args

        retval = C().outdated_method(1, 'of anything')

        self.assertThat(retval, matchers.Equals((1, 'of anything')))

    @mock.patch('openstack.common.versionutils.LOG')
    def test_deprecated_with_unknown_future_release(self, mock_log):

        @versionutils.deprecated(as_of=versionutils.deprecated.BEXAR,
                                 in_favor_of='different_stuff()')
        def do_outdated_stuff():
            return

        do_outdated_stuff()

        self.assert_deprecated(mock_log,
                               what='do_outdated_stuff()',
                               in_favor_of='different_stuff()',
                               as_of='Bexar',
                               remove_in='D')

    @mock.patch('openstack.common.versionutils.LOG')
    def test_deprecated_with_known_future_release(self, mock_log):

        @versionutils.deprecated(as_of=versionutils.deprecated.GRIZZLY,
                                 in_favor_of='different_stuff()')
        def do_outdated_stuff():
            return

        do_outdated_stuff()

        self.assert_deprecated(mock_log,
                               what='do_outdated_stuff()',
                               in_favor_of='different_stuff()',
                               as_of='Grizzly',
                               remove_in='Icehouse')

    @mock.patch('openstack.common.versionutils.LOG')
    def test_deprecated_without_replacement(self, mock_log):

        @versionutils.deprecated(as_of=versionutils.deprecated.GRIZZLY)
        def do_outdated_stuff():
            return

        do_outdated_stuff()

        self.assert_deprecated(mock_log,
                               what='do_outdated_stuff()',
                               as_of='Grizzly',
                               remove_in='Icehouse')

    @mock.patch('openstack.common.versionutils.LOG')
    def test_deprecated_with_custom_what(self, mock_log):

        @versionutils.deprecated(as_of=versionutils.deprecated.GRIZZLY,
                                 what='v2.0 API',
                                 in_favor_of='v3 API')
        def do_outdated_stuff():
            return

        do_outdated_stuff()

        self.assert_deprecated(mock_log,
                               what='v2.0 API',
                               in_favor_of='v3 API',
                               as_of='Grizzly',
                               remove_in='Icehouse')

    @mock.patch('openstack.common.versionutils.LOG')
    def test_deprecated_with_removed_next_release(self, mock_log):

        @versionutils.deprecated(as_of=versionutils.deprecated.GRIZZLY,
                                 remove_in=1)
        def do_outdated_stuff():
            return

        do_outdated_stuff()

        self.assert_deprecated(mock_log,
                               what='do_outdated_stuff()',
                               as_of='Grizzly',
                               remove_in='Havana')

    @mock.patch('openstack.common.versionutils.LOG')
    def test_deprecated_with_removed_plus_3(self, mock_log):

        @versionutils.deprecated(as_of=versionutils.deprecated.GRIZZLY,
                                 remove_in=+3)
        def do_outdated_stuff():
            return

        do_outdated_stuff()

        self.assert_deprecated(mock_log,
                               what='do_outdated_stuff()',
                               as_of='Grizzly',
                               remove_in='Juno')

    @mock.patch('openstack.common.versionutils.LOG')
    def test_deprecated_with_removed_zero(self, mock_log):
        @versionutils.deprecated(as_of=versionutils.deprecated.GRIZZLY,
                                 remove_in=0)
        def do_outdated_stuff():
            return

        do_outdated_stuff()
        self.assert_deprecated(mock_log,
                               no_removal=True,
                               what='do_outdated_stuff()',
                               as_of='Grizzly',
                               remove_in='Grizzly')

    @mock.patch('openstack.common.versionutils.LOG')
    def test_deprecated_with_removed_zero_and_alternative(self, mock_log):
        @versionutils.deprecated(as_of=versionutils.deprecated.GRIZZLY,
                                 in_favor_of='different_stuff()',
                                 remove_in=0)
        def do_outdated_stuff():
            return

        do_outdated_stuff()
        self.assert_deprecated(mock_log,
                               no_removal=True,
                               what='do_outdated_stuff()',
                               as_of='Grizzly',
                               in_favor_of='different_stuff()',
                               remove_in='Grizzly')

    @mock.patch('openstack.common.versionutils.LOG')
    def test_deprecated_class_without_init(self, mock_log):

        @versionutils.deprecated(as_of=versionutils.deprecated.JUNO,
                                 remove_in=+1)
        class OutdatedClass(object):
            pass
        obj = OutdatedClass()

        self.assertIsInstance(obj, OutdatedClass)
        self.assert_deprecated(mock_log,
                               what='OutdatedClass()',
                               as_of='Juno',
                               remove_in='Kilo')

    @mock.patch('openstack.common.versionutils.LOG')
    def test_deprecated_class_with_init(self, mock_log):
        mock_arguments = mock.MagicMock()
        args = (1, 5, 7)
        kwargs = {'first': 10, 'second': 20}

        @versionutils.deprecated(as_of=versionutils.deprecated.JUNO,
                                 remove_in=+1)
        class OutdatedClass(object):
            def __init__(self, *args, **kwargs):
                """It is __init__ method."""
                mock_arguments.args = args
                mock_arguments.kwargs = kwargs
                super(OutdatedClass, self).__init__()
        obj = OutdatedClass(*args, **kwargs)

        self.assertIsInstance(obj, OutdatedClass)
        self.assertEqual('__init__', obj.__init__.__name__)
        self.assertEqual('It is __init__ method.', obj.__init__.__doc__)
        self.assertEqual(args, mock_arguments.args)
        self.assertEqual(kwargs, mock_arguments.kwargs)
        self.assert_deprecated(mock_log,
                               what='OutdatedClass()',
                               as_of='Juno',
                               remove_in='Kilo')


class IsCompatibleTestCase(test_base.BaseTestCase):
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
