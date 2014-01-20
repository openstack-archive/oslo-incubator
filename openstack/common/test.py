# Copyright (c) 2013 Hewlett-Packard Development Company, L.P.
# All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

"""Common utilities used in testing"""

import logging
import os

import fixtures
import testtools

_TRUE_VALUES = ('True', 'true', '1', 'yes')
_LOG_FORMAT = "%(levelname)8s [%(name)s] %(message)s"


class BaseTestCase(testtools.TestCase):

    def setUp(self):
        super(BaseTestCase, self).setUp()
        self._set_timeout()
        self._fake_output()
        self._fake_logs()
        self.useFixture(fixtures.NestedTempfile())
        self.useFixture(fixtures.TempHomeDir())

    def _set_timeout(self):
        test_timeout = os.environ.get('OS_TEST_TIMEOUT', 0)
        try:
            test_timeout = int(test_timeout)
        except ValueError:
            # If timeout value is invalid do not set a timeout.
            test_timeout = 0
        if test_timeout > 0:
            self.useFixture(fixtures.Timeout(test_timeout, gentle=True))

    def _fake_output(self):
        if os.environ.get('OS_STDOUT_CAPTURE') in _TRUE_VALUES:
            stdout = self.useFixture(fixtures.StringStream('stdout')).stream
            self.useFixture(fixtures.MonkeyPatch('sys.stdout', stdout))
        if os.environ.get('OS_STDERR_CAPTURE') in _TRUE_VALUES:
            stderr = self.useFixture(fixtures.StringStream('stderr')).stream
            self.useFixture(fixtures.MonkeyPatch('sys.stderr', stderr))

    def _fake_logs(self):
        if os.environ.get('OS_DEBUG') in _TRUE_VALUES:
            level = logging.DEBUG
        else:
            level = logging.INFO
        capture_logs = os.environ.get('OS_LOG_CAPTURE') in _TRUE_VALUES
        if capture_logs:
            self.useFixture(
                fixtures.FakeLogger(
                    format=_LOG_FORMAT,
                    level=level,
                    nuke_handlers=capture_logs,
                )
            )
        else:
            logging.basicConfig(format=_LOG_FORMAT, level=level)


class ModelsObjectComparatorMixin(object):
    def _items(self, obj):
        try:
            return obj.iteritems()
        except AttributeError:
            return obj.items()

    def _dict_from_object(self, obj, ignored_keys):
        if ignored_keys is None:
            ignored_keys = []
        return dict(
            [(k, v) for k, v in self._items(obj) if k not in ignored_keys]
        )

    def assertEqualObjects(self, obj1, obj2, ignored_keys=None):
        """Check equal of the two objects

        :param obj1: First object. An 'object' is an instance of
            ModelBase or dict.
        :param obj2: Second object.
        :param ignored_keys: Set of keys that will be ignored, when
            comparing
        :type ignored_keys: set or None
        """
        obj1 = self._dict_from_object(obj1, ignored_keys)
        obj2 = self._dict_from_object(obj2, ignored_keys)

        self.assertEqual(
            len(obj1),
            len(obj2),
            "Keys mismatch: %s" % str(set(obj1.keys()) ^ set(obj2.keys()))
        )
        for key, value in self._items(obj1):
            self.assertEqual(value, obj2[key])

    def assertEqualListsOfObjects(self, objs1, objs2, ignored_keys=None):
        """Check equal of the two lists. List's object is objects.

        :param objs1: First list of objects. An 'object' is an instance of
            ModelBase or dict.
        :param objs2: Second list of objects.
        :param ignored_keys: Set of keys that will be ignored, when
            comparing.
        :type ignored_keys: set or None
        """
        obj_to_dict = lambda o: self._dict_from_object(o, ignored_keys)
        sort_key = lambda d: [d[k] for k in sorted(d)]
        conv_and_sort = lambda obj: sorted(map(obj_to_dict, obj), key=sort_key)

        self.assertEqual(conv_and_sort(objs1), conv_and_sort(objs2))

    def assertEqualListsOfPrimitivesAsSets(self, primitives1, primitives2):
        """Check equal of the two built-in collections(list, tuple)."""
        self.assertEqual(len(primitives1), len(primitives2))
        for primitive in primitives1:
            self.assertIn(primitive, primitives2)

        for primitive in primitives2:
            self.assertIn(primitive, primitives1)
