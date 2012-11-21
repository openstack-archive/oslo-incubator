# vim: tabstop=4 shiftwidth=4 softtabstop=4

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
from openstack.common import periodic_task
from tests import utils


class AService(periodic_task.PeriodicTasks):

    def __init__(self):
        self.called = {}

    @periodic_task.periodic_task
    def doit(self, context):
        self.called['doit'] = True

    @periodic_task.periodic_task
    def crashit(self, context):
        self.called['urg'] = True
        raise Exception('urg')

    @periodic_task.periodic_task(ticks_between_runs=1)
    def doit_with_kwargs_odd(self, context):
        self.called['ticks'] = True


class PeriodicTasksTestCase(utils.BaseTestCase):
    """Test cases for PeriodicTasks"""

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
        self.assertRaises(Exception,
                          serv.run_periodic_tasks,
                          None, raise_on_error=True)
