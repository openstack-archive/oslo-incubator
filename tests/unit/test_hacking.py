# Copyright (c) 2014 EasyStack, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from oslotest import base as test_base

from openstack.hacking import checks


class HackingTestCase(test_base.BaseTestCase):

    def test_no_import_from(self):
        self.assertIsNone(checks.no_import_from(
            "from openstack.common.apiclient import exceptions"))

        self.assertIsNone(checks.no_import_from(
            "from openstack.common import log as logging"))

        self.assertIsInstance(checks.no_import_from(
            "import openstack.common.report.generators.conf as cgen"), tuple)
