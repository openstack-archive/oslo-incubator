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
import mock

from openstack.common import profiler
from openstack.common import test


class ProfilerTest(test.BaseTestCase):

    def setUp(self):
        super(ProfilerTest, self).setUp()

    def test_profiler_notify(self):
        with mock.patch('openstack.common.notifier.api.notify') as notifier:
            prof = profiler.Profiler(service='oslo', base_id='test_call')
            with prof('some method'):
                pass  # here be dragons :)
            notifier.assert_has_calls([
                mock.call(
                    prof._context,
                    mock.ANY,
                    'profiler.oslo',
                    'INFO',
                    {
                        'parent_id': 'test_call',
                        'name': 'some method-start',
                        'base_id': 'test_call',
                        'trace_id': mock.ANY,
                    }
                ),
                mock.call(
                    prof._context,
                    mock.ANY,
                    'profiler.oslo',
                    'INFO',
                    {
                        'parent_id': 'test_call',
                        'name': 'some method-stop',
                        'base_id': 'test_call',
                        'trace_id': mock.ANY,
                    }
                )
            ])
