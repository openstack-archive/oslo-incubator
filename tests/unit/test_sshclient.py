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

import mock

from openstack.common import sshclient
from openstack.common import test


class SSHTestCase(test.BaseTestCase):
    """Test all small SSH methods."""

    def setUp(self):
        super(SSHTestCase, self).setUp()
        with mock.patch('openstack.common.sshclient.os.path.isfile'):
            self.ssh = sshclient.SSH('root', 'example.net')

    @mock.patch('openstack.common.sshclient.os.path.isfile')
    def test_construct(self, m_isfile):
        ssh = sshclient.SSH('root', 'example.net', port=33, key='key',
                            password='secret')
        self.assertEqual('root', ssh.user)
        self.assertEqual('example.net', ssh.host)
        self.assertEqual(33, ssh.port)
        self.assertEqual('key', ssh.key)
        self.assertEqual('secret', ssh.password)
        m_isfile.assert_called_once_with('key')

    @mock.patch('openstack.common.sshclient.os.path.isfile')
    def test_construct_invalid_key(self, m_isfile):
        m_isfile.return_value = False
        self.assertRaises(sshclient.SSHError, sshclient.SSH, 'root', 'host')

    def test_construct_default(self):
        self.assertEqual(22, self.ssh.port)
        self.assertTrue(self.ssh.key.endswith('/.ssh/id_rsa'))

    @mock.patch('openstack.common.sshclient.paramiko')
    def test__get_client(self, m_paramiko):
        fake_client = mock.Mock()
        m_paramiko.SSHClient.return_value = fake_client
        m_paramiko.AutoAddPolicy.return_value = 'autoadd'

        with mock.patch('openstack.common.sshclient.os.path.isfile'):
            ssh = sshclient.SSH('admin', 'example.net', key='key')
        client = ssh._get_client()

        self.assertEqual(fake_client, client)
        client_calls = [
            mock.call.set_missing_host_key_policy('autoadd'),
            mock.call.connect('example.net', username='admin', port=22,
                              key_filename='key', password=None),
        ]
        self.assertEqual(client_calls, client.mock_calls)

    def test_execute(self):
        self.ssh.run = mock.Mock()
        self.ssh.execute('cmd', stdin='fake_stdin', timeout=43)
        self.ssh.run.assert_called_once_with('cmd',
                                             stderr_callback=mock.ANY,
                                             stdout_callback=mock.ANY,
                                             stdin='fake_stdin',
                                             timeout=43,
                                             raise_on_error=False)

    @mock.patch('openstack.common.sshclient.time')
    def test_wait_timeout(self, m_time):
        m_time.time.side_effect = [1, 50, 150]
        self.ssh.execute = mock.Mock(side_effect=[sshclient.SSHError,
                                                  sshclient.SSHError,
                                                  0])
        self.assertRaises(sshclient.SSHTimeout, self.ssh.wait)
        self.assertEqual([mock.call('uname')] * 2, self.ssh.execute.mock_calls)

    @mock.patch('openstack.common.sshclient.time')
    def test_wait(self, m_time):
        m_time.time.side_effect = [1, 50, 100]
        self.ssh.execute = mock.Mock(side_effect=[sshclient.SSHError,
                                                  sshclient.SSHError,
                                                  0])
        self.ssh.wait()
        self.assertEqual([mock.call('uname')] * 3, self.ssh.execute.mock_calls)


class SSHRunTestCase(test.BaseTestCase):
    """Test SSH.run method in different aspects.

    Also tested method 'execute'.
    """

    def setUp(self):
        super(SSHRunTestCase, self).setUp()

        self.fake_client = mock.Mock()
        self.fake_session = mock.Mock()
        self.fake_transport = mock.Mock()

        self.fake_transport.open_session.return_value = self.fake_session
        self.fake_client.get_transport.return_value = self.fake_transport

        self.fake_session.recv_ready.return_value = False
        self.fake_session.recv_stderr_ready.return_value = False
        self.fake_session.send_ready.return_value = False
        self.fake_session.exit_status_ready.return_value = True
        self.fake_session.recv_exit_status.return_value = 0

        with mock.patch('openstack.common.sshclient.os.path.isfile'):
            self.ssh = sshclient.SSH('admin', 'example.net')
        self.ssh._get_client = mock.Mock(return_value=self.fake_client)

    @mock.patch('openstack.common.sshclient.select')
    def test_execute(self, m_select):
        m_select.select.return_value = ([], [], [])
        self.fake_session.recv_ready.side_effect = [1, 0, 0]
        self.fake_session.recv_stderr_ready.side_effect = [1, 0]
        self.fake_session.recv.return_value = 'ok'
        self.fake_session.recv_stderr.return_value = 'error'
        self.fake_session.exit_status_ready.return_value = 1
        self.fake_session.recv_exit_status.return_value = 127
        self.assertEqual((127, 'ok', 'error'), self.ssh.execute('cmd'))
        self.fake_session.exec_command.assert_called_once_with('cmd')

    @mock.patch('openstack.common.sshclient.select')
    def test_run(self, m_select):
        m_select.select.return_value = ([], [], [])
        self.assertEqual(0, self.ssh.run('cmd'))

    @mock.patch('openstack.common.sshclient.select')
    def test_run_nonzero_status(self, m_select):
        m_select.select.return_value = ([], [], [])
        self.fake_session.recv_exit_status.return_value = 1
        self.assertRaises(sshclient.SSHError, self.ssh.run, 'cmd')
        self.assertEqual(1, self.ssh.run('cmd', raise_on_error=False))

    @mock.patch('openstack.common.sshclient.select')
    def test_run_stdout_callback(self, m_select):
        m_select.select.return_value = ([], [], [])
        self.fake_session.recv_ready.side_effect = [True, True, False]
        self.fake_session.recv.side_effect = ['ok1', 'ok2']
        stdout_callback = mock.Mock()
        self.ssh.run('cmd', stdout_callback=stdout_callback)
        self.assertEqual([mock.call('ok1'), mock.call('ok2')],
                         stdout_callback.mock_calls)

    @mock.patch('openstack.common.sshclient.select')
    def test_run_stderr_callback(self, m_select):
        m_select.select.return_value = ([], [], [])
        self.fake_session.recv_stderr_ready.side_effect = [True, False]
        self.fake_session.recv_stderr.return_value = 'error'
        stderr_callback = mock.Mock()
        self.ssh.run('cmd', stderr_callback=stderr_callback)
        stderr_callback.assert_called_once_with('error')

    @mock.patch('openstack.common.sshclient.select')
    def test_run_stdin(self, m_select):
        """Test run method with stdin.

        Third send call was called with 'e2' because only 3 bytes was sent
        by second call. So remainig 2 bytes of 'line2' was sent by third call.
        """
        m_select.select.return_value = ([], [], [])
        self.fake_session.exit_status_ready.side_effect = [0, 0, 0, True]
        self.fake_session.send_ready.return_value = True
        self.fake_session.send.side_effect = [5, 3, 2]
        fake_stdin = mock.Mock()
        fake_stdin.read.side_effect = ['line1', 'line2', '']
        fake_stdin.closed = False
        def close():
            fake_stdin.closed = True
        fake_stdin.close = mock.Mock(side_effect=close)
        self.ssh.run('cmd', stdin=fake_stdin)
        call = mock.call
        send_calls = [call('line1'), call('line2'), call('e2')]
        self.assertEqual(send_calls, self.fake_session.send.mock_calls)

    @mock.patch('openstack.common.sshclient.select')
    def test_run_select_error(self, m_select):
        self.fake_session.exit_status_ready.return_value = False
        m_select.select.return_value = ([], [], [True])
        self.assertRaises(sshclient.SSHError, self.ssh.run, 'cmd')

    @mock.patch('openstack.common.sshclient.time')
    @mock.patch('openstack.common.sshclient.select')
    def test_run_timemout(self, m_select, m_time):
        m_time.time.side_effect = [1, 3700]
        m_select.select.return_value = ([], [], [])
        self.fake_session.exit_status_ready.return_value = False
        self.assertRaises(sshclient.SSHTimeout, self.ssh.run, 'cmd')

    @mock.patch('openstack.common.sshclient.select')
    def test__run_client_closed_on_error(self, m_select):
        m_select.select.return_value = ([], [], [])
        self.fake_session.recv_ready.return_value = True
        self.fake_session.recv.side_effect = IOError
        self.assertRaises(IOError, self.ssh._run, self.fake_client, 'cmd')
        self.fake_client.close.assert_called_once()
