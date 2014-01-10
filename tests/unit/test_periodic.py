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

import datetime

from openstack.common.fixture import config
from openstack.common import periodic_task
from openstack.common import test
from openstack.common import timeutils
from testtools import matchers


class AnException(Exception):
    pass


class AService(periodic_task.PeriodicTasks):

    def __init__(self):
        self.called = {}

    @periodic_task.periodic_task
    def doit(self, context):
        self.called['doit'] = True

    @periodic_task.periodic_task
    def crashit(self, context):
        self.called['urg'] = True
        raise AnException('urg')

    @periodic_task.periodic_task(spacing=10)
    def doit_with_kwargs_odd(self, context):
        self.called['ticks'] = True


class PeriodicTasksTestCase(test.BaseTestCase):
    """Test cases for PeriodicTasks."""

    def test_is_called(self):
        serv = AService()
        serv.run_periodic_tasks(None)
        self.assertTrue(serv.called['doit'])
        self.assertTrue(len(serv.called) == 2)

    def test_called_twice(self):
        serv = AService()
        serv.run_periodic_tasks(None)
        serv.run_periodic_tasks(None)
        # expect doit_with_kwargs to be called twice
        # and doit_with_kwargs_odd to be called once.
        self.assertTrue(len(serv.called) == 3)

    def test_raises(self):
        serv = AService()
        self.assertRaises(AnException,
                          serv.run_periodic_tasks,
                          None, raise_on_error=True)


class ManagerMetaTestCase(test.BaseTestCase):
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
        self.assertIsNone(m._periodic_spacing['foo'])
        self.assertEqual(4, m._periodic_spacing['bar'])
        self.assertThat(
            m._periodic_spacing, matchers.Not(matchers.Contains('baz')))


class ManagerTestCase(test.BaseTestCase):
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

    def test_periodic_tasks_idle_calculation(self):
        fake_time = datetime.datetime(3000, 1, 1)
        timeutils.set_time_override(fake_time)

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
        self.assertIsNotNone(task._periodic_last_run)

        # Test the manager's representation of those values
        self.assertEqual(10, m._periodic_spacing[task_name])
        self.assertIsNotNone(m._periodic_last_run[task_name])

        timeutils.advance_time_delta(datetime.timedelta(seconds=5))
        m.run_periodic_tasks(None)

        timeutils.advance_time_delta(datetime.timedelta(seconds=5))
        idle = m.run_periodic_tasks(None)
        self.assertAlmostEqual(10, idle, 1)

    def test_periodic_tasks_immediate_runs_now(self):
        fake_time = datetime.datetime(3000, 1, 1)
        timeutils.set_time_override(fake_time)

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
        self.assertEqual(datetime.datetime(3000, 1, 1, 0, 0),
                         m._periodic_last_run[task_name])
        self.assertAlmostEqual(10, idle, 1)

        timeutils.advance_time_delta(datetime.timedelta(seconds=5))
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
