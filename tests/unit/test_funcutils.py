# Copyright 2011 OpenStack Foundation.
# Copyright 2011 Justin Santa Barbara
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

import functools

from oslotest import base as test_base
import six

from openstack.common import funcutils


class FuncutilsTestCase(test_base.BaseTestCase):
    def _test_func(self, instance, red=None, blue=None):
        pass

    def test_all_kwargs(self):
        args = ()
        kwargs = {'instance': {'uuid': 1}, 'red': 3, 'blue': 4}
        callargs = funcutils.getcallargs(self._test_func, *args, **kwargs)

        # implicit self counts as an arg
        self.assertEqual(4, len(callargs))
        self.assertTrue('instance' in callargs)
        self.assertEqual({'uuid': 1}, callargs['instance'])
        self.assertTrue('red' in callargs)
        self.assertEqual(3, callargs['red'])
        self.assertTrue('blue' in callargs)
        self.assertEqual(4, callargs['blue'])

    def test_all_args(self):
        args = ({'uuid': 1}, 3, 4)
        kwargs = {}
        callargs = funcutils.getcallargs(self._test_func, *args, **kwargs)

        # implicit self counts as an arg
        self.assertEqual(4, len(callargs))
        self.assertTrue('instance' in callargs)
        self.assertEqual({'uuid': 1}, callargs['instance'])
        self.assertTrue('red' in callargs)
        self.assertEqual(3, callargs['red'])
        self.assertTrue('blue' in callargs)
        self.assertEqual(4, callargs['blue'])

    def test_mixed_args(self):
        args = ({'uuid': 1}, 3)
        kwargs = {'blue': 4}
        callargs = funcutils.getcallargs(self._test_func, *args, **kwargs)

        # implicit self counts as an arg
        self.assertEqual(4, len(callargs))
        self.assertTrue('instance' in callargs)
        self.assertEqual({'uuid': 1}, callargs['instance'])
        self.assertTrue('red' in callargs)
        self.assertEqual(3, callargs['red'])
        self.assertTrue('blue' in callargs)
        self.assertEqual(4, callargs['blue'])

    def test_partial_kwargs(self):
        args = ()
        kwargs = {'instance': {'uuid': 1}, 'red': 3}
        callargs = funcutils.getcallargs(self._test_func, *args, **kwargs)

        # implicit self counts as an arg
        self.assertEqual(4, len(callargs))
        self.assertTrue('instance' in callargs)
        self.assertEqual({'uuid': 1}, callargs['instance'])
        self.assertTrue('red' in callargs)
        self.assertEqual(3, callargs['red'])
        self.assertTrue('blue' in callargs)
        self.assertIsNone(callargs['blue'])

    def test_partial_args(self):
        args = ({'uuid': 1}, 3)
        kwargs = {}
        callargs = funcutils.getcallargs(self._test_func, *args, **kwargs)

        # implicit self counts as an arg
        self.assertEqual(4, len(callargs))
        self.assertTrue('instance' in callargs)
        self.assertEqual({'uuid': 1}, callargs['instance'])
        self.assertTrue('red' in callargs)
        self.assertEqual(3, callargs['red'])
        self.assertTrue('blue' in callargs)
        self.assertIsNone(callargs['blue'])

    def test_partial_mixed_args(self):
        args = (3,)
        kwargs = {'instance': {'uuid': 1}}
        callargs = funcutils.getcallargs(self._test_func, *args, **kwargs)

        self.assertEqual(4, len(callargs))
        self.assertTrue('instance' in callargs)
        self.assertEqual({'uuid': 1}, callargs['instance'])
        self.assertTrue('red' in callargs)
        self.assertEqual(3, callargs['red'])
        self.assertTrue('blue' in callargs)
        self.assertIsNone(callargs['blue'])

    def _wrapper(self, function):

        @functools.wraps(function)
        def decorated_function(self, *args, **kwargs):
            function(self, *args, **kwargs)

        return decorated_function

    def test_wrapped_X(self):

        def wrapped(self, instance, red=None, blue=None):
            pass

        old_wrapped = wrapped

        # Wrap it many times and ensure that its still the right one.
        for _i in range(10):
            wrapped = self._wrapper(wrapped)
            func = funcutils.get_wrapped_function(wrapped)
            func_code = six.get_function_code(func)
            self.assertEqual(4, len(func_code.co_varnames))
            self.assertTrue('self' in func_code.co_varnames)
            self.assertTrue('instance' in func_code.co_varnames)
            self.assertTrue('red' in func_code.co_varnames)
            self.assertTrue('blue' in func_code.co_varnames)
            self.assertEqual(old_wrapped, func)
