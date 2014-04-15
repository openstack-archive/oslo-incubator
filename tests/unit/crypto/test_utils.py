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
Unit Tests for crypto utils.
"""

from oslotest import base as test_base

from openstack.common.crypto import utils as cryptoutils


class CryptoUtilsTestCase(test_base.BaseTestCase):

    # Uses Tests from RFC5869
    def _test_HKDF(self, ikm, prk, okm, length,
                   salt=None, info='', hashtype='SHA256'):
        hkdf = cryptoutils.HKDF(hashtype=hashtype)

        tprk = hkdf.extract(ikm, salt=salt)
        self.assertEqual(prk, tprk)

        tokm = hkdf.expand(prk, info, length)
        self.assertEqual(okm, tokm)

    def test_HKDF_1(self):
        ikm = '\x0b' * 22
        salt = ''.join(map(lambda x: chr(x), range(0x00, 0x0d)))
        info = ''.join(map(lambda x: chr(x), range(0xf0, 0xfa)))
        length = 42

        prk = ('\x07\x77\x09\x36\x2c\x2e\x32\xdf\x0d\xdc\x3f\x0d\xc4\x7b'
               '\xba\x63\x90\xb6\xc7\x3b\xb5\x0f\x9c\x31\x22\xec\x84\x4a'
               '\xd7\xc2\xb3\xe5')

        okm = ('\x3c\xb2\x5f\x25\xfa\xac\xd5\x7a\x90\x43\x4f\x64\xd0\x36'
               '\x2f\x2a\x2d\x2d\x0a\x90\xcf\x1a\x5a\x4c\x5d\xb0\x2d\x56'
               '\xec\xc4\xc5\xbf\x34\x00\x72\x08\xd5\xb8\x87\x18\x58\x65')

        self._test_HKDF(ikm, prk, okm, length, salt, info)

    def test_HKDF_2(self):
        ikm = ''.join(map(lambda x: chr(x), range(0x00, 0x50)))
        salt = ''.join(map(lambda x: chr(x), range(0x60, 0xb0)))
        info = ''.join(map(lambda x: chr(x), range(0xb0, 0x100)))
        length = 82

        prk = ('\x06\xa6\xb8\x8c\x58\x53\x36\x1a\x06\x10\x4c\x9c\xeb\x35'
               '\xb4\x5c\xef\x76\x00\x14\x90\x46\x71\x01\x4a\x19\x3f\x40'
               '\xc1\x5f\xc2\x44')

        okm = ('\xb1\x1e\x39\x8d\xc8\x03\x27\xa1\xc8\xe7\xf7\x8c\x59\x6a'
               '\x49\x34\x4f\x01\x2e\xda\x2d\x4e\xfa\xd8\xa0\x50\xcc\x4c'
               '\x19\xaf\xa9\x7c\x59\x04\x5a\x99\xca\xc7\x82\x72\x71\xcb'
               '\x41\xc6\x5e\x59\x0e\x09\xda\x32\x75\x60\x0c\x2f\x09\xb8'
               '\x36\x77\x93\xa9\xac\xa3\xdb\x71\xcc\x30\xc5\x81\x79\xec'
               '\x3e\x87\xc1\x4c\x01\xd5\xc1\xf3\x43\x4f\x1d\x87')

        self._test_HKDF(ikm, prk, okm, length, salt, info)

    def test_HKDF_3(self):
        ikm = '\x0b' * 22
        length = 42

        prk = ('\x19\xef\x24\xa3\x2c\x71\x7b\x16\x7f\x33\xa9\x1d\x6f\x64'
               '\x8b\xdf\x96\x59\x67\x76\xaf\xdb\x63\x77\xac\x43\x4c\x1c'
               '\x29\x3c\xcb\x04')

        okm = ('\x8d\xa4\xe7\x75\xa5\x63\xc1\x8f\x71\x5f\x80\x2a\x06\x3c'
               '\x5a\x31\xb8\xa1\x1f\x5c\x5e\xe1\x87\x9e\xc3\x45\x4e\x5f'
               '\x3c\x73\x8d\x2d\x9d\x20\x13\x95\xfa\xa4\xb6\x1a\x96\xc8')

        self._test_HKDF(ikm, prk, okm, length)

    def test_HKDF_4(self):
        ikm = '\x0b' * 11
        salt = ''.join(map(lambda x: chr(x), range(0x00, 0x0d)))
        info = ''.join(map(lambda x: chr(x), range(0xf0, 0xfa)))
        length = 42

        prk = ('\x9b\x6c\x18\xc4\x32\xa7\xbf\x8f\x0e\x71\xc8\xeb\x88\xf4'
               '\xb3\x0b\xaa\x2b\xa2\x43')

        okm = ('\x08\x5a\x01\xea\x1b\x10\xf3\x69\x33\x06\x8b\x56\xef\xa5'
               '\xad\x81\xa4\xf1\x4b\x82\x2f\x5b\x09\x15\x68\xa9\xcd\xd4'
               '\xf1\x55\xfd\xa2\xc2\x2e\x42\x24\x78\xd3\x05\xf3\xf8\x96')

        self._test_HKDF(ikm, prk, okm, length, salt, info, hashtype='SHA')

    def test_HKDF_5(self):
        ikm = ''.join(map(lambda x: chr(x), range(0x00, 0x50)))
        salt = ''.join(map(lambda x: chr(x), range(0x60, 0xb0)))
        info = ''.join(map(lambda x: chr(x), range(0xb0, 0x100)))
        length = 82

        prk = ('\x8a\xda\xe0\x9a\x2a\x30\x70\x59\x47\x8d\x30\x9b\x26\xc4'
               '\x11\x5a\x22\x4c\xfa\xf6')

        okm = ('\x0b\xd7\x70\xa7\x4d\x11\x60\xf7\xc9\xf1\x2c\xd5\x91\x2a'
               '\x06\xeb\xff\x6a\xdc\xae\x89\x9d\x92\x19\x1f\xe4\x30\x56'
               '\x73\xba\x2f\xfe\x8f\xa3\xf1\xa4\xe5\xad\x79\xf3\xf3\x34'
               '\xb3\xb2\x02\xb2\x17\x3c\x48\x6e\xa3\x7c\xe3\xd3\x97\xed'
               '\x03\x4c\x7f\x9d\xfe\xb1\x5c\x5e\x92\x73\x36\xd0\x44\x1f'
               '\x4c\x43\x00\xe2\xcf\xf0\xd0\x90\x0b\x52\xd3\xb4')

        self._test_HKDF(ikm, prk, okm, length, salt, info, hashtype='SHA')

    def test_HKDF_6(self):
        ikm = '\x0b' * 22
        length = 42

        prk = ('\xda\x8c\x8a\x73\xc7\xfa\x77\x28\x8e\xc6\xf5\xe7\xc2\x97'
               '\x78\x6a\xa0\xd3\x2d\x01')

        okm = ('\x0a\xc1\xaf\x70\x02\xb3\xd7\x61\xd1\xe5\x52\x98\xda\x9d'
               '\x05\x06\xb9\xae\x52\x05\x72\x20\xa3\x06\xe0\x7b\x6b\x87'
               '\xe8\xdf\x21\xd0\xea\x00\x03\x3d\xe0\x39\x84\xd3\x49\x18')

        self._test_HKDF(ikm, prk, okm, length, hashtype='SHA')

    def test_HKDF_7(self):
        ikm = '\x0c' * 22
        length = 42

        prk = ('\x2a\xdc\xca\xda\x18\x77\x9e\x7c\x20\x77\xad\x2e\xb1\x9d'
               '\x3f\x3e\x73\x13\x85\xdd')

        okm = ('\x2c\x91\x11\x72\x04\xd7\x45\xf3\x50\x0d\x63\x6a\x62\xf6'
               '\x4f\x0a\xb3\xba\xe5\x48\xaa\x53\xd4\x23\xb0\xd1\xf2\x7e'
               '\xbb\xa6\xf5\xe5\x67\x3a\x08\x1d\x70\xcc\xe7\xac\xfc\x48')

        self._test_HKDF(ikm, prk, okm, length, hashtype='SHA')

    def test_HKDF_8(self):
        ikm = '\x0b' * 22
        prk = ('\x19\xef\x24\xa3\x2c\x71\x7b\x16\x7f\x33\xa9\x1d\x6f\x64'
               '\x8b\xdf\x96\x59\x67\x76\xaf\xdb\x63\x77\xac\x43\x4c\x1c'
               '\x29\x3c\xcb\x04')

        # Just testing HKDFOutputLengthTooLong is returned
        try:
            self._test_HKDF(ikm, prk, None, 1000000)
        except cryptoutils.HKDFOutputLengthTooLong:
            pass

    def test_SymmetricCrypto_encrypt_string(self):
        msg = 'Plain Text'

        skc = cryptoutils.SymmetricCrypto()
        key = skc.new_key(16)
        cipher = skc.encrypt(key, msg)
        plain = skc.decrypt(key, cipher)
        self.assertEqual(msg, plain)

    def test_SymmetricCrypto_encrypt_blocks(self):
        cb = 16
        et = 'AES'

        skc = cryptoutils.SymmetricCrypto(enctype=et)
        key = skc.new_key(16)
        msg = skc.new_key(cb * 2)

        for i in range(cb * 2):
            cipher = skc.encrypt(key, msg[0:i], b64encode=False)
            plain = skc.decrypt(key, cipher, b64decode=False)
            self.assertEqual(msg[0:i], plain)

    def test_SymmetricCrypto_signing(self):
        msg = 'Authenticated Message'
        signature = 'KWjl6i30RMjc5PjnaccRwTPKTRCWM6sPpmGS2bxm5fQ='
        skey = 'L\xdd0\xf3\xb4\xc6\xe2p\xef\xc7\xbd\xaa\xc9eNC'

        skc = cryptoutils.SymmetricCrypto()
        validate = skc.sign(skey, msg)
        self.assertEqual(signature, validate)
