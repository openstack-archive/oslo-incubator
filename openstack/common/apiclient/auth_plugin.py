# Copyright 2013 OpenStack Foundation
# Copyright 2013 Spanish National Research Council.
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

import logging
import pkg_resources

from openstack.common.apiclient import exceptions
from openstack.common.apiclient import utils


logger = logging.getLogger(__name__)


_discovered_plugins = {}


def discover_auth_systems():
    """Discover the available auth-systems.

    This won't take into account the old style auth-systems.
    """
    ep_name = 'openstack.client.auth_plugin'
    for ep in pkg_resources.iter_entry_points(ep_name):
        try:
            auth_plugin = ep.load()
        except (ImportError, pkg_resources.UnknownExtra, AttributeError) as e:
            logger.debug("ERROR: Cannot load auth plugin %s" % ep.name)
            logger.debug(e, exc_info=1)
        else:
            _discovered_plugins[ep.name] = auth_plugin


def load_auth_system_opts(parser):
    """Load options needed by the available auth-systems into a parser.

    This function will try to populate the parser with options from the
    available plugins.
    """
    for name, auth_plugin in _discovered_plugins.iteritems():
        add_opts_fn = getattr(auth_plugin, "add_opts", None)
        if add_opts_fn:
            group = parser.add_argument_group("Auth-system '%s' options" %
                                              name)
            add_opts_fn(group)


def load_plugin(auth_system):
    if auth_system in _discovered_plugins:
        return _discovered_plugins[auth_system]()

    # NOTE(aloga): If we arrive here, the plugin will be an old-style one,
    # so we have to create a fake AuthPlugin for it.
    return DeprecatedAuthPlugin(auth_system)


class BaseAuthPlugin(object):
    """Base class for authentication plugins.

    An authentication plugin needs to override at least the authenticate
    method to be a valid plugin.
    """
    def __init__(self):
        self.opts = {}

    def get_auth_url(self):
        """Return the auth url for the plugin (if any)."""
        return None

    @staticmethod
    def add_opts(parser):
        """Populate and return the parser with the options for this plugin.

        If the plugin does not need any options, it should return the same
        parser untouched.
        """
        return parser

    def parse_opts(self, args):
        """Parse the actual auth-system options if any.

        This method is expected to populate the attribute self.opts with a
        dict containing the options and values needed to make authentication.
        If the dict is empty, the client should assume that it needs the same
        options as the 'keystone' auth system (i.e. os_username and
        os_password).

        Returns the self.opts dict.
        """
        return self.opts

    def authenticate(self, cls, auth_url):
        """Authenticate using plugin defined method."""
        raise exceptions.AuthSystemNotFound(self.auth_system)


def _load_entry_point(ep_name, name=None):
    """Try to load the entry point ep_name that matches name."""
    for ep in pkg_resources.iter_entry_points(ep_name, name=name):
        try:
            return ep.load()
        except (ImportError, pkg_resources.UnknownExtra, AttributeError):
            continue


class DeprecatedAuthPlugin(object):
    """Class to mimic the AuthPlugin class for deprecated auth systems.

    Old auth systems only define two entry points: openstack.client.auth_url
    and openstack.client.authenticate. This class will load those entry points
    into a class similar to a valid AuthPlugin.
    """
    def __init__(self, auth_system):
        self.auth_system = auth_system

        def authenticate(cls, auth_url):
            raise exceptions.AuthSystemNotFound(self.auth_system)

        self.opts = {}

        self.get_auth_url = lambda: None
        self.authenticate = authenticate

        self._load_endpoints()

    def _load_endpoints(self):
        ep_name = 'openstack.client.auth_url'
        fn = _load_entry_point(ep_name, name=self.auth_system)
        if fn:
            self.get_auth_url = fn

        ep_name = 'openstack.client.authenticate'
        fn = _load_entry_point(ep_name, name=self.auth_system)
        if fn:
            self.authenticate = fn

    def parse_opts(self, args):
        return self.opts


class KeystoneV2AuthPlugin(BaseAuthPlugin):
    auth_system = "keystone"

    def authenticate(self, http_client, auth_url):
        """Authenticate using plugin defined method."""
        if http_client.token:
            params = {"auth": {"token": {"id": http_client.token}}}
        elif http_client.username and http_client.password:
            params = {
                "auth": {
                    "passwordCredentials": {
                        "username": http_client.username,
                        "password": http_client.password,
                    }
                }
            }
        else:
            raise ValueError("A username and password or token is required.")
        if http_client.tenant_id:
            params["auth"]["tenantId"] = http_client.tenant_id
        elif http_client.tenant_name:
            params["auth"]["tenantName"] = http_client.tenant_name
        resp, body = http_client.request(
            "POST", http_client.concat_url(auth_url, "/v2.0/tokens"),
            allow_redirects=True,
            body=params)

        http_client.auth_response = body


class NovaLegacyAuthPlugin(BaseAuthPlugin):
    auth_system = "nova-legacy"

    def authenticate(self, http_client, auth_url):
        headers = {'X-Auth-User': http_client.username,
                   'X-Auth-Key': http_client.password}
        if http_client.tenant_id:
            headers['X-Auth-Project-Id'] = http_client.tenant_id

        resp, body = http_client.request(
            "GET", url, headers=headers, allow_redirects=True)
        if resp.status_code in (200, 204):  # in some cases we get No Content
            try:
                # set endpoint for compute if it exists
                try:
                    http_client.compute.endpoint = (
                        resp.headers['x-server-management-url'].rstrip('/'))
                except AttributeError:
                    pass
                http_client.token = resp.headers['x-auth-token']
                http_client.auth_url = url
            except (KeyError, TypeError):
                raise exceptions.AuthorizationFailure()
