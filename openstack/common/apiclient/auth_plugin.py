# vim: tabstop=4 shiftwidth=4 softtabstop=4

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

from openstack.common.apiclient import client
from openstack.common.apiclient import exceptions


logger = logging.getLogger(__name__)


_discovered_plugins = {}


def discover_auth_systems():
    """Discover the available auth-systems.

    This won't take into account the old style auth-systems.
    """
    global _discovered_plugins
    ep_name = 'openstack.client.auth_plugin'
    _discovered_plugins["keystone"] = KeystoneV2AuthPlugin
    _discovered_plugins["token-endpoint"] = TokenEndpointAuthPlugin
    _discovered_plugins["nova-legacy"] = NovaLegacyAuthPlugin
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
    auth_system = None

    """Base class for authentication plugins.

    An authentication plugin needs to override at least the authenticate
    method to be a valid plugin.
    """
    def __init__(self):
        self.opts = {}

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

    def authenticate(self, http_client):
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
        self.opts = {}

        self._load_endpoints()

    def authenticate(self, http_client):
        return self.do_authenticate(http_client, self.get_auth_url())

    def do_authenticate(self, http_client, url):
        raise exceptions.AuthSystemNotFound(self.auth_system)

    def get_auth_url(self):
        return None

    def _load_endpoints(self):
        ep_name = 'openstack.client.auth_url'
        fn = _load_entry_point(ep_name, name=self.auth_system)
        if fn:
            self.get_auth_url = fn

        ep_name = 'openstack.client.authenticate'
        fn = _load_entry_point(ep_name, name=self.auth_system)
        if fn:
            self.do_authenticate = fn

    def parse_opts(self, args):
        return self.opts


class KeystoneV2AuthPlugin(BaseAuthPlugin):
    auth_system = "keystone"

    def __init__(self,
                 username=None,
                 password=None,
                 tenant_id=None,
                 tenant_name=None,
                 token=None,
                 auth_url=None):
        super(KeystoneV2AuthPlugin, self).__init__()
        self.opts = {
            "username": username,
            "password": password,
            "tenant_id": tenant_id,
            "tenant_name": tenant_name,
            "token": token,
            "auth_url": auth_url,
        }

    def parse_opts(self, args):
        self.opts = {
            "username": args.os_username,
            "password": args.os_password,
            "tenant_id": args.os_tenant_id,
            "tenant_name": args.os_tenant_name,
            "token": args.os_token,
            "auth_url": args.os_auth_url,
        }
        return self.opts

    def authenticate(self, http_client):
        if not self.opts.get("auth_url"):
            raise exceptions.AuthPluginOptionsMissing(["auth_url"])
        if self.opts.get("token"):
            params = {"auth": {"token": {"id": self.opts.get("token")}}}
        elif self.opts.get("username") and self.opts.get("password"):
            params = {
                "auth": {
                    "passwordCredentials": {
                        "username": self.opts.get("username"),
                        "password": self.opts.get("password"),
                    }
                }
            }
        else:
            raise exceptions.AuthPluginOptionsMissing(
                [opt
                 for opt in "username", "password", "token"
                 if not self.opts.get(opt)])
        if self.opts.get("tenant_id"):
            params["auth"]["tenantId"] = self.opts.get("tenant_id")
        elif self.opts.get("tenant_name"):
            params["auth"]["tenantName"] = self.opts.get("tenant_name")
        resp, body = http_client.request(
            "POST",
            http_client.concat_url(self.opts.get("auth_url"), "/tokens"),
            allow_redirects=True,
            json=params)

        http_client.set_auth_response(body)


class TokenEndpointAuthPlugin(BaseAuthPlugin):
    auth_system = "token-endpoint"

    def __init__(self,
                 token=None,
                 endpoint=None):
        super(TokenEndpointAuthPlugin, self).__init__()
        self.opts = {
            "token": token,
            "endpoint": endpoint,
        }

    def parse_opts(self, args):
        self.opts = {
            "token": args.os_token,
            "endpoint": args.os_endpoint,
        }
        return self.opts

    def authenticate(self, http_client):
        # we can work without an endpoint (`BaseClient.endpoint` can be used),
        # but a token is required
        if not self.opts.get("token"):
            raise exceptions.AuthPluginOptionsMissing(["token"])
        http_client.token = self.opts["token"]
        http_client.endpoint = self.opts["endpoint"]


class NovaLegacyAuthPlugin(BaseAuthPlugin):
    auth_system = "nova-legacy"

    def __init__(self,
                 username=None,
                 password=None,
                 project_id=None,
                 auth_url=None):
        super(NovaLegacyAuthPlugin, self).__init__()
        self.opts = {
            "username": username,
            "password": password,
            "project_id": project_id,
            "auth_url": auth_url,
        }

    def parse_opts(self, args):
        self.opts = {
            "username": args.os_username,
            "password": args.os_password,
            "project_id": args.project_id or args.os_tenant_name,
            "auth_url": args.os_auth_url,
        }
        return self.opts

    def authenticate(self, http_client):
        headers = {'X-Auth-User': self.opts["username"],
                   'X-Auth-Key': self.opts["password"]}
        if self.opts.get("project_id"):
            headers['X-Auth-Project-Id'] = self.opts.get("project_id")

        resp, body = http_client.request(
            "GET", self.opts["auth_url"],
            headers=headers, allow_redirects=True)
        try:
            # set endpoint for compute if it exists
            try:
                http_client.compute.endpoint = (
                    resp.headers['X-Server-Management-Url'].rstrip('/'))
            except AttributeError:
                pass
            http_client.auth_token = resp.headers['X-Auth-Token']
        except (KeyError, TypeError):
            raise exceptions.AuthorizationFailure()
