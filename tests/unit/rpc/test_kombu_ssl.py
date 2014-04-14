# Copyright 2010 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
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

"""
Unit Tests for remote procedure calls using kombu + ssl
"""

import ssl

import eventlet
eventlet.monkey_patch()

from openstack.common.fixture import config
from openstack.common import test


try:
    import kombu
    from openstack.common.rpc import impl_kombu
except ImportError:
    kombu = None
    impl_kombu = None


# Flag settings we will ensure get passed to amqplib
SSL_VERSION = "SSLv3"
SSL_CERT = "/tmp/cert.blah.blah"
SSL_CA_CERT = "/tmp/cert.ca.blah.blah"
SSL_KEYFILE = "/tmp/keyfile.blah.blah"


class RpcKombuSslTestCase(test.BaseTestCase):

    def setUp(self):
        super(RpcKombuSslTestCase, self).setUp()
        if kombu is None:
            self.skipTest("Test requires kombu")
        configfixture = self.useFixture(config.Config())
        self.config = configfixture.config
        self.FLAGS = configfixture.conf
        self.config(kombu_ssl_keyfile=SSL_KEYFILE,
                    kombu_ssl_ca_certs=SSL_CA_CERT,
                    kombu_ssl_certfile=SSL_CERT,
                    kombu_ssl_version=SSL_VERSION,
                    rabbit_use_ssl=True,
                    fake_rabbit=True)

    def test_ssl_on_extended(self):
        rpc = impl_kombu
        conn = rpc.create_connection(self.FLAGS, True)
        c = conn.connection
        # This might be kombu version dependent...
        # Since we are now peaking into the internals of kombu...
        self.assertTrue(isinstance(c.connection.ssl, dict))
        self.assertEqual(ssl.PROTOCOL_SSLv3,
                         c.connection.ssl.get("ssl_version"))
        self.assertEqual(SSL_CERT, c.connection.ssl.get("certfile"))
        self.assertEqual(SSL_CA_CERT, c.connection.ssl.get("ca_certs"))
        self.assertEqual(SSL_KEYFILE, c.connection.ssl.get("keyfile"))
        # That hash then goes into amqplib which then goes
        # Into python ssl creation...


class RpcKombuSslBadVersionTestCase(test.BaseTestCase):

    def setUp(self):
        super(RpcKombuSslBadVersionTestCase, self).setUp()
        if kombu is None:
            self.skipTest("Test requires kombu")
        configfixture = self.useFixture(config.Config())
        self.config = configfixture.config
        self.FLAGS = configfixture.conf
        self.config(kombu_ssl_keyfile=SSL_KEYFILE,
                    kombu_ssl_ca_certs=SSL_CA_CERT,
                    kombu_ssl_certfile=SSL_CERT,
                    kombu_ssl_version="SSLv24",
                    rabbit_use_ssl=True,
                    fake_rabbit=True)

    def test_bad_ssl_version(self):
        rpc = impl_kombu
        self.assertRaises(RuntimeError,
                          rpc.create_connection, self.FLAGS, True)
