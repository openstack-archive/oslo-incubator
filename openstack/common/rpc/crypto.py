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

import time
import base64
import errno
from random import SystemRandom

from oslo.config import cfg

from openstack.common.gettextutils import _
from openstack.common import jsonutils
from openstack.common import log as logging

from openstack.common import cryptoutils

CONF = cfg.CONF
LOG = logging.getLogger(__name__)


class SecureMessageException(Exception):
    """Generic Exception for Secure Messages"""

    message = _("An unknown Secure Message related exception occurred.")


class SharedKeyNotFound(SecureMessageException):
    """No shared key was found and no other external authentication mechanism
    is available"""

    message = _("Shared Key Not Found")


class InvalidMetadata(SecureMessageException):
    """The metadata is invalid"""

    def __init__(self, errmsg):
        message = _("Invalid metadata object: %s") % errmsg
        super(SecureMessageException, self).__init__(message)


class InvalidSignature(SecureMessageException):
    """Signature validation failed"""

    message = _('Failed to validate signature')


class UnknownDestinationName(SecureMessageException):
    """The Destination name is unknown to us."""

    message = _('Invalid destination name')


class InvalidEncryptedSEKToken(SecureMessageException):
    """The Encrypted SEK token could not be successfully handled."""

    message = _('Invalid Token')


_sek_cache = dict()


class SEKcache(object):
    """
    Simple cache for SEK values.

    This is a global simple cache implementation.
    """

    def __init__(self, wipe=False):
        if wipe:
            self._wipe_cache()
        self._kvps = self._get_global_cache()

    @staticmethod
    def _wipe_cache():
        _sek_cache.clear()

    @staticmethod
    def _get_global_cache():
        return _sek_cache

    def _get_key(self, source, target):
        return source + '\x00' + target

    def put(self, source, target, expiration, sek):
        key = self._get_key(source, target)
        if key in self._kvps:
            del self._kvps[key]
        self._kvps[key] = (expiration, sek)

    def get(self, source, target):
        key = self._get_key(source, target)
        if key in self._kvps:
            val = self._kvps[key]
            if val[0] > time.time():
                return val[1]
            else:
                del self._kvps[key]

        return None


SKEY = 0
EKEY = 1
ESEK = 2


class SEKstore(object):
    """A storage class for Signing and Encryption Keys.

    This class creates an object that holds Signing Keys, and optionally also
    Encryption Keys and Encrypted SEK Tokens.

    :param source: the source service
    :param target: the destination service
    """

    def __init__(self, source, target):
        self.source = source
        self.target = target

    @property
    def sek(self):
        """Returns a tuple containing skey, ekey and esek, or None if
        nothing was found."""
        return SEKcache().get(self.source, self.target)

    def put(self, expire, skey, ekey=None, esek=None):
        """Set all keys anew.

        :param expire: Expiration time in seconds since EPOCH
        :param skey: Signing key
        :param ekey: Encryption Key (optional)
        :param esek: Target ESEK Token (optional)
        """
        SEKcache().put(self.source, self.target, expire, (skey, ekey, esek))


class SecureMessage(object):
    """A Secure Message object.

    This class creates a signing/encryption facility for RPC messages.
    It encapsulates all the necessary crypto primitives to insulate
    regular code from the intricacies of message authentication, validation
    and optionally encryption.
    """

    def __init__(self, myname, mykey=None, encrypt=False,
                 enctype='AES', hashtype='SHA256'):
        self.name = myname
        self.key = mykey
        self.encrypt = encrypt
        self.nonce = None
        self.crypto = cryptoutils.SymmetricCrypto(enctype, hashtype)
        self.hkdf = cryptoutils.HKDF(hashtype)

        if not self.key:
            if not CONF.secure_message_key:
                raise SharedKeyNotFound("Missing secure_message_key option.")
            opt = CONF.secure_message_key.strip()
            keys = None
            if opt.startswith('key:'):
                keys = opt[len('key:'):].split(',')
            elif opt.startswith('file:'):
                try:
                    f = open(opt[len('file://'):], 'r')
                    keys = f.readlines()
                    f.close()
                except IOError as e:
                    if e.errno == errno.ENOENT:
                        raise SharedKeyNotFound(e.strerror)
                    else:
                        raise
            for k in keys:
                svc, key = k.split(':')
                if myname == svc or myname.startswith(svc + '.'):
                    self.key = base64.b64decode(key)
                    break
            if self.key is None:
                raise SharedKeyNotFound('Invalid secure_message_key format')

    def _decode_esek(self, key, source, target, timestamp, esek):
        """This function decypts the esek buffer passed in and returns a
        SEKstore to be used to check and decrypt the received message.

        :param source: The name of the source service
        :param traget: The name of the target service
        :param timestamp: The incoming message timestamp
        :param esek: a base64 encoded encrypted block containing a JSON string
        """
        rkey = None

        try:
            s = self.crypto.decrypt(key, esek)
            j = jsonutils.loads(s)

            rkey = base64.b64decode(j['key'])
            expiration = j['timestamp'] + j['ttl']
            if j['timestamp'] > timestamp or timestamp > expiration:
                raise

        except:
            raise InvalidEncryptedSEKToken()

        info = source + '\x00' + target + '\x00' + str(j['timestamp'])

        sek = self.hkdf.expand(rkey, info, len(key) * 2)

        store = SEKstore(source, target)
        store.put(expiration, sek[len(key):], sek[:len(key)])
        return store

    def _get_sek(self, target):
        """This function will check if we already have a SEK for the specified
        target in the cache, or will go and try to fetch a new SEK from the key
        server.

        :param source: The name of the source service
        :param target: The name of the target service
        """
        store = SEKstore(self.name, target)
        sek = store.sek
        if sek is None:
            # FIXME: fetch from server
            raise UnknownDestinationName()
        return sek

    def _get_nonce(self):
        """We keep a single counter per instance, as it is so huge we can't
        possibly cycle through within 1/110 of a second anyway.
        """

        # Lazy initialize, for now get a random value, multiply by 2^32 and
        # use it as the nonce base. The counter itself will rotate after
        # 2^32 increments. TODO: Assure no collisions for 'base' if multiple
        # instantiations happen on the same host.
        if self.nonce is None:
            sr = SystemRandom()
            base = 1L * sr.randint(0, 0xffffffff)
            self.nonce = [base, 0]

        # Increment counter and wrap at 2^32
        self.nonce[1] += 1
        if self.nonce[1] > 0xffffffff:
            self.nonce[1] = 0

        # Return base + counter
        return self.nonce[0] + self.nonce[1]

    def encode(self, version, target, json_msg):
        """This is the main encoding function.

        It takes a target and a message and returns a tuple consisting of a
        JSON serialized metadata object, a JSON serialized (and optionally
        encrypted) message, and a signature.

        :param version: the current envelope version
        :param target: The name of the target service (usually with hostname)
        :param raw_msg: a raw message object
        """
        sek = self._get_sek(target)

        metadata = jsonutils.dumps({'source': self.name,
                                    'destination': target,
                                    'timestamp': time.time(),
                                    'nonce': self._get_nonce(),
                                    'esek': sek[ESEK],
                                    'encryption': self.encrypt})

        message = json_msg
        if self.encrypt:
            message = self.crypto.encrypt(sek[EKEY], message)

        signature = self.crypto.sign(sek[SKEY], version + metadata + message)

        return (metadata, message, signature)

    def decode(self, version, metadata, message, signature):
        """This is the main decoding function.

        It takes a version, metadata, message and signature strings and
        returns a tuple with a (decrypted) message and metadata or raises
        an exception in case of error.

        :param version: the current envelope version
        :param metadata: a JSON serialized object with metadata for validaiton
        :param message: a JSON serialized (base64 encoded encrypted) message
        :param signture: a base64 encoded signature
        """
        md = jsonutils.loads(metadata)

        if not ('source' in md):
            raise InvalidMetadata('Source is missing')
        if not ('destination' in md):
            raise InvalidMetadata('Destination is missing')
        if not ('timestamp' in md):
            raise InvalidMetadata('Timestamp is missing')
        if not ('nonce' in md):
            raise InvalidMetadata('Nonce is missing')
        if not ('esek' in md):
            raise InvalidMetadata('Encrypted SEK Token is missing')
        if not ('encryption' in md):
            raise InvalidMetadata('Encryption flag is missing')

        if md['destination'] != self.name:
            # TODO handle group keys by checking target
            raise UnknownDestinationName()

        try:
            store = self._decode_esek(self.key,
                                      md['source'], md['destination'],
                                      md['timestamp'], md['esek'])
        except:
            raise InvalidMetadata('Failed to decode ESEK')

        sek = store.sek
        s = self.crypto.sign(sek[SKEY], version + metadata + message)

        if s != signature:
            raise InvalidSignature()

        if md['encryption'] is True:
            msg = self.crypto.decrypt(sek[EKEY], message)
        else:
            msg = message

        msg = jsonutils.loads(msg)

        return (md, msg)
