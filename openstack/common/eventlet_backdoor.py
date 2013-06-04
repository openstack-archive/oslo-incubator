# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright (c) 2012 OpenStack Foundation.
# Administrator of the National Aeronautics and Space Administration.
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

from __future__ import print_function

import errno
import gc
import os
import pprint
import socket
import sys
import traceback

import eventlet
import eventlet.backdoor
import greenlet
from oslo.config import cfg

from openstack.common import log as logging

# TODO(pekowski): remove backdoor_port in I
eventlet_backdoor_opts = [
    cfg.IntOpt('backdoor_port',
               default=None,
               help='(deprecated) port for eventlet backdoor to listen. Set '
               'to zero to enable the backdoor on a random port and non-zero '
               'to enable it on a specific port. The chosen port is displayed '
               'in the service\'s log file.'),
    cfg.IntOpt('enable_backdoor_with_random_port',
               default=False,
               help='enable eventlet backdoor listening on a random port'),
    cfg.IntOpt('enable_backdoor_with_port_hint',
               default=None,
               help='enable eventlet backdoor listening on a port starting at '
               'the hint and incrementing by one until a free port is found.'),
    cfg.IntOpt('enable_backdoor_for_unix_socket',
               default=False,
               help='enable eventlet backdoor listening a unix socket named '
               'by openstack_<proccess ID>')
]

CONF = cfg.CONF
CONF.register_opts(eventlet_backdoor_opts)
LOG = logging.getLogger(__name__)


def _dont_use_this():
    print("Don't use this, just disconnect instead")


def _find_objects(t):
    return filter(lambda o: isinstance(o, t), gc.get_objects())


def _print_greenthreads():
    for i, gt in enumerate(_find_objects(greenlet.greenlet)):
        print(i, gt)
        traceback.print_stack(gt.gr_frame)
        print()


def _print_nativethreads():
    for threadId, stack in sys._current_frames().items():
        print(threadId)
        traceback.print_stack(stack)
        print()


def initialize_if_enabled():
    backdoor_locals = {
        'exit': _dont_use_this,      # So we don't exit the entire process
        'quit': _dont_use_this,      # So we don't exit the entire process
        'fo': _find_objects,
        'pgt': _print_greenthreads,
        'pnt': _print_nativethreads,
    }

    # TODO(pekowski): remove backdoor_port in I
    if CONF.backdoor_port is not None:
        msg = 'backdoor_port is deprecated. ' + \
              'Please replace backdoor_port ' + \
              'with one of enable_backdoor_with_random_port, ' + \
              'enable_backdoor_with_port_hint or ' + \
              'enable_backdoor_for_unix_socket.'
        LOG.info(_('%s') % msg)
    ambiguity_count = 0
    for is_configured in (CONF.backdoor_port is not None,
                          CONF.enable_backdoor_with_random_port,
                          CONF.enable_backdoor_with_port_hint is not None,
                          CONF.enable_backdoor_for_unix_socket):
        if is_configured:
            ambiguity_count += 1
    if ambiguity_count == 0:
        return None
    elif ambiguity_count > 1:
        msg = 'Only one of backdoor_port, ' + \
              'enable_backdoor_with_random_port, ' + \
              'enable_backdoor_with_port_hint or ' + \
              'enable_backdoor_for_unix_socket' + \
              'is allowed. Defaulting to ' + \
              'enable_backdoor_with_random_port.'
        LOG.info(_('%s') % msg)

    # NOTE(johannes): The standard sys.displayhook will print the value of
    # the last expression and set it to __builtin__._, which overwrites
    # the __builtin__._ that gettext sets. Let's switch to using pprint
    # since it won't interact poorly with gettext, and it's easier to
    # read the output too.
    def displayhook(val):
        if val is not None:
            pprint.pprint(val)
    sys.displayhook = displayhook

    if CONF.enable_backdoor_with_random_port:
        # zero results in a random port assignment
        sock = eventlet.listen(('localhost', 0))
    # TODO(pekowski): Remove backdoor_port in I
    elif CONF.backdoor_port is not None:
        sock = eventlet.listen(('localhost', CONF.backdoor_port))
    elif CONF.enable_backdoor_with_port_hint is not None:
        try_port = CONF.enable_backdoor_with_port_hint
        while True:
            try:
                sock = eventlet.listen(('localhost', try_port))
                break
            except socket.error as exc:
                if exc.errno == errno.EADDRINUSE:
                    try_port += 1
                else:
                    raise
    elif CONF.enable_backdoor_for_unix_socket:
        unix_sock = 'openstack_%d' % os.getpid()
        sock = eventlet.listen(unix_sock, family=socket.AF_UNIX)

    if CONF.enable_backdoor_for_unix_socket:
        port = unix_sock
    else:
        # In the case of backdoor port being zero, a port number is assigned by
        # listen().  In any case, pull the port number out here.
        port = sock.getsockname()[1]
    LOG.info(_('Eventlet backdoor listening on %(port)s for process %(pid)d') %
             {'port': port, 'pid': os.getpid()})
    eventlet.spawn_n(eventlet.backdoor.backdoor_server, sock,
                     locals=backdoor_locals)
    return port
