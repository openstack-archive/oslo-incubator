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

import codecs


class ParseError(Exception):
    def __init__(self, message, line):
        self.msg = message
        self.line = line

    def __str__(self):
        return '%s: %r' % (self.msg, self.line)


class BaseParser(object):
    lineno = 0
    parse_exc = ParseError

    def _assignment(self, key, value):
        self.assignment(key, value)
        return None, []

    def _get_section(self, line):
        if line[-1] != ']':
            self.error_no_section_end_bracket(line)
            return None
        if len(line) <= 2:
            self.error_no_section_name(line)
            return None

        return line[1:-1]

    def _split_key_value(self, line):
        colon = line.find(':')
        equal = line.find('=')
        if colon < 0 and equal < 0:
            self.error_invalid_assignment(line)
            return None

        if colon < 0 or equal < colon:
            key, value = line[:equal], line[equal + 1:]
        else:
            key, value = line[:colon], line[colon + 1:]

        return key.strip(), [value.strip()]

    def parse(self, lineiter):
        key = None
        value = []

        for line in lineiter:
            self.lineno += 1

            line = line.rstrip()
            if not line:
                # Blank line, ends multi-line values
                if key:
                    key, value = self._assignment(key, value)
            elif line[0] in (' ', '\t'):
                # Continuation of previous assignment
                if key is None:
                    self.error_unexpected_continuation(line)
                    continue

                value.append(line.lstrip())
            elif line[0] == '[':
                # Section start
                if key:
                    # Flush previous assignment, if any
                    key, value = self._assignment(key, value)

                section = self._get_section(line)
                if section:
                    self.new_section(section)
            elif line[0] in '#;':
                if key:
                    # Flush previous assignment, if any
                    key, value = self._assignment(key, value)

                self.comment(line[1:].lstrip())
            else:
                if key:
                    # Flush previous assignment, if any
                    key, value = self._assignment(key, value)

                key, value = self._split_key_value(line)
                if not key:
                    self.error_empty_key(line)

        if key:
            # Flush previous assignment, if any
            self._assignment(key, value)

    def assignment(self, key, value):
        """Called when a full assignment is parsed"""
        raise NotImplementedError()

    def new_section(self, section):
        """Called when a new section is started"""
        raise NotImplementedError()

    def comment(self, comment):
        """Called when a comment is parsed"""
        pass

    def error_unexpected_continuation(self, line):
        self.parse_exc('Unexpected continuation line', line)

    def error_no_section_end_bracket(self, line):
        self.parse_exc('Invalid section (must end with ])', line)

    def error_invalid_assignment(self, line):
        self.parse_exc("No ':' or '=' found in assignment", line)

    def error_no_section_name(self, line):
        self.parse_exc('Empty section name', line)
