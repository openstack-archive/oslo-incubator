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


import datetime
import logging
import re
import time

try:
    import simplejson as json
except ImportError:
    import json

import requests

from openstack.common.apiclient import auth_plugin
from openstack.common.apiclient import exceptions
from openstack.common import timeutils


_logger = logging.getLogger(__name__)
VERSION_REGEX = re.compile(r"v\d+\.?\d*")
default_auth_plugin_class = auth_plugin.KeystoneV2AuthPlugin

# gap, in seconds, to determine whether the given token is about to expire
STALE_TOKEN_DURATION = 30


class HttpClient(object):

    USER_AGENT = "openstack.common.apiclient"

    def __init__(self,
                 username=None,
                 password=None,
                 tenant_id=None,
                 tenant_name=None,
                 auth_url=None,
                 endpoint=None,
                 token=None,
                 region_name=None,
                 endpoint_type="publicURL",
                 auth_response=None,
                 original_ip=None,
                 verify=True,
                 cert=None,
                 timeout=None,
                 timings=False,
                 auth_plugin=None,
                 keyring_saver=None,
                 http_log_debug=False):
        if not auth_plugin:
            auth_plugin = default_auth_plugin_class()

        self.auth_url = auth_url
        self.auth_plugin = auth_plugin
        self.username = username
        self.tenant_id = tenant_id
        self.tenant_name = tenant_name
        self.password = password
        self.token = token
        self.endpoint = endpoint
        self.endpoint_type = endpoint_type
        self.region_name = region_name
        self.original_ip = original_ip
        self.timeout = timeout
        self.auth_response = auth_response
        self.keyring_saver = keyring_saver
        self.keyring_saved = False
        self.http_log_debug = http_log_debug

        # requests within the same session can reuse TCP connections from pool
        self.http = requests.Session()

        self.times = []  # [("item", starttime, endtime), ...]
        self.timings = timings

        self.verify = verify
        self.cert = cert

    def will_expire_soon(self, stale_duration=None):
        """ Determines if expiration is about to occur.

        :return: boolean : true if expiration is within the given duration

        """
        stale_duration = (STALE_TOKEN_DURATION if stale_duration is None
                          else stale_duration)
        norm_expires = timeutils.normalize_time(self.get_expires())
        # (gyee) should we move will_expire_soon() to timeutils
        # instead of duplicating code here?
        soon = (timeutils.utcnow() + datetime.timedelta(
                seconds=stale_duration))
        return norm_expires < soon

    def get_expires(self):
        """ Returns the token expiration (as datetime object)

        :returns: datetime

        """
        return timeutils.parse_isotime(
            self.auth_response['access']['token']['expires'])

    def get_token(self):
        return self.auth_response['access']['token']['id']

    def get_tenant_id(self):
        return self.auth_response['access']['token']['tenant']['id']

    def get_user_id(self):
        return self.auth_response['access']['user']['id']

    def filter_endpoints(self, endpoint_type=None,
                         service_type=None, service_name=None,
                         filter_attrs={}):
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

        if 'endpoints' in self.auth_response:
            # We have a bastardized service catalog. Treat it special. :/
            for endpoint in self.auth_response['endpoints']:
                add_if_appropriate(endpoint)
        elif 'serviceCatalog' in self.auth_response['access']:
            # Full catalog ...
            for service in self.auth_response['access']['serviceCatalog']:
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
                service_type, service_name=None, filter_attrs={}):
        """Fetch the public URL from the Compute service for
        a particular endpoint attribute."""
        matching_endpoints = self.filter_endpoints(
            endpoint_type, service_type, service_name, filter_attrs)
        # NOTE(imelnikov): for unbound tokens, we get no endpoints,
        #     but we are still able to use public identity service
        if not matching_endpoints:
            if (endpoint_type == 'publicURL' and service_type == 'identity'):
                return self.auth_url
            else:
                raise exceptions.EndpointNotFound()
        elif len(matching_endpoints) > 1:
            raise exceptions.AmbiguousEndpoints(
                endpoints=matching_endpoints)
        else:
            return matching_endpoints[0][endpoint_type]

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

    def serialize(self, entity):
        return json.dumps(entity)

    def get_timings(self):
        return self.times

    def reset_timings(self):
        self.times = []

    def request(self, method, url, **kwargs):
        """ Send an http request with the specified characteristics.

        Wrapper around requests.request to handle tasks such as
        setting headers, JSON encoding/decoding, and error handling.
        """
        kwargs.setdefault('headers', kwargs.get('headers', {}))
        kwargs['headers']['User-Agent'] = self.USER_AGENT
        if self.original_ip:
            kwargs['headers']['Forwarded'] = "for=%s;by=%s" % (
                self.original_ip, self.USER_AGENT)
        if kwargs.get('body') is not None:
            kwargs['headers']['Content-Type'] = 'application/json'
            kwargs['data'] = self.serialize(kwargs['body'])
        try:
            del kwargs['body']
        except KeyError:
            pass
        if self.timeout is not None:
            kwargs.setdefault('timeout', self.timeout)
        kwargs.setdefault("verify", self.verify)
        if self.cert is not None:
            kwargs.setdefault("cert", self.cert)

        self.http_log_req(method, url, kwargs)
        if self.timings:
            start_time = time.time()
        resp = self.http.request(method, url, **kwargs)
        if self.timings:
            self.times.append(("%s %s" % (method, url),
                               start_time, time.time()))

        self.http_log_resp(resp)

        body = None
        if resp.headers.get("Content-Type", "").startswith("application/json"):
            try:
                body = resp.json()
            except ValueError:
                _logger.debug("Could not decode JSON from body: %s"
                              % resp.text)

        if resp.status_code >= 400:
            _logger.debug(
                "Request returned failure status: %s",
                resp.status_code)
            raise exceptions.from_response(resp, body, method, url)

        return resp, body

    @staticmethod
    def concat_url(endpoint, url):
        version = None
        endpoint = endpoint.rstrip("/")
        spl = endpoint.rsplit("/", 1)
        if len(spl) > 1 and VERSION_REGEX.match(spl[1]):
            endpoint = spl[0]
            version = spl[1]
        url = url.strip("/")
        spl = url.split("/", 1)
        if VERSION_REGEX.match(spl[0]):
            version = spl[0]
            url = spl[1]
        if version:
            return "%s/%s/%s" % (endpoint, version, url)
        else:
            return "%s/%s" % (endpoint, url)

    def cs_request(self, client, method, url, **kwargs):
        if self.endpoint:
            endpoint = self.endpoint
            token = self.token
        else:
            if not self.auth_response:
                self.authenticate()
                client.endpoint = None
            url_for_args = {
                "endpoint_type": client.endpoint_type or self.endpoint_type,
                "service_type": client.service_type,
                "filter_attrs": (
                    {"region": self.region_name}
                    if self.region_name
                    else {}
                )
            }

            if not client.endpoint:
                client.endpoint = self.url_for(**url_for_args)
            endpoint = client.endpoint
            token = self.get_token()

        kwargs.setdefault("headers", {})
        kwargs["headers"]["X-Auth-Token"] = token
        # Perform the request once. If we get a 401 back then it
        # might be because the auth token expired, so try to
        # re-authenticate and try again. If it still fails, bail.
        try:
            return self.request(
                method, self.concat_url(endpoint, url), **kwargs)
        except exceptions.Unauthorized:
            if self.endpoint:
                raise
            self.authenticate()
            endpoint = self.url_for(**url_for_args)
            client.endpoint = endpoint
            token = self.get_token()
            kwargs["headers"]["X-Auth-Token"] = token
            return self.request(
                method, self.concat_url(endpoint, url), **kwargs)

    def add_client(self, base_client_instance):
        base_client_instance.http_client = self
        service_type = base_client_instance.service_type
        if service_type and not hasattr(self, service_type):
            setattr(self, service_type, base_client_instance)

    def authenticate(self):
        if not self.auth_url:
            self.auth_url = self.auth_plugin.get_auth_url()
            if not self.auth_url:
                raise exceptions.EndpointNotFound()
        self.auth_plugin.authenticate(self, self.auth_url)
        # Store the token/mgmt url in the keyring for later requests.
        if self.keyring_saver and not self.keyring_saved:
            self.keyring_saver.save(self)
            self.keyring_saved = True

    def unauthenticate(self):
        """Forget all of our authentication information."""
        self.auth_response = None


class BaseClient(object):
    """
    Top-level object to access the OpenStack API.
    """

    service_type = None
    endpoint_type = None  # "publicURL" will be used
    endpoint = None

    def __init__(self, http_client, extensions=None):
        http_client.add_client(self)

        # Add in any extensions...
        if extensions:
            for extension in extensions:
                if extension.manager_class:
                    setattr(self, extension.name,
                            extension.manager_class(self))

    def cs_request(self, method, url, **kwargs):
        return self.http_client.cs_request(
            self, method, url, **kwargs)

    def head(self, url, **kwargs):
        return self.cs_request("HEAD", url, **kwargs)

    def get(self, url, **kwargs):
        return self.cs_request("GET", url, **kwargs)

    def post(self, url, **kwargs):
        return self.cs_request("POST", url, **kwargs)

    def put(self, url, **kwargs):
        return self.cs_request("PUT", url, **kwargs)

    def delete(self, url, **kwargs):
        return self.cs_request("DELETE", url, **kwargs)

    def patch(self, url, **kwargs):
        return self.cs_request("PATCH", url, **kwargs)
