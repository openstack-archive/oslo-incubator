# Copyright 2010 United States Government as represented by the
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

"""
Unit Tests for periodic_task decorator and PeriodicTasks class.
"""


from oslotest import base as test_base
from six.moves import mock
from testtools import matchers

from openstack.common.fixture import config
from openstack.common import periodic_task


class AnException(Exception):
    pass


class PeriodicTasksTestCase(test_base.BaseTestCase):
    """Test cases for PeriodicTasks."""

    @mock.patch('time.time')
    def test_called_thrice(self, mock_time):

        time = 340
        mock_time.return_value = time

        # Class inside test def to mock 'time.time' in
        # the periodic task decorator
        class AService(periodic_task.PeriodicTasks):
            def __init__(self):
                super(AService, self).__init__()
                self.called = {'doit': 0, 'urg': 0, 'ticks': 0, 'tocks': 0}

            @periodic_task.periodic_task
            def doit(self, context):
                self.called['doit'] += 1

            @periodic_task.periodic_task
            def crashit(self, context):
                self.called['urg'] += 1
                raise AnException('urg')

            @periodic_task.periodic_task(
                spacing=10 + periodic_task.DEFAULT_INTERVAL,
                run_immediately=True)
            def doit_with_ticks(self, context):
                self.called['ticks'] += 1

            @periodic_task.periodic_task(
                spacing=10 + periodic_task.DEFAULT_INTERVAL)
            def doit_with_tocks(self, context):
                self.called['tocks'] += 1

        serv = AService()
        serv.run_periodic_tasks(None)
        # Time: 340
        self.assertEqual(serv.called['doit'], 0)
        self.assertEqual(serv.called['urg'], 0)
        # New last run will be 350
        self.assertEqual(serv.called['ticks'], 1)
        self.assertEqual(serv.called['tocks'], 0)

        time = time + periodic_task.DEFAULT_INTERVAL
        mock_time.return_value = time
        serv.run_periodic_tasks(None)

        # Time:400
        # New Last run: 420
        self.assertEqual(serv.called['doit'], 1)
        self.assertEqual(serv.called['urg'], 1)
        # Closest multiple of 70 is 420
        self.assertEqual(serv.called['ticks'], 1)
        self.assertEqual(serv.called['tocks'], 0)

        time = time + periodic_task.DEFAULT_INTERVAL / 2
        mock_time.return_value = time
        serv.run_periodic_tasks(None)
        self.assertEqual(serv.called['doit'], 1)
        self.assertEqual(serv.called['urg'], 1)
        self.assertEqual(serv.called['ticks'], 2)
        self.assertEqual(serv.called['tocks'], 1)

        time = time + periodic_task.DEFAULT_INTERVAL
        mock_time.return_value = time
        serv.run_periodic_tasks(None)
        self.assertEqual(serv.called['doit'], 2)
        self.assertEqual(serv.called['urg'], 2)
        self.assertEqual(serv.called['ticks'], 3)
        self.assertEqual(serv.called['tocks'], 2)

    @mock.patch('time.time')
    def test_called_correct(self, mock_time):

        time = 360444
        mock_time.return_value = time

        test_spacing = 9

        # Class inside test def to mock 'time.time' in
        # the periodic task decorator
        class AService(periodic_task.PeriodicTasks):
            def __init__(self):
                super(AService, self).__init__()
                self.called = {'ticks': 0}

            @periodic_task.periodic_task(spacing=test_spacing)
            def tick(self, context):
                self.called['ticks'] += 1

        serv = AService()
        for i in range(200):
            serv.run_periodic_tasks(None)
            self.assertEqual(serv.called['ticks'], int(i / test_spacing))
            time += 1
            mock_time.return_value = time

    @mock.patch('time.time')
    def test_raises(self, mock_time):
        time = 230000
        mock_time.return_value = time

        class AService(periodic_task.PeriodicTasks):
            def __init__(self):
                super(AService, self).__init__()
                self.called = {'urg': 0, }

            @periodic_task.periodic_task
            def crashit(self, context):
                self.called['urg'] += 1
                raise AnException('urg')

        serv = AService()
        now = serv._periodic_last_run['crashit']

        mock_time.return_value = now + periodic_task.DEFAULT_INTERVAL
        self.assertRaises(AnException,
                          serv.run_periodic_tasks,
                          None, raise_on_error=True)


class ManagerMetaTestCase(test_base.BaseTestCase):
    """Tests for the meta class which manages the creation of periodic tasks.
    """

    def test_meta(self):
        class Manager(periodic_task.PeriodicTasks):

            @periodic_task.periodic_task
            def foo(self):
                return 'foo'

            @periodic_task.periodic_task(spacing=4)
            def bar(self):
                return 'bar'

            @periodic_task.periodic_task(enabled=False)
            def baz(self):
                return 'baz'

        m = Manager()
        self.assertThat(m._periodic_tasks, matchers.HasLength(2))
        self.assertEqual(periodic_task.DEFAULT_INTERVAL,
                         m._periodic_spacing['foo'])
        self.assertEqual(4, m._periodic_spacing['bar'])
        self.assertThat(
            m._periodic_spacing, matchers.Not(matchers.Contains('baz')))


class ManagerTestCase(test_base.BaseTestCase):
    """Tests the periodic tasks portion of the manager class."""
    def setUp(self):
        super(ManagerTestCase, self).setUp()
        self.config = self.useFixture(config.Config()).config

    def test_periodic_tasks_with_idle(self):
        class Manager(periodic_task.PeriodicTasks):

            @periodic_task.periodic_task(spacing=200)
            def bar(self):
                return 'bar'

        m = Manager()
        self.assertThat(m._periodic_tasks, matchers.HasLength(1))
        self.assertEqual(200, m._periodic_spacing['bar'])

        # Now a single pass of the periodic tasks
        idle = m.run_periodic_tasks(None)
        self.assertAlmostEqual(60, idle, 1)

    def test_periodic_tasks_constant(self):
        class Manager(periodic_task.PeriodicTasks):

            @periodic_task.periodic_task(spacing=0)
            def bar(self):
                return 'bar'

        m = Manager()
        idle = m.run_periodic_tasks(None)
        self.assertAlmostEqual(60, idle, 1)

    @mock.patch('time.time')
    def test_periodic_tasks_idle_calculation(self, mock_time):
        fake_time = 32503680000.0
        mock_time.return_value = fake_time

        class Manager(periodic_task.PeriodicTasks):

            @periodic_task.periodic_task(spacing=10)
            def bar(self, context):
                return 'bar'

        m = Manager()

        # Ensure initial values are correct
        self.assertEqual(1, len(m._periodic_tasks))
        task_name, task = m._periodic_tasks[0]

        # Test task values
        self.assertEqual('bar', task_name)
        self.assertEqual(10, task._periodic_spacing)
        self.assertEqual(True, task._periodic_enabled)
        self.assertEqual(False, task._periodic_external_ok)
        self.assertEqual(False, task._periodic_immediate)
        self.assertAlmostEqual(32503680000.0,
                               task._periodic_last_run)

        # Test the manager's representation of those values
        self.assertEqual(10, m._periodic_spacing[task_name])
        self.assertAlmostEqual(32503680000.0,
                               m._periodic_last_run[task_name])

        mock_time.return_value = fake_time + 5
        idle = m.run_periodic_tasks(None)
        self.assertAlmostEqual(5, idle, 1)
        self.assertAlmostEqual(32503680000.0,
                               m._periodic_last_run[task_name])

        mock_time.return_value = fake_time + 10
        idle = m.run_periodic_tasks(None)
        self.assertAlmostEqual(10, idle, 1)
        self.assertAlmostEqual(32503680010.0,
                               m._periodic_last_run[task_name])

    @mock.patch('time.time')
    def test_periodic_tasks_immediate_runs_now(self, mock_time):
        fake_time = 32503680000.0
        mock_time.return_value = fake_time

        class Manager(periodic_task.PeriodicTasks):

            @periodic_task.periodic_task(spacing=10, run_immediately=True)
            def bar(self, context):
                return 'bar'

        m = Manager()

        # Ensure initial values are correct
        self.assertEqual(1, len(m._periodic_tasks))
        task_name, task = m._periodic_tasks[0]

        # Test task values
        self.assertEqual('bar', task_name)
        self.assertEqual(10, task._periodic_spacing)
        self.assertEqual(True, task._periodic_enabled)
        self.assertEqual(False, task._periodic_external_ok)
        self.assertEqual(True, task._periodic_immediate)
        self.assertIsNone(task._periodic_last_run)

        # Test the manager's representation of those values
        self.assertEqual(10, m._periodic_spacing[task_name])
        self.assertIsNone(m._periodic_last_run[task_name])

        idle = m.run_periodic_tasks(None)
        self.assertAlmostEqual(32503680000.0,
                               m._periodic_last_run[task_name])
        self.assertAlmostEqual(10, idle, 1)

        mock_time.return_value = fake_time + 5
        idle = m.run_periodic_tasks(None)
        self.assertAlmostEqual(5, idle, 1)

    def test_periodic_tasks_disabled(self):
        class Manager(periodic_task.PeriodicTasks):

            @periodic_task.periodic_task(spacing=-1)
            def bar(self):
                return 'bar'

        m = Manager()
        idle = m.run_periodic_tasks(None)
        self.assertAlmostEqual(60, idle, 1)

    def test_external_running_here(self):
        self.config(run_external_periodic_tasks=True)

        class Manager(periodic_task.PeriodicTasks):

            @periodic_task.periodic_task(spacing=200, external_process_ok=True)
            def bar(self):
                return 'bar'

        m = Manager()
        self.assertThat(m._periodic_tasks, matchers.HasLength(1))

    def test_external_running_elsewhere(self):
        self.config(run_external_periodic_tasks=False)

        class Manager(periodic_task.PeriodicTasks):

            @periodic_task.periodic_task(spacing=200, external_process_ok=True)
            def bar(self):
                return 'bar'

        m = Manager()
        self.assertEqual([], m._periodic_tasks)

    @mock.patch('time.time')
    @mock.patch('random.random')
    def test_nearest_boundary(self, mock_random, mock_time):
        mock_time.return_value = 19
        mock_random.return_value = 0
        self.assertEqual(17, periodic_task._nearest_boundary(10, 7))
        mock_time.return_value = 28
        self.assertEqual(27, periodic_task._nearest_boundary(13, 7))
        mock_time.return_value = 1841
        self.assertEqual(1837, periodic_task._nearest_boundary(781, 88))
        mock_time.return_value = 1835
        self.assertEqual(mock_time.return_value,
                         periodic_task._nearest_boundary(None, 88))

        # Add 5% jitter
        mock_random.return_value = 1.0
        mock_time.return_value = 1300
        self.assertEqual(1200 + 10, periodic_task._nearest_boundary(1000, 200))
        # Add 2.5% jitter
        mock_random.return_value = 0.5
        mock_time.return_value = 1300
        self.assertEqual(1200 + 5, periodic_task._nearest_boundary(1000, 200))
