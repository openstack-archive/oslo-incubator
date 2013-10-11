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
Unit Tests for rpc 'securemessage' functions.
"""

import logging

from openstack.common.fixture import config
from openstack.common import jsonutils
from openstack.common.rpc import common as rpc_common
from openstack.common.rpc import securemessage as rpc_secmsg
from openstack.common import test


LOG = logging.getLogger(__name__)


class RpcCryptoTestCase(test.BaseTestCase):

    def setUp(self):
        super(RpcCryptoTestCase, self).setUp()
        self.CONF = self.useFixture(config.Config()).conf

    def test_KeyStore(self):
        store = rpc_secmsg.KeyStore()

        # check empty cache returns noting
        keys = store.get_ticket('foo', 'bar')
        self.assertIsNone(keys)

        ticket = rpc_secmsg.Ticket('skey', 'ekey', 'esek')

        #add entry in the cache
        store.put_ticket('foo', 'bar', 'skey', 'ekey', 'esek', 2000000000)

        #chck it returns the object
        keys = store.get_ticket('foo', 'bar')
        self.assertEqual(keys, ticket)

        #check inverted source/target returns nothing
        keys = store.get_ticket('bar', 'foo')
        self.assertIsNone(keys)

        #add expired entry in the cache
        store.put_ticket('foo', 'bar', 'skey', 'ekey', 'skey', 1000000000)

        #check expired entries are not returned
        keys = store.get_ticket('foo', 'bar')
        self.assertIsNone(keys)

    def _test_secure_message(self, data, encrypt):
        msg = {'message': 'body'}

        # Use a fresh store for each test
        store = rpc_secmsg.KeyStore()

        send = rpc_secmsg.SecureMessage(data['source'][0], data['source'][1],
                                        self.CONF, data['send_key'],
                                        store, encrypt, enctype=data['cipher'],
                                        hashtype=data['hash'])
        recv = rpc_secmsg.SecureMessage(data['target'][0], data['target'][1],
                                        self.CONF, data['recv_key'],
                                        store, encrypt, enctype=data['cipher'],
                                        hashtype=data['hash'])

        source = '%s.%s' % data['source']
        target = '%s.%s' % data['target']
        # Adds test keys in cache, we do it twice, once for client side use,
        # then for server side use as we run both in the same process
        store.put_ticket(source, target,
                         data['skey'], data['ekey'], data['esek'], 2000000000)

        pkt = send.encode(rpc_common._RPC_ENVELOPE_VERSION,
                          target, jsonutils.dumps(msg))

        out = recv.decode(rpc_common._RPC_ENVELOPE_VERSION,
                          pkt[0], pkt[1], pkt[2])
        rmsg = jsonutils.loads(out[1])

        self.assertEqual(len(msg),
                         len(set(msg.items()) & set(rmsg.items())))

    def test_secure_message_sha256_aes(self):
        foo_to_bar_sha256_aes = {
            'source': ('foo', 'host.example.com'),
            'target': ('bar', 'host.example.com'),
            'send_key': '\x0b' * 16,
            'recv_key': '\x0b' * 16,
            'hash': 'SHA256',
            'cipher': 'AES',
            'skey': "\xaf\xab\x81\x14'\xdd\x1ck\xd1\xb4[\x84MZ\xf5\r",
            'ekey': '\x98\x06\x1bW\x1e\xc1z\xdd\xe2\xb1h\xa5\xb7;\x14\n',
            'esek': ('IehVCF684xJVN0sHc/zngsCAZWQkKSueK4I+ycRhxDGYsqYaAw+nECnZ'
                     'mgA3R+DM8halM5TEwwI/uuPqExu8p+fW4CqSMh8oEtLGGqrx85GromaH'
                     '/YVqK1GpIfUSIQSZrXhAzITN9MeYfeLhD0w2ENUG6AyAk3D56W6l9zJw'
                     'ZsI=')
        }
        # Test signing only first
        self._test_secure_message(foo_to_bar_sha256_aes, False)
        # Test encryption too
        self._test_secure_message(foo_to_bar_sha256_aes, True)

    def test_secure_message_md5_des(self):
        foo_to_baz_md5_des = {
            'source': ('foo', 'host.example.com'),
            'target': ('bar', 'host.example.com'),
            'send_key': '????????',
            'recv_key': '????????',
            'hash': 'MD5',
            'cipher': 'DES',
            'skey': 'N<\xeb\x98\x9f$\xa9\xa8',
            'ekey': '\x8c\xd2\x02\x89\xbb6\xd0\xdd',
            'esek': ('CyVMteHe5LiYWFcRnodPv4t8UJ14QztJCC0p/olib9vq50/wua0LY6sk'
                     'WWe0GGcvEdzaoZAuH6eBh00CdAVT2LqlK0nBE3Szj93jmVIJxMM+ydxZ'
                     '2VCvEZohhKeenMiI')
        }
        # Test signing only first
        self._test_secure_message(foo_to_baz_md5_des, False)
        # Test encryption too
        self._test_secure_message(foo_to_baz_md5_des, True)

    #TODO(simo): test fetching key from file
