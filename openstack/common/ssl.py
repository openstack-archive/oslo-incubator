# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2012 Cloudscaling
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
OpenSSL wrapper
"""

from openstack.common import cfg
from openstack.common.gettextutils import _

from OpenSSL import crypto


ssl_opts = [
    cfg.StrOpt("ssl_private_keyfile", default="",
               help="Path to private key"),
    cfg.StrOpt("ssl_digest", default="sha256",
               help="OpenSSL digest"),
    cfg.StrOpt("ssl_ca_cert", default="",
               help="Path to X509 CA certificate for verification")
]
CONF = cfg.CONF
CONF.register_opts(ssl_opts)

# Load private key into _crypto_key
private_key_file = open(CONF.ssl_private_key)
_crypto_key = crypto.load_privatekey(crypto.FILETYPE.PEM,
                                    private_key.read())
private_key_file.close()

# Load CA Cert into _crypto_ca
ca_file = open(CONF.ssl_private_keyfile)
_crypto_ca = crypto.load_certificate(ca_file.read())
ca_file.close()


def sign(message):
    return crypto.sign(_crypto_key, message, CONF.ssl_digest)

def verify(signature, message):
    return crypto.verify(_crypto_ca, signature, message, CONF.ssl_digest)
