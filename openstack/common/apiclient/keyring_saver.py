# vim: tabstop=4 shiftwidth=4 softtabstop=4

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


HAS_KEYRING = False
all_errors = (ValueError,)
try:
    import keyring
    HAS_KEYRING = True
    try:
        if isinstance(keyring.get_keyring(), keyring.backend.GnomeKeyring):
            import gnomekeyring
            all_errors = (ValueError,
                          gnomekeyring.IOError,
                          gnomekeyring.NoKeyringDaemonError)
    except:  # flake8: noqa
        pass
except ImportError:
    pass


class TokenKeyringSaver(object):
    """A class for saving OpenStack token in a keyring."""

    service = "openstackclient_auth"

    def __init__(self, key, service=None):
        self.key = key
        self.service = service or self.service
        self.token = None

    @staticmethod
    def make_key(auth_url, tenant_id, username, region_name):
        keys = [
            auth_url,
            tenant_id,
            username,
            region_name,
        ]
        for (index, key) in enumerate(keys):
            if key is None:
                keys[index] = '?'
            else:
                keys[index] = str(keys[index])
        return "/".join(keys)

    def save(self, http_client):
        if not HAS_KEYRING:
            return
        token = str(http_client.token or http_client.auth_response.token)
        if not token:
            raise ValueError("Unable to save an empty token")
        if token == self.token:
            # Nothing changed....
            return
        keyring.set_password(self.service, self.key, token)
        self.token = token

    def load(self):
        self.token = None
        if not HAS_KEYRING:
            return False
        try:
            block = keyring.get_password(self.service, self.key)
            if block:
                self.token = block
        except all_errors:
            pass

        if not self.token:
            return False
        return True
