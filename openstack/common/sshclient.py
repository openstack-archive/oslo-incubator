# Copyright 2013: Mirantis Inc.
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


"""High level ssh library.

Usage examples:

Simply execute command with small output:

    ssh = sshclient.SSH('root', 'example.com', port=33)
    status, stdout, stderr = ssh.execute('ps ax')
    if status:
        raise Exception('Command failed with non-zero exit status.')
    print stdout.splitlines()

Execute command with huge output:

    def stdout_callback(data):
        LOG.debug(data)
    ssh = sshclient.SSH('root', 'example.com')
    ssh.run('tail -f /var/log/syslog', stdout_callback=stdout_callback,
            timeout=False)

Execute local script on remote side:

    ssh = sshclient.SSH('user', 'example.com')
    status, out, err = ssh.execute('/bin/sh -s arg1 arg2',
                                   stdin=open('~/myscript.sh', 'r'))

Upload file:

    ssh = sshclient.SSH('user', 'example.com')
    ssh.run('cat > ~/upload/file.gz', stdin=open('/store/file.gz', 'rb'))

Eventlet:

    eventlet.monkey_patch(select=True, time=True)
    or
    eventlet.monkey_patch()
    or
    sshclient = eventlet.import_patched("opentstack.common.sshclient")

"""

import paramiko
import select
import socket
import StringIO
import time

from openstack.common.gettextutils import _
from openstack.common import log as logging


LOG = logging.getLogger(__name__)


class SSHError(Exception):
    pass


class SSHTimeout(SSHError):
    pass


class SSH(object):
    """Represent ssh connection."""

    def __init__(self, user, host, port=22, pkey=None,
                 key_filename=None, password=None):
        """Initialize SSH client.

        Attribute pkey is RSA or DSS private key string or file object.

        """

        self.user = user
        self.host = host
        self.port = port
        self.pkey = self._get_pkey(pkey) if pkey else None
        self.password = password
        self.key_filename = key_filename

    def _get_pkey(self, key):
        if isinstance(key, basestring):
            key = StringIO.StringIO(key)
        for key_class in (paramiko.rsakey.RSAKey, paramiko.dsskey.DSSKey):
            try:
                return key_class.from_private_key(key)
            except paramiko.SSHException:
                pass
        raise SSHError('Invalid pkey')

    def _get_client(self):
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(self.host, username=self.user, port=self.port,
                           pkey=self.pkey, key_filename=self.key_filename,
                           password=self.password)
            return client
        except paramiko.SSHException as e:
            message = _("Paramiko exception %(exception_type)s was raised "
                        "during connect. Exception value is: %(exception)r")
            raise SSHError(message % {'exception': e,
                                      'exception_type': type(e)})

    def run(self, cmd, stdin=None, stdout_callback=None, stderr_callback=None,
            raise_on_error=True, timeout=3600):
        """Execute specified command on the server.

        :param cmd:             Command to be executed.
        :param stdin:           Open file to be send to command's stdin.
        :param stdout_callback: Callback for stdout data handling.
        :param stderr_callback: Callback for stderr data handling.
        :param raise_on_error:  If False then exit code will be return. If True
                                then exception will be raized if non-zero code.
        :param timeout:         Timeout in seconds for command execution.
                                Default 1 hour. Set to 0 for disable timeout.
        """

        client = self._get_client()
        try:
            return self._run(client, cmd, stdin=stdin,
                             stdout_callback=stdout_callback,
                             stderr_callback=stderr_callback,
                             raise_on_error=raise_on_error,
                             timeout=timeout)
        finally:
            client.close()

    def _run(self, client, cmd, stdin=None, stdout_callback=None,
             stderr_callback=None, raise_on_error=True, timeout=3600):

        transport = client.get_transport()
        session = transport.open_session()
        session.exec_command(cmd)
        start_time = time.time()

        data_to_send = ''
        stderr_data = None

        # If we have data to be sent to stdin then `select' should also
        # check for stdin availability.
        if stdin and not stdin.closed:
            writes = [session]
        else:
            writes = []

        while True:
            # Block until data can be read/write.
            r, w, e = select.select([session], writes, [session], 1)

            if session.recv_ready():
                data = session.recv(4096)
                LOG.debug(_('stdout: %r') % data)
                if stdout_callback is not None:
                    stdout_callback(data)
                continue

            if session.recv_stderr_ready():
                stderr_data = session.recv_stderr(4096)
                LOG.debug(_('stderr: %r') % stderr_data)
                if stderr_callback is not None:
                    stderr_callback(stderr_data)
                continue

            if session.send_ready():
                if stdin is not None and not stdin.closed:
                    if not data_to_send:
                        data_to_send = stdin.read(4096)
                        if not data_to_send:
                            stdin.close()
                            session.shutdown_write()
                            writes = []
                            continue
                    sent_bytes = session.send(data_to_send)
                    data_to_send = data_to_send[sent_bytes:]

            if session.exit_status_ready():
                break

            if timeout and (time.time() - timeout) > start_time:
                args = {'cmd': cmd, 'host': self.host}
                raise SSHTimeout(_('Timeout executing command '
                                   '"%(cmd)s" on host %(host)s') % args)
            if e:
                raise SSHError('Socket error.')

        exit_status = session.recv_exit_status()
        if 0 != exit_status and raise_on_error:
            details = _('Command failed with exit_status %d.') % exit_status
            if stderr_data:
                details += _(' Last stderr data: "%s".') % stderr_data
            raise SSHError(details)
        return exit_status

    def execute(self, cmd, stdin=None, timeout=3600):
        """Execute the specified command on the server.

        :param cmd:     Command to be executed.
        :param stdin:   Open file to be sent on process stdin.
        :param timeout: Timeout for execution of the command.

        Return tuple (exit_status, stdout, stderr)

        """
        stdout = ['']
        stderr = ['']

        def stderr_callback(data):
            stderr[0] += data

        def stdout_callback(data):
            stdout[0] += data

        exit_status = self.run(cmd, stderr_callback=stderr_callback,
                               stdout_callback=stdout_callback, stdin=stdin,
                               timeout=timeout, raise_on_error=False)
        return (exit_status, stdout[0], stderr[0])

    def wait(self, timeout=120, interval=1):
        """Wait for the host will be available via ssh."""
        start_time = time.time()
        while True:
            try:
                return self.execute('uname')
            except (socket.error, SSHError) as e:
                LOG.debug(_('Ssh is still unavailable: %r') % e)
                time.sleep(interval)
            if (time.time() - timeout) > start_time:
                raise SSHTimeout(_('Timeout waiting for "%s"') % self.host)
