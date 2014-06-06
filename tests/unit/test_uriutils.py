# Copyright 2014 NEC Corporation. All rights reserved.
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

from oslotest import base as test_base

from openstack.common import uriutils


class UriUtilsTest(test_base.BaseTestCase):

    def test_is_valid_uri_with_host_only(self):
        self.assertTrue(uriutils.is_valid_uri('http://localhost'))
        self.assertTrue(uriutils.is_valid_uri('ftp://localhost'))
        self.assertTrue(uriutils.is_valid_uri('http://192.168.0.100'))
        self.assertTrue(uriutils.is_valid_uri('http://2001:db8::9abc'))

    def test_is_valid_uri_with_port(self):
        self.assertTrue(uriutils.is_valid_uri('http://localhost:8080'))

    def test_is_valid_uri_with_userinfo(self):
        self.assertTrue(uriutils.is_valid_uri('http://foo@localhost'))

    def test_is_valid_uri_with_path(self):
        self.assertTrue(uriutils.is_valid_uri('http://localhost/'))
        self.assertTrue(uriutils.is_valid_uri('http://localhost/foo'))
        self.assertTrue(uriutils.is_valid_uri('http://localhost/foo/bar'))

    def test_is_valid_uri_with_query(self):
        self.assertTrue(uriutils.is_valid_uri('http://localhost?foo=bar'))

    def test_is_valid_uri_with_fragment(self):
        self.assertTrue(uriutils.is_valid_uri('http://localhost#nose'))

    def test_is_valid_uri_with_all(self):
        uri = 'http://user@localhost:8080/foo/bar?foo=bar#nose'
        self.assertTrue(uriutils.is_valid_uri(uri))

    def test_is_valid_uri_with_invalid_scheme(self):
        self.assertFalse(uriutils.is_valid_uri('http:localhost'))
        self.assertFalse(uriutils.is_valid_uri('0ttp://localhost'))

    def test_is_valid_uri_with_invalid_host(self):
        self.assertFalse(uriutils.is_valid_uri('http://local\host'))
