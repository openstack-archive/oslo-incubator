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

import httplib
import json
from eventlet import greenthread
from urlparse import urlparse

from openstack.common import cfg
from openstack.common import context as req_context
from openstack.common.gettextutils import _
from openstack.common import log as logging

http_notify_opts = [
    cfg.StrOpt('tracking_callback_url',
               default='http://localhost:9999/cc/action/openstack/{id}/notify',
               help='HOST for connecting to complete notify'),
    cfg.ListOpt('callback_events_filter',
                default=[],
                help='list of events for which notification should be sent.'
                     'leave it empty to receive notification for all events.')
    ]

CONF = cfg.CONF
CONF.register_opts(http_notify_opts)
LOG = logging.getLogger(__name__)


status_dict = {"INFO": "SUCCESS",
               "ERROR": "ERROR"}


def notify(context, message):
    event_type = message['event_type']
    priority = message['priority']

    if not context:
        context = req_context.get_admin_context()

    if not CONF.callback_events_filter or \
            event_type in CONF.callback_events_filter:
        url = CONF.tracking_callback_url.replace("{id}", context.request_id)

        request_body = json.dumps(
                            dict(status=status_dict[priority],
                                 message="status"))
        greenthread.spawn_n(http_notify, url, request_body)


def http_notify(url, body):
    headers = {'Content-type': "application/json"}
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
    except Exception as e:
        LOG.warning(_("Connection error contacting notification server. "
                    "(error=%s)") % str(e))
