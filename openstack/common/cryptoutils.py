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

import base64

from Crypto import Random
from Crypto import Cipher
from Crypto import Hash
from Crypto.Hash import HMAC

from openstack.common.gettextutils import _


class CryptoutilsException(Exception):
    """Generic Exception for Crypto utilities"""

    message = _("An unknown error occurred in crypto utils.")


class HKDFOutputLenghtTooLong(CryptoutilsException):
    """The amount of Key Material asked is too much"""

    def __init__(self, requested, permitted):
        message = _("Lenght value=%d is too big,"
                    " max allowed=%d " % (requested, permitted))
        super(CryptoutilsException, self).__init__(message)


class HKDF(object):
    """An HMAC-based Key Derivation Function implementation (RFC5869)

    This class creates an object that allows to use HKDF to derive keys.
    """

    def __init__(self, hashtype='SHA256'):
        self.hashtype = hashtype
        __import__('Crypto.Hash.' + self.hashtype)
        self.Hash = getattr(Hash, self.hashtype)
        self.max_OKM_length = 255 * self.Hash.digest_size

    def extract(self, ikm, salt=None):
        """An extract function that can be used to derive a robust key given
        weak Input Key Material (IKM) which could be a password.
        Returns a pseudorandom key (of HashLen octets)

        :param ikm: input keying material (ex a password)
        :param salt: optional salt value (a non-secret random value)
        """
        if salt is None:
            salt = '\x00' * self.Hash.digest_size

        return HMAC.new(salt, ikm, self.Hash).digest()

    def expand(self, prk, info, length):
        """An expand function that will return arbitrary length output that can
        be used as keys.
        Returns a buffer usable as key material.

        :param prk: a pseudorandom key of at least HashLen octets
        :param info: optional string (can be a zero-length string)
        :param length: length of output keying material (<= 255 * HashLen)
        """
        if length > self.max_OKM_length:
            raise HKDFOutputLenghtTooLong(length, self.max_OKM_length)

        N = (length + self.Hash.digest_size - 1) / self.Hash.digest_size

        okm = ""
        tmp = ""
        for block in range(1, N + 1):
            tmp = HMAC.new(prk, tmp + info + chr(block), self.Hash).digest()
            okm += tmp

        return okm[:length]


class SymmetricCrypto(object):
    """Simmetric Key Crypto object.

    This class creates a Simmetric Key Crypto object that can be used
    to encrypt, decrypt, or sign arbitrary data.

    :param enctype: Encryption Cipher name (default: AES)
    :param hashtype: Hash/HMAC type name (default: SHA256)
    """

    def __init__(self, enctype='AES', hashtype='SHA256'):
        __import__('Crypto.Cipher.' + enctype)
        self.Cipher = getattr(Cipher, enctype)
        __import__('Crypto.Hash.' + hashtype)
        self.Hash = getattr(Hash, hashtype)
        self.HKDF = HKDF(hashtype)

    def new_key(self, size):
        return Random.new().read(size)

    def encrypt(self, key, msg, b64encode=True):
        """Encrypt the provided msg and returns the cyphertext optionally
        base64 encoded.

        Uses AES-128-CBC with a Random IV by default.

        :param key: The Encryption key.
        :param msg: the plain text
        """
        iv = Random.new().read(self.Cipher.block_size)
        cipher = self.Cipher.new(key, self.Cipher.MODE_CBC, iv)

        # CBC mode requires a fixed block size. And msg is always a string,
        # so we'll just append nulls for now
        r = len(msg) % self.Cipher.block_size
        if r != 0:
            msg += '\x00' * (self.Cipher.block_size - r)

        enc = iv + cipher.encrypt(msg)
        if b64encode is True:
            enc = base64.b64encode(enc)
        return enc

    def decrypt(self, key, msg, b64decode=True, strip=True):
        """Decrypts the provided ciphertext, optionally base 64 encoded, and
        returns the plaintext message, after, optionlly, stripping trailing
        nulls (padding).

        Uses AES-128-CBC with an IV by default.

        :param key: The Encryption key.
        :param msg: the ciphetext, the first block is the IV
        """
        if b64decode is True:
            msg = base64.b64decode(msg)
        iv = msg[:self.Cipher.block_size]
        cipher = self.Cipher.new(key, self.Cipher.MODE_CBC, iv)

        plain = cipher.decrypt(msg[self.Cipher.block_size:])
        if strip is True:
            #strip additional nulls added for padding at the end
            plain = plain.rstrip('\x00')
        return plain

    def sign(self, key, msg, b64encode=True):
        """Signs a message string and returns a base64 encoded signature.

        Uses HMAC-SHA-256 by default.

        :param key: The Signing key.
        :param msg: the message to sign.
        """
        h = HMAC.new(key, msg, self.Hash)
        out = h.digest()
        if b64encode is True:
            out = base64.b64encode(out)
        return out
