# Copyright (c) 2012 OpenStack Foundation
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

"""Tests for hook customization."""

import stevedore

from openstack.common.fixture import moxstubout
from openstack.common import hooks
from openstack.common import test


class SampleHookA(object):
    name = "a"

    def _add_called(self, op, kwargs):
        called = kwargs.get('called')
        if called is not None:
            called.append(op + self.name)

    def pre(self, *args, **kwargs):
        self._add_called("pre", kwargs)


class SampleHookB(SampleHookA):
    name = "b"

    def post(self, rv, *args, **kwargs):
        self._add_called("post", kwargs)


class SampleHookC(SampleHookA):
    name = "c"

    def pre(self, f, *args, **kwargs):
        self._add_called("pre" + f.__name__, kwargs)

    def post(self, f, rv, *args, **kwargs):
        self._add_called("post" + f.__name__, kwargs)


class MockEntryPoint(object):

    def __init__(self, cls):
        self.cls = cls

    def load(self):
        return self.cls


class HookTestCase(test.BaseTestCase):

    def _mock_load_plugins(self, iload, iargs, ikwargs):
        return [
            stevedore.extension.Extension(
                'test_hook',
                MockEntryPoint(SampleHookA), SampleHookA, SampleHookA()),
            stevedore.extension.Extension(
                'test_hook',
                MockEntryPoint(SampleHookB), SampleHookB, SampleHookB()),
        ]

    def setUp(self):
        moxfixture = self.useFixture(moxstubout.MoxStubout())
        self.stubs = moxfixture.stubs
        self.mox = moxfixture.mox
        super(HookTestCase, self).setUp()

        hooks.reset()

        self.stubs.Set(stevedore.extension.ExtensionManager, '_load_plugins',
                       self._mock_load_plugins)

    @hooks.add_hook('test_hook')
    def _hooked(self, a, b=1, c=2, called=None):
        return 42

    def test_basic(self):
        self.assertEqual(42, self._hooked(1))

        mgr = hooks._HOOKS['test_hook']
        self.assertEqual(2, len(mgr.extensions))
        self.assertEqual(SampleHookA, mgr.extensions[0].plugin)
        self.assertEqual(SampleHookB, mgr.extensions[1].plugin)

    def test_order_of_execution(self):
        called_order = []
        self._hooked(42, called=called_order)
        self.assertEqual(['prea', 'preb', 'postb'], called_order)


class HookTestCaseWithFunction(HookTestCase):
    def _mock_load_plugins(self, iload, iargs, ikwargs):
        return [
            stevedore.extension.Extension(
                'function_hook',
                MockEntryPoint(SampleHookC), SampleHookC, SampleHookC()),
        ]

    @hooks.add_hook('function_hook', pass_function=True)
    def _hooked(self, a, b=1, c=2, called=None):
        return 42

    def test_basic(self):
        self.assertEqual(42, self._hooked(1))
        mgr = hooks._HOOKS['function_hook']

        self.assertEqual(1, len(mgr.extensions))
        self.assertEqual(SampleHookC, mgr.extensions[0].plugin)

    def test_order_of_execution(self):
        called_order = []
        self._hooked(42, called=called_order)
        self.assertEqual(['pre_hookedc', 'post_hookedc'], called_order)
