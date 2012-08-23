# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2011 OpenStack LLC.
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

import unittest

from openstack.common import exception


def good_function():
    return "Is Bueno!"


def bad_function_error():
    raise exception.Error()


def bad_function_exception():
    raise Exception()


class WrapExceptionTest(unittest.TestCase):

    def test_wrap_exception_good_return(self):
        wrapped = exception.wrap_exception
        self.assertEquals(good_function(), wrapped(good_function)())

    def test_wrap_exception_throws_error(self):
        wrapped = exception.wrap_exception
        self.assertRaises(exception.Error, wrapped(bad_function_error))

    def test_wrap_exception_throws_exception(self):
        wrapped = exception.wrap_exception
        self.assertRaises(Exception, wrapped(bad_function_exception))


class ApiErrorTest(unittest.TestCase):

    def test_without_code(self):
        err = exception.ApiError('fake error')
        self.assertEqual(err.__str__(), 'Unknown: fake error')
        self.assertEqual(err.code, 'Unknown')
        self.assertEqual(err.message, 'fake error')

    def test_with_code(self):
        err = exception.ApiError('fake error', 'blah code')
        self.assertEqual(err.__str__(), 'blah code: fake error')
        self.assertEqual(err.code, 'blah code')
        self.assertEqual(err.message, 'fake error')


class ProcessExecutionErrorTest(unittest.TestCase):

    def test_defaults(self):
        err = exception.ProcessExecutionError()
        self.assertTrue('None\n' in err.message)
        self.assertTrue('code: -\n' in err.message)

    def test_with_description(self):
        description = 'The Narwhal Bacons at Midnight'
        err = exception.ProcessExecutionError(description=description)
        self.assertTrue(description in err.message)

    def test_with_exit_code(self):
        exit_code = 0
        err = exception.ProcessExecutionError(exit_code=exit_code)
        self.assertTrue(str(exit_code) in err.message)

    def test_with_cmd(self):
        cmd = 'telinit'
        err = exception.ProcessExecutionError(cmd=cmd)
        self.assertTrue(cmd in err.message)

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
        err = exception.ProcessExecutionError(stdout=stdout)
        print err.message
        self.assertTrue('people-kings' in err.message)

    def test_with_stderr(self):
        stderr = 'Cottonian library'
        err = exception.ProcessExecutionError(stderr=stderr)
        self.assertTrue(stderr in str(err.message))


class BadStoreUriTest(unittest.TestCase):

    def test(self):
        uri = 'http:///etc/passwd'
        reason = 'Permission DENIED!'
        err = exception.BadStoreUri(uri, reason)
        self.assertTrue(uri in str(err.message))
        self.assertTrue(reason in str(err.message))


class UnknownSchemeTest(unittest.TestCase):

    def test(self):
        scheme = 'http'
        err = exception.UnknownScheme(scheme)
        self.assertTrue(scheme in str(err.message))


class OpenstackExceptionTest(unittest.TestCase):
    class TestException(exception.OpenstackException):
        message = '%(test)s'

    def test_format_error_string(self):
        test_message = 'Know Your Meme'
        err = self.TestException(test=test_message)
        self.assertEqual(err._error_string, test_message)

    def test_error_forating_error_string(self):
        err = self.TestException(lol='U mad brah')
        self.assertEqual(err._error_string, self.TestException.message)

    def test_str(self):
        message = 'Y u no fail'
        err = self.TestException(test=message)
        self.assertEqual(str(err), message)
