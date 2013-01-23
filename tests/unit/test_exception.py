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

from openstack.common import exception
from tests import utils


def good_function():
    return "Is Bueno!"


def bad_function_error():
    raise exception.Error()


def bad_function_exception():
    raise Exception()


class WrapExceptionTest(utils.BaseTestCase):

    def test_wrap_exception_good_return(self):
        wrapped = exception.wrap_exception
        self.assertEquals(good_function(), wrapped(good_function)())

    def test_wrap_exception_throws_error(self):
        wrapped = exception.wrap_exception
        self.assertRaises(exception.Error, wrapped(bad_function_error))

    def test_wrap_exception_throws_exception(self):
        wrapped = exception.wrap_exception
        self.assertRaises(Exception, wrapped(bad_function_exception))


class ApiErrorTest(utils.BaseTestCase):

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


class BadStoreUriTest(utils.BaseTestCase):

    def test(self):
        uri = 'http:///etc/passwd'
        reason = 'Permission DENIED!'
        err = exception.BadStoreUri(uri, reason)
        self.assertTrue(uri in str(err.message))
        self.assertTrue(reason in str(err.message))


class UnknownSchemeTest(utils.BaseTestCase):

    def test(self):
        scheme = 'http'
        err = exception.UnknownScheme(scheme)
        self.assertTrue(scheme in str(err.message))


class OpenstackExceptionTest(utils.BaseTestCase):
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
