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

"""Proxy openstack.common.notifier.api.notify() to look like an
   oslo.messaging.notify Driver"""


class NotifierProxy(object):
    def __init__(self, notifier_api, publisher_id):
        self.notifier_api = notifier_api
        self.publisher_id = publisher_id

    def audit(self, ctxt, event_type, payload):
        # No audit in old notifier.
        self.notifier_api.notify(ctxt, self.publisher_id, event_type, payload,
                                 'INFO')

    def debug(self, ctxt, event_type, payload):
        self.notifier_api.notify(ctxt, self.publisher_id, event_type, payload,
                                 'DEBUG')

    def info(self, ctxt, event_type, payload):
        self.notifier_api.notify(ctxt, self.publisher_id, event_type, payload,
                                 'INFO')

    def warn(self, ctxt, event_type, payload):
        self.notifier_api.notify(ctxt, self.publisher_id, event_type, payload,
                                 'WARN')

    warning = warn

    def error(self, ctxt, event_type, payload):
        self.notifier_api.notify(ctxt, self.publisher_id, event_type, payload,
                                 'ERROR')

    def critical(self, ctxt, event_type, payload):
        self.notifier_api.notify(ctxt, self.publisher_id, event_type, payload,
                                 'CRITICAL')
