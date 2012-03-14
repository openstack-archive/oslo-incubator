# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2012 OpenStack LLC.
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

import unittest

from openstack.common import iniparser


class TestParser(iniparser.BaseParser):
    comment_called = False
    values = None
    section = ''

    def __init__(self):
        self.values = {}

    def assignment(self, key, value):
        self.values.setdefault(self.section, {})
        self.values[self.section][key] = value

    def new_section(self, section):
        self.section = section

    def comment(self, section):
        self.comment_called = True


class BaseParserTestCase(unittest.TestCase):
    def test_invalid_assignment(self):
        lines = ["foo - bar"]
        parser = iniparser.BaseParser()
        self.assertRaises(iniparser.ParseError, parser.parse, lines)

    def test_unexpected_continuation(self):
        lines = ["   baz"]
        parser = iniparser.BaseParser()
        self.assertRaises(iniparser.ParseError, parser.parse, lines)

    def test_invalid_section(self):
        lines = ["[section"]
        parser = iniparser.BaseParser()
        self.assertRaises(iniparser.ParseError, parser.parse, lines)

    def test_no_section_name(self):
        lines = ["[]"]
        parser = iniparser.BaseParser()
        self.assertRaises(iniparser.ParseError, parser.parse, lines)

    def test_assignment(self):
        lines = ["foo = bar"]
        tparser = TestParser()
        tparser.parse(lines)
        self.assertEquals(tparser.values, {'': {'foo': ['bar']}})

    def test_section_assignment(self):
        lines = ["[test]", "foo = bar"]
        tparser = TestParser()
        tparser.parse(lines)
        self.assertEquals(tparser.values, {'test': {'foo': ['bar']}})

    def test_new_section(self):
        lines = ["[foo]"]
        tparser = TestParser()
        tparser.parse(lines)
        self.assertEquals(tparser.section, 'foo')

    def test_comment(self):
        lines = ["# foobar"]
        tparser = TestParser()
        tparser.parse(lines)
        self.assertTrue(tparser.comment_called)
