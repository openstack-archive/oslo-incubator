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

import StringIO
import sys

import fixtures
import mock

from openstack.common import cliutils
from tests import utils


class ValidateArgsTest(utils.BaseTestCase):

    def test_lambda_no_args(self):
        cliutils.validate_args(lambda: None)

    def _test_lambda_with_args(self, *args, **kwargs):
        cliutils.validate_args(lambda x, y: None, *args, **kwargs)

    def test_lambda_positional_args(self):
        self._test_lambda_with_args(1, 2)

    def test_lambda_kwargs(self):
        self._test_lambda_with_args(x=1, y=2)

    def test_lambda_mixed_kwargs(self):
        self._test_lambda_with_args(1, y=2)

    def test_lambda_missing_args1(self):
        self.assertRaises(cliutils.MissingArgs,
                          self._test_lambda_with_args)

    def test_lambda_missing_args2(self):
        self.assertRaises(cliutils.MissingArgs,
                          self._test_lambda_with_args, 1)

    def test_lambda_missing_args3(self):
        self.assertRaises(cliutils.MissingArgs,
                          self._test_lambda_with_args, y=2)

    def _test_lambda_with_default(self, *args, **kwargs):
        cliutils.validate_args(lambda x, y, z=3: None, *args, **kwargs)

    def test_lambda_positional_args_with_default(self):
        self._test_lambda_with_default(1, 2)

    def test_lambda_kwargs_with_default(self):
        self._test_lambda_with_default(x=1, y=2)

    def test_lambda_mixed_kwargs_with_default(self):
        self._test_lambda_with_default(1, y=2)

    def test_lambda_positional_args_all_with_default(self):
        self._test_lambda_with_default(1, 2, 3)

    def test_lambda_kwargs_all_with_default(self):
        self._test_lambda_with_default(x=1, y=2, z=3)

    def test_lambda_mixed_kwargs_all_with_default(self):
        self._test_lambda_with_default(1, y=2, z=3)

    def test_lambda_with_default_missing_args1(self):
        self.assertRaises(cliutils.MissingArgs,
                          self._test_lambda_with_default)

    def test_lambda_with_default_missing_args2(self):
        self.assertRaises(cliutils.MissingArgs,
                          self._test_lambda_with_default, 1)

    def test_lambda_with_default_missing_args3(self):
        self.assertRaises(cliutils.MissingArgs,
                          self._test_lambda_with_default, y=2)

    def test_lambda_with_default_missing_args4(self):
        self.assertRaises(cliutils.MissingArgs,
                          self._test_lambda_with_default, y=2, z=3)

    def test_function_no_args(self):
        def func():
            pass
        cliutils.validate_args(func)

    def _test_function_with_args(self, *args, **kwargs):
        def func(x, y):
            pass
        cliutils.validate_args(func, *args, **kwargs)

    def test_function_positional_args(self):
        self._test_function_with_args(1, 2)

    def test_function_kwargs(self):
        self._test_function_with_args(x=1, y=2)

    def test_function_mixed_kwargs(self):
        self._test_function_with_args(1, y=2)

    def test_function_missing_args1(self):
        self.assertRaises(cliutils.MissingArgs, self._test_function_with_args)

    def test_function_missing_args2(self):
        self.assertRaises(cliutils.MissingArgs,
                          self._test_function_with_args, 1)

    def test_function_missing_args3(self):
        self.assertRaises(cliutils.MissingArgs,
                          self._test_function_with_args, y=2)

    def _test_function_with_default(self, *args, **kwargs):
        def func(x, y, z=3):
            pass
        cliutils.validate_args(func, *args, **kwargs)

    def test_function_positional_args_with_default(self):
        self._test_function_with_default(1, 2)

    def test_function_kwargs_with_default(self):
        self._test_function_with_default(x=1, y=2)

    def test_function_mixed_kwargs_with_default(self):
        self._test_function_with_default(1, y=2)

    def test_function_positional_args_all_with_default(self):
        self._test_function_with_default(1, 2, 3)

    def test_function_kwargs_all_with_default(self):
        self._test_function_with_default(x=1, y=2, z=3)

    def test_function_mixed_kwargs_all_with_default(self):
        self._test_function_with_default(1, y=2, z=3)

    def test_function_with_default_missing_args1(self):
        self.assertRaises(cliutils.MissingArgs,
                          self._test_function_with_default)

    def test_function_with_default_missing_args2(self):
        self.assertRaises(cliutils.MissingArgs,
                          self._test_function_with_default, 1)

    def test_function_with_default_missing_args3(self):
        self.assertRaises(cliutils.MissingArgs,
                          self._test_function_with_default, y=2)

    def test_function_with_default_missing_args4(self):
        self.assertRaises(cliutils.MissingArgs,
                          self._test_function_with_default, y=2, z=3)

    def test_bound_method_no_args(self):
        class Foo:
            def bar(self):
                pass
        cliutils.validate_args(Foo().bar)

    def _test_bound_method_with_args(self, *args, **kwargs):
        class Foo:
            def bar(self, x, y):
                pass
        cliutils.validate_args(Foo().bar, *args, **kwargs)

    def test_bound_method_positional_args(self):
        self._test_bound_method_with_args(1, 2)

    def test_bound_method_kwargs(self):
        self._test_bound_method_with_args(x=1, y=2)

    def test_bound_method_mixed_kwargs(self):
        self._test_bound_method_with_args(1, y=2)

    def test_bound_method_missing_args1(self):
        self.assertRaises(cliutils.MissingArgs,
                          self._test_bound_method_with_args)

    def test_bound_method_missing_args2(self):
        self.assertRaises(cliutils.MissingArgs,
                          self._test_bound_method_with_args, 1)

    def test_bound_method_missing_args3(self):
        self.assertRaises(cliutils.MissingArgs,
                          self._test_bound_method_with_args, y=2)

    def _test_bound_method_with_default(self, *args, **kwargs):
        class Foo:
            def bar(self, x, y, z=3):
                pass
        cliutils.validate_args(Foo().bar, *args, **kwargs)

    def test_bound_method_positional_args_with_default(self):
        self._test_bound_method_with_default(1, 2)

    def test_bound_method_kwargs_with_default(self):
        self._test_bound_method_with_default(x=1, y=2)

    def test_bound_method_mixed_kwargs_with_default(self):
        self._test_bound_method_with_default(1, y=2)

    def test_bound_method_positional_args_all_with_default(self):
        self._test_bound_method_with_default(1, 2, 3)

    def test_bound_method_kwargs_all_with_default(self):
        self._test_bound_method_with_default(x=1, y=2, z=3)

    def test_bound_method_mixed_kwargs_all_with_default(self):
        self._test_bound_method_with_default(1, y=2, z=3)

    def test_bound_method_with_default_missing_args1(self):
        self.assertRaises(cliutils.MissingArgs,
                          self._test_bound_method_with_default)

    def test_bound_method_with_default_missing_args2(self):
        self.assertRaises(cliutils.MissingArgs,
                          self._test_bound_method_with_default, 1)

    def test_bound_method_with_default_missing_args3(self):
        self.assertRaises(cliutils.MissingArgs,
                          self._test_bound_method_with_default, y=2)

    def test_bound_method_with_default_missing_args4(self):
        self.assertRaises(cliutils.MissingArgs,
                          self._test_bound_method_with_default, y=2, z=3)

    def test_unbound_method_no_args(self):
        class Foo:
            def bar(self):
                pass
        cliutils.validate_args(Foo.bar, Foo())

    def _test_unbound_method_with_args(self, *args, **kwargs):
        class Foo:
            def bar(self, x, y):
                pass
        cliutils.validate_args(Foo.bar, Foo(), *args, **kwargs)

    def test_unbound_method_positional_args(self):
        self._test_unbound_method_with_args(1, 2)

    def test_unbound_method_kwargs(self):
        self._test_unbound_method_with_args(x=1, y=2)

    def test_unbound_method_mixed_kwargs(self):
        self._test_unbound_method_with_args(1, y=2)

    def test_unbound_method_missing_args1(self):
        self.assertRaises(cliutils.MissingArgs,
                          self._test_unbound_method_with_args)

    def test_unbound_method_missing_args2(self):
        self.assertRaises(cliutils.MissingArgs,
                          self._test_unbound_method_with_args, 1)

    def test_unbound_method_missing_args3(self):
        self.assertRaises(cliutils.MissingArgs,
                          self._test_unbound_method_with_args, y=2)

    def _test_unbound_method_with_default(self, *args, **kwargs):
        class Foo:
            def bar(self, x, y, z=3):
                pass
        cliutils.validate_args(Foo.bar, Foo(), *args, **kwargs)

    def test_unbound_method_positional_args_with_default(self):
        self._test_unbound_method_with_default(1, 2)

    def test_unbound_method_kwargs_with_default(self):
        self._test_unbound_method_with_default(x=1, y=2)

    def test_unbound_method_mixed_kwargs_with_default(self):
        self._test_unbound_method_with_default(1, y=2)

    def test_unbound_method_with_default_missing_args1(self):
        self.assertRaises(cliutils.MissingArgs,
                          self._test_unbound_method_with_default)

    def test_unbound_method_with_default_missing_args2(self):
        self.assertRaises(cliutils.MissingArgs,
                          self._test_unbound_method_with_default, 1)

    def test_unbound_method_with_default_missing_args3(self):
        self.assertRaises(cliutils.MissingArgs,
                          self._test_unbound_method_with_default, y=2)

    def test_unbound_method_with_default_missing_args4(self):
        self.assertRaises(cliutils.MissingArgs,
                          self._test_unbound_method_with_default, y=2, z=3)

    def test_class_method_no_args(self):
        class Foo:
            @classmethod
            def bar(cls):
                pass
        cliutils.validate_args(Foo.bar)

    def _test_class_method_with_args(self, *args, **kwargs):
        class Foo:
            @classmethod
            def bar(cls, x, y):
                pass
        cliutils.validate_args(Foo.bar, *args, **kwargs)

    def test_class_method_positional_args(self):
        self._test_class_method_with_args(1, 2)

    def test_class_method_kwargs(self):
        self._test_class_method_with_args(x=1, y=2)

    def test_class_method_mixed_kwargs(self):
        self._test_class_method_with_args(1, y=2)

    def test_class_method_missing_args1(self):
        self.assertRaises(cliutils.MissingArgs,
                          self._test_class_method_with_args)

    def test_class_method_missing_args2(self):
        self.assertRaises(cliutils.MissingArgs,
                          self._test_class_method_with_args, 1)

    def test_class_method_missing_args3(self):
        self.assertRaises(cliutils.MissingArgs,
                          self._test_class_method_with_args, y=2)

    def _test_class_method_with_default(self, *args, **kwargs):
        class Foo:
            @classmethod
            def bar(cls, x, y, z=3):
                pass
        cliutils.validate_args(Foo.bar, *args, **kwargs)

    def test_class_method_positional_args_with_default(self):
        self._test_class_method_with_default(1, 2)

    def test_class_method_kwargs_with_default(self):
        self._test_class_method_with_default(x=1, y=2)

    def test_class_method_mixed_kwargs_with_default(self):
        self._test_class_method_with_default(1, y=2)

    def test_class_method_with_default_missing_args1(self):
        self.assertRaises(cliutils.MissingArgs,
                          self._test_class_method_with_default)

    def test_class_method_with_default_missing_args2(self):
        self.assertRaises(cliutils.MissingArgs,
                          self._test_class_method_with_default, 1)

    def test_class_method_with_default_missing_args3(self):
        self.assertRaises(cliutils.MissingArgs,
                          self._test_class_method_with_default, y=2)

    def test_class_method_with_default_missing_args4(self):
        self.assertRaises(cliutils.MissingArgs,
                          self._test_class_method_with_default, y=2, z=3)

    def test_static_method_no_args(self):
        class Foo:
            @staticmethod
            def bar():
                pass
        cliutils.validate_args(Foo.bar)

    def _test_static_method_with_args(self, *args, **kwargs):
        class Foo:
            @staticmethod
            def bar(x, y):
                pass
        cliutils.validate_args(Foo.bar, *args, **kwargs)

    def test_static_method_positional_args(self):
        self._test_static_method_with_args(1, 2)

    def test_static_method_kwargs(self):
        self._test_static_method_with_args(x=1, y=2)

    def test_static_method_mixed_kwargs(self):
        self._test_static_method_with_args(1, y=2)

    def test_static_method_missing_args1(self):
        self.assertRaises(cliutils.MissingArgs,
                          self._test_static_method_with_args)

    def test_static_method_missing_args2(self):
        self.assertRaises(cliutils.MissingArgs,
                          self._test_static_method_with_args, 1)

    def test_static_method_missing_args3(self):
        self.assertRaises(cliutils.MissingArgs,
                          self._test_static_method_with_args, y=2)

    def _test_static_method_with_default(self, *args, **kwargs):
        class Foo:
            @staticmethod
            def bar(x, y, z=3):
                pass
        cliutils.validate_args(Foo.bar, *args, **kwargs)

    def test_static_method_positional_args_with_default(self):
        self._test_static_method_with_default(1, 2)

    def test_static_method_kwargs_with_default(self):
        self._test_static_method_with_default(x=1, y=2)

    def test_static_method_mixed_kwargs_with_default(self):
        self._test_static_method_with_default(1, y=2)

    def test_static_method_with_default_missing_args1(self):
        self.assertRaises(cliutils.MissingArgs,
                          self._test_static_method_with_default)

    def test_static_method_with_default_missing_args2(self):
        self.assertRaises(cliutils.MissingArgs,
                          self._test_static_method_with_default, 1)

    def test_static_method_with_default_missing_args3(self):
        self.assertRaises(cliutils.MissingArgs,
                          self._test_static_method_with_default, y=2)

    def test_static_method_with_default_missing_args4(self):
        self.assertRaises(cliutils.MissingArgs,
                          self._test_static_method_with_default, y=2, z=3)


UUID = '8e8ec658-c7b0-4243-bdf8-6f7f2952c0d0'
exceptions = sys.modules[__name__]
cliutils.set_exceptions_module(exceptions)


class NotFound(Exception):
    pass


class NoUniqueMatch(Exception):
    pass


class CommandError(Exception):
    pass


class UnsupportedVersion(Exception):
    pass


class FakeResource(object):
    NAME_ATTR = 'name'

    def __init__(self, _id, properties):
        self.id = _id
        try:
            self.name = properties['name']
        except KeyError:
            pass


class FakeManager(object):

    resource_class = FakeResource

    resources = [
        FakeResource('1234', {'name': 'entity_one'}),
        FakeResource(UUID, {'name': 'entity_two'}),
        FakeResource('5678', {'name': '9876'})
    ]

    def __init__(self, client):
        pass

    def find(self, **kwargs):
        searches = kwargs.items()

        for obj in self.list():
            try:
                if all(getattr(obj, attr) == value
                       for (attr, value) in searches):
                    return obj
            except AttributeError:
                continue

        raise exceptions.NotFound()

    def get(self, resource_id):
        for resource in self.resources:
            if resource.id == str(resource_id):
                return resource
        raise exceptions.NotFound(resource_id)

    def list(self):
        return self.resources


class FakeDisplayResource(object):
    NAME_ATTR = 'display_name'

    def __init__(self, _id, properties):
        self.id = _id
        try:
            self.display_name = properties['display_name']
        except KeyError:
            pass


class FakeDisplayManager(FakeManager):

    resource_class = FakeDisplayResource

    resources = [
        FakeDisplayResource('4242', {'display_name': 'entity_three'}),
    ]


class FindResourceTestCase(utils.BaseTestCase):

    def setUp(self):
        super(FindResourceTestCase, self).setUp()
        self.manager = FakeManager(None)

    def test_find_none(self):
        """Test a few non-valid inputs."""
        self.assertRaises(exceptions.CommandError,
                          cliutils.find_resource,
                          self.manager,
                          'asdf')
        self.assertRaises(exceptions.CommandError,
                          cliutils.find_resource,
                          self.manager,
                          None)
        self.assertRaises(exceptions.CommandError,
                          cliutils.find_resource,
                          self.manager,
                          {})

    def test_find_by_integer_id(self):
        output = cliutils.find_resource(self.manager, 1234)
        self.assertEqual(output, self.manager.get('1234'))

    def test_find_by_str_id(self):
        output = cliutils.find_resource(self.manager, '1234')
        self.assertEqual(output, self.manager.get('1234'))

    def test_find_by_uuid(self):
        output = cliutils.find_resource(self.manager, UUID)
        self.assertEqual(output, self.manager.get(UUID))

    def test_find_by_str_name(self):
        output = cliutils.find_resource(self.manager, 'entity_one')
        self.assertEqual(output, self.manager.get('1234'))

    def test_find_by_str_displayname(self):
        display_manager = FakeDisplayManager(None)
        output = cliutils.find_resource(display_manager, 'entity_three')
        self.assertEqual(output, display_manager.get('4242'))


class _FakeResult(object):
    def __init__(self, name, value):
        self.name = name
        self.value = value


class PrintResultTestCase(utils.BaseTestCase):
    @mock.patch('sys.stdout', StringIO.StringIO())
    def test_print_list_sort_by_str(self):
        objs = [_FakeResult("k1", 1),
                _FakeResult("k3", 2),
                _FakeResult("k2", 3)]

        cliutils.print_list(objs, ["Name", "Value"], sortby_index=0)

        self.assertEqual(sys.stdout.getvalue(),
                         '+------+-------+\n'
                         '| Name | Value |\n'
                         '+------+-------+\n'
                         '| k1   | 1     |\n'
                         '| k2   | 3     |\n'
                         '| k3   | 2     |\n'
                         '+------+-------+\n')

    @mock.patch('sys.stdout', StringIO.StringIO())
    def test_print_list_sort_by_integer(self):
        objs = [_FakeResult("k1", 1),
                _FakeResult("k3", 2),
                _FakeResult("k2", 3)]

        cliutils.print_list(objs, ["Name", "Value"], sortby_index=1)

        self.assertEqual(sys.stdout.getvalue(),
                         '+------+-------+\n'
                         '| Name | Value |\n'
                         '+------+-------+\n'
                         '| k1   | 1     |\n'
                         '| k3   | 2     |\n'
                         '| k2   | 3     |\n'
                         '+------+-------+\n')

    # without sorting
    @mock.patch('sys.stdout', StringIO.StringIO())
    def test_print_list_sort_by_none(self):
        objs = [_FakeResult("k1", 1),
                _FakeResult("k3", 3),
                _FakeResult("k2", 2)]

        cliutils.print_list(objs, ["Name", "Value"], sortby_index=None)

        self.assertEqual(sys.stdout.getvalue(),
                         '+------+-------+\n'
                         '| Name | Value |\n'
                         '+------+-------+\n'
                         '| k1   | 1     |\n'
                         '| k3   | 3     |\n'
                         '| k2   | 2     |\n'
                         '+------+-------+\n')

    @mock.patch('sys.stdout', StringIO.StringIO())
    def test_print_dict(self):
        cliutils.print_dict({'K': 'k', 'Key': 'Value'})
        cliutils.print_dict({'K': 'k', 'Key': 'Long\\nValue'})

        self.assertEqual(sys.stdout.getvalue(),
                         "+----------+-------+\n"
                         "| Property | Value |\n"
                         "+----------+-------+\n"
                         "| K        | k     |\n"
                         "| Key      | Value |\n"
                         "+----------+-------+\n"
                         "+----------+-------+\n"
                         "| Property | Value |\n"
                         "+----------+-------+\n"
                         "| K        | k     |\n"
                         "| Key      | Long  |\n"
                         "|          | Value |\n"
                         "+----------+-------+\n")


class FakeClient1(object):
    pass


class FakeClient21(object):
    pass


class GetClientClassTestCase(utils.BaseTestCase):
    version_map = {
        "1": "%s.FakeClient1" % __name__,
        "2.1": "%s.FakeClient21" % __name__,
    }

    def test_get_int(self):
        self.assertEqual(
            cliutils.get_client_class("fake", 1, self.version_map),
            FakeClient1)

    def test_get_str(self):
        self.assertEqual(
            cliutils.get_client_class("fake", "2.1", self.version_map),
            FakeClient21)

    def test_unsupported_version(self):
        self.assertRaises(
            exceptions.UnsupportedVersion,
            cliutils.get_client_class,
            "fake", "7", self.version_map)


class DecoratorsTestCase(utils.BaseTestCase):

    def test_arg(self):
        func_args = [("--image", ), ('--flavor', )]
        func_kwargs = [dict(default=None,
                            metavar='<image>'),
                       dict(default=None,
                            metavar='<flavor>')]

        @cliutils.arg(*func_args[1], **func_kwargs[1])
        @cliutils.arg(*func_args[0], **func_kwargs[0])
        def dummy_func():
            pass

        self.assertTrue(hasattr(dummy_func, "arguments"))
        self.assertEqual(len(dummy_func.arguments), 2)
        for i in xrange(2):
            self.assertIn((func_args[i], func_kwargs[i]), dummy_func.arguments)

    def test_unauthenticated(self):
        def dummy_func():
            pass

        self.assertFalse(cliutils.isunauthenticated(dummy_func))
        dummy_func = cliutils.unauthenticated(dummy_func)
        self.assertTrue(cliutils.isunauthenticated(dummy_func))


class EnvTestCase(utils.BaseTestCase):

    def test_env(self):
        env = {"alpha": "a", "beta": "b"}
        self.useFixture(fixtures.MonkeyPatch("os.environ", env))
        self.assertEqual(cliutils.env("beta"), env["beta"])
        self.assertEqual(cliutils.env("beta", "alpha"), env["beta"])
        self.assertEqual(cliutils.env("gamma"), "")
        self.assertEqual(cliutils.env("gamma", default="c"), "c")


class GetPasswordTestCase(utils.BaseTestCase):

    def test_get_password(self):

        class FakeFile(object):
            def isatty(self):
                return True

        self.useFixture(fixtures.MonkeyPatch("sys.stdin", FakeFile()))
        self.useFixture(fixtures.MonkeyPatch("getpass.getpass",
                                             lambda prompt: "mellon"))
        self.assertEqual(cliutils.get_password(), "mellon")
