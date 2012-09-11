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

import StringIO

import contextlib
import json
import os
import platform
import sys
import types

from webob import Response

from eventlet import debug

from openstack.common import wsgi

# Adds on a write + newline function, very useful....
class StringIOPlus(StringIO.StringIO):
    def writeline(self, line):
        self.write(line)
        self.write(os.linesep)


@contextlib.contextmanager
def wrap(name, output):
    output.writeline(name)
    output.writeline("-" * 80)
    yield name
    output.writeline("-" * 80)


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

        Detailed @ http://paste.openstack.org/show/20890/
        Basic @ http://paste.openstack.org/show/20891/

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
            return None
        if not self.extended_status or req.method.lower() in ['head']:
            return self._form_basic_status(req)
        else:
            try:
                return self._form_extended_status(req)
            except Exception:
                # Always return something valid
                return self._form_basic_status(req)

    def _form_basic_status(self, req):
        """Returns a 200 response with an empty body."""
        return Response(request=req, content_type="text/plain")

    def _gather_system_information(self):
        output = StringIOPlus()
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
        return output.getvalue()

    def _gather_request_information(self, req):
        output = StringIOPlus()
        with wrap("Request environment", output):
            req_environ = {}
            for (k, v) in req.environ.items():
                # Filter out file handles
                if isinstance(v, types.FileType):
                    continue
                req_environ[k] = str(v)
            output.writeline(json.dumps(req_environ, indent=4, sort_keys=True))
        return output.getvalue()

    def _form_extended_status(self, req):
        """Returns a 200 response with system +
           request + python + eventlet info in the body."""
        output = StringIOPlus()
        output.write(self._gather_request_information(req))
        output.write(self._gather_system_information())
        return Response(request=req, body=output.getvalue(),
                        content_type="text/plain")
