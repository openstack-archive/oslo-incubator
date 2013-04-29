# Copyright 2010 Jacob Kaplan-Moss
# Copyright 2011 OpenStack LLC.
# Copyright 2011 Piston Cloud Computing, Inc.
# Copyright 2011 Nebula, Inc.
# Copyright 2013 Grid Dynamics.

# All Rights Reserved.
"""
OpenStack Client interface. Handles the REST calls and responses.
"""


import logging
import re
import requests


try:
    import simplejson as json
except ImportError:
    import json

from openstack.common.apiclient import exceptions


_logger = logging.getLogger(__name__)
VERSION_REGEX = re.compile(r"v\d+\.?\d*")


class HttpClient(object):

    USER_AGENT = "openstack.common.apiclient"

    def __init__(self, username=None, password=None,
                 tenant_id=None, tenant_name=None,
                 auth_url=None,
                 endpoint=None, token=None, region_name=None,
                 endpoint_type="publicURL",
                 access=None,
                 original_ip=None,
                 insecure=False, cacert=None,
                 timeout=None):
        self.username = username
        self.tenant_id = tenant_id
        self.tenant_name = tenant_name
        self.password = password
        self.auth_uri = auth_url
        self.token = token
        self.endpoint = endpoint
        self.endpoint_type = endpoint_type
        self.region_name = region_name
        self.access = access
        self.original_ip = original_ip
        self.timeout = timeout

        if insecure:
            self.verify_cert = False
        else:
            if cacert:
                self.verify_cert = cacert
            else:
                self.verify_cert = True

    def url_for(self, endpoint_type, service_type, region_name=None):
        """Fetch an endpoint from the service catalog.

        Fetch the specified endpoint from the service catalog for
        a particular endpoint attribute. If no attribute is given, return
        the first endpoint of the specified type.

        See tests for a sample service catalog.
        """
        catalog = self.access.get("serviceCatalog", [])
        # NOTE(imelnikov): for unbound tokens, we get no endpoints,
        #     but we are still able to use public identity service
        if (not catalog and endpoint_type == 'publicURL'
                and service_type == 'identity'):
            return self.auth_uri
        if not region_name:
            region_name = self.region_name
        for service in catalog:
            if service["type"] != service_type:
                continue

            endpoints = service["endpoints"]
            for endpoint in endpoints:
                if region_name and endpoint["region"] != region_name:
                    continue
                return endpoint[endpoint_type]

        raise exceptions.EndpointNotFound("Endpoint not found.")

    def get_endpoints(self, endpoint_type=None,
                      service_type=None, region_name=None):
        """Fetch and filter endpoints for the specified service(s)

        Returns endpoints for the specified service (or all) and
        that contain the specified type (or all).
        """
        sc = {}
        if not region_name:
            region_name = self.region_name
        for service in self.access.get("serviceCatalog", []):
            if service_type and service_type != service["type"]:
                continue
            sc[service["type"]] = []
            for endpoint in service["endpoints"]:
                if endpoint_type and endpoint_type not in endpoint.keys():
                    continue
                if region_name and endpoint["region"] != region_name:
                    continue
                sc[service["type"]].append(endpoint)
        return sc

    def authenticate(self):
        """ Authenticate against the keystone API v2.0.
        """
        if self.token:
            params = {"auth": {"token": {"id": self.token}}}
        elif self.username and self.password:
            params = {
                "auth": {
                    "passwordCredentials": {
                        "username": self.username,
                        "password": self.password,
                    }
                }
            }
        else:
            raise ValueError("A username and password or token is required.")
        if self.tenant_id:
            params["auth"]["tenantId"] = self.tenant_id
        elif self.tenant_name:
            params["auth"]["tenantName"] = self.tenant_name
        resp, body = self.request(
            self.concat_url(self.auth_uri, "/v2.0/tokens"), "POST",
            body=params)
        try:
            self.access = body["access"]
        except KeyError:
            _logger.error("expected `access' key in keystone response")
            raise

    def unauthenticate(self):
        """Forget all of our authentication information."""
        self.access = None

    def http_log_req(self, method, url, kwargs):
        if not self.debug_log:
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
        if self.debug_log:
            _logger.debug(
                "RESP: [%s] %s\nRESP BODY: %s\n",
                resp.status_code,
                resp.headers,
                resp.text)

    def request(self, method, url, **kwargs):
        """ Send an http request with the specified characteristics.

        Wrapper around requests.request to handle tasks such as
        setting headers, JSON encoding/decoding, and error handling.
        """
        # Copy the kwargs so we can reuse the original in case of redirects
        request_kwargs = copy.copy(kwargs)
        request_kwargs.setdefault('headers', kwargs.get('headers', {}))
        request_kwargs['headers']['User-Agent'] = self.USER_AGENT
        if self.original_ip:
            request_kwargs['headers']['Forwarded'] = "for=%s;by=%s" % (
                self.original_ip, self.USER_AGENT)
        if 'body' in kwargs:
            request_kwargs['headers']['Content-Type'] = 'application/json'
            request_kwargs['data'] = self.serialize(kwargs['body'])
            del request_kwargs['body']
        if self.cert:
            request_kwargs['cert'] = self.cert
        if self.timeout is not None:
            request_kwargs.setdefault('timeout', self.timeout)

        self.http_log_req(method, url, request_kwargs)
        resp = requests.request(
            method,
            url,
            verify=self.verify_cert,
            **request_kwargs)

        self.http_log_resp(resp)

        if resp.status_code >= 400:
            _logger.debug(
                "Request returned failure status: %s",
                resp.status_code)
            raise exceptions.from_response(resp, body, url, method)

        if resp.text:
            try:
                body = json.loads(resp.text)
            except ValueError:
                body = None
                _logger.debug("Could not decode JSON from body: %s"
                              % resp.text)
        else:
            _logger.debug("No body was returned.")
            body = None

        return resp, body

    @staticmethod
    def concat_url(endpoint, url):
        version = None
        endpoint = endpoint.rstrip("/")
        spl = endpoint.rsplit("/", 1)
        if VERSION_REGEX.match(spl[1]):
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

    def cs_request(self, client, url, method, **kwargs):
        if self.endpoint:
            endpoint = self.endpoint
            token = self.token
        else:
            if not self.access:
                self.authenticate()
                client.endpoint = None
            endpoint = self.url_for(
                client.endpoint_type or self.endpoint_type,
                client.service_type)
            if not client.endpoint:
                client.endpoint = endpoint
            token = self.access["token"]["id"]

        kwargs.setdefault("headers", {})
        kwargs["headers"]["X-Auth-Token"] = token
        # Perform the request once. If we get a 401 back then it
        # might be because the auth token expired, so try to
        # re-authenticate and try again. If it still fails, bail.
        try:
            return self.request(
                self.concat_url(endpoint, url), method, **kwargs)
        except exceptions.Unauthorized:
            if self.endpoint:
                raise
            self.authenticate()
            endpoint = self.url_for(
                client.endpoint_type,
                client.service_type)
            client.endpoint = endpoint
            token = self.access["token"]["id"]
            kwargs["headers"]["X-Auth-Token"] = token
            return self.request(
                self.concat_url(endpoint, url), method, **kwargs)

    def add_client(self, base_client_instance):
        base_client_instance.http_client = self
        service_type = base_client_instance.service_type
        if service_type and not hasattr(self, service_type):
            setattr(self, service_type, base_client_instance)


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

    def cs_request(self, url, method, **kwargs):
        return self.http_client.cs_request(
            self, url, method, **kwargs)

    def head(self, url, **kwargs):
        return self.cs_request(url, "HEAD", **kwargs)

    def get(self, url, **kwargs):
        return self.cs_request(url, "GET", **kwargs)

    def post(self, url, **kwargs):
        return self.cs_request(url, "POST", **kwargs)

    def put(self, url, **kwargs):
        return self.cs_request(url, "PUT", **kwargs)

    def delete(self, url, **kwargs):
        return self.cs_request(url, "DELETE", **kwargs)

    def patch(self, url, **kwargs):
        return self.cs_request(url, "PATCH", **kwargs)
