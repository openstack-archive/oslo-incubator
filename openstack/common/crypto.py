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
from openstack.common import cfg
from openstack.common import importutils
from openstack.common import jsonutils

import Crypto.Hash
from Crypto.PublicKey import DSA
from Crypto.Random import random


def load_key(key_file):
    with open(key_file) as pk:
        self = DSA.construct(*jsonutils.loads(pk.read()).values())


class Signing(object):
    def __init__(self, private_key, algorithm="DSA", digest="SHA256"):
        """Create a signing object.
           private_key: pycrypto key
           ca: CA to verify keys.
        """
        self._key = private_key

        # Load hashing algorithm
        HashModule = __import__('Crypto.Hash', globals(), locals(),
                [digest], -1)
        self._hashalg = getattr(HashModule, digest).new

    def get_hash(self, message):
        return self._hashalg(message).digest()

    def sign(self, message):
        k = random.StrongRandom().randint(1, self._key.q-1)
        return self._key.sign(self.get_hash(message), k)

    def verify(self, signature, message):
        return self._key.verify(self.get_hash(message), signature)
