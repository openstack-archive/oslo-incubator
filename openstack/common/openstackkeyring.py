# Copyright 2011 OpenStack LLC.
# All Rights Reserved
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
#
# vim: tabstop=4 shiftwidth=4 softtabstop=4

"""
Keyring backend for Openstack, to store encrypted password in a file.
"""

from Crypto.Cipher import AES

import crypt
import keyring
import os

KEYRING_FILE = os.path.join(os.path.expanduser('~'), '.openstack-keyring.cfg')


class OpenstackKeyring(keyring.backend.BasicFileKeyring):
    """ Openstack Keyring to store encrypted password """

    filename = KEYRING_FILE

    def supported(self):
        """ applicable for all platforms, but not recommend """
        pass

    def _init_crypter(self):
        """ initialize the crypter using the class name """
        block_size = 32
        padding = '0'

        # init the cipher with the class name, upto block_size
        password = __name__[block_size:]
        password = password + (block_size - len(password) % \
                              block_size) * padding
        return AES.new(password, AES.MODE_CFB)

    def encrypt(self, password):
        """ encrypt the given password """
        crypter = self._init_crypter()
        return crypter.encrypt(password)

    def decrypt(self, password_encrypted):
        """ decrypt the given password """
        crypter = self._init_crypter()
        return crypter.decrypt(password_encrypted)


def os_keyring():
    """ initialize the openstack keyring """
    return keyring.core.load_keyring(None,
             'openstackclient.common.openstackkeyring.OpenstackKeyring')
