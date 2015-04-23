
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

# An eventlet server that runs a service.py pool.

# Opens listens on a random port. The port # is printed to stdout.

import socket
import sys

import eventlet.wsgi
import greenlet

from oslo_config import cfg

from openstack.common import service


CONF = cfg.CONF

POOL_SIZE = 1


class Server(object):
    """Server class to manage multiple WSGI sockets and applications."""

    def __init__(self, application, host=None, port=None, keepalive=False,
                 keepidle=None):
        self.application = application
        self.host = host or '0.0.0.0'
        self.port = port or 0
        # Pool for a green thread in which wsgi server will be running
        self.pool = eventlet.GreenPool(POOL_SIZE)
        self.socket_info = {}
        self.greenthread = None
        self.keepalive = keepalive
        self.keepidle = keepidle
        self.socket = None

    def listen(self, key=None, backlog=128):
        """Create and start listening on socket.

        Call before forking worker processes.

        Raises Exception if this has already been called.
        """

        # TODO(dims): eventlet's green dns/socket module does not actually
        # support IPv6 in getaddrinfo(). We need to get around this in the
        # future or monitor upstream for a fix.
        # Please refer below link
        # (https://bitbucket.org/eventlet/eventlet/
        # src/e0f578180d7d82d2ed3d8a96d520103503c524ec/eventlet/support/
        # greendns.py?at=0.12#cl-163)
        info = socket.getaddrinfo(self.host,
                                  self.port,
                                  socket.AF_UNSPEC,
                                  socket.SOCK_STREAM)[0]

        self.socket = eventlet.listen(info[-1], family=info[0],
                                      backlog=backlog)

    def start(self, key=None, backlog=128):
        """Run a WSGI server with the given application."""

        if self.socket is None:
            self.listen(key=key, backlog=backlog)

        dup_socket = self.socket.dup()
        if key:
            self.socket_info[key] = self.socket.getsockname()

        # Optionally enable keepalive on the wsgi socket.
        if self.keepalive:
            dup_socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)

            if self.keepidle is not None:
                dup_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE,
                                      self.keepidle)

        self.greenthread = self.pool.spawn(self._run,
                                           self.application,
                                           dup_socket)

    def stop(self):
        if self.greenthread is not None:
            self.greenthread.kill()

    def wait(self):
        """Wait until all servers have completed running."""
        try:
            self.pool.waitall()
        except KeyboardInterrupt:
            pass
        except greenlet.GreenletExit:
            pass

    def reset(self):
        """Required by the service interface.

        The service interface is used by the launcher when receiving a
        SIGHUP. The service interface is defined in
        openstack.common.service.Service.

        Test server does not need to do anything here.
        """
        pass

    def _run(self, application, socket):
        """Start a WSGI server with a new green thread pool."""
        try:
            eventlet.wsgi.server(socket, application, debug=False)
        except greenlet.GreenletExit:
            # Wait until all servers have completed running
            pass


class ServerWrapper(object):
    """Wraps a Server with some launching info & capabilities."""

    def __init__(self, server, workers):
        self.server = server
        self.workers = workers

    def launch_with(self, launcher):
        self.server.listen()
        if self.workers > 1:
            # Use multi-process launcher
            launcher.launch_service(self.server, self.workers)
        else:
            # Use single process launcher
            launcher.launch_service(self.server)


def run():

    CONF()

    eventlet.patcher.monkey_patch()

    launcher = service.ProcessLauncher()

    def hi_app(environ, start_response):
        start_response('200 OK', [('Content-Type', 'application/json')])
        yield 'hi'

    server = ServerWrapper(Server(hi_app), workers=3)
    server.launch_with(launcher)

    print('%s' % server.server.socket.getsockname()[1])

    sys.stdout.flush()

    launcher.wait()


if __name__ == '__main__':
    run()
