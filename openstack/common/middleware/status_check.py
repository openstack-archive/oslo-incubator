# Copyright (c) 2010-2012 OpenStack, LLC.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import httplib
import os
import platform
import sys

from webob import Response

from eventlet import hubs

from openstack.common import jsonutils
from openstack.common import wsgi


class StatusCheck(wsgi.Middleware):
    """
    Status and or health check middleware used
    for monitoring/load balancing/operational usage

    This is useful for the following reasons:
    1. Load balancers can 'ping' this url to determine service availability
    2. Provides a endpoint that is similar to 'mod_status' in apache which
       can provide details (or no details, depending on if configured) about
       the activity of the server (as much as we can get from eventlet/python)

    To enable the basic health check perform adjust
    the following in your paste files:

    1. Add this to get a simple no body response
        [filter:healthcheck]
        paste.filter_factory = nova.common.status_check:StatusCheck.factory
        path = /healthcheck (or other path)
    2. Adjust all pipelines to have this as the first member

    To enable more 'mod_status' like health checks perform adjust
    the following in your paste files:
    0. WARNING WARNING!! ensure you restrict the ips that can call this
        endpoint to avoid disclosing any system information that you
        would not like to expose...
    1. Add this to get a more 'mod_status' like response
        [filter:healthcheck]
        paste.filter_factory = nova.common.status_check:StatusCheck.factory
        path = /status (or other path)
        extended_status = 1
    2. Adjust all pipelines to have this as the first member

    Example outputs:

        Detailed @ http://paste.openstack.org/show/20910/
        Basic @ http://paste.openstack.org/show/20911/

    TODO(harlowja):
    1. Add in more advanced eventlet information such as bytes received,
       bytes sent, pool size, pool activity (waiting, idle...)

    """
    def __init__(self, application, path=None, extended_status=False):
        wsgi.Middleware.__init__(self, application)
        self.path = (path or '/healthcheck').strip()
        if str(extended_status).lower().strip() in ['true', '1', 'on']:
            self.extended_status = True
        else:
            self.extended_status = False

    def process_request(self, req):
        if req.path != self.path:
            # Not ours to handle
            return None
        if not self.extended_status or req.method.lower() == 'head':
            return self._form_basic_status(req)
        else:
            try:
                return self._form_extended_status(req)
            except Exception:
                # Always return something valid
                return self._form_basic_status(req)

    def _form_basic_status(self, req):
        """Returns a 200/204 response with an empty body."""
        if req.method.lower() == 'head':
            return Response(request=req, status=httplib.NO_CONTENT,
                            content_type="text/plain")
        else:
            return Response(request=req, status=httplib.OK, body='OK',
                            content_type="text/plain")

    def _gather_eventlet_information(self):
        hub = hubs.get_hub()
        readers = []
        for r in hub.get_readers():
            readers.append("%r" % (r))
        writers = []
        for w in hub.get_writers():
            writers.append("%r" % (w))
        timers = []
        for t in hub.timers:
            timers.append("%r" % (t))
        eventlet_info = {
            'listeners': {
                'readers': readers,
                'writers': writers,
            },
            'timers': timers,
        }
        return eventlet_info


    def _gather_python_information(self):
        python_info = {
            'path': sys.path,
            'encodings': {
                'default': sys.getdefaultencoding(),
                'filesystem': sys.getfilesystemencoding(),
            },
        }
        sys_modules = {}
        for (name, mod) in sys.modules.items():
            if not name or name.startswith('_'):
                continue
            try:
                for attr in ('__file__', '__name__'):
                    if hasattr(mod, attr):
                        sys_modules[name] = getattr(mod, attr)
                        break
            except AttributeError:
                if mod is not None:
                    sys_modules[name] = str(mod)
                else:
                    continue
        python_info['modules'] = sys_modules
        python_info['version'] = [x.strip() for x in sys.version.split("\n")
                                  if x.strip()]
        return python_info

    def _gather_app_information(self):
        # Override with any app details gathered
        # by looking into app resources/db/mq...
        return {}

    def _gather_system_information(self):
        times = os.times()
        sys_info = {
            'user_time': times[0],
            'system_time': times[1],
            'uname': " ".join(platform.uname()),
            'architecture': " ".join(platform.architecture()),
        }
        try:
            sys_info['load_avg'] = "%.2f/%.2f/%.2f" % (os.getloadavg())
        except OSError:
            pass
        try:
            with open('/proc/uptime', 'r') as fh:
                sys_info['uptime'] = fh.read().split()[0].strip()
        except (IOError, IndexError):
            pass
        return sys_info

    def _gather_information(self, req):
        info = {
            'python': self._gather_python_information(),
            'eventlet': self._gather_eventlet_information(),
            'system': self._gather_system_information(),
            'application': self._gather_app_information(),
        }
        return info

    def _form_extended_status(self, req):
        """Returns a 200 response with system +
           + python + eventlet info in the body."""
        gathered_info = self._gather_information(req)
        return Response(request=req,
                        body=jsonutils.dumps(gathered_info,
                                             indent=4, sort_keys=True),
                        content_type="application/json")
