# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2010 Jacob Kaplan-Moss
# Copyright 2011 OpenStack LLC
# Copyright 2011 Piston Cloud Computing, Inc.
# Copyright 2011 Nebula, Inc.
# Copyright 2013 Alessio Ababilov
# Copyright 2013 Grid Dynamics
# Copyright 2013 OpenStack Foundation
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

"""
OpenStack Client interface. Handles the REST calls and responses.
"""

# E0202: An attribute inherited from %s hide this method
# pylint: disable=E0202

import logging
import time

try:
    import simplejson as json
except ImportError:
    import json

import requests

from openstack.common.apiclient import exceptions
from openstack.common import importutils
from openstack.common import timeutils


_logger = logging.getLogger(__name__)


class AuthResponse(dict):
    """An object for encapsulating a raw authentication response from keystone.

    The class provides methods for extracting useful values from that token.
    """

    @property
    def expires(self):
        """Returns the token expiration (as datetime object)

        :returns: datetime

        """
        try:
            return timeutils.parse_isotime(self['access']['token']['expires'])
        except KeyError:
            return None

    @property
    def token(self):
        """Returns the token_id associated with the auth request.

        :returns: str
        """
        try:
            return self['access']['token']['id']
        except KeyError:
            return None

    @property
    def username(self):
        """Returns the username associated with the authentication request.

        Follows the pattern defined in the V2 API of first looking for 'name',
        returning that if available, and falling back to 'username' if name
        is unavailable.

        :returns: str
        """
        try:
            return self['access']['user']['name']
        except KeyError:
            pass
        try:
            return self['access']['user']['username']
        except KeyError:
            return None

    @property
    def user_id(self):
        """Returns the user id associated with the authentication request.

        :returns: str
        """
        try:
            return self['access']['user']['id']
        except KeyError:
            return None

    @property
    def tenant_name(self):
        """Returns the tenant name associated with the authentication request.

        :returns: str
        """
        try:
            return self['access']['token']['tenant']['name']
        except KeyError:
            return None

    @property
    def project_name(self):
        """Synonym for tenant_name."""
        return self.tenant_name

    @property
    def tenant_id(self):
        """Returns the tenant id associated with the authentication request.

        :returns: str
        """
        try:
            return self['access']['token']['tenant']['id']
        except KeyError:
            return None

    @property
    def project_id(self):
        """Synonym for tenant_id."""
        return self.tenant_id

    @property
    def scoped(self):
        """Checks if the authorization token is scoped to a tenant.

        Additionally verifies that there is a populated service catalog.

        :returns: bool
        """
        try:
            if (self['access']['serviceCatalog'] and
                    self['access']['token']['tenant']):
                return True
        except KeyError:
            pass
        return False

    def filter_endpoints(self, endpoint_type=None,
                         service_type=None, service_name=None,
                         filter_attrs=None):
        """Returns a list of endpoints which match provided criteria.
        """
        filter_attrs = filter_attrs or {}
        matching_endpoints = []

        def add_if_appropriate(endpoint):
            # Ignore 1.0 compute endpoints
            if (endpoint.get("serviceType") == 'compute' and
                    endpoint.get('versionId', '2') not in ('1.1', '2')):
                return
            if endpoint_type and endpoint_type not in endpoint.keys():
                return
            for k, v in filter_attrs.iteritems():
                if endpoint.get(k).lower() != v.lower():
                    return
            matching_endpoints.append(endpoint)

        if 'endpoints' in self:
            # We have a bastardized service catalog. Treat it special. :/
            for endpoint in self['endpoints']:
                add_if_appropriate(endpoint)
        elif 'access' in self and 'serviceCatalog' in self['access']:
            # Full catalog ...
            for service in self['access']['serviceCatalog']:
                if service_type and service.get("type") != service_type:
                    continue
                if service_name and service.get('name') != service_name:
                    continue

                for endpoint in service['endpoints']:
                    endpoint["serviceName"] = service.get("name")
                    endpoint["serviceType"] = service.get("type")
                    add_if_appropriate(endpoint)

        return matching_endpoints

    def url_for(self, endpoint_type,
                service_type, service_name=None, filter_attrs=None):
        """Returns a unique endpoint which match provided criteria.
        """
        filter_attrs = filter_attrs or {}
        matching_endpoints = self.filter_endpoints(
            endpoint_type, service_type, service_name, filter_attrs)
        if not matching_endpoints:
            raise exceptions.EndpointNotFound(
                "Cannot find requested %s endpoint" % service_type)
        elif len(matching_endpoints) > 1:
            raise exceptions.AmbiguousEndpoints(
                endpoints=matching_endpoints)
        else:
            return matching_endpoints[0][endpoint_type]


class HttpClient(object):
    """This client handles sending HTTP requests to OpenStack servers.

    Features:
    - share authentication information between several clients to different
      services (e.g., for compute and image clients);
    - reissue authentication request for expired tokens;
    - encode/decode JSON bodies;
    - raise exeptions on HTTP errors;
    - pluggable authentication;
    - store authentication information in a keyring;
    - store time spent for requests;
    - register clients for particular services, so one can use
      `http_client.identity` or `http_client.compute`;
    - log requests and responses in a format that is easy to copy-and-paste
      into terminal and send the same request with curl.
    """

    user_agent = "openstack.common.apiclient"
    _auth_response = None

    def __init__(self,
                 auth_plugin,
                 auth_response=None,
                 region_name=None,
                 endpoint_type="publicURL",
                 original_ip=None,
                 verify=True,
                 cert=None,
                 timeout=None,
                 timings=False,
                 keyring_saver=None,
                 http_log_debug=False,
                 user_agent=None):
        self.auth_plugin = auth_plugin
        self.auth_response = auth_response

        self.endpoint_type = endpoint_type
        self.region_name = region_name

        self.original_ip = original_ip
        self.timeout = timeout
        self.verify = verify
        self.cert = cert

        self.keyring_saver = keyring_saver
        self.http_log_debug = http_log_debug
        self.user_agent = user_agent or self.user_agent

        self.times = []  # [("item", starttime, endtime), ...]
        self.timings = timings

        # requests within the same session can reuse TCP connections from pool
        self.http = requests.Session()

        self.token = None
        self.endpoint = None

    @property
    def auth_response(self):
        return self._auth_response

    @auth_response.setter
    def auth_response(self, value):
        self._auth_response = AuthResponse(value or {})

    def http_log_req(self, method, url, kwargs):
        if not self.http_log_debug:
            return

        string_parts = [
            "curl -i",
            "-X '%s'" % method,
            "'%s'" % url,
        ]

        for element in kwargs['headers']:
            header = "-H '%s: %s'" % (element, kwargs['headers'][element])
            string_parts.append(header)

        _logger.debug("REQ: %s" % " ".join(string_parts))
        if 'data' in kwargs:
            _logger.debug("REQ BODY: %s\n" % (kwargs['data']))

    def http_log_resp(self, resp):
        if not self.http_log_debug:
            return
        _logger.debug(
            "RESP: [%s] %s\n",
            resp.status_code,
            resp.headers)
        if resp._content_consumed:
            _logger.debug(
                "RESP BODY: %s\n",
                resp.text)

    def serialize(self, kwargs):
        if kwargs.get('json') is not None:
            kwargs['headers']['Content-Type'] = 'application/json'
            kwargs['data'] = json.dumps(kwargs['json'])
        try:
            del kwargs['json']
        except KeyError:
            pass

    def get_timings(self):
        return self.times

    def reset_timings(self):
        self.times = []

    def request(self, method, url, **kwargs):
        """Send an http request with the specified characteristics.

        Wrapper around `requests.Session.request` to handle tasks such as
        setting headers, JSON encoding/decoding, and error handling.

        :param method: method of HTTP request
        :param url: URL of HTTP request
        :param kwargs: any other parameter that can be passed to
'            requests.Session.request (such as `headers`) or `json`
             that will be encoded as JSON and used as `data` argument
        """
        kwargs.setdefault("headers", kwargs.get("headers", {}))
        kwargs["headers"]["User-Agent"] = self.user_agent
        if self.original_ip:
            kwargs["headers"]["Forwarded"] = "for=%s;by=%s" % (
                self.original_ip, self.user_agent)
        if self.timeout is not None:
            kwargs.setdefault("timeout", self.timeout)
        kwargs.setdefault("verify", self.verify)
        if self.cert is not None:
            kwargs.setdefault("cert", self.cert)
        self.serialize(kwargs)

        self.http_log_req(method, url, kwargs)
        if self.timings:
            start_time = time.time()
        resp = self.http.request(method, url, **kwargs)
        if self.timings:
            self.times.append(("%s %s" % (method, url),
                               start_time, time.time()))
        self.http_log_resp(resp)

        if resp.status_code >= 400:
            _logger.debug(
                "Request returned failure status: %s",
                resp.status_code)
            raise exceptions.from_response(resp, method, url)

        return resp

    @staticmethod
    def concat_url(endpoint, url):
        """Concatenate endpoint and final URL.

        E.g., "http://keystone/v2.0/" and "/tokens" are concatenated to
        "http://keystone/v2.0/tokens".

        :param endpoint: the base URL
        :param url: the final URL
        """
        return "%s/%s" % (endpoint.rstrip("/"), url.strip("/"))

    def client_request(self, client, method, url, **kwargs):
        """Send an http request using `client`'s endpoint and specified `url`.

        If request was rejected as unauthorized (possibly because the token is
        expired), issue one authorization attempt and send the request once
        again.

        :param client: instance of BaseClient descendant
        :param method: method of HTTP request
        :param url: URL of HTTP request
        :param kwargs: any other parameter that can be passed to
'            `HttpClient.request`
        """

        # To send a request, we need a token and an endpoint.
        # There are several ways to retrieve them.
        # token:
        # - self.token
        # - self.auth_response.token
        # endpoint:
        # - client.endpoint
        # - client.cache_endpoint
        # - self.endpoint
        # - self.auth_response.url_for()
        # All these fields can be set by auth_plugin during
        # authentication.

        url_for_args = {
            "endpoint_type": client.endpoint_type or self.endpoint_type,
            "service_type": client.service_type,
            "filter_attrs": (
                {"region": self.region_name}
                if self.region_name
                else {}
            )
        }

        def get_token_and_endpoint(silent):
            token = self.token or self.auth_response.token
            endpoint = (client.endpoint or client.cached_endpoint or
                        self.endpoint)
            if not endpoint:
                try:
                    endpoint = self.auth_response.url_for(**url_for_args)
                except exceptions.EndpointException:
                    if not silent:
                        raise
            return (token, endpoint)

        token, endpoint = get_token_and_endpoint(True)
        just_authenticated = False
        if not (endpoint and token):
            self.authenticate()
            just_authenticated = True
            token, endpoint = get_token_and_endpoint(False)
            if not (endpoint and token):
                raise exceptions.AuthorizationFailure(
                    "Cannot find endpoint or token for request")

        old_token_endpoint = (token, endpoint)
        kwargs.setdefault("headers", {})["X-Auth-Token"] = token
        client.cached_endpoint = endpoint
        # Perform the request once. If we get Unauthorized, then it
        # might be because the auth token expired, so try to
        # re-authenticate and try again. If it still fails, bail.
        try:
            return self.request(
                method, self.concat_url(endpoint, url), **kwargs)
        except exceptions.Unauthorized:
            if just_authenticated:
                raise
            client.cached_endpoint = None
            self.authenticate()
            token, endpoint = get_token_and_endpoint(True)
            if (not (endpoint and token) or
                    old_token_endpoint == (endpoint, token)):
                raise
            client.cached_endpoint = endpoint
            kwargs["headers"]["X-Auth-Token"] = token
            return self.request(
                method, self.concat_url(endpoint, url), **kwargs)

    def add_client(self, base_client_instance):
        """Add a new instance of :class:`BaseClient` descendant.

        `self` will store a reference to `base_client_instance`.

        Example:

        >>> def test_clients():
        ...     from openstack.common.apiclient import auth_plugin
        ...     from openstack.common.apiclient import client
        ...     auth = auth_plugin.KeystoneV2AuthPlugin(
        ...         "user", "pass", "tenant", auth_url="http://auth:5000/v2.0")
        ...     openstack_client = client.HttpClient(auth)
        ...     # create nova client
        ...     from novaclient.v1_1 import client
        ...     client.Client(openstack_client)
        ...     # create keystone client
        ...     from keystoneclient.v2_0 import client
        ...     client.Client(openstack_client)
        ...     # use them
        ...     openstack_client.identity.tenants.list()
        ...     openstack_client.compute.servers.list()
        """
        service_type = base_client_instance.service_type
        if service_type and not hasattr(self, service_type):
            setattr(self, service_type, base_client_instance)

    def authenticate(self):
        self.auth_plugin.authenticate(self)
        # Store the authentication results in the keyring for later requests
        if self.keyring_saver:
            self.keyring_saver.save(self)


class BaseClient(object):
    """Top-level object to access the OpenStack API.

    This client uses :class:`HttpClient` to send requests. :class:`HttpClient`
    will handle a bunch of issues such as authentication.
    """

    service_type = None
    endpoint_type = None  # "publicURL" will be used
    endpoint = None
    cached_endpoint = None

    def __init__(self, http_client, extensions=None):
        self.http_client = http_client
        http_client.add_client(self)

        # Add in any extensions...
        if extensions:
            for extension in extensions:
                if extension.manager_class:
                    setattr(self, extension.name,
                            extension.manager_class(self))

    def client_request(self, method, url, **kwargs):
        return self.http_client.client_request(
            self, method, url, **kwargs)

    def head(self, url, **kwargs):
        return self.client_request("HEAD", url, **kwargs)

    def get(self, url, **kwargs):
        return self.client_request("GET", url, **kwargs)

    def post(self, url, **kwargs):
        return self.client_request("POST", url, **kwargs)

    def put(self, url, **kwargs):
        return self.client_request("PUT", url, **kwargs)

    def delete(self, url, **kwargs):
        return self.client_request("DELETE", url, **kwargs)

    def patch(self, url, **kwargs):
        return self.client_request("PATCH", url, **kwargs)

    @staticmethod
    def get_class(api_name, version, version_map):
        """Returns the client class for the requested API version

        :param api_name: the name of the API, e.g. 'compute', 'image', etc
        :param version: the requested API version
        :param version_map: a dict of client classes keyed by version
        :rtype: a client class for the requested API version
        """
        try:
            client_path = version_map[str(version)]
        except (KeyError, ValueError):
            msg = "Invalid %s client version '%s'. must be one of: %s" % (
                  (api_name, version, ', '.join(version_map.keys())))
            raise exceptions.UnsupportedVersion(msg)

        return importutils.import_class(client_path)
