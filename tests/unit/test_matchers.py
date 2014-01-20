# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2012 Hewlett-Packard Development Company, L.P.
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

import testtools
from testtools.tests.matchers import helpers

from openstack.common import matchers


class TestDictMatches(testtools.TestCase, helpers.TestMatchersInterface):

    matches_matcher = matchers.DictMatches(
        {'foo': 'bar', 'baz': 'DONTCARE',
         'cat': {'tabby': True, 'fluffy': False}}
    )

    matches_matches = [
        {'foo': 'bar', 'baz': 'noox', 'cat': {'tabby': True, 'fluffy': False}},
        {'foo': 'bar', 'baz': 'quux', 'cat': {'tabby': True, 'fluffy': False}},
    ]

    matches_mismatches = [
        {},
        {'foo': 'bar', 'baz': 'qux'},
        {'foo': 'bop', 'baz': 'qux',
         'cat': {'tabby': True, 'fluffy': False}},
        {'foo': 'bar', 'baz': 'quux',
         'cat': {'tabby': True, 'fluffy': True}},
        {'foo': 'bar', 'cat': {'tabby': True, 'fluffy': False}},
    ]

    str_examples = [
        ("DictMatches({'baz': 'DONTCARE', 'cat':"
         " {'fluffy': False, 'tabby': True}, 'foo': 'bar'})",
         matches_matcher),
    ]

    describe_examples = [
        ("Keys in d1 and not d2: set(['foo', 'baz', 'cat'])."
         " Keys in d2 and not d1: set([])", {}, matches_matcher),
        ("Dictionaries do not match at fluffy. d1: False d2: True",
         {'foo': 'bar', 'baz': 'quux',
          'cat': {'tabby': True, 'fluffy': True}}, matches_matcher),
        ("Dictionaries do not match at foo. d1: bar d2: bop",
         {'foo': 'bop', 'baz': 'quux',
          'cat': {'tabby': True, 'fluffy': False}}, matches_matcher),
    ]


class TestDictListMatches(testtools.TestCase, helpers.TestMatchersInterface):

    matches_matcher = matchers.DictListMatches(
        [{'foo': 'bar', 'baz': 'DONTCARE',
         'cat': {'tabby': True, 'fluffy': False}},
         {'dog': 'yorkie'},
         ])

    matches_matches = [
        [{'foo': 'bar', 'baz': 'qoox',
         'cat': {'tabby': True, 'fluffy': False}},
         {'dog': 'yorkie'}],
        [{'foo': 'bar', 'baz': False,
         'cat': {'tabby': True, 'fluffy': False}},
         {'dog': 'yorkie'}],
    ]

    matches_mismatches = [
        [],
        {},
        [{'foo': 'bar', 'baz': 'qoox',
         'cat': {'tabby': True, 'fluffy': True}},
         {'dog': 'yorkie'}],
        [{'foo': 'bar', 'baz': False,
         'cat': {'tabby': True, 'fluffy': False}},
         {'cat': 'yorkie'}],
        [{'foo': 'bop', 'baz': False,
         'cat': {'tabby': True, 'fluffy': False}},
         {'dog': 'yorkie'}],
    ]

    str_examples = [
        ("DictListMatches([{'baz': 'DONTCARE', 'cat':"
         " {'fluffy': False, 'tabby': True}, 'foo': 'bar'},\n"
         " {'dog': 'yorkie'}])",
         matches_matcher),
    ]

    describe_examples = [
        ("Length mismatch: len(L1)=2 != len(L2)=0", {}, matches_matcher),
        ("Dictionaries do not match at fluffy. d1: True d2: False",
         [{'foo': 'bar', 'baz': 'qoox',
           'cat': {'tabby': True, 'fluffy': True}},
          {'dog': 'yorkie'}],
         matches_matcher),
    ]


class TestIsSubDictOf(testtools.TestCase, helpers.TestMatchersInterface):

    matches_matcher = matchers.IsSubDictOf(
        {'foo': 'bar', 'baz': 'DONTCARE',
         'cat': {'tabby': True, 'fluffy': False}}
    )

    matches_matches = [
        {'foo': 'bar', 'baz': 'noox', 'cat': {'tabby': True, 'fluffy': False}},
        {'foo': 'bar', 'baz': 'quux'}
    ]

    matches_mismatches = [
        {'foo': 'bop', 'baz': 'qux',
         'cat': {'tabby': True, 'fluffy': False}},
        {'foo': 'bar', 'baz': 'quux',
         'cat': {'tabby': True, 'fluffy': True}},
        {'foo': 'bar', 'cat': {'tabby': True, 'fluffy': False}, 'dog': None},
    ]

    str_examples = [
        ("IsSubDictOf({'foo': 'bar', 'baz': 'DONTCARE',"
         " 'cat': {'fluffy': False, 'tabby': True}})",
         matches_matcher),
    ]

    describe_examples = [
        ("Dictionaries do not match at fluffy. d1: False d2: True",
         {'foo': 'bar', 'baz': 'quux',
          'cat': {'tabby': True, 'fluffy': True}}, matches_matcher),
        ("Dictionaries do not match at foo. d1: bar d2: bop",
         {'foo': 'bop', 'baz': 'quux',
          'cat': {'tabby': True, 'fluffy': False}}, matches_matcher),
    ]


class TestXMLMatches(testtools.TestCase, helpers.TestMatchersInterface):

    matches_matcher = matchers.XMLMatches("""<?xml version="1.0"?>
<root>
  <text>some text here</text>
  <text>some other text here</text>
  <attrs key1="spam" key2="DONTCARE"/>
  <children>
    <!--This is a comment-->
    <child1>child 1</child1>
    <child2>child 2</child2>
    <child3>DONTCARE</child3>
    <?spam processing instruction?>
  </children>
</root>""")

    matches_matches = ["""<?xml version="1.0"?>
<root>
  <text>some text here</text>
  <text>some other text here</text>
  <attrs key2="spam" key1="spam"/>
  <children>
    <child1>child 1</child1>
    <child2>child 2</child2>
    <child3>child 3</child3>
  </children>
</root>""",
                       """<?xml version="1.0"?>
<root>
  <text>some text here</text>
  <text>some other text here</text>
  <attrs key1="spam" key2="quux"/>
  <children><child1>child 1</child1>
<child2>child 2</child2>
<child3>blah</child3>
  </children>
</root>""",
                       ]

    matches_mismatches = ["""<?xml version="1.0"?>
<root>
  <text>some text here</text>
  <text>mismatch text</text>
  <attrs key1="spam" key2="quux"/>
  <children>
    <child1>child 1</child1>
    <child2>child 2</child2>
    <child3>child 3</child3>
  </children>
</root>""",
                          """<?xml version="1.0"?>
<root>
  <text>some text here</text>
  <text>some other text here</text>
  <attrs key1="spam" key3="quux"/>
  <children>
    <child1>child 1</child1>
    <child2>child 2</child2>
    <child3>child 3</child3>
  </children>
</root>""",
                          """<?xml version="1.0"?>
<root>
  <text>some text here</text>
  <text>some other text here</text>
  <attrs key1="quux" key2="quux"/>
  <children>
    <child1>child 1</child1>
    <child2>child 2</child2>
    <child3>child 3</child3>
  </children>
</root>""",
                          """<?xml version="1.0"?>
<root>
  <text>some text here</text>
  <text>some other text here</text>
  <attrs key1="spam" key2="quux"/>
  <children>
    <child1>child 1</child1>
    <child4>child 4</child4>
    <child2>child 2</child2>
    <child3>child 3</child3>
  </children>
</root>""",
                          """<?xml version="1.0"?>
<root>
  <text>some text here</text>
  <text>some other text here</text>
  <attrs key1="spam" key2="quux"/>
  <children>
    <child1>child 1</child1>
    <child2>child 2</child2>
  </children>
</root>""",
                          """<?xml version="1.0"?>
<root>
  <text>some text here</text>
  <text>some other text here</text>
  <attrs key1="spam" key2="quux"/>
  <children>
    <child1>child 1</child1>
    <child2>child 2</child2>
    <child3>child 3</child3>
    <child4>child 4</child4>
  </children>
</root>""",
                          ]

    str_examples = [
        ("XMLMatches('<?xml version=\"1.0\"?>\\n"
         "<root>\\n"
         "  <text>some text here</text>\\n"
         "  <text>some other text here</text>\\n"
         "  <attrs key1=\"spam\" key2=\"DONTCARE\"/>\\n"
         "  <children>\\n"
         "    <!--This is a comment-->\\n"
         "    <child1>child 1</child1>\\n"
         "    <child2>child 2</child2>\\n"
         "    <child3>DONTCARE</child3>\\n"
         "    <?spam processing instruction?>\\n"
         "  </children>\\n"
         "</root>')", matches_matcher),
    ]

    describe_examples = [
        ("/root/text[1]: XML text value mismatch: expected text value: "
         "'some other text here'; actual value: 'mismatch text'",
         """<?xml version="1.0"?>
<root>
  <text>some text here</text>
  <text>mismatch text</text>
  <attrs key1="spam" key2="quux"/>
  <children>
    <child1>child 1</child1>
    <child2>child 2</child2>
    <child3>child 3</child3>
  </children>
</root>""", matches_matcher),
        ("/root/attrs[2]: XML attributes mismatch: keys only in expected: "
         "key2; keys only in actual: key3",
         """<?xml version="1.0"?>
<root>
  <text>some text here</text>
  <text>some other text here</text>
  <attrs key1="spam" key3="quux"/>
  <children>
    <child1>child 1</child1>
    <child2>child 2</child2>
    <child3>child 3</child3>
  </children>
</root>""", matches_matcher),
        ("/root/attrs[2]: XML attribute value mismatch: expected value of "
         "attribute key1: 'spam'; actual value: 'quux'",
         """<?xml version="1.0"?>
<root>
  <text>some text here</text>
  <text>some other text here</text>
  <attrs key1="quux" key2="quux"/>
  <children>
    <child1>child 1</child1>
    <child2>child 2</child2>
    <child3>child 3</child3>
  </children>
</root>""", matches_matcher),
        ("/root/children[3]: XML tag mismatch at index 1: expected tag "
         "<child2>; actual tag <child4>",
         """<?xml version="1.0"?>
<root>
  <text>some text here</text>
  <text>some other text here</text>
  <attrs key1="spam" key2="quux"/>
  <children>
    <child1>child 1</child1>
    <child4>child 4</child4>
    <child2>child 2</child2>
    <child3>child 3</child3>
  </children>
</root>""", matches_matcher),
        ("/root/children[3]: XML expected child element <child3> not "
         "present at index 2",
         """<?xml version="1.0"?>
<root>
  <text>some text here</text>
  <text>some other text here</text>
  <attrs key1="spam" key2="quux"/>
  <children>
    <child1>child 1</child1>
    <child2>child 2</child2>
  </children>
</root>""", matches_matcher),
        ("/root/children[3]: XML unexpected child element <child4> "
         "present at index 3",
         """<?xml version="1.0"?>
<root>
  <text>some text here</text>
  <text>some other text here</text>
  <attrs key1="spam" key2="quux"/>
  <children>
    <child1>child 1</child1>
    <child2>child 2</child2>
    <child3>child 3</child3>
    <child4>child 4</child4>
  </children>
</root>""", matches_matcher),
    ]
