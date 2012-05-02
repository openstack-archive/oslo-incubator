# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2011 OpenStack LLC.
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

import datetime
import sys
import unittest

from openstack.common import importutils


class ImportUtilsTest(unittest.TestCase):
    # NOTE(jkoelker) There has GOT to be a way to test this. But mocking
    #                __import__ is the devil. Right now we just make
    #               sure we can import something from the stdlib
    def test_import_class(self):
        dt = importutils.import_class('datetime.datetime')
        self.assertEqual(sys.modules['datetime'].datetime, dt)

    def test_import_bad_class(self):
        self.assertRaises(ImportError, importutils.import_class,
                          'lol.u_mad.brah')

    def test_import_module(self):
        dt = importutils.import_module('datetime')
        self.assertEqual(sys.modules['datetime'], dt)

    def test_import_object(self):
        dt = importutils.import_object('datetime.time')
        self.assertTrue(isinstance(dt, sys.modules['datetime'].time))

    def test_import_object_with_args(self):
        dt = importutils.import_object('datetime.datetime', 2012, 4, 5)
        self.assertTrue(isinstance(dt, sys.modules['datetime'].datetime))
        self.assertEqual(dt, datetime.datetime(2012, 4, 5))
