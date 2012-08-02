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
Pycrypto wrapper
"""
import contextlib

from openstack.common import cfg
from openstack.common.gettextutils import _

import Crypto.Hash
from Crypto.PublicKey import RSA
from Crypto.Signature import PKCS1_v1_5


ssl_opts = [
    cfg.StrOpt("ssl_private_keyfile", default="",
               help="Path to private key"),
    cfg.StrOpt("ssl_digest", default="SHA256",
               help="Hashing algorithm, see Crypto.Hash"),
    cfg.StrOpt("ssl_ca_cert", default="",
               help="Path to X509 CA certificate for verification")
]
CONF = cfg.CONF
CONF.register_opts(ssl_opts)

# Load hashing algorithm
HashModule = __import__('Crypto.Hash'. globals(), locals(),
        [CONF.ssl_digest], -1)
_hashalg = getattr(HashModule, CONF.ssl_digest).new

# Load private key into _crypto_key
with open(CONF.ssl_private_key) as pk:
    _crypto_key = RSA.importKey(pk.read())
    _signer = PKCS1_v1_5.new(_crypto_key)

# Load CA into _crypto_ca
with open(CONF.ssl_ca_cert) as ca:
    _crypto_ca = RSA.importKey(ca.read())
    _verifier = PKCS1_v1_5.new(_crypto_ca)


def sign(message):
    h = _hashalg(message)
    return _signer.sign(h)

def verify(signature, message):
    h = _hashalg(message)
    return _verifier.verify(h, signature)
