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

import ssl

from oslotest import base as test_base

from openstack.common import sslutils


class SSLUtilsTest(test_base.BaseTestCase):
    def test_valid_versions(self):
        self.assertEqual(sslutils.validate_ssl_version("SSLv3"),
                         ssl.PROTOCOL_SSLv3)
        self.assertEqual(sslutils.validate_ssl_version("SSLv23"),
                         ssl.PROTOCOL_SSLv23)
        self.assertEqual(sslutils.validate_ssl_version("TLSv1"),
                         ssl.PROTOCOL_TLSv1)
        try:
            protocol = ssl.PROTOCOL_SSLv2
        except AttributeError:
            pass
        else:
            self.assertEqual(sslutils.validate_ssl_version("SSLv2"), protocol)

    def test_lowercase_valid_versions(self):
        self.assertEqual(sslutils.validate_ssl_version("sslv3"),
                         ssl.PROTOCOL_SSLv3)
        self.assertEqual(sslutils.validate_ssl_version("sslv23"),
                         ssl.PROTOCOL_SSLv23)
        self.assertEqual(sslutils.validate_ssl_version("tlsv1"),
                         ssl.PROTOCOL_TLSv1)
        try:
            protocol = ssl.PROTOCOL_SSLv2
        except AttributeError:
            pass
        else:
            self.assertEqual(sslutils.validate_ssl_version("sslv2"),
                             protocol)

    def test_invalid_version(self):
        self.assertRaises(RuntimeError,
                          sslutils.validate_ssl_version,
                          "v3")

        # Some distributions do not have SSLv2 enabled, make sure
        # we throw a runtime error
        try:
            ssl.PROTOCOL_SSLv2
        except AttributeError:
            self.assertRaises(RuntimeError,
                              sslutils.validate_ssl_version,
                              "SSLv2")
