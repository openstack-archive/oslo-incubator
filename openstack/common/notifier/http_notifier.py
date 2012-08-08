# Copyright 2012 NTT
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

"""
HTTP POST notifier for OpenStack projects.

To use this notifier, set the 'notification_driver' to
'<project_name>.openstack.common.notifier.http_notifier' and specify the HTTP
server URL in 'tracking_callback_url' config param.

The notifier replaces the place holder '{id}' in the 'tracking_callback_url'
with the request id.

The default behavior of this notifier is to send out notifications for all the
events. To receive notifications for specific events, specify the list of
events to be notified in the config param 'callback_events_filter'.
"""

import httplib
import json
from urlparse import urlparse

from eventlet import greenthread

from openstack.common import cfg
from openstack.common.gettextutils import _
from openstack.common import log as logging

http_notify_opts = [
    cfg.StrOpt('tracking_callback_url',
               default='http://localhost:9999/cc/action/openstack/{id}/notify',
               help='HOST for connecting to complete notify'),
    cfg.ListOpt('callback_events_filter',
                default=['all'],
                help='list of events for which notification should be sent.'
                     'set it to "all" to receive notification for all '
                     'events.')
    ]

CONF = cfg.CONF
CONF.register_opts(http_notify_opts)
LOG = logging.getLogger(__name__)


def notify(context, message):
    if not context:
        LOG.error(_("Notification not sent as context is not available."))
        return

    if 'all' in CONF.callback_events_filter or \
            message['event_type'] in CONF.callback_events_filter:
        url = CONF.tracking_callback_url.replace("{id}", context.request_id)

        greenthread.spawn_n(http_notify, url, message)


def http_notify(url, body):
    headers = {'Content-type': "application/json"}
    body = json.dumps(body)
    try:
        urlps = urlparse(url)
        connection = httplib.HTTPConnection(urlps.netloc)
        connection.request("POST", urlps.path, body, headers)
        response = connection.getresponse()
        response_str = response.read()
        if response.status < 400:
            LOG.debug(_("HTTP notification successful. "
                      "(url=%s body=%s)") % (url, body))
        else:
            LOG.warning(_("HTTP notification failed. (status=%s response=%s)")
                         % (response.status, response_str))
        connection.close()
    except (IOError, httplib.HTTPException) as e:
        LOG.warning(_("Connection error contacting notification server. "
                    "(error=%s)") % unicode(e))
    except Exception as e:
        LOG.warning(_("Error sending notification. (error=%s)") % unicode(e))
