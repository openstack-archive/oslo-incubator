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

from openstack.common.report.generators import conf as os_cgen
from openstack.common.report.generators import threading as os_tgen
from openstack.common.report.generators import version as os_pgen
from openstack.common.report.models import threading as os_tmod
from oslo.config import cfg

from tests import utils

import greenlet
import threading


class TestOpenstackGenerators(utils.BaseTestCase):
    def test_thread_generator(self):
        model = os_tgen.ThreadReportGenerator()()
        # self.assertGreaterEqual(len(model.keys()), 1)
        self.assertTrue(len(model.keys()) >= 1)
        self.assertIsInstance(model[0], os_tmod.ThreadModel)
        self.assertIsNotNone(model[0].stack_trace)

        was_ok = False
        for tm in model.values():
            if tm.thread_id == threading.current_thread().ident:
                was_ok = True
                break
        self.assertTrue(was_ok)

        model.set_current_view_type('text')
        self.assertIsNotNone(str(model))

    def test_green_thread_generator(self):
        curr_g = greenlet.getcurrent()

        model = os_tgen.GreenThreadReportGenerator()()

        # self.assertGreaterEqual(len(model.keys()), 1)
        self.assertTrue(len(model.keys()) >= 1)

        was_ok = False
        for tm in model.values():
            if tm.stack_trace == os_tmod.StackTraceModel(curr_g.gr_frame):
                was_ok = True
                break
        self.assertTrue(was_ok)

        model.set_current_view_type('text')
        self.assertIsNotNone(str(model))

    def test_config_model(self):
        conf = cfg.ConfigOpts()
        conf.register_opt(cfg.StrOpt('crackers', default='triscuit'))
        conf.register_group(cfg.OptGroup('cheese', title='Cheese Info'))
        conf.register_opt(cfg.IntOpt('sharpness', default=1),
                          group='cheese')
        conf.register_opt(cfg.StrOpt('name', default='cheddar'),
                          group='cheese')
        conf.register_opt(cfg.BoolOpt('from_cow', default=True),
                          group='cheese')

        model = os_cgen.ConfigReportGenerator(conf)()
        model.set_current_view_type('text')

        target_str = ('\ndefault: \n'
                      '  crackers = triscuit\n'
                      '\n'
                      'cheese: \n'
                      '  from_cow = True\n'
                      '  sharpness = 1\n'
                      '  name = cheddar')
        self.assertEquals(target_str, str(model))

    def test_package_report_generator(self):
        class VersionObj(object):
            def vendor_string(self):
                return 'Cheese Shoppe'

            def product_string(self):
                return 'Sharp Cheddar'

            def version_string_with_package(self):
                return '1.0.0'

        model = os_pgen.PackageReportGenerator(VersionObj())()
        model.set_current_view_type('text')

        target_str = ('product = Sharp Cheddar\n'
                      'version = 1.0.0\n'
                      'vendor = Cheese Shoppe')
        self.assertEquals(target_str, str(model))
