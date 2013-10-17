# Copyright 2013 OpenStack Foundation.
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

import fnmatch
import six
import yaml

from oslo.config import cfg
from stevedore import dispatch

from openstack.common.gettextutils import _  # noqa
from openstack.common import log as logging

LOG = logging.getLogger(__name__)

router_config = cfg.StrOpt('routing_notifier_config', default='',
                           help='RoutingNotifier configuration file location')

disabled_notify_drivers = cfg.MultiStrOpt('disabled_notification_driver',
                                          default=[],
                                          help='Entry point name of disabled '
                                               'notification driver')
CONF = cfg.CONF
CONF.register_opt(router_config)
CONF.register_opt(disabled_notify_drivers)

NOTIFIER_PLUGIN_NAMESPACE = 'openstack.common.notifier.drivers'

plugin_manager = None
groups = None


# NOTE(sandy): Be sure to copy the routing notifier entry points from
#              oslo-incubator/setup.cfg to your project.

def _should_load_plugin(ext, *args, **kwargs):
    return ext.name not in CONF.disabled_notification_driver


def _get_notifier_config_file(filename):
    """Broken out for testing.
    """
    return file(filename, 'r')


def _load_notifiers():
    """One-time load of notifier config file.
    """
    global groups
    global plugin_manager

    LOG.debug(_('loading notifiers from %(namespace)s') %
              {'namespace': NOTIFIER_PLUGIN_NAMESPACE})
    plugin_manager = dispatch.DispatchExtensionManager(
        namespace=NOTIFIER_PLUGIN_NAMESPACE,
        check_func=_should_load_plugin,
        invoke_on_load=False,
        invoke_args=None)
    if not list(plugin_manager):
        LOG.warning(_("Failed to load any notifiers "
                      "for %(namespace)s") %
                    {'namespace': NOTIFIER_PLUGIN_NAMESPACE})

    groups = {}
    filename = CONF.routing_notifier_config
    if filename:
        groups = yaml.load(_get_notifier_config_file(filename))


def _get_drivers_for_message(group, event_type, priority):
    """Which drivers should be called for this event_type
       or priority.
    """
    accepted_drivers = set()

    for block in group:
        for driver, rules in six.iteritems(block):
            checks = []
            for key, patterns in six.iteritems(rules):
                if key == 'accepted_events':
                    c = [fnmatch.fnmatch(event_type, p)
                         for p in patterns]
                    checks.append(any(c))
                if key == 'accepted_priorities':
                    c = [fnmatch.fnmatch(priority, p.lower())
                         for p in patterns]
                    checks.append(any(c))
            if all(checks):
                accepted_drivers.add(driver)

    return list(accepted_drivers)


def _filter_func(ext, context, message):
    """True/False if the driver should be called for this message.
    """
    # context is unused here, but passed in by map()
    global groups

    # Fail if these aren't present ...
    event_type = message['event_type']
    priority = message['priority'].lower()

    accepted_drivers = set()
    for group in groups.values():
        accepted_drivers.update(_get_drivers_for_message(group, event_type,
                                                         priority))

    return ext.name in accepted_drivers


def _call_notify(ext, context, message):
    LOG.info(_("Routing '%s' notification to '%s' driver") %
             (message.get('event_type'), ext.name))
    ext.obj.notify(context, message)


def notify(context, message):
    global plugin_manager

    if not plugin_manager:
        _load_notifiers()

    plugin_manager.map(_filter_func, _call_notify, context, message)
