# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2011 OpenStack Foundation.
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

import fixtures
import os
import tempfile

import six

from openstack.common import processutils
from openstack.common import test


class UtilsTest(test.BaseTestCase):
    # NOTE(jkoelker) Moar tests from nova need to be ported. But they
    #                need to be mock'd out. Currently they requre actually
    #                running code.
    def test_execute_unknown_kwargs(self):
        self.assertRaises(processutils.UnknownArgumentError,
                          processutils.execute,
                          hozer=True)


class ProcessExecutionErrorTest(test.BaseTestCase):

    def test_defaults(self):
        err = processutils.ProcessExecutionError()
        self.assertTrue('None\n' in unicode(err))
        self.assertTrue('code: -\n' in unicode(err))

    def test_with_description(self):
        description = 'The Narwhal Bacons at Midnight'
        err = processutils.ProcessExecutionError(description=description)
        self.assertTrue(description in unicode(err))

    def test_with_exit_code(self):
        exit_code = 0
        err = processutils.ProcessExecutionError(exit_code=exit_code)
        self.assertTrue(str(exit_code) in unicode(err))

    def test_with_cmd(self):
        cmd = 'telinit'
        err = processutils.ProcessExecutionError(cmd=cmd)
        self.assertTrue(cmd in unicode(err))

    def test_with_stdout(self):
        stdout = """
        Lo, praise of the prowess of people-kings
        of spear-armed Danes, in days long sped,
        we have heard, and what honot the athelings won!
        Oft Scyld the Scefing from squadroned foes,
        from many a tribe, the mead-bench tore,
        awing the earls. Since erse he lay
        friendless, a foundling, fate repaid him:
        for he waxed under welkin, in wealth he trove,
        till before him the folk, both far and near,
        who house by the whale-path, heard his mandate,
        gabe him gits: a good king he!
        To him an heir was afterward born,
        a son in his halls, whom heaven sent
        to favor the fol, feeling their woe
        that erst they had lacked an earl for leader
        so long a while; the Lord endowed him,
        the Wielder of Wonder, with world's renown.
        """.strip()
        err = processutils.ProcessExecutionError(stdout=stdout)
        print(unicode(err))
        self.assertTrue('people-kings' in unicode(err))

    def test_with_stderr(self):
        stderr = 'Cottonian library'
        err = processutils.ProcessExecutionError(stderr=stderr)
        self.assertTrue(stderr in unicode(err))

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
            self.assertRaises(processutils.ProcessExecutionError,
                              processutils.execute,
                              tmpfilename, tmpfilename2, attempts=10,
                              process_input='foo',
                              delay_on_retry=False)
            fp = open(tmpfilename2, 'r')
            runs = fp.read()
            fp.close()
            self.assertNotEquals(runs.strip(), 'failure', 'stdin did not '
                                                          'always get passed '
                                                          'correctly')
            runs = int(runs.strip())
            self.assertEqual(runs, 10, 'Ran %d times instead of 10.' % (runs,))
        finally:
            os.unlink(tmpfilename)
            os.unlink(tmpfilename2)

    def test_unknown_kwargs_raises_error(self):
        self.assertRaises(processutils.UnknownArgumentError,
                          processutils.execute,
                          '/usr/bin/env', 'true',
                          this_is_not_a_valid_kwarg=True)

    def test_check_exit_code_boolean(self):
        processutils.execute('/usr/bin/env', 'false', check_exit_code=False)
        self.assertRaises(processutils.ProcessExecutionError,
                          processutils.execute,
                          '/usr/bin/env', 'false', check_exit_code=True)

    def test_no_retry_on_success(self):
        fd, tmpfilename = tempfile.mkstemp()
        _, tmpfilename2 = tempfile.mkstemp()
        try:
            fp = os.fdopen(fd, 'w+')
            fp.write("""#!/bin/sh
# If we've already run, bail out.
grep -q foo "$1" && exit 1
# Mark that we've run before.
echo foo > "$1"
# Check that stdin gets passed correctly.
grep foo
""")
            fp.close()
            os.chmod(tmpfilename, 0o755)
            processutils.execute(tmpfilename,
                                 tmpfilename2,
                                 process_input='foo',
                                 attempts=2)
        finally:
            os.unlink(tmpfilename)
            os.unlink(tmpfilename2)


def fake_execute(*cmd, **kwargs):
    return 'stdout', 'stderr'


def fake_execute_raises(*cmd, **kwargs):
    raise processutils.ProcessExecutionError(exit_code=42,
                                             stdout='stdout',
                                             stderr='stderr',
                                             cmd=['this', 'is', 'a',
                                                  'command'])


class TryCmdTestCase(test.BaseTestCase):
    def test_keep_warnings(self):
        self.useFixture(fixtures.MonkeyPatch(
            'openstack.common.processutils.execute', fake_execute))
        o, e = processutils.trycmd('this is a command'.split(' '))
        self.assertNotEqual('', o)
        self.assertNotEqual('', e)

    def test_keep_warnings_from_raise(self):
        self.useFixture(fixtures.MonkeyPatch(
            'openstack.common.processutils.execute', fake_execute_raises))
        o, e = processutils.trycmd('this is a command'.split(' '),
                                   discard_warnings=True)
        self.assertIsNotNone(o)
        self.assertNotEqual('', e)

    def test_discard_warnings(self):
        self.useFixture(fixtures.MonkeyPatch(
            'openstack.common.processutils.execute', fake_execute))
        o, e = processutils.trycmd('this is a command'.split(' '),
                                   discard_warnings=True)
        self.assertIsNotNone(o)
        self.assertEqual('', e)


class FakeSshChannel(object):
    def __init__(self, rc):
        self.rc = rc

    def recv_exit_status(self):
        return self.rc


class FakeSshStream(six.StringIO):
    def setup_channel(self, rc):
        self.channel = FakeSshChannel(rc)


class FakeSshConnection(object):
    def __init__(self, rc):
        self.rc = rc

    def exec_command(self, cmd):
        stdout = FakeSshStream('stdout')
        stdout.setup_channel(self.rc)
        return (six.StringIO(),
                stdout,
                six.StringIO('stderr'))


class SshExecuteTestCase(test.BaseTestCase):
    def test_invalid_addl_env(self):
        self.assertRaises(processutils.InvalidArgumentError,
                          processutils.ssh_execute,
                          None, 'ls', addl_env='important')

    def test_invalid_process_input(self):
        self.assertRaises(processutils.InvalidArgumentError,
                          processutils.ssh_execute,
                          None, 'ls', process_input='important')

    def test_works(self):
        o, e = processutils.ssh_execute(FakeSshConnection(0), 'ls')
        self.assertEqual('stdout', o)
        self.assertEqual('stderr', e)

    def test_fails(self):
        self.assertRaises(processutils.ProcessExecutionError,
                          processutils.ssh_execute, FakeSshConnection(1), 'ls')
