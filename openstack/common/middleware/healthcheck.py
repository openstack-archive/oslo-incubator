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

import contextlib
import json
import os
import platform
import sys

from StringIO import StringIO

from webob import Response

from eventlet import debug

from openstack.common import cfg
from openstack.common import utils
from openstack.common import wsgi


health_check_opts = [
    cfg.BoolOpt('health_extended_status',
                default=True,
                help="Show extended health status"),
]

CONF = cfg.CONF
CONF.register_opts(health_check_opts)


# Adds on a write + newline function, very useful....
class StringIOPlus(StringIO):
    def writeline(self, line):
        self.write(line)
        self.write(os.linesep)


@contextlib.contextmanager
def wrap(name, output):
    output.writeline(name)
    output.writeline("-" * 80)
    yield name
    output.writeline("-" * 80)


class HealthCheckMiddleware(wsgi.Middleware):
    """
    Healthcheck middleware used for monitoring/load balancing/operational usage

    If the path is /healthcheck, it will respond with "OK" in the body.

    This is useful for the following reasons:
    1. Load balancers can 'ping' this url to determine service availability
    2. Provides a endpoint that is similar to 'mod_status' in apache which
       can provide details (or no details, depending on if configured) about
       the activity of the server (as much as we can get from eventlet/python)
    """

    def process_request(self, req):
        # TODO(harlowja) can we make this configurable?
        # not everyone probably wants it to be /status...
        if req.path != '/status':
            return None
        else:
            return self._form_status(req)

    def _form_basic_status(self, req):
        """Returns a 200 response with "OK" in the body."""
        return Response(request=req, body="OK", content_type="text/plain")

    def form_extended_status(self, req):
        """Returns a 200 response with system +
           request + python + eventlet info in the body."""
        output = StringIOPlus()
        with wrap("Request environment", output):
            req_environ = {}
            for (k, v) in req.environ.items():
                req_environ[k] = str(v)
            if req_environ:
                output.writeline(json.dumps(req_environ, indent=4, sort_keys=True))
        with wrap("Python path", output):     
            output.writeline(json.dumps(sys.path, indent=4))
        with wrap("Python encodings", output):     
            encodings = {
                'default': sys.getdefaultencoding(),
                'filesystem': sys.getfilesystemencoding(),
            }
            output.writeline(json.dumps(encodings, indent=4))
        with wrap("Python modules", output):
            sys_modules = {}
            for (name, mod) in sys.modules.items():
                if not name or name.startswith('_'):
                    continue
                try:
                    sys_modules[name] = mod.__file__
                except:
                    sys_modules[name] = '???'
            output.writeline(json.dumps(sys_modules, indent=4, sort_keys=True))
        with wrap("Python version", output):
            output.writeline(sys.version)
        with wrap("Eventlet hub listeners", output):
            output.writeline(debug.format_hub_listeners())
        with wrap("Eventlet hub timers", output):
            output.writeline(debug.format_hub_timers())
        with wrap("System information", output):
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
            except IOError:
                pass
            output.writeline(json.dumps(sys_info, indent=4, sort_keys=True))
        return Response(request=req, body=output.getvalue(),
                        content_type="text/plain")

    def _form_status(self, req):
        if not CONF.health_extended_status:
            return self._form_basic_status(req)
        else:
            try:
                return self._form_extended_status(req)
            except Exception:
                # Always return something valid
                return self._form_basic_status(req)
