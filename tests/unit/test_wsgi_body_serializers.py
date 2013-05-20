# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2013 OpenStack Foundation.
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


import six

from openstack.common import wsgi_body_serializers
from tests import utils


class XMLDictSerializerTest(utils.BaseTestCase):

    def test_xml(self):
        input_dict = dict(servers=dict(a=(2, 3)))
        expected_xml = """<servers xmlns="asdf">
                           <a>(2,3)</a>
                         </servers>"""
        serializer = wsgi_body_serializers.XMLDictSerializer(xmlns="asdf")
        result = serializer.serialize(input_dict)
        result = result.replace('\n', '').replace(' ', '')
        expected_xml = expected_xml.replace('\n', '').replace(' ', '')
        self.assertEqual(result, expected_xml)


class JSONDictSerializerTest(utils.BaseTestCase):

    def test_json(self):
        input_dict = dict(servers=dict(a=(2, 3)))
        expected_json = '{"servers":{"a":[2,3]}}'
        serializer = wsgi_body_serializers.JSONDictSerializer()
        result = serializer.serialize(input_dict)
        result = result.replace('\n', '').replace(' ', '')
        self.assertEqual(result, expected_json)

    def test_object_unicode(self):
        class TestUnicode:
            def __unicode__(self):
                return six.u('TestUnicode')
        input_dict = dict(cls=TestUnicode())
        expected_str = '{"cls":"TestUnicode"}'
        serializer = wsgi_body_serializers.JSONDictSerializer()
        result = serializer.serialize(input_dict)
        result = result.replace('\n', '').replace(' ', '')
        self.assertEqual(result, expected_str)


class JSONDeserializerTest(utils.BaseTestCase):

    def test_json(self):
        data = """{"a": {
                "a1": "1",
                "a2": "2",
                "bs": ["1", "2", "3", {"c": {"c1": "1"}}],
                "d": {"e": "1"},
                "f": "1"}}"""
        as_dict = {
            'body': {
                'a': {
                    'a1': '1',
                    'a2': '2',
                    'bs': ['1', '2', '3', {'c': {'c1': '1'}}],
                    'd': {'e': '1'},
                    'f': '1',
                },
            },
        }
        deserializer = wsgi_body_serializers.JSONDeserializer()
        self.assertEqual(deserializer.deserialize(data), as_dict)


class XMLDeserializerTest(utils.BaseTestCase):

    def test_xml(self):
        xml = """
            <a a1="1" a2="2">
              <bs><b>1</b><b>2</b><b>3</b><b><c c1="1"/></b></bs>
              <d><e>1</e></d>
              <f>1</f>
            </a>
            """.strip()
        as_dict = {
            'body': {
                'a': {
                    'a1': '1',
                    'a2': '2',
                    'bs': ['1', '2', '3', {'c': {'c1': '1'}}],
                    'd': {'e': '1'},
                    'f': '1',
                },
            },
        }
        metadata = {'plurals': {'bs': 'b', 'ts': 't'}}
        deserializer = wsgi_body_serializers.XMLDeserializer(metadata=metadata)
        self.assertEqual(deserializer.deserialize(xml), as_dict)

    def test_xml_empty(self):
        xml = '<a></a>'
        as_dict = {"body": {"a": {}}}
        deserializer = wsgi_body_serializers.XMLDeserializer()
        self.assertEqual(deserializer.deserialize(xml), as_dict)
