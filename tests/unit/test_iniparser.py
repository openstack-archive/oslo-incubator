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

import stubout

from openstack.common import iniparser


class TestParser(iniparser.BaseParser):
    assignment_called = False
    new_section_called = False
    comment_called = False

    def assignment(self, key, value):
        self.assignment_called = True

    def new_section(self, section):
        self.new_section_called = True

    def comment(self, section):
        self.comment_called = True


class BaseParserTestCase(unittest.TestCase):
    def test_invalid_assignment(self):
        lines = ["foo - bar"]
        parser = TestParser()
        self.assertRaises(iniparser.ParseError, parser.parse, lines)

    def test_unexpected_continuation(self):
        lines = ["   baz"]
        parser = TestParser()
        self.assertRaises(iniparser.ParseError, parser.parse, lines)

    def test_invalid_section(self):
        lines = ["[section"]
        parser = TestParser()
        self.assertRaises(iniparser.ParseError, parser.parse, lines)

    def test_no_section_name(self):
        lines = ["[]"]
        parser = TestParser()
        self.assertRaises(iniparser.ParseError, parser.parse, lines)

    def test_assignment(self):
        lines = ["foo = bar"]
        tparser = TestParser()
        tparser.parse(lines)
        self.assertTrue(tparser.assignment_called)

    def test_new_section(self):
        lines = ["[foo]"]
        tparser = TestParser()
        tparser.parse(lines)
        self.assertTrue(tparser.new_section_called)

    def test_comment(self):
        lines = ["# foobar"]
        tparser = TestParser()
        tparser.parse(lines)
        self.assertTrue(tparser.comment_called)
