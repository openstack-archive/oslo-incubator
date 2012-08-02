# vim: tabstop=4 shiftwidth=4 softtabstop=4

#    Copyright 2012 Cloudscaling Group, Inc
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

from tests import utils as test_utils


class SSLTestCase(test_utils.BaseTestCase):
    def setUp(self):
        # Mock private key - small bit size for speed.
        # Abusing _ variables!
        ssl._crypto_key = OpenSSL.PKey.generate_key(OpenSSL.TYPE_RSA, '128')

        super(SSLTestCase, self).setUp()

    def test_sign(self):
        msg = "Hello World"
        signature = ssl.sign(msg)
        #self.assert...

    def test_verify(self):
        msg = "Hello World"
        signature = ssl.sign(msg)
        ssl.verify(signature, msg)
        #self.assert
