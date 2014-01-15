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

from openstack.common import hooks
from tests import utils


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


class HookTestCase(utils.BaseTestCase):
    hook_name = 'test_hook'
    extensions = []

    def setUp(self):
        super(HookTestCase, self).setUp()
        self.mgr = self._create_mgr(self.hook_name, self.extensions)

    def tearDown(self):
        super(HookTestCase, self).tearDown()
        self.mgr = None
        hooks.reset()

    def _create_mgr(self, hook_name, extensions):
        mgr = hooks.get_hook(hook_name)
        mgr.api = stevedore.HookManager.make_test_instance(
            extensions, hooks.NS)
        return mgr


class HookTestCaseWithoutFunction(HookTestCase):
    hook_name = 'test_hook_without_function'
    extensions = [
        stevedore.extension.Extension(
            'test_hook_without_function',
            MockEntryPoint(SampleHookA), SampleHookA, SampleHookA()),
        stevedore.extension.Extension(
            'test_hook_without_function',
            MockEntryPoint(SampleHookB), SampleHookB, SampleHookB()),
    ]

    @hooks.add_hook('test_hook_without_function')
    def _hooked(self, a, b=1, c=2, called=None):
        return 42

    def test_basic(self):
        self.assertEqual(42, self._hooked(1))

        self.assertEqual(2, len(self.mgr.extensions))
        self.assertEqual(SampleHookA, self.mgr.extensions[0].plugin)
        self.assertEqual(SampleHookB, self.mgr.extensions[1].plugin)

    def test_order_of_execution(self):
        called_order = []
        self._hooked(42, called=called_order)
        self.assertEqual(['prea', 'preb', 'postb'], called_order)


class HookTestCaseWithFunction(HookTestCase):
    hook_name = 'test_hook_with_function'

    extensions = [stevedore.extension.Extension(
        'test_hook_with_function',
        MockEntryPoint(SampleHookC), SampleHookC, SampleHookC()),
    ]

    @hooks.add_hook('test_hook_with_function', pass_function=True)
    def _hooked(self, a, b=1, c=2, called=None):
        return 42

    def test_basic(self):
        self.assertEqual(42, self._hooked(1))
        self.assertEqual(1, len(self.mgr.extensions))
        self.assertEqual(SampleHookC, self.mgr.extensions[0].plugin)

    def test_order_of_execution(self):
        called_order = []
        self._hooked(42, called=called_order)
        self.assertEqual(['pre_hookedc', 'post_hookedc'], called_order)


class FailedHook(SampleHookA):

    def downgrade(self, *args, **kwargs):
        self._add_called("downgrade", kwargs)


class FailedHookA(FailedHook):
    name = "failed_a"

    def pre(self, f, *args, **kwargs):
        self._add_called("pre", kwargs)

    def post(self, f, rv, *args, **kwargs):
        self._add_called("post", kwargs)
        raise AttributeError('Unexpected error in post-method...')


class FailedHookB(FailedHook):
    name = "failed_b"

    def pre(self, f, *args, **kwargs):
        self._add_called("pre", kwargs)
        raise ValueError('Unexpected error in pre-method...')

    def post(self, f, rv, *args, **kwargs):
        self._add_called("post", kwargs)
        raise KeyError('Unexpected error in post-method...')


class HookTestCaseWithFailedHook(HookTestCase):
    hook_name = 'failed_hook'

    extensions = [
        stevedore.extension.Extension(
            'failed_hook',
            MockEntryPoint(FailedHookA), FailedHookA, FailedHookA()),
        stevedore.extension.Extension(
            'failed_hook',
            MockEntryPoint(FailedHookB), FailedHookB, FailedHookB()),
    ]

    @hooks.add_hook('failed_hook', pass_function=True)
    def _hooked(self, a, b=1, c=2, called=None):
        return 42

    def test_basic(self):
        self.assertEqual(42, self._hooked(1))
        self.assertEqual(2, len(self.mgr.extensions))
        self.assertEqual(FailedHookA, self.mgr.extensions[0].plugin)
        self.assertEqual(FailedHookB, self.mgr.extensions[1].plugin)

    def test_raising(self):
        mgr = hooks.get_hook(self.hook_name)
        mgr.rollback = 'raise'
        called_order = []
        self.assertRaises(ValueError, self._hooked, 1, called=called_order)
        self.assertEqual(['prefailed_a', 'prefailed_b'], called_order)

    def test_local(self):
        mgr = hooks.get_hook(self.hook_name)
        mgr.rollback = 'local'
        called_order = []
        self._hooked(1, called=called_order)
        self.assertEqual(['prefailed_a', 'prefailed_b', 'downgradefailed_b',
                          'postfailed_a', 'downgradefailed_a',
                          'postfailed_b', 'downgradefailed_b'], called_order)

    def test_full(self):
        mgr = hooks.get_hook(self.hook_name)
        mgr.rollback = 'full'

        called_order = []
        self.assertRaises(hooks.HookMethodException, self._hooked,
                          1, called=called_order)
        self.assertEqual(['prefailed_a', 'prefailed_b', 'downgradefailed_b',
                          'downgradefailed_a'], called_order)
