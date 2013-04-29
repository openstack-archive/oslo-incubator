# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2010 Jacob Kaplan-Moss
# Copyright 2011 OpenStack Foundation
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

import getpass
import sys

from openstack.common.apiclient import utils
from openstack.common import strutils


HAS_KEYRING = False
all_errors = ValueError
try:
    import keyring
    HAS_KEYRING = True
    try:
        if isinstance(keyring.get_keyring(), keyring.backend.GnomeKeyring):
            import gnomekeyring
            all_errors = (ValueError,
                          gnomekeyring.IOError,
                          gnomekeyring.NoKeyringDaemonError)
    except Exception:
        pass
except ImportError:
    pass


MAX_PASSWORD_PROMTS = 3


class SecretsHelper(object):
    service = "openstackclient_auth"

    def __init__(self, password, http_client, key=None, service=None):
        self._password = password
        self.http_client = http_client
        self.key = key
        self.service = service or self.service
        self.clear_saved()

    def _validate_string(self, text):
        if text is None or len(text) == 0:
            return False
        return True

    def _prompt_password(self, verify=True):
        pw = None
        if hasattr(sys.stdin, 'isatty') and sys.stdin.isatty():
            # Check for Ctl-D
            try:
                for i in xrange(MAX_PASSWORD_PROMTS):
                    pw1 = getpass.getpass('OS Password: ')
                    if verify:
                        pw2 = getpass.getpass('Please verify: ')
                    else:
                        pw2 = pw1
                    if pw1 == pw2 and self._validate_string(pw1):
                        pw = pw1
                        break
            except EOFError:
                pass
        return pw

    @property
    def password(self):
        if self._validate_string(self._password):
            return self._password
        verify_pass = strutils.bool_from_string(
            utils.env("OS_VERIFY_PASSWORD"))
        return self._prompt_password(verify_pass)

    def _make_key(self):
        if self.key is not None:
            return self.key
        keys = [
            self.http_client.auth_url,
            self.http_client.tenant_id,
            self.http_client.username,
            self.http_client.region_name,
        ]
        for (index, key) in enumerate(keys):
            if key is None:
                keys[index] = '?'
            else:
                keys[index] = str(keys[index])
        self.key = "/".join(keys)
        return self.key

    def save(self, http_client):
        if not HAS_KEYRING:
            return
        (token, auth_url, tenant_id) = (
            http_client.get_token(),
            http_client.auth_url,
            http_client.get_tenant_id())
        if (token == self.token and auth_url == self.auth_url):
            # Nothing changed....
            return
        if not all([auth_url, token, tenant_id]):
            raise ValueError("Unable to save empty auth url/token")
        value = "|".join([str(token),
                          str(auth_url),
                          str(tenant_id)])
        keyring.set_password(self.service, self._make_key(), value)
        self.token, self.auth_url, self.tenant_id = (
            token, auth_url, tenant_id)

    def clear_saved(self):
        self.token, self.auth_url, self.tenant_id = None, None, None

    def load(self, http_client=None):
        self.clear_saved()
        if not HAS_KEYRING:
            return False
        try:
            block = keyring.get_password(self.service, self._make_key())
            if block:
                self.token, self.auth_url, self.tenant_id = block.split(
                    '|', 2)
        except all_errors:
            pass

        if not (self.token and self.auth_url and self.tenant_id):
            return False
        if http_client:
            http_client.token = self.token
            http_client.auth_url = self.auth_url
            http_client.tenant_id = self.tenant_id
        return True
