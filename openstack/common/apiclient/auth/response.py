# vim: tabstop=4 shiftwidth=4 softtabstop=4

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

import logging

from openstack.common.apiclient import exceptions
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
