# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2013 Red Hat, Inc.
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
Unit Tests for rpc 'crypto' functions.
"""

import logging

from oslo.config import cfg

from openstack.common import jsonutils
from openstack.common.rpc import common as rpc_common
from openstack.common.rpc import crypto as rpc_crypto
from tests import utils as test_utils


FLAGS = cfg.CONF
LOG = logging.getLogger(__name__)


class RpcCryptoTestCase(test_utils.BaseTestCase):

    def test_SEKcache(self):
        cache = rpc_crypto.SEKcache(True)

        # check empty cache returns noting
        sek = cache.get('foo', 'bar')
        self.assertEqual(sek, None)

        #add entry in the cache
        cache.put('foo', 'bar', 2000000000, ('skey' 'ekey', 'esek'))

        #chck it returns the object
        sek = cache.get('foo', 'bar')
        self.assertEqual(sek, ('skey' 'ekey', 'esek'))

        #check inverted source/target returns nothing
        sek = cache.get('bar', 'foo')
        self.assertEqual(sek, None)

        #add expired entry in the cache
        cache.put('foo', 'bar', 1000000000, ('skey' 'ekey', 'esek'))

        #check expired entries are not returned
        sek = cache.get('foo', 'bar')
        self.assertEqual(sek, None)

    def _test_secure_message(self, data, encrypt):
        msg = {'message': 'body'}

        send = rpc_crypto.SecureMessage(data['source'], data['send_key'],
                                        encrypt, enctype=data['cipher'],
                                        hashtype=data['hash'])
        recv = rpc_crypto.SecureMessage(data['target'], data['recv_key'],
                                        encrypt, enctype=data['cipher'],
                                        hashtype=data['hash'])

        # Adds test keys in cache
        rpc_crypto.SEKcache().put(data['source'], data['target'], 2000000000,
                                  (data['skey'], data['ekey'], data['esek']))

        pkt = send.encode(rpc_common._RPC_ENVELOPE_VERSION,
                          data['target'], jsonutils.dumps(msg))

        out = recv.decode(rpc_common._RPC_ENVELOPE_VERSION,
                          pkt[0], pkt[1], pkt[2])

        self.assertEqual(len(msg),
                         len(set(msg.items()) & set(out[1].items())))

    def test_secure_message_sha256_aes(self):
        foo_to_bar_sha256_aes = {
            'source': 'foo',
            'target': 'bar',
            'send_key': '\x0b' * 16,
            'recv_key': '\x0b' * 16,
            'hash': 'SHA256',
            'cipher': 'AES',
            'skey': 'p\xb4f\xcd\xc7o\x88U\x18\xd5\xd60\x87\x88\x97J',
            'ekey': '\xa9f>\xe7\xe6*\x17Z`U\xde\xf5\x1d>\x0c\xde',
            'esek': ('MrQ1sW7sWnyyhnbZ6q21luqvLBUvpsBugGatEORUSXr'
                     'gFZ8TRlJspbuG323U1xu15Swxy8VKbGCvqB+goe3Yyo'
                     'Owcm0iA7avqYFd4bsDKDk7WAnPrVdrfijSkfCqqGkx')
        }
        # Test signing only first
        self._test_secure_message(foo_to_bar_sha256_aes, False)
        # Test encryption too
        self._test_secure_message(foo_to_bar_sha256_aes, True)

    def test_secure_message_md5_des(self):
        foo_to_baz_md5_des = {
            'source': 'foo',
            'target': 'bar',
            'send_key': '\x3f' * 8,
            'recv_key': '\x3f' * 8,
            'hash': 'MD5',
            'cipher': 'DES',
            'skey': '\xfb\xefm!\x9d\x82\x0c\x05',
            'ekey': '\xef\xb39\x12\xb5\xe6\xb3\xc8',
            'esek': ('RGh27DSvLQDFkaQrCQmKiz6LZ61Lfp7FYzqA'
                     'PC3V59iPOT6xzPJmgApDti83hhse9G8/dHDE'
                     'NAj4QfM+F52umnhlMsPJs6mCuFYV1u5eqjg=')
        }
        # Test signing only first
        self._test_secure_message(foo_to_baz_md5_des, False)
        # Test encryption too
        self._test_secure_message(foo_to_baz_md5_des, True)

    #TODO: test fetching key from file
