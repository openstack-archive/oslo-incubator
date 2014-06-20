# Copyright 2013 IBM Corp.
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

from xml.dom import minidom

from oslotest import base as test_base

from openstack.common import xmlutils


class XMLUtilsTestCase(test_base.BaseTestCase):
    def test_safe_parse_xml(self):

        normal_body = ("""
                 <?xml version="1.0" ?><foo>
                    <bar>
                        <v1>hey</v1>
                        <v2>there</v2>
                    </bar>
                </foo>""").strip()

        def killer_body():
            return (("""<!DOCTYPE x [
                    <!ENTITY a "%(a)s">
                    <!ENTITY b "%(b)s">
                    <!ENTITY c "%(c)s">]>
                <foo>
                    <bar>
                        <v1>%(d)s</v1>
                    </bar>
                </foo>""") % {
                'a': 'A' * 10,
                'b': '&a;' * 10,
                'c': '&b;' * 10,
                'd': '&c;' * 9999,
            }).strip()

        dom = xmlutils.safe_minidom_parse_string(normal_body)
        self.assertEqual(normal_body, str(dom.toxml()))

        self.assertRaises(ValueError,
                          xmlutils.safe_minidom_parse_string,
                          killer_body())


class SafeParserTestCase(test_base.BaseTestCase):
    def test_external_dtd(self):
        xml_string = ("""<?xml version="1.0" encoding="utf-8"?>
                <!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
                 "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
                <html>
                   <head/>
                     <body>html with dtd</body>
                   </html>""")

        parser = xmlutils.ProtectedExpatParser(forbid_dtd=True,
                                               forbid_entities=True)
        self.assertRaises(ValueError,
                          minidom.parseString,
                          xml_string, parser)

    def test_external_file(self):
        xml_string = """<!DOCTYPE external [
                <!ENTITY ee SYSTEM "file:///PATH/TO/root.xml">
                ]>
                <root>&ee;</root>"""

        parser = xmlutils.ProtectedExpatParser(forbid_dtd=False,
                                               forbid_entities=True)
        self.assertRaises(ValueError,
                          minidom.parseString,
                          xml_string, parser)

    def test_notation(self):
        xml_string = """<?xml version="1.0" standalone="no"?>
                        <!-- comment data -->
                        <!DOCTYPE x [
                        <!NOTATION notation SYSTEM "notation.jpeg">
                        ]>
                        <root attr1="value1">
                        </root>"""

        parser = xmlutils.ProtectedExpatParser(forbid_dtd=False,
                                               forbid_entities=True)
        self.assertRaises(ValueError,
                          minidom.parseString,
                          xml_string, parser)
