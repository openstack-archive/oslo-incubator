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

import datetime

try:
    import mock
except ImportError:
    import unittest.mock

from openstack.common.fixture import config
from openstack.common.fixture import moxstubout
from openstack.common import quota
from openstack.common import test


class FakeContext(object):
    project_id = 'p1'
    user_id = 'u1'
    quota_class = 'QuotaClass_'

    def elevated(self):
        return self


class ExceptionTestCase(test.BaseTestCase):

    def _get_raised_exception(self, exception, *args, **kwargs):
        try:
            raise exception(*args, **kwargs)
        except Exception as e:
            return e

    def test_quota_exception_format(self):

        class TestException(quota.QuotaException):
            msg_fmt = "Test format %(string)s"

        e = self._get_raised_exception(TestException)
        self.assertEqual(str(e), e.msg_fmt)

        e = self._get_raised_exception(TestException, number=42)
        self.assertEqual(str(e), e.msg_fmt)

        e = self._get_raised_exception(TestException, string="test")
        self.assertEqual(str(e), e.msg_fmt % {"string": "test"})


class DbQuotaDriverTestCase(test.BaseTestCase):

    def setUp(self):
        self.stubs = self.useFixture(moxstubout.MoxStubout()).stubs
        self.CONF = self.useFixture(config.Config()).conf
        self.sample_resources = {'r1': quota.BaseResource('r1'),
                                 'r2': quota.BaseResource('r2')}

        dbapi = mock.Mock()
        dbapi.quota_usage_get_all_by_project_and_user = mock.Mock(
            return_value={'project_id': 'p1', 'user_id': 'u1',
                          'r1': {'reserved': 1, 'in_use': 2},
                          'r2': {'reserved': 2, 'in_use': 3}})
        dbapi.quota_get_all_by_project_and_user = mock.Mock(
            return_value={'project_id': 'p1', 'user_id': 'u1',
                          'r1': 5, 'r2': 6})
        dbapi.quota_get = mock.Mock(return_value='quota_get')
        dbapi.quota_reserve = mock.Mock(return_value='quota_reserve')
        dbapi.quota_class_get = mock.Mock(return_value='quota_class_get')
        dbapi.quota_class_reserve = mock.Mock(
            return_value='quota_class_reserve')
        dbapi.quota_class_get_default = mock.Mock(
            return_value={'r1': 1, 'r2': 2})
        dbapi.quota_class_get_all_by_name = mock.Mock(return_value={'r1': 9})
        dbapi.quota_get_all_by_project = mock.Mock(
            return_value=dict([('r%d' % i, i) for i in range(3)]))
        dbapi.quota_get_all = mock.Mock(
            return_value=[{'resource': 'r1', 'hard_limit': 3},
                          {'resource': 'r2', 'hard_limit': 4}])
        dbapi.quota_usage_get_all_by_project = mock.Mock(
            return_value=dict([('r%d' % i, {'in_use': i, 'reserved': i + 1})
                               for i in range(3)]))
        self.dbapi = dbapi
        self.driver = quota.DbQuotaDriver(dbapi)
        self.ctxt = FakeContext()
        return super(DbQuotaDriverTestCase, self).setUp()

    def test_get_by_project(self):
        args = ['p1', 'resource']
        self.assertEqual('quota_get',
                         self.driver.get_by_project(self.ctxt, *args))
        self.driver.db.quota_get.assert_called_once_with(self.ctxt, *args)

    def test_get_by_project_and_user(self):
        args = ['p1', 'u1', 'resource']
        self.assertEqual('quota_get',
                         self.driver.get_by_project_and_user(self.ctxt, *args))
        self.driver.db.quota_get.assert_called_once_with(self.ctxt, *args)

    def test_get_by_class(self):
        args = ['class', 'resource']
        self.assertEqual('quota_class_get',
                         self.driver.get_by_class(self.ctxt, *args))
        self.driver.db.quota_class_get.assert_called_once_with(self.ctxt,
                                                               *args)

    def test_get_defaults(self):
        defaults = self.driver.get_defaults(self.ctxt, self.sample_resources)
        self.assertEqual(defaults, {'r1': 1, 'r2': 2})
        self.sample_resources.pop('r1')
        defaults = self.driver.get_defaults(self.ctxt, self.sample_resources)
        self.assertEqual(defaults, {'r2': 2})

    def test_get_class_quotas(self):
        quotas = self.driver.get_class_quotas(self.ctxt,
                                              self.sample_resources,
                                              'ClassName')
        self.assertEqual(quotas, {'r1': 9, 'r2': 2})

    def test_get_user_quotas(self):
        actual = self.driver.get_user_quotas(
            self.ctxt, self.sample_resources.copy(), 'p1', 'u1')
        expected = {'r1': {'in_use': 2, 'limit': 5, 'reserved': 1},
                    'r2': {'in_use': 3, 'limit': 6, 'reserved': 2}}
        self.assertEqual(actual, expected)

    def test_get_default_user_quotas(self):
        self.dbapi.quota_get_all_by_project_and_user = mock.Mock(
            return_value={'project_id': 'p1', 'user_id': 'u1'})
        self.dbapi.quota_get_all_by_project = mock.Mock(
            return_value={'r1': 5, 'r2': 6})
        driver = quota.DbQuotaDriver(self.dbapi)
        actual = driver.get_user_quotas(
            self.ctxt, self.sample_resources.copy(), 'p1', 'u1')
        expected = {'r1': {'in_use': 2, 'limit': 5, 'reserved': 1},
                    'r2': {'in_use': 3, 'limit': 6, 'reserved': 2}}
        self.assertEqual(actual, expected)

    def test_get_settable_quotas(self):
        actual = self.driver.get_settable_quotas(self.ctxt,
                                                 self.sample_resources, 'p1')
        expected = {'r1': {'maximum': -1, 'minimum': 3},
                    'r2': {'maximum': -1, 'minimum': 5}}
        self.assertEqual(actual, expected)

    def test_get_settable_quotas_with_user_id(self):
        actual = self.driver.get_settable_quotas(
            self.ctxt, self.sample_resources, 'p1', user_id='u1')
        expected = {'r1': {'maximum': 3, 'minimum': 3},
                    'r2': {'maximum': 4, 'minimum': 5}}
        self.assertEqual(actual, expected)

    def test_get_project_quotas(self):
        self.ctxt.quota_class = 'ClassName'
        expected = {'r1': {'limit': 1, 'in_use': 1, 'reserved': 2},
                    'r2': {'limit': 2, 'in_use': 2, 'reserved': 3}}
        quotas = self.driver.get_project_quotas(self.ctxt,
                                                self.sample_resources, 'p1')
        self.assertEqual(quotas, expected)

    def test_get_project_quotas_project_id_differs(self):
        self.ctxt.project_id = 'p2'
        expected = {'r1': {'limit': 1, 'in_use': 1, 'reserved': 2},
                    'r2': {'limit': 2, 'in_use': 2, 'reserved': 3}}
        quotas = self.driver.get_project_quotas(self.ctxt,
                                                self.sample_resources, 'p1')
        self.assertEqual(quotas, expected)

    def test_get_project_quotas_omit_default_quota_class(self):
        self.sample_resources['r3'] = quota.BaseResource('r3')
        quotas = self.driver.get_project_quotas(
            self.ctxt, self.sample_resources, 'p1', defaults=False)
        expected = {'r1': {'limit': 1, 'in_use': 1, 'reserved': 2},
                    'r2': {'limit': 2, 'in_use': 2, 'reserved': 3}}
        self.assertEqual(quotas, expected)

    def test_limit_check_invalid_quota_value(self):
        self.assertRaises(quota.InvalidQuotaValue,
                          self.driver.limit_check, self.ctxt, [], {'r1': -1})

    def test_limit_check_quota_resource_unknown(self):
        self.assertRaises(quota.QuotaResourceUnknown,
                          self.driver.limit_check,
                          self.ctxt,
                          {'r1': quota.ReservableResource('r1', 'r1')},
                          {'r1': 42})

    def test_limit_check_over_quota(self):
        self.assertRaises(quota.OverQuota,
                          self.driver.limit_check,
                          self.ctxt,
                          {'r1': quota.BaseResource('r1')},
                          {'r1': 2})

    def test_limit_check(self):
        self.assertIsNone(self.driver.limit_check(
            self.ctxt, {'r1': quota.BaseResource('r1')}, {'r1': 1}))

    def test_quota_reserve(self):
        now = datetime.datetime.utcnow()

        class FakeTimeutils(object):
            @staticmethod
            def utcnow():
                return now

        self.stubs.Set(quota, "timeutils", FakeTimeutils)

        expected = [self.ctxt, self.sample_resources, {}, {}, {}, None,
                    self.CONF.until_refresh, self.CONF.max_age]

        # expire as None
        self.assertEqual('quota_reserve', self.driver.reserve(
            self.ctxt, self.sample_resources, {}, None, 'p1'))
        expected[5] = now + datetime.timedelta(
            seconds=self.CONF.reservation_expire)
        self.driver.db.quota_reserve.assert_called_once_with(*expected,
                                                             project_id='p1',
                                                             user_id='u1')
        self.driver.db.reset_mock()
        # expire as seconds
        self.assertEqual('quota_reserve', self.driver.reserve(
            self.ctxt, self.sample_resources, {}, 42, 'p1'))
        expected[5] = now + datetime.timedelta(seconds=42)
        self.driver.db.quota_reserve.assert_called_once_with(*expected,
                                                             project_id='p1',
                                                             user_id='u1')
        self.driver.db.reset_mock()
        # expire as absolute
        expected[5] = now + datetime.timedelta(hours=1)
        self.assertEqual('quota_reserve', self.driver.reserve(
            self.ctxt, self.sample_resources, {},
            now + datetime.timedelta(hours=1), 'p1'))
        self.driver.db.quota_reserve.assert_called_once_with(*expected,
                                                             project_id='p1',
                                                             user_id='u1')
        self.driver.db.reset_mock()
        # InvalidReservationExpiration
        self.assertRaises(quota.InvalidReservationExpiration,
                          self.driver.reserve, self.ctxt,
                          self.sample_resources, {}, (), 'p1')
        self.driver.db.reset_mock()
        # project_id is None
        self.assertEqual('quota_reserve', self.driver.reserve(
            self.ctxt, self.sample_resources, {},
            now + datetime.timedelta(hours=1)))
        self.driver.db.quota_reserve.assert_called_once_with(*expected,
                                                             project_id='p1',
                                                             user_id='u1')

    def test_commit(self):
        self.assertIsNone(self.driver.commit(self.ctxt, 'reservations',
                          project_id='p1'))
        self.driver.db.reservation_commit.assert_called_once_with(
            self.ctxt, 'reservations', project_id='p1', user_id='u1')

    def test_commit_project_id_none(self):
        self.assertIsNone(self.driver.commit(self.ctxt, 'reservations'))
        self.driver.db.reservation_commit.assert_called_once_with(
            self.ctxt, 'reservations', project_id='p1', user_id='u1')

    def test_rollback(self):
        self.assertIsNone(self.driver.rollback(self.ctxt, 'reservations',
                                               project_id='p1'))
        self.driver.db.reservation_rollback.assert_called_once_with(
            self.ctxt, 'reservations', project_id='p1', user_id='u1')

    def test_rollback_project_id_none(self):
        self.assertIsNone(self.driver.rollback(self.ctxt, 'reservations'))
        self.driver.db.reservation_rollback.assert_called_once_with(
            self.ctxt, 'reservations', project_id='p1', user_id='u1')

    def test_usage_reset(self):
        resource = self.sample_resources['r1']
        self.assertIsNone(self.driver.usage_reset(self.ctxt, [resource]))
        self.driver.db.quota_usage_update.assert_called_once_with(
            self.ctxt, 'p1', 'u1', resource, in_use=-1)

    def test_usage_reset_quota_usage_not_found(self):
        resource = self.sample_resources['r1']
        self.driver.db.quota_usage_update = mock.Mock(
            side_effect=quota.QuotaUsageNotFound)
        self.assertIsNone(self.driver.usage_reset(self.ctxt, [resource]))
        self.driver.db.quota_usage_update.assert_called_once_with(
            self.ctxt, 'p1', 'u1', resource, in_use=-1)

    def test_destroy_all_by_project_and_user(self):
        self.assertIsNone(self.driver.destroy_all_by_project_and_user(
            self.ctxt, 'p1', 'u1'))
        method = self.driver.db.quota_destroy_all_by_project_and_user
        method.assert_called_once_with(self.ctxt, 'p1', 'u1')

    def test_destroy_all_by_project(self):
        self.assertIsNone(self.driver.destroy_all_by_project(self.ctxt, 'p1'))
        self.driver.db.quota_destroy_all_by_project.assert_called_once_with(
            self.ctxt, 'p1')

    def test_expire(self):
        self.assertIsNone(self.driver.expire(self.ctxt))
        self.driver.db.reservation_expire.assert_called_once_with(self.ctxt)


class BaseResourceTestCase(test.BaseTestCase):

    def setUp(self):
        self.ctxt = FakeContext()
        self.dbapi = mock.Mock()
        self.dbapi.quota_get = mock.Mock(return_value='quota_get')
        self.dbapi.quota_class_get = mock.Mock(
            return_value='quota_class_get')
        self.dbapi.quota_class_get_default = mock.Mock(
            return_value={'r1': 1})
        self.driver = quota.DbQuotaDriver(self.dbapi)
        super(BaseResourceTestCase, self).setUp()

    def test_quota(self):
        resource = quota.BaseResource('r1')
        self.assertEqual('quota_get', resource.quota(self.driver, self.ctxt))

    def test_quota_no_project_id(self):
        self.ctxt.project_id = None
        resource = quota.BaseResource('r1')
        self.assertEqual('quota_class_get',
                         resource.quota(self.driver, self.ctxt))

    def test_quota_project_quota_not_found(self):
        self.dbapi.quota_get = mock.Mock(
            side_effect=quota.ProjectQuotaNotFound())
        resource = quota.BaseResource('r1')
        self.assertEqual('quota_class_get',
                         resource.quota(self.driver, self.ctxt))

    def test_quota_quota_class_not_found(self):
        self.dbapi.quota_get = mock.Mock(
            side_effect=quota.ProjectQuotaNotFound(project_id='p1'))
        self.dbapi.quota_class_get = mock.Mock(
            side_effect=quota.QuotaClassNotFound(class_name='ClassName'))
        resource = quota.BaseResource('r1')
        self.assertEqual(1, resource.quota(self.driver, self.ctxt))


class CountableResourceTestCase(test.BaseTestCase):

    def test_init(self):
        resource = quota.CountableResource('r1', 42)
        self.assertEqual('r1', resource.name)
        self.assertEqual(42, resource.count)


class QuotaEngineTestCase(test.BaseTestCase):

    def setUp(self):
        self.ctxt = FakeContext()
        self.dbapi = mock.Mock()
        self.quota_driver = mock.Mock()
        self.engine = quota.QuotaEngine(self.dbapi, self.quota_driver)
        self.r1 = quota.BaseResource('r1')
        self.r2 = quota.BaseResource('r2')
        self.engine.register_resources([self.r1, self.r2])
        super(QuotaEngineTestCase, self).setUp()

    def assertProxyMethod(self, method, *args, **kwargs):
        if 'retval' in kwargs:
            retval = kwargs.pop('retval')
        else:
            retval = method
        setattr(self.quota_driver, method, mock.Mock(return_value=method))
        actual = getattr(self.engine, method)(self.ctxt, *args, **kwargs)
        getattr(self.quota_driver, method).assert_called_once_with(self.ctxt,
                                                                   *args,
                                                                   **kwargs)
        self.assertEqual(actual, retval)

    def assertMethod(self, method, args, kwargs, called_args,
                     called_kwargs, retval):
        setattr(self.quota_driver, method, mock.Mock(return_value=method))
        actual = getattr(self.engine, method)(self.ctxt, *args, **kwargs)
        getattr(self.quota_driver, method).assert_called_once_with(
            self.ctxt, *called_args, **called_kwargs)
        self.assertEqual(actual, retval)

    def test_proxy_methods(self):
        self.assertProxyMethod('get_by_project', 'p1', 'resname')
        self.assertProxyMethod('get_by_project_and_user', 'p1', 'u1', 'res')
        self.assertProxyMethod('get_by_class', 'quota_class', 'resname')
        self.assertProxyMethod('get_default', 'resource')
        self.assertProxyMethod('expire', retval=None)
        self.assertProxyMethod('usage_reset', 'resources', retval=None)
        self.assertProxyMethod('destroy_all_by_project', 'p1', retval=None)
        self.assertProxyMethod('destroy_all_by_project_and_user', 'p1',
                               'u1', retval=None)
        self.assertProxyMethod('commit', 'reservations', project_id='p1',
                               user_id='u1', retval=None)
        self.assertProxyMethod('rollback', 'reservations', project_id='p1',
                               user_id=None, retval=None)

        self.assertMethod('get_settable_quotas', ['p1'], {'user_id': 'u1'},
                          [self.engine.resources, 'p1'], {'user_id': 'u1'},
                          'get_settable_quotas')
        self.assertMethod('get_defaults', [], {},
                          [self.engine.resources], {}, 'get_defaults')
        self.assertMethod('get_project_quotas', ['p1', 'quotaclass'],
                          {'defaults': 'defaults', 'usages': 'usages'},
                          [self.engine.resources, 'p1'],
                          {'quota_class': 'quotaclass', 'defaults': 'defaults',
                           'usages': 'usages', 'remains': False},
                          'get_project_quotas')
        self.assertMethod('reserve', [],
                          {'expire': 'expire', 'project_id': 'p1',
                           'user_id': 'u1', 'deltas': 'd1'},
                          [self.engine.resources, {'deltas': 'd1'}],
                          {'expire': 'expire',
                           'project_id': 'p1', 'user_id': 'u1'}, 'reserve')
        self.assertMethod('get_class_quotas',
                          ['quota_class'], {'defaults': 'defaults'},
                          [self.engine.resources, 'quota_class'],
                          {'defaults': 'defaults'}, 'get_class_quotas')
        self.assertMethod('get_user_quotas', ['project_id', 'user_id'],
                          {'quota_class': 'qc', 'defaults': 'de',
                           'usages': 'us'},
                          [self.engine.resources, 'project_id', 'user_id'],
                          {'quota_class': 'qc', 'defaults': 'de',
                           'usages': 'us'},
                          'get_user_quotas')
        self.assertMethod('limit_check',
                          [], {'project_id': 'p1', 'user_id': 'u1',
                               'val1': 'val1'},
                          [self.engine.resources, {'val1': 'val1'}],
                          {'project_id': 'p1', 'user_id': 'u1'}, 'limit_check')

    def test_resource_names(self):
        self.assertEqual(['r1', 'r2'], self.engine.resource_names)

    def test_contains(self):
        self.assertTrue(self.r1.name in self.engine)
        self.assertTrue(self.r2.name in self.engine)
        self.assertFalse('r3' in self.engine)

    def test_count(self):
        count = mock.Mock(return_value=42)
        r = quota.CountableResource('r1', count)
        self.engine.register_resource(r)
        actual = self.engine.count(self.ctxt, 'r1')
        self.assertEqual(42, actual)
        count.assert_called_once_with(self.ctxt)
        self.assertRaises(quota.QuotaResourceUnknown,
                          self.engine.count, self.ctxt, 'r2')

    def test_init(self):
        engine = quota.QuotaEngine(self.dbapi)
        self.assertIsInstance(engine._driver, quota.DbQuotaDriver)
