# Copyright 2012 Grid Dynamics.
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

from openstack.common.apiclient.client import HttpClient


def lazyproperty(fn):
    attr_name = '_lazy_' + fn.__name__
    @property
    def _lazyprop(self):
        if not hasattr(self, attr_name):
            setattr(self, attr_name, fn(self))
        return getattr(self, attr_name)
    return _lazyprop


class ClientSet(object):

    def __init__(self, **kwargs):
        try:
            self.http_client = kwargs["http_client"]
        except KeyError:
            self.http_client = HttpClient(**kwargs)

    @lazyproperty
    def keystone(self):
        return self.identity_admin

    @lazyproperty
    def nova(self):
        return self.compute

    @lazyproperty
    def glance(self):
        return self.image

    @lazyproperty
    def identity_admin(self):
        from openstack.common.apiclient.keystone.client import IdentityAdminClient
        return IdentityAdminClient(self.http_client)

    @lazyproperty
    def identity_public(self):
        from openstack.common.apiclient.keystone.client import IdentityPublicClient
        return IdentityPublicClient(self.http_client)

    @lazyproperty
    def compute(self):
        from openstack.common.apiclient.nova.client import ComputeClient
        from openstack.common.apiclient.nova import networks
        from openstack.common.apiclient.nova import fping
        return ComputeClient(self.http_client, extensions=[fping, networks])

    @lazyproperty
    def volume(self):
        from openstack.common.apiclient.nova.client import VolumeClient
        return VolumeClient(self.http_client)

    @lazyproperty
    def image(self):
        from openstack.common.apiclient.glance.v1.client import ImageClient
        return ImageClient(self.http_client)

    @lazyproperty
    def billing(self):
        from openstack.common.apiclient.billing.client import BillingClient
        return BillingClient(self.http_client)

    @lazyproperty
    def compute_ext(self):
        from openstack.common.apiclient.compute_ext.client import ComputeExtClient
        return ComputeExtClient(self.http_client)
