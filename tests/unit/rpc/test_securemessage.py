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
Unit Tests for rpc 'securemessage' functions.
"""

import logging

from oslo.config import cfg

from openstack.common import jsonutils
from openstack.common.rpc import common as rpc_common
from openstack.common.rpc import securemessage as rpc_secmsg
from tests import utils as test_utils


FLAGS = cfg.CONF
LOG = logging.getLogger(__name__)


class RpcCryptoTestCase(test_utils.BaseTestCase):

    def test_KEYcache(self):
        cache = rpc_secmsg.KEYcache(wipe=True)

        # check empty cache returns noting
        keys = cache.get('sek,foo,bar')
        self.assertIsNone(keys)

        sek = rpc_secmsg.KEYstore('foo', 'bar').format_sek('skey', 'ekey')

        #add entry in the cache
        cache.put('sek,foo,bar', 2000000000, sek)

        #chck it returns the object
        keys = cache.get('sek,foo,bar')
        self.assertEqual(keys, sek)

        #check inverted source/target returns nothing
        keys = cache.get('sek,bar,foo')
        self.assertIsNone(keys)

        #add expired entry in the cache
        cache.put('sek,foo,bar', 1000000000, sek)

        #check expired entries are not returned
        keys = cache.get('sek,foo,bar')
        self.assertIsNone(keys)

    def _test_secure_message(self, data, encrypt):
        msg = {'message': 'body'}

        send = rpc_secmsg.SecureMessage(data['source'], None, data['send_key'],
                                        encrypt, enctype=data['cipher'],
                                        hashtype=data['hash'])
        recv = rpc_secmsg.SecureMessage(data['target'], None, data['recv_key'],
                                        encrypt, enctype=data['cipher'],
                                        hashtype=data['hash'])

        # Adds test keys in cache, we do it twice, once for client side use,
        # then for server side use as we run both in the same process
        store = rpc_secmsg.KEYstore(data['source'], data['target'])
        keys = store.format_ticket(data['target'], data['skey'],
                                   data['ekey'], data['esek'])
        store.put_keys('ticket', 2000000000, keys)
        keys = store.format_sek(data['skey'], data['ekey'])
        store.put_keys('sek', 2000000000, keys)

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
            'skey': '\x0fS\xcb\xf5x\xe2\x83X%\x0b\xe5\xe5\x92\xd7\x0e4',
            'ekey': 'L\x85\x11\x9b9\xa6\x9a\xaa]\xcb4\xfa\x9f\xa0\xf7\xeb',
            'esek': ('DbfMIyYVFHYPyeUjQY0AwDAz6roe6Y2qqrNTenJJwGE8'
                     'pyN8QiRBxTND8M2xVvyanIbwmW8h1FhH7T1GHD4hy8eE'
                     'l50IexWzlEbMks8kuFflCpVhTdE40W+NtqcGc9C58Oy/'
                     'boTa1IU5Yk60EjU5Bp+t6ogBBTA5A/8s3J45udY=')
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
            'skey': "$\xc4\xaf\xa0\x1d\xee'\x8a",
            'ekey': ';\xeaw\xf6d\xd6\xa1I',
            'esek': ('feykZWWznbw4Vb/9bwoKtgMSm5UBSEMl'
                     'pJ5YekWiQM0SYU3Pdn1pg/96tGL7IjXP'
                     'W76AHRX8dpmPsAlnJwUil91EujVqmEK3'
                     'ekTUua3nf4DBm7pJA9kmUAkdKfI+d5qH')
        }
        # Test signing only first
        self._test_secure_message(foo_to_baz_md5_des, False)
        # Test encryption too
        self._test_secure_message(foo_to_baz_md5_des, True)

    #TODO(simo): test fetching key from file
