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

import fixtures
import mock
from oslotest import base as test_base

from openstack.common import cliutils


class ValidateArgsTest(test_base.BaseTestCase):

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
        self.assertRaises(cliutils.MissingArgs,
                          self._test_function_with_args)

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


class _FakeResult(object):
    def __init__(self, name, value):
        self.name = name
        self.value = value


class PrintResultTestCase(test_base.BaseTestCase):

    def setUp(self):
        super(PrintResultTestCase, self).setUp()
        self.mock_add_row = mock.MagicMock()
        self.useFixture(fixtures.MonkeyPatch(
            "prettytable.PrettyTable.add_row",
            self.mock_add_row))
        self.mock_get_string = mock.MagicMock(return_value="")
        self.useFixture(fixtures.MonkeyPatch(
            "prettytable.PrettyTable.get_string",
            self.mock_get_string))
        self.mock_init = mock.MagicMock(return_value=None)
        self.useFixture(fixtures.MonkeyPatch(
            "prettytable.PrettyTable.__init__",
            self.mock_init))
        # NOTE(dtantsur): won't work with mocked __init__
        self.useFixture(fixtures.MonkeyPatch(
            "prettytable.PrettyTable.align",
            mock.MagicMock()))

    def test_print_list_sort_by_str(self):
        objs = [_FakeResult("k1", 1),
                _FakeResult("k3", 2),
                _FakeResult("k2", 3)]

        cliutils.print_list(objs, ["Name", "Value"], sortby_index=0)

        self.assertEqual(self.mock_add_row.call_args_list,
                         [mock.call(["k1", 1]),
                          mock.call(["k3", 2]),
                          mock.call(["k2", 3])])
        self.mock_get_string.assert_called_with(sortby="Name")
        self.mock_init.assert_called_once_with(["Name", "Value"])

    def test_print_list_sort_by_integer(self):
        objs = [_FakeResult("k1", 1),
                _FakeResult("k2", 3),
                _FakeResult("k3", 2)]

        cliutils.print_list(objs, ["Name", "Value"], sortby_index=1)

        self.assertEqual(self.mock_add_row.call_args_list,
                         [mock.call(["k1", 1]),
                          mock.call(["k2", 3]),
                          mock.call(["k3", 2])])
        self.mock_get_string.assert_called_with(sortby="Value")
        self.mock_init.assert_called_once_with(["Name", "Value"])

    def test_print_list_sort_by_none(self):
        objs = [_FakeResult("k1", 1),
                _FakeResult("k3", 3),
                _FakeResult("k2", 2)]

        cliutils.print_list(objs, ["Name", "Value"], sortby_index=None)

        self.assertEqual(self.mock_add_row.call_args_list,
                         [mock.call(["k1", 1]),
                          mock.call(["k3", 3]),
                          mock.call(["k2", 2])])
        self.mock_get_string.assert_called_with()
        self.mock_init.assert_called_once_with(["Name", "Value"])

    def test_print_dict(self):
        cliutils.print_dict({"K": "k", "Key": "Value"})
        cliutils.print_dict({"K": "k", "Key": "Long\\nValue"})
        self.mock_add_row.assert_has_calls([
            mock.call(["K", "k"]),
            mock.call(["Key", "Value"]),
            mock.call(["K", "k"]),
            mock.call(["Key", "Long"]),
            mock.call(["", "Value"])],
            any_order=True)

    def test_print_list_field_labels(self):
        objs = [_FakeResult("k1", 1),
                _FakeResult("k3", 3),
                _FakeResult("k2", 2)]
        field_labels = ["Another Name", "Another Value"]

        cliutils.print_list(objs, ["Name", "Value"], sortby_index=None,
                            field_labels=field_labels)

        self.assertEqual(self.mock_add_row.call_args_list,
                         [mock.call(["k1", 1]),
                          mock.call(["k3", 3]),
                          mock.call(["k2", 2])])
        self.mock_init.assert_called_once_with(field_labels)

    def test_print_list_field_labels_sort(self):
        objs = [_FakeResult("k1", 1),
                _FakeResult("k3", 3),
                _FakeResult("k2", 2)]
        field_labels = ["Another Name", "Another Value"]

        cliutils.print_list(objs, ["Name", "Value"], sortby_index=0,
                            field_labels=field_labels)

        self.assertEqual(self.mock_add_row.call_args_list,
                         [mock.call(["k1", 1]),
                          mock.call(["k3", 3]),
                          mock.call(["k2", 2])])
        self.mock_init.assert_called_once_with(field_labels)
        self.mock_get_string.assert_called_with(sortby="Another Name")

    def test_print_list_field_labels_too_many(self):
        objs = [_FakeResult("k1", 1),
                _FakeResult("k3", 3),
                _FakeResult("k2", 2)]
        field_labels = ["Another Name", "Another Value", "Redundant"]

        self.assertRaises(ValueError, cliutils.print_list,
                          objs, ["Name", "Value"], sortby_index=None,
                          field_labels=field_labels)


class DecoratorsTestCase(test_base.BaseTestCase):

    def test_arg(self):
        func_args = [("--image", ), ("--flavor", )]
        func_kwargs = [dict(default=None,
                            metavar="<image>"),
                       dict(default=None,
                            metavar="<flavor>")]

        @cliutils.arg(*func_args[1], **func_kwargs[1])
        @cliutils.arg(*func_args[0], **func_kwargs[0])
        def dummy_func():
            pass

        self.assertTrue(hasattr(dummy_func, "arguments"))
        self.assertEqual(len(dummy_func.arguments), 2)
        for args_kwargs in zip(func_args, func_kwargs):
            self.assertIn(args_kwargs, dummy_func.arguments)

    def test_unauthenticated(self):
        def dummy_func():
            pass

        self.assertFalse(cliutils.isunauthenticated(dummy_func))
        dummy_func = cliutils.unauthenticated(dummy_func)
        self.assertTrue(cliutils.isunauthenticated(dummy_func))


class EnvTestCase(test_base.BaseTestCase):

    def test_env(self):
        env = {"alpha": "a", "beta": "b"}
        self.useFixture(fixtures.MonkeyPatch("os.environ", env))
        self.assertEqual(cliutils.env("beta"), env["beta"])
        self.assertEqual(cliutils.env("beta", "alpha"), env["beta"])
        self.assertEqual(cliutils.env("alpha", "beta"), env["alpha"])
        self.assertEqual(cliutils.env("gamma", "beta"), env["beta"])
        self.assertEqual(cliutils.env("gamma"), "")
        self.assertEqual(cliutils.env("gamma", default="c"), "c")


class GetPasswordTestCase(test_base.BaseTestCase):

    def setUp(self):
        super(GetPasswordTestCase, self).setUp()

        class FakeFile(object):
            def isatty(self):
                return True

        self.useFixture(fixtures.MonkeyPatch("sys.stdin", FakeFile()))

    def test_get_password(self):
        self.useFixture(fixtures.MonkeyPatch("getpass.getpass",
                                             lambda prompt: "mellon"))
        self.assertEqual(cliutils.get_password(), "mellon")

    def test_get_password_verify(self):
        env = {"OS_VERIFY_PASSWORD": "True"}
        self.useFixture(fixtures.MonkeyPatch("os.environ", env))
        self.useFixture(fixtures.MonkeyPatch("getpass.getpass",
                                             lambda prompt: "mellon"))
        self.assertEqual(cliutils.get_password(), "mellon")

    def test_get_password_verify_failure(self):
        env = {"OS_VERIFY_PASSWORD": "True"}
        self.useFixture(fixtures.MonkeyPatch("os.environ", env))
        self.useFixture(fixtures.MonkeyPatch("getpass.getpass",
                                             lambda prompt: prompt))
        self.assertIsNone(cliutils.get_password())
