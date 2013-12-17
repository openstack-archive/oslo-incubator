# -*- encoding: utf-8 -*-
#
# Copyright © 2013 Intel Corp.
#
# Author: Lianhao Lu <lianhao.lu@intel.com>
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import fixtures

from openstack.common.config import generator
from openstack.common.fixture import mockpatch
from openstack.common import test


class GeneratorTestcase(test.BaseTestCase):
    # The .py suffix left out for file fblaa_opt, to trigger the ext_names
    # code snippet in generator.generate()
    conffiles = ["tests/testmods/baar_baa_opt.py",
                 "tests/testmods/bar_foo_opt.py",
                 "tests/testmods/fblaa_opt"]

    def setUp(self):
        super(GeneratorTestcase, self).setUp()
        self.groups = []

    def tearDown(self):
        self.groups = []
        super(GeneratorTestcase, self).tearDown()

    def faux_print_group_opts(self, group, opts):
        self.groups.append(group)

    def test_group_order(self):
        self.useFixture(mockpatch.Patch(
            'openstack.common.config.generator.print_group_opts',
            new=self.faux_print_group_opts))
        generator.generate(self.conffiles)
        self.assertEqual(['DEFAULT', 'baar', 'bar'], self.groups)

    def test_generate(self):
        stdout = self.useFixture(fixtures.StringStream('confstdout')).stream
        self.useFixture(mockpatch.Patch('sys.stdout', new=stdout))
        generator.generate(self.conffiles)
        stdout.flush()
        stdout.seek(0)
        lines = stdout.readlines()
        # Test we have group in the output
        self.assertIn('[DEFAULT]\n', lines)
        self.assertIn('[baar]\n', lines)
        self.assertIn('[bar]\n', lines)
        # Test we have opt in the output
        self.assertIn('#baa=<None>\n', lines)
        self.assertIn('#foo=<None>\n', lines)
        self.assertIn('#fblaa=fblaa\n', lines)
