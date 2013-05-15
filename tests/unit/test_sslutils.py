# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2013 Rackspace Hosting
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

import ssl

from openstack.common import sslutils
from tests import utils


class SslUtilsTest(utils.BaseTestCase):

    def test_no_wrap(self):
        wrapper = sslutils.SslWrapper()
        self.assertFalse(wrapper.enabled)

    def test_missing_cert_file(self):
        self.config(group='ssl', cert_file="foo")
        self.assertRaises(RuntimeError, sslutils.SslWrapper)

    def test_missing_key_file(self):
        self.config(group='ssl', key_file="foo")
        self.assertRaises(RuntimeError, sslutils.SslWrapper)

    def test_missing_ca_file(self):
        self.config(group='ssl', ca_file="foo")
        self.assertRaises(RuntimeError, sslutils.SslWrapper)


class SslUtilsTestFileStub(utils.BaseTestCase):
    def setUp(self):
        super(SslUtilsTestFileStub, self).setUp()
        self.stubs.Set(sslutils.SslWrapper, '_file_exists',
                       lambda self, f: True)

    def test_only_cert_file(self):
        self.config(group='ssl', cert_file='foo')
        self.assertRaises(RuntimeError, sslutils.SslWrapper)

    def test_only_key_file(self):
        self.config(group='ssl', key_file='foo')
        self.assertRaises(RuntimeError, sslutils.SslWrapper)

    def test_key_and_cert_files(self):
        self.config(group='ssl', key_file='key', cert_file='cert')
        wrapper = sslutils.SslWrapper()
        self.assertTrue(wrapper.enabled)
        self.assertEqual('key', wrapper.key_file)
        self.assertEqual('cert', wrapper.cert_file)

    def test_opts_override(self):
        # option values passed in take precedence:
        self.config(group='ssl', key_file='keyB', cert_file='certB',
                    ca_file='caB')
        opts = {'use_ssl': False,
                'key_file': 'keyA',
                'cert_file': 'certA',
                'ca_file': 'caA'}
        wrapper = sslutils.SslWrapper(opts)
        self.assertFalse(wrapper.enabled)
        self.assertEqual('keyA', wrapper.key_file)
        self.assertEqual('certA', wrapper.cert_file)
        self.assertEqual('caA', wrapper.ca_file)

    def _wrap(self, sock, **kwargs):
        self.assertTrue(kwargs['server_side'])
        self.assertEqual('key', kwargs['keyfile'])
        self.assertEqual('cert', kwargs['certfile'])
        self.assertEqual(ssl.CERT_NONE, kwargs['cert_reqs'])

    def test_wrap(self):
        self.config(group='ssl', key_file='key', cert_file='cert')
        self.stubs.Set(ssl, 'wrap_socket', self._wrap)

        wrapper = sslutils.SslWrapper()
        self.assertTrue(wrapper.enabled)

        wrapper.wrap(None)
