# Copyright 2011 OpenStack LLC.
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

import inspect
import uuid

from openstack.common import cfg
from openstack.common import context
from openstack.common.gettextutils import _
from openstack.common import importutils
from openstack.common import jsonutils
from openstack.common import log as logging
from openstack.common import timeutils


LOG = logging.getLogger(__name__)

notifier_opts = [
    cfg.MultiStrOpt('notification_driver',
                    default=[],
                    help='Default driver for sending notifications'),
    cfg.MultiStrOpt('list_notifier_drivers',
                    default=[],
           help='DEPRECATED  Use multi-option notification_driver instead.'),
    cfg.StrOpt('default_notification_level',
               default='INFO',
               help='Default notification level for outgoing notifications'),
    cfg.StrOpt('default_publisher_id',
               default='$host',
               help='Default publisher_id for outgoing notifications'),
]

CONF = cfg.CONF
CONF.register_opts(notifier_opts)

WARN = 'WARN'
INFO = 'INFO'
ERROR = 'ERROR'
CRITICAL = 'CRITICAL'
DEBUG = 'DEBUG'

log_levels = (DEBUG, WARN, INFO, ERROR, CRITICAL)


class BadPriorityException(Exception):
    pass


def notify_decorator(name, fn):
    """ decorator for notify which is used from utils.monkey_patch()

        :param name: name of the function
        :param function: - object of the function
        :returns: function -- decorated function

    """
    def wrapped_func(*args, **kwarg):
        body = {}
        body['args'] = []
        body['kwarg'] = {}
        for arg in args:
            body['args'].append(arg)
        for key in kwarg:
            body['kwarg'][key] = kwarg[key]

        ctxt = context.get_context_from_function_and_args(fn, args, kwarg)
        notify(ctxt,
               CONF.default_publisher_id,
               name,
               CONF.default_notification_level,
               body)
        return fn(*args, **kwarg)
    return wrapped_func


def publisher_id(service, host=None):
    if not host:
        host = CONF.host
    return "%s.%s" % (service, host)


def notify(context, publisher_id, event_type, priority, payload):
    """Sends a notification using the specified driver

    :param publisher_id: the source worker_type.host of the message
    :param event_type:   the literal type of event (ex. Instance Creation)
    :param priority:     patterned after the enumeration of Python logging
                         levels in the set (DEBUG, WARN, INFO, ERROR, CRITICAL)
    :param payload:       A python dictionary of attributes

    Outgoing message format includes the above parameters, and appends the
    following:

    message_id
      a UUID representing the id for this notification

    timestamp
      the GMT timestamp the notification was sent at

    The composite message will be constructed as a dictionary of the above
    attributes, which will then be sent via the transport mechanism defined
    by the driver.

    Message example::

        {'message_id': str(uuid.uuid4()),
         'publisher_id': 'compute.host1',
         'timestamp': timeutils.utcnow(),
         'priority': 'WARN',
         'event_type': 'compute.create_instance',
         'payload': {'instance_id': 12, ... }}

    """
    if priority not in log_levels:
        raise BadPriorityException(
            _('%s not in valid priorities') % priority)

    # Ensure everything is JSON serializable.
    payload = jsonutils.to_primitive(payload, convert_instances=True)

    msg = dict(message_id=str(uuid.uuid4()),
               publisher_id=publisher_id,
               event_type=event_type,
               priority=priority,
               payload=payload,
               timestamp=str(timeutils.utcnow()))

    for driver in _get_drivers():
        try:
            driver.notify(context, msg)
        except Exception, e:
            LOG.exception(_("Problem '%(e)s' attempting to "
              "send to notification system. Payload=%(payload)s") %
                            locals())


class ImportFailureNotifier(object):
    """Noisily re-raises some exception a few times when notify is called."""

    def __init__(self, exception):
        self.exception = exception

    def notify(self, context, message):
        raise self.exception


drivers = None


def _get_drivers():
    """Instantiate, cache, and return drivers based on the CONF."""
    global drivers
    if drivers is None:
        drivers = []
        for notification_driver in CONF.notification_driver:
            try:
                drivers.append(importutils.import_module(notification_driver))
            except ImportError as e:
                drivers.append(ImportFailureNotifier(e))

        # FIXME: This block is transitional, should maybe be removed
        # in Grizzly.
        if CONF.list_notifier_drivers:
            LOG.warn(_("list_notifier_drivers is deprecated."
                       "The notificiation_driver option can now take"
                       "multiple values; use that instead."))
            for ln_driver in CONF.list_notifier_drivers:
                try:
                    drivers.append(importutils.import_module(ln_driver))
                except ImportError as e:
                    drivers.append(ImportFailureNotifier(e))
    return drivers


def add_driver(notification_driver):
    """Add a notification driver at runtime."""
    # Make sure the driver list is initialized.
    _get_drivers()
    if isinstance(notification_driver, basestring):
        # Load and add
        try:
            drivers.append(importutils.import_module(notification_driver))
        except ImportError as e:
            drivers.append(ImportFailureNotifier(e))
    else:
        # Driver is already loaded; just add the object.
        drivers.append(notification_driver)


def _object_name(obj):
    name = []
    if hasattr(obj, '__module__'):
        name.append(obj.__module__)
    if hasattr(obj, '__name__'):
        name.append(obj.__name__)
    else:
        name.append(obj.__class__.__name__)
    return '.'.join(name)


def remove_driver(notification_driver):
    """Remove a notification driver at runtime."""
    # Make sure the driver list is initialized.
    _get_drivers()
    removed = False
    if notification_driver in drivers:
        # We're removing an object.  Easy.
        drivers.remove(notification_driver)
        removed = True
    else:
        # We're removing a driver by name.  Search for it.
        for driver in drivers:
            if _object_name(driver) == notification_driver:
                drivers.remove(driver)
                removed = True

    if not removed:
        raise ValueError("Cannot remove; %s is not in list" %
                         notification_driver)


def _reset_drivers():
    """Used by unit tests to reset the drivers."""
    global drivers
    drivers = None
