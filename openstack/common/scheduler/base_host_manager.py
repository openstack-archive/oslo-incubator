# Copyright (c) 2011 OpenStack, LLC.
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
Base settings of managing hosts in the current zone.
"""

from oslo.config import cfg

import UserDict

from openstack.common import exception
from openstack.common import log as logging
from openstack.common.scheduler import filters
from openstack.common.scheduler import weights
from openstack.common import timeutils

host_manager_opts = [
    cfg.MultiStrOpt('scheduler_available_filters',
                    default=['openatsck.common.scheduler.filters.'
                             'standard_filters'],
                    help='Filter classes available to the scheduler which may '
                         'be specified more than once.'),
    cfg.ListOpt('scheduler_default_filters',
                default=[],
                help='Which filter class names to use for filtering hosts '
                     'when not specified in the request.'),
    cfg.ListOpt('scheduler_weight_classes',
                default=['openstack.common.scheduler.weights.all_weighers'],
                help='Which weight class names to use for weighing hosts'),
    cfg.ListOpt('scheduler_default_weighers',
                default=[],
                help='Which weigher class names to use for weighing hosts.'),
]

CONF = cfg.CONF
CONF.register_opts(host_manager_opts)

LOG = logging.getLogger(__name__)


class ReadOnlyDict(UserDict.IterableUserDict):
    """A read-only dict."""
    def __init__(self, source=None):
        self.data = {}
        self.update(source)

    def __setitem__(self, key, item):
        raise TypeError

    def __delitem__(self, key):
        raise TypeError

    def clear(self):
        raise TypeError

    def pop(self, key, *args):
        raise TypeError

    def popitem(self):
        raise TypeError

    def update(self, source=None):
        if source is None:
            return
        elif isinstance(source, UserDict.UserDict):
            self.data = source.data
        elif isinstance(source, type({})):
            self.data = source
        else:
            raise TypeError


class BaseHostState(object):
    """Mutable and immutable information tracked for a host."""

    def __init__(self, host, node=None, capabilities=None, service=None):
        self.host = host
        self.nodename = node
        self.update_capabilities(capabilities, service)

        self.spec_service_settings_init()

        self.updated = None

    def spec_service_settings_init(self):
        pass

    def update_capabilities(self, capabilities=None, service=None):
        # Read-only capability dicts

        if capabilities is None:
            capabilities = {}
        self.capabilities = ReadOnlyDict(capabilities)
        if service is None:
            service = {}
        self.service = ReadOnlyDict(service)

    def _statmap(self, stats):
        return dict((st['key'], st['value']) for st in stats)

    def __repr__(self):
        raise NotImplementedError(_("Must implement a representation "
                                  "for HostState"))


class BaseHostManager(object):
    """Base HostManager class."""

    host_state_cls = BaseHostState

    def __init__(self, component_name, *args, **kwargs):
        self.service_states = {}
        self.host_state_map = {}
        self.filter_handler = filters.HostFilterHandler('%(component_name)s.'
                                                        'scheduler.filters')
        self.filter_classes = self.filter_handler.get_all_classes()
        self.weight_handler = weights.HostWeightHandler('%(component_name)s.'
                                                        'scheduler.weights')
        self.weight_classes = self.weight_handler.get_all_classes()

        #Conf and service_name should be redefined in child classes.
        self.conf = None
        self.service_name = None

    def _choose_host_filters(self, filter_cls_names):
        """Since the caller may specify which filters to use we need
        to have an authoritative list of what is permissible. This
        function checks the filter names against a predefined set
        of acceptable filters.
        """
        if filter_cls_names is None:
            filter_cls_names = self.conf.scheduler_default_filters
        if not isinstance(filter_cls_names, (list, tuple)):
            filter_cls_names = [filter_cls_names]
        good_filters = []
        bad_filters = []
        for filter_name in filter_cls_names:
            found_class = False
            for cls in self.filter_classes:
                if cls.__name__ == filter_name:
                    found_class = True
                    good_filters.append(cls)
                    break
            if not found_class:
                bad_filters.append(filter_name)
        if bad_filters:
            msg = ", ".join(bad_filters)
            raise exception.SchedulerHostFilterNotFound(filter_name=msg)
        return good_filters

    def _choose_host_weighers(self, weight_cls_names):
        """Since the caller may specify which weighers to use, we need
        to have an authoritative list of what is permissible. This
        function checks the weigher names against a predefined set
        of acceptable weighers.
        """
        if weight_cls_names is None:
            weight_cls_names = self.conf.scheduler_default_weighers
        if not isinstance(weight_cls_names, (list, tuple)):
            weight_cls_names = [weight_cls_names]

        good_weighers = []
        bad_weighers = []
        for weigher_name in weight_cls_names:
            found_class = False
            for cls in self.weight_classes:
                if cls.__name__ == weigher_name:
                    good_weighers.append(cls)
                    found_class = True
                    break
            if not found_class:
                bad_weighers.append(weigher_name)
        if bad_weighers:
            msg = ", ".join(bad_weighers)
            raise exception.SchedulerHostWeigherNotFound(weigher_name=msg)
        return good_weighers

    def _get_filter_classes(self, filter_class_names=None):
        return self._choose_host_filters(filter_class_names)

    def get_filtered_hosts(self, hosts, filter_properties,
                           filter_class_names=None):
        """Filter hosts and return only ones passing all filters.
        """
        filter_classes = self._get_filter_classes(filter_class_names)
        return self.filter_handler.get_filtered_objects(filter_classes,
                                                        hosts,
                                                        filter_properties)

    def _get_weigher_classes(self, weigher_class_names=None):
        return self._choose_host_weighers(weigher_class_names)

    def get_weighed_hosts(self, hosts, weight_properties,
                          weigher_class_names=None):
        """Weigh the hosts."""
        weigher_classes = self._get_weigher_classes(weigher_class_names)
        return self.weight_handler.get_weighed_objects(weigher_classes,
                                                       hosts,
                                                       weight_properties)

    def _get_state_key(self, host, capabilities):
        return host

    def update_service_capabilities(self, service_name, host, capabilities):
        """Update the per-service capabilities based on this notification."""
        if service_name != self.service_name:
            LOG.debug(_('Ignoring %(service_name)s service update '
                        'from %(host)s'), locals())
            return
        state_key = self._get_state_key(host, capabilities)
        LOG.debug(_("Received %(service_name)s service update from "
                    "%(state_key)s.") % locals())

        # Copy the capabilities, so we don't modify the original dict
        capab_copy = dict(capabilities)
        capab_copy["timestamp"] = timeutils.utcnow()  # Reported time
        self.service_states[state_key] = capab_copy

    def get_service_capabilities(self, *args, **kwargs):
        raise NotImplementedError(_("Must implement for HostState"))

    def get_host_list(self, *args, **kwargs):
        raise NotImplementedError(_("Must implement for HostState"))
