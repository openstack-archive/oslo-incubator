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

from openstack.common.report.models import base as base_model
from openstack.common.report import report

from tests import utils


class BasicView(object):
    def __call__(self, model):
        res = ""
        for k, v in model.items():
            res += str(k) + ": " + str(v) + ";"

        return res


def basic_generator():
    return base_model.ReportModel(data={'string': 'value', 'int': 1})


class TestBasicReport(utils.BaseTestCase):
    def setUp(self):
        super(TestBasicReport, self).setUp()

        self.report = report.BasicReport()

    def test_add_section(self):
        self.report.add_section(BasicView(), basic_generator)
        self.assertEqual(len(self.report.sections), 1)

    def test_append_section(self):
        self.report.add_section(BasicView(), lambda: {'a': 1})
        self.report.add_section(BasicView(), basic_generator)

        self.assertEqual(len(self.report.sections), 2)
        self.assertEqual(self.report.sections[1].generator, basic_generator)

    def test_insert_section(self):
        self.report.add_section(BasicView(), lambda: {'a': 1})
        self.report.add_section(BasicView(), basic_generator, 0)

        self.assertEqual(len(self.report.sections), 2)
        self.assertEqual(self.report.sections[0].generator, basic_generator)

    def test_basic_render(self):
        self.report.add_section(BasicView(), basic_generator)
        self.assertEquals(self.report.run(), "int: 1;string: value;")

    def test_submodel_attached_view(self):
        class TmpView(object):
            def __call__(self, model):
                return '{len: ' + str(len(model.c)) + '}'

        def generate_model_with_submodel():
            base_m = basic_generator()
            sm = base_model.ReportModel(data={'c': [1, 2, 3]},
                                        attached_view=TmpView())

            base_m['submodel'] = sm
            return base_m

        self.report.add_section(BasicView(), generate_model_with_submodel)

        self.assertEqual(self.report.run(),
                         'int: 1;string: value;submodel: {len: 3};')
