# Copyright 2011 Justin Santa Barbara
# Copyright 2012 Hewlett-Packard Development Company, L.P.
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

import errno
import os
import os.path
import tempfile

import mock
from oslo.config import cfg
from oslo_concurrency import processutils
from oslotest import base as test_base

from openstack.common.libironic import exception
from openstack.common.libironic import utils

CONF = cfg.CONF


class BareMetalUtilsTestCase(test_base.BaseTestCase):

    def test_unlink(self):
        with mock.patch.object(os, "unlink") as unlink_mock:
            unlink_mock.return_value = None
            utils.unlink_without_raise("/fake/path")
            unlink_mock.assert_called_once_with("/fake/path")

    def test_unlink_ENOENT(self):
        with mock.patch.object(os, "unlink") as unlink_mock:
            unlink_mock.side_effect = OSError(errno.ENOENT)
            utils.unlink_without_raise("/fake/path")
            unlink_mock.assert_called_once_with("/fake/path")


class ExecuteTestCase(test_base.BaseTestCase):

    def test_retry_on_failure(self):
        fd, tmpfilename = tempfile.mkstemp()
        _, tmpfilename2 = tempfile.mkstemp()
        try:
            fp = os.fdopen(fd, 'w+')
            fp.write('''#!/bin/sh
# If stdin fails to get passed during one of the runs, make a note.
if ! grep -q foo
then
    echo 'failure' > "$1"
fi
# If stdin has failed to get passed during this or a previous run, exit early.
if grep failure "$1"
then
    exit 1
fi
runs="$(cat $1)"
if [ -z "$runs" ]
then
    runs=0
fi
runs=$(($runs + 1))
echo $runs > "$1"
exit 1
''')
            fp.close()
            os.chmod(tmpfilename, 0o755)
            try:
                self.assertRaises(processutils.ProcessExecutionError,
                                  utils.execute,
                                  tmpfilename, tmpfilename2, attempts=10,
                                  process_input='foo',
                                  delay_on_retry=False)
            except OSError as e:
                if e.errno == errno.EACCES:
                    self.skipTest("Permissions error detected. "
                                  "Are you running with a noexec /tmp?")
                else:
                    raise
            fp = open(tmpfilename2, 'r')
            runs = fp.read()
            fp.close()
            self.assertNotEqual(runs.strip(), 'failure', 'stdin did not '
                                'always get passed '
                                'correctly')
            runs = int(runs.strip())
            self.assertEqual(10, runs,
                             'Ran %d times instead of 10.' % (runs,))
        finally:
            os.unlink(tmpfilename)
            os.unlink(tmpfilename2)

    def test_unknown_kwargs_raises_error(self):
        self.assertRaises(processutils.UnknownArgumentError,
                          utils.execute,
                          '/usr/bin/env', 'true',
                          this_is_not_a_valid_kwarg=True)

    def test_check_exit_code_boolean(self):
        utils.execute('/usr/bin/env', 'false', check_exit_code=False)
        self.assertRaises(processutils.ProcessExecutionError,
                          utils.execute,
                          '/usr/bin/env', 'false', check_exit_code=True)

    def test_no_retry_on_success(self):
        fd, tmpfilename = tempfile.mkstemp()
        _, tmpfilename2 = tempfile.mkstemp()
        try:
            fp = os.fdopen(fd, 'w+')
            fp.write('''#!/bin/sh
# If we've already run, bail out.
grep -q foo "$1" && exit 1
# Mark that we've run before.
echo foo > "$1"
# Check that stdin gets passed correctly.
grep foo
''')
            fp.close()
            os.chmod(tmpfilename, 0o755)
            try:
                utils.execute(tmpfilename,
                              tmpfilename2,
                              process_input='foo',
                              attempts=2)
            except OSError as e:
                if e.errno == errno.EACCES:
                    self.skipTest("Permissions error detected. "
                                  "Are you running with a noexec /tmp?")
                else:
                    raise
        finally:
            os.unlink(tmpfilename)
            os.unlink(tmpfilename2)

    @mock.patch.object(processutils, 'execute')
    @mock.patch.object(os.environ, 'copy', return_value={})
    def test_execute_use_standard_locale_no_env_variables(self, env_mock,
                                                          execute_mock):
        utils.execute('foo', use_standard_locale=True)
        execute_mock.assert_called_once_with('foo',
                                             env_variables={'LC_ALL': 'C'})

    @mock.patch.object(processutils, 'execute')
    def test_execute_use_standard_locale_with_env_variables(self,
                                                            execute_mock):
        utils.execute('foo', use_standard_locale=True,
                      env_variables={'foo': 'bar'})
        execute_mock.assert_called_once_with('foo',
                                             env_variables={'LC_ALL': 'C',
                                                            'foo': 'bar'})

    @mock.patch.object(processutils, 'execute')
    def test_execute_not_use_standard_locale(self, execute_mock):
        utils.execute('foo', use_standard_locale=False,
                      env_variables={'foo': 'bar'})
        execute_mock.assert_called_once_with('foo',
                                             env_variables={'foo': 'bar'})

    def test_execute_get_root_helper(self):
        with mock.patch.object(processutils, 'execute') as execute_mock:
            helper = utils._get_root_helper()
            utils.execute('foo', run_as_root=True)
            execute_mock.assert_called_once_with('foo', run_as_root=True,
                                                 root_helper=helper)

    def test_execute_without_root_helper(self):
        with mock.patch.object(processutils, 'execute') as execute_mock:
            utils.execute('foo', run_as_root=False)
            execute_mock.assert_called_once_with('foo', run_as_root=False)


class MkfsTestCase(test_base.BaseTestCase):

    @mock.patch.object(utils, 'execute')
    def test_mkfs(self, execute_mock):
        utils.mkfs('ext4', '/my/block/dev')
        utils.mkfs('msdos', '/my/msdos/block/dev')
        utils.mkfs('swap', '/my/swap/block/dev')

        expected = [mock.call('mkfs', '-t', 'ext4', '-F', '/my/block/dev',
                              run_as_root=True,
                              use_standard_locale=True),
                    mock.call('mkfs', '-t', 'msdos', '/my/msdos/block/dev',
                              run_as_root=True,
                              use_standard_locale=True),
                    mock.call('mkswap', '/my/swap/block/dev',
                              run_as_root=True,
                              use_standard_locale=True)]
        self.assertEqual(expected, execute_mock.call_args_list)

    @mock.patch.object(utils, 'execute')
    def test_mkfs_with_label(self, execute_mock):
        utils.mkfs('ext4', '/my/block/dev', 'ext4-vol')
        utils.mkfs('msdos', '/my/msdos/block/dev', 'msdos-vol')
        utils.mkfs('swap', '/my/swap/block/dev', 'swap-vol')

        expected = [mock.call('mkfs', '-t', 'ext4', '-F', '-L', 'ext4-vol',
                              '/my/block/dev', run_as_root=True,
                              use_standard_locale=True),
                    mock.call('mkfs', '-t', 'msdos', '-n', 'msdos-vol',
                              '/my/msdos/block/dev', run_as_root=True,
                              use_standard_locale=True),
                    mock.call('mkswap', '-L', 'swap-vol',
                              '/my/swap/block/dev', run_as_root=True,
                              use_standard_locale=True)]
        self.assertEqual(expected, execute_mock.call_args_list)

    @mock.patch.object(utils, 'execute',
                       side_effect=processutils.ProcessExecutionError(
                           stderr=os.strerror(errno.ENOENT)))
    def test_mkfs_with_unsupported_fs(self, execute_mock):
        self.assertRaises(exception.FileSystemNotSupported,
                          utils.mkfs, 'foo', '/my/block/dev')

    @mock.patch.object(utils, 'execute',
                       side_effect=processutils.ProcessExecutionError(
                           stderr='fake'))
    def test_mkfs_with_unexpected_error(self, execute_mock):
        self.assertRaises(processutils.ProcessExecutionError, utils.mkfs,
                          'ext4', '/my/block/dev', 'ext4-vol')


class IsHttpUrlTestCase(test_base.BaseTestCase):

    def test_is_http_url(self):
        self.assertTrue(utils.is_http_url('http://127.0.0.1'))
        self.assertTrue(utils.is_http_url('https://127.0.0.1'))
        self.assertTrue(utils.is_http_url('HTTP://127.1.2.3'))
        self.assertTrue(utils.is_http_url('HTTPS://127.3.2.1'))
        self.assertFalse(utils.is_http_url('Zm9vYmFy'))
        self.assertFalse(utils.is_http_url('11111111'))
