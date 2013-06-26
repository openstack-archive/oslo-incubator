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
import errno
import os
import struct
import time

from oslo.config import cfg
import requests

from openstack.common.crypto import utils as cryptoutils
from openstack.common.gettextutils import _  # noqa
from openstack.common import jsonutils
from openstack.common import log as logging


CONF = cfg.CONF
LOG = logging.getLogger(__name__)


class SecureMessageException(Exception):
    """Generic Exception for Secure Messages."""

    message = _("An unknown Secure Message related exception occurred.")


class SharedKeyNotFound(SecureMessageException):
    """No shared key was found and no other external authentication mechanism
    is available.
    """

    message = _("Shared Key Not Found")


class InvalidMetadata(SecureMessageException):
    """The metadata is invalid."""

    def __init__(self, errmsg):
        message = _("Invalid metadata object: %s") % errmsg
        super(SecureMessageException, self).__init__(message)


class InvalidSignature(SecureMessageException):
    """Signature validation failed."""

    message = _('Failed to validate signature')


class UnknownDestinationName(SecureMessageException):
    """The Destination name is unknown to us."""

    message = _('Invalid destination name')


class InvalidEncryptedTicket(SecureMessageException):
    """The Encrypted Ticket could not be successfully handled."""

    message = _('Invalid Ticket')


class InvalidExpiredTicket(SecureMessageException):
    """The ticket received is already expired."""

    message = _('Expired ticket')


class InvalidKDSReply(SecureMessageException):
    """The KDS Reply could not be successfully verified."""

    message = _('Invalid KDS Reply')


class CommunicationError(SecureMessageException):
    """The Communication with the KDS failed."""

    def __init__(self, errmsg):
        message = _("Communication Error: %s") % errmsg
        super(SecureMessageException, self).__init__(message)


class InvalidArgument(SecureMessageException):
    """Bad initialization argument."""

    def __init__(self, errmsg):
        message = _("Invalid argument: %s") % errmsg
        super(SecureMessageException, self).__init__(message)


_key_cache = dict()


class KEYcache(object):
    """Simple cache for Keys.

    This is a global simple cache implementation.
    """

    def __init__(self, wipe=False):
        if wipe:
            self._wipe_cache()
        self._kvps = self._get_global_cache()

    @staticmethod
    def _wipe_cache():
        _key_cache.clear()

    @staticmethod
    def _get_global_cache():
        return _key_cache

    def put(self, name, expiration, keys):
        self._kvps[name] = (expiration, keys)

    def get(self, name):
        if name in self._kvps:
            expiration, keys = self._kvps[name]
            if expiration > time.time():
                return keys
            else:
                del self._kvps[name]

        return None


class KEYstore(object):
    """A storage class for Signing and Encryption Keys.

    This class creates an object that holds Generic Keys like Signing
    Keys, Encryption Keys, Encrypted SEK Tickets ...

    :param source: the source service
    :param target: the destination service
    """

    type_sek = 'sek'
    type_ticket = 'ticket'
    type_group_key = 'group_key'

    def __init__(self, source, target):
        self.name = '%s,%s' % (source, target)

    def _get_key_name(self, key_type):
        return '%s,%s' % (self.name, key_type)

    def get_keys(self, key_type):
        """Returns a tuple containing stored keys, or None if
        nothing was found.

        :param key_type: The type of key to retrieve
        """

        keys = KEYcache().get(self._get_key_name(key_type))
        return keys

    def put_keys(self, key_type, expire, keys):
        """Set all keys anew.

        :param key_type: The type of key to store
        :param expire: Expiration time in seconds since Epoch
        :param keys: The keys associated with the source/target pair
        """

        if key_type != keys['type']:
            raise ValueError('Mismatched key type')

        KEYcache().put(self._get_key_name(key_type), expire, keys)

    def format_sek(self, skey, ekey):
        return {'type': 'sek', 'skey': skey, 'ekey': ekey}

    def format_ticket(self, dest, skey, ekey, esek):
        # Explicit destination as it may be qualified with a generation
        # number for group tickets
        return {'type': 'ticket', 'destination': dest,
                'skey': skey, 'ekey': ekey, 'esek': esek}

    def format_group_key(self, generation, key):
        return {'type': 'group_key', 'generation': generation, 'key': key}


class KDSClient(object):

    USER_AGENT = 'oslo-incubator/rpc'

    def __init__(self, endpoint=None, timeout=None):
        """A KDS Client class."""

        self.endpoint = endpoint
        if timeout is not None:
            self.timeout = float(timeout)
        else:
            self.timeout = None

    def make_request(self, request, url=None, redirects=10):
        """Send an HTTP request.

        Wraps around requests to handle redirects and common errors.
        """
        #do not allow too many redirects
        if redirects <= 0:
            msg = "Too many redirections, giving up!"
            raise CommunicationError(msg)

        if url.startswith('/'):
            if self.endpoint is None or len(self.endpoint) == 0:
                raise CommunicationError('Endpoint not configured')
            url = self.endpoint + url

        # Copy the kwargs so we can reuse the original in case of redirects
        req_kwargs = dict()
        req_kwargs['headers'] = dict()
        req_kwargs['headers']['User-Agent'] = self.USER_AGENT
        req_kwargs['headers']['Content-Type'] = 'application/json'
        req_kwargs['data'] = jsonutils.dumps({'request': request})
        if self.timeout is not None:
            req_kwargs['timeout'] = self.timeout

        try:
            resp = requests.get(url, **req_kwargs)
        except requests.ConnectionError:
            msg = "Unable to establish connection to %s" % url
            raise CommunicationError(msg)

        if resp.status_code in (301, 302, 305):
            # Redirected. Reissue the request to the new location.
            url = resp.headers['location']
            return self.make_request(request, url, redirects - 1)
        elif resp.status_code != 200:
            msg = "Request returned failure status: %s (%s)"
            raise CommunicationError(msg % (resp.status_code, resp.text))

        if resp.text:
            try:
                body = jsonutils.loads(resp.text)
                reply = body['reply']
            except (ValueError, TypeError):
                msg = "Failed to decode reply: %s" % resp.text
                raise CommunicationError(msg)
        else:
            msg = "No reply data was returned."
            raise CommunicationError(msg)

        return reply

    def get_ticket(self, request):
        return self.make_request(request, url='/kds/ticket')

    def get_group_key(self, request):
        return self.make_request(request, url='/kds/group_key')


class SecureMessage(object):
    """A Secure Message object.

    This class creates a signing/encryption facility for RPC messages.
    It encapsulates all the necessary crypto primitives to insulate
    regular code from the intricacies of message authentication, validation
    and optionally encryption.

    :param name: The endpoint name, tihs is used to source signing keys, and
                   verify incoming messages.
    :param kds_endpoint: URL of the KDS server to fetch tickets.
    :param key: (optional) explicitly pass in endpoint private key.
                  If not provided it will be sourced from the service config
    :param encrypt: (defaults to False) Whether to encrypt messages
    :param enctype: (defaults to AES) Cipher to use
    :param hashtype: (defaults to SHA256) Hash function to use for signatures
    """

    def __init__(self, name, kds_endpoint=None, key=None, encrypt=False,
                 enctype='AES', hashtype='SHA256', group=None):

        if not name:
            raise InvalidArgument("Name cannot be None or Empty")

        self.name = name
        self.key = key
        self.encrypt = encrypt
        self.nonce = None
        self.group = group
        self.crypto = cryptoutils.SymmetricCrypto(enctype, hashtype)
        self.hkdf = cryptoutils.HKDF(hashtype)
        self.kds = KDSClient(kds_endpoint)

        if self.key is None:
            if not CONF.secure_message_key:
                raise SharedKeyNotFound("Missing secure_message_key option.")
            opt = CONF.secure_message_key.strip()
            keys = None
            if opt.startswith('key:'):
                keys = opt[len('key:'):].split(',')
            elif opt.startswith('file:'):
                try:
                    with open(opt[len('file://'):], 'r') as f:
                        keys = f.readlines()
                except IOError as e:
                    if e.errno == errno.ENOENT:
                        raise SharedKeyNotFound(e.strerror)
                    else:
                        raise
            for k in keys:
                svc, key = k.split(':')
                if name == svc or name.startswith(svc + '.'):
                    self.key = base64.b64decode(key)
                    break
            if self.key is None:
                raise SharedKeyNotFound('Invalid secure_message_key format')

        if self.group is None and '.' in name:
            self.group = self.name.split('.')[0]

    def _split_key(key, size):
        sig_key = key[:size]
        enc_key = key[size:]
        return sig_key, enc_key

    def _decode_esek(self, key, source, target, timestamp, esek):
        """This function decrypts the esek buffer passed in and returns a
        KEYstore to be used to check and decrypt the received message.

        :param key: The key to use to decrypt the ticket (esek)
        :param source: The name of the source service
        :param traget: The name of the target service
        :param timestamp: The incoming message timestamp
        :param esek: a base64 encoded encrypted block containing a JSON string
        :param generation: Key generation number, for group keys
        """
        rkey = None

        try:
            s = self.crypto.decrypt(key, esek)
            j = jsonutils.loads(s)

            rkey = base64.b64decode(j['key'])
            expiration = j['timestamp'] + j['ttl']
            if j['timestamp'] > timestamp or timestamp > expiration:
                raise InvalidExpiredTicket()

        except Exception:
            raise InvalidEncryptedTicket()

        info = '%s,%s,%s' % (source, target, str(j['timestamp']))

        sek = self.hkdf.expand(rkey, info, len(key) * 2)

        store = KEYstore(source, target)
        skey, ekey = self._split_key(sek, len(key))
        store.put_keys(KEYstore.type_sek, expiration,
                       store.format_sek(skey, ekey)
        return store

    def _prep_req_metadata(self, target):
        md = dict()
        md['requestor'] = self.name
        md['target'] = target
        md['timestamp'] = time.time()
        md['nonce'] = struct.unpack('Q', os.urandom(8))[0]
        metadata = base64.b64encode(jsonutils.dumps(md))

        # sign metadata
        signature = self.crypto.sign(self.key, metadata)

        return metadata, signature

    def _check_signature(self, metadata, payload, signature):
        sig = self.crypto.sign(self.key, metadata + payload)
        if sig != signature:
            raise InvalidKDSReply()

    def _get_ticket(self, target):
        """This function will check if we already have a SEK for the specified
        target in the cache, or will go and try to fetch a new SEK from the key
        server.

        :param target: The name of the target service
        """
        store = KEYstore(self.name, target)
        tkt = store.get_keys('ticket')

        if tkt is not None:
            return tkt

        metadata, signature = self._prep_req_metadata(target)
        reply = self.kds.get_ticket({'metadata': metadata,
                                     'signature': signature})
        self._check_signature(reply['metadata'],
                              reply['ticket'],
                              reply['signature'])

        md = jsonutils.loads(base64.b64decode(reply['metadata']))
        if (md['source'] != self.name or
            md['expiration'] < time.time() or
            (md['destination'] != target and
             md['destination'].split(':')[0] != target)):
            raise InvalidKDSReply()

        #return ticket data
        tkt = self.crypto.decrypt(self.key, reply['ticket'])
        tkt = jsonutils.loads(tkt)

        store.put_keys(KEYstore.type_ticket, md['expiration'],
                       store.format_ticket(md['destination'],
                                           base64.b64decode(tkt['skey']),
                                           base64.b64decode(tkt['ekey']),
                                           tkt['esek']))
        return store.get_keys('ticket')

    def _get_group_key(self, target):
        store = KEYstore(self.name, target)
        gkey = store.get_keys('group_key')
        if gkey is not None:
            return gkey['key']

        metadata, signature = self._prep_req_metadata(target)
        reply = self.kds.get_group_key({'metadata': metadata,
                                        'signature': signature})
        self._check_signature(reply['metadata'],
                              reply['group_key'],
                              reply['signature'])

        md = jsonutils.loads(base64.b64decode(reply['metadata']))
        if ((md['source'] != self.name or
             md['destination'] != target or
             md['expiration'] < time.time())):
            raise InvalidKDSReply()

        #return group key
        group_key = self.crypto.decrypt(self.key, reply['group_key'])
        store.put_keys(KEYstore.type_group_key, md['expiration'],
                       store.format_group_key(long(target.split(':')[1]),
                                              group_key))
        return group_key

    def _get_nonce(self):
        """We keep a single counter per instance, as it is so huge we can't
        possibly cycle through within 1/100 of a second anyway.
        """

        # Lazy initialize, for now get a random value, multiply by 2^32 and
        # use it as the nonce base. The counter itself will rotate after
        # 2^32 increments.
        if self.nonce is None:
            self.nonce = [struct.unpack('I', os.urandom(4))[0], 0]

        # Increment counter and wrap at 2^32
        self.nonce[1] += 1
        if self.nonce[1] > 0xffffffff:
            self.nonce[1] = 0

        # Return base + counter
        return long((self.nonce[0] * 0xffffffff)) + self.nonce[1]

    def encode(self, version, target, json_msg):
        """This is the main encoding function.

        It takes a target and a message and returns a tuple consisting of a
        JSON serialized metadata object, a JSON serialized (and optionally
        encrypted) message, and a signature.

        :param version: the current envelope version
        :param target: The name of the target service (usually with hostname)
        :param json_msg: a serialized json message object
        """
        ticket = self._get_ticket(target)

        metadata = jsonutils.dumps({'source': self.name,
                                    'destination': ticket['destination'],
                                    'timestamp': time.time(),
                                    'nonce': self._get_nonce(),
                                    'esek': ticket['esek'],
                                    'encryption': self.encrypt})

        message = json_msg
        if self.encrypt:
            message = self.crypto.encrypt(ticket['ekey'], message)

        signature = self.crypto.sign(ticket['skey'],
                                     version + metadata + message)

        return (metadata, message, signature)

    def decode(self, version, metadata, message, signature):
        """This is the main decoding function.

        It takes a version, metadata, message and signature strings and
        returns a tuple with a (decrypted) message and metadata or raises
        an exception in case of error.

        :param version: the current envelope version
        :param metadata: a JSON serialized object with metadata for validation
        :param message: a JSON serialized (base64 encoded encrypted) message
        :param signature: a base64 encoded signature
        """
        md = jsonutils.loads(metadata)

        check_args = ('source', 'destination', 'timestamp',
                      'nonce', 'esek', 'encryption')
        for arg in check_args:
            if arg not in md:
                raise InvalidMetadata('Missing argument "%s"' % arg)

        dkey = None
        if md['destination'] == self.name:
            dkey = self.key
        elif md['destination'].split(':')[0] == self.group:
            dkey = self._get_group_key(md['destination'])
        else:
            raise UnknownDestinationName()

        try:
            store = self._decode_esek(dkey,
                                      md['source'], md['destination'],
                                      md['timestamp'], md['esek'])
        except InvalidExpiredTicket:
            raise
        except Exception:
            raise InvalidMetadata('Failed to decode ESEK')

        sek = store.get_keys('sek')
        sig = self.crypto.sign(sek['skey'], version + metadata + message)

        if sig != signature:
            raise InvalidSignature()

        if md['encryption'] is True:
            msg = self.crypto.decrypt(sek['ekey'], message)
        else:
            msg = message

        msg = jsonutils.loads(msg)

        return (md, msg)
