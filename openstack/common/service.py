# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2010 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
# Copyright 2011 Justin Santa Barbara
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

"""Generic Node base class for all workers that run on hosts."""

import signal
import sys

import eventlet
import greenlet

from openstack.common import cfg
from openstack.common import importutils
from openstack.common import log as logging
from openstack.common.gettextutils import _


LOG = logging.getLogger(__name__)

CONF = cfg.CONF


class Launcher(object):
    """Launch one or more services and wait for them to complete."""

    def __init__(self):
        """Initialize the service launcher.

        :returns: None

        """
        self._services = []

    @staticmethod
    def run_server(server):
        """Start and wait for a server to finish.

        :param service: Server to run and wait for.
        :returns: None

        """
        server.start()
        server.wait()

    def launch_server(self, server):
        """Load and start the given server.

        :param server: The server you would like to start.
        :returns: None

        """
        gt = eventlet.spawn(self.run_server, server)
        self._services.append(gt)

    def stop(self):
        """Stop all services which are currently running.

        :returns: None

        """
        for service in self._services:
            service.kill()

    def wait(self):
        """Waits until all services have been stopped, and then returns.

        :returns: None

        """
        for service in self._services:
            try:
                service.wait()
            except greenlet.GreenletExit:
                pass


class ServiceLauncher(Launcher):
    def _handle_signal(self, signo, frame):
        signame = {signal.SIGTERM: 'SIGTERM', signal.SIGINT: 'SIGINT'}[signo]
        LOG.info(_('Caught %s, exiting'), signame)

        # Allow the process to be killed again and die from natural causes
        signal.signal(signal.SIGTERM, signal.SIG_DFL)
        signal.signal(signal.SIGINT, signal.SIG_DFL)

        sys.exit(1)

    def wait(self):
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

        status = None
        try:
            super(ServiceLauncher, self).wait()
        except SystemExit as exc:
            status = exc.code
            self.stop()

        if status is not None:
            sys.exit(status)


class Service(object):
    """Service object for binaries running on hosts.

    A service takes a manager."""

    def __init__(self, host, manager, *args, **kwargs):
        self.host = host
        self.manager = manager

    def start(self):
        if self.manager:
            self.manager.init_host()

    def stop(self):
        pass

    def wait(self):
        pass


# NOTE(vish): the global launcher is to maintain the existing
#             functionality of calling service.serve +
#             service.wait
_launcher = None


def serve(server, workers=None):
    global _launcher
    if _launcher:
        raise RuntimeError(_('serve() can only be called once'))

    _launcher = ServiceLauncher()
    _launcher.launch_server(server)


def wait():
    _launcher.wait()
