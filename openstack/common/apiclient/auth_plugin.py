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

# E0202: An attribute inherited from %s hide this method
# pylint: disable=E0202

import abc
import argparse
import logging
import os

import pkg_resources

from openstack.common.apiclient import exceptions


logger = logging.getLogger(__name__)


_discovered_plugins = {}


def discover_auth_systems():
    """Discover the available auth-systems.

    This won't take into account the old style auth-systems.
    """
    # put standard classes here
    # don't register them as entry points in setup.py
    # becase it will make users of incubated apiclient
    # update setup.py of their client packages
    for cls in (KeystoneV2AuthPlugin, TokenEndpointAuthPlugin,
                NovaLegacyAuthPlugin):
        _discovered_plugins[cls.auth_system] = cls
    ep_name = 'openstack.common.apiclient.auth_plugin'
    for ep in pkg_resources.iter_entry_points(ep_name):
        try:
            auth_plugin = ep.load()
        except (ImportError, pkg_resources.UnknownExtra, AttributeError) as e:
            logger.debug("ERROR: Cannot load auth plugin %s" % ep.name)
            logger.debug(e, exc_info=1)
        else:
            _discovered_plugins[ep.name] = auth_plugin


def load_auth_system_opts(parser, client_prefix=None):
    """Load options needed by the available auth-systems into a parser.

    This function will try to populate the parser with options from the
    available plugins.
    """
    if client_prefix:
        client_prefix = client_prefix.upper()

    options = [
        ("auth_system", "auth_system"),
        ("username", "username"),
        ("tenant_name", "project_id"),
        ("tenant_id", None),
        ("auth_url", "url"),
    ]
    for opt in options:
        common_opt, client_opt = opt
        dashed_opt = common_opt.replace("_", "-")
        common_env = "OS_%s" % common_opt.upper()
        if client_prefix and client_opt:
            client_env = "%s_%s" % (client_prefix, client_opt.upper())
            arg_default = os.environ.get(
                common_env, os.environ.get(client_env, ""))
            arg_help = 'Defaults to env[%s] or env[%s].' % (
                common_env, client_env)
        else:
            arg_default = os.environ.get(common_env, "")
            arg_help = 'Defaults to env[%s].' % common_env
        parser.add_argument(
            '--os-%s' % dashed_opt,
            metavar='<%s>' % dashed_opt,
            default=arg_default,
            help=arg_help)
        parser.add_argument(
            '--os_%s' % common_opt,
            metavar='<%s>' % dashed_opt,
            help=argparse.SUPPRESS)

    for name, auth_plugin in _discovered_plugins.iteritems():
        group = parser.add_argument_group("Auth-system '%s' options" % name)
        auth_plugin.add_opts(group)


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

    __metaclass__ = abc.ABCMeta

    auth_system = None

    def __init__(self):
        self.opts = {}

    @staticmethod
    def add_opts(parser):
        """Populate the parser with the options for this plugin.
        """

    def parse_opts(self, args):
        """Parse the actual auth-system options if any.

        This method is expected to populate the attribute self.opts with a
        dict containing the options and values needed to make authentication.
        """

    @abc.abstractmethod
    def authenticate(self, http_client):
        """Authenticate using plugin defined method."""


def _load_entry_point(ep_name, name=None):
    """Try to load the entry point ep_name that matches name."""
    for ep in pkg_resources.iter_entry_points(ep_name, name=name):
        try:
            return ep.load()
        except (ImportError, pkg_resources.UnknownExtra, AttributeError):
            continue


class DeprecatedAuthPlugin(BaseAuthPlugin):
    """Class to mimic the :class:`BaseAuthPlugin` for deprecated auth systems.

    Old auth systems only define two entry points:
    "openstack.common.apiclient.auth_url" and
    "openstack.common.apiclient.authenticate". This class will load those
     entry points into a class similar to a valid :class:`BaseAuthPlugin`.
    """
    def __init__(self, auth_system):
        super(DeprecatedAuthPlugin, self).__init__()
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
        ep_name = 'openstack.common.apiclient.auth_url'
        fn = _load_entry_point(ep_name, name=self.auth_system)
        if fn:
            self.get_auth_url = fn

        ep_name = 'openstack.common.apiclient.authenticate'
        fn = _load_entry_point(ep_name, name=self.auth_system)
        if fn:
            self.do_authenticate = fn


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
            "username": getattr(args, "os_username", None),
            "password": getattr(args, "os_password", None),
            "tenant_id": getattr(args, "os_tenant_id", None),
            "tenant_name": getattr(args, "os_tenant_name", None),
            "token": getattr(args, "os_token", None),
            "auth_url": getattr(args, "os_auth_url", None),
        }

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
        try:
            body = http_client.request(
                "POST",
                http_client.concat_url(self.opts.get("auth_url"), "/tokens"),
                allow_redirects=True,
                json=params).json()
        except ValueError as ex:
            raise exceptions.AuthorizationFailure(ex)
        http_client.auth_response = body


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
            "token": getattr(args, "os_token", None),
            "endpoint": getattr(args, "os_endpoint", None),
        }

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
            "username": getattr(args, "os_username", None),
            "password": getattr(args, "os_password", None),
            "project_id": getattr(args, "os_tenant_name", None),
            "auth_url": getattr(args, "os_auth_url", None),
        }

    def authenticate(self, http_client):
        headers = {"X-Auth-User": self.opts["username"],
                   "X-Auth-Key": self.opts["password"]}
        if self.opts.get("project_id"):
            headers["X-Auth-Project-Id"] = self.opts.get("project_id")

        resp = http_client.request(
            "GET", self.opts["auth_url"],
            headers=headers, allow_redirects=True)
        try:
            # set endpoint for compute if it exists
            try:
                compute = http_client.compute
            except AttributeError:
                pass
            else:
                compute.endpoint = (
                    resp.headers["X-Server-Management-Url"].rstrip("/"))
            http_client.auth_token = resp.headers["X-Auth-Token"]
        except (KeyError, TypeError):
            raise exceptions.AuthorizationFailure()
