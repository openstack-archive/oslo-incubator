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
"""
Though openstack.commom.manager.base_service_manager.BaseManager is just a
helper class for creation origin service manager, some methods should be
overwritten during definition for successfull work.
For example, get_project_name should return 'nova' for nova service in loading
plugins. In cinder it can be missed.
"""

from openstack.common.manager import base_service_manager


class FakeManager(base_service_manager.BaseManager):

    def get_project_name(self):
        return 'fake_project'


class FakeSchedulerDependentManager(FakeManager,
                                    base_service_manager.
                                    BaseSchedulerDependentManager):
    pass
