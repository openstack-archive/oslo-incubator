# Copyright 2013 Red Hat, Inc.
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

from __future__ import print_function

import os
import re
import signal
import StringIO
import sys

# needed to get greenthreads
import greenlet

from openstack.common.report import guru_meditation_report as gmr
from openstack.common.report.models import with_default_views as mwdv
from tests import utils


class FakeVersionObj(object):
    def vendor_string(self):
        return 'Cheese Shoppe'

    def product_string(self):
        return 'Sharp Cheddar'

    def version_string_with_package(self):
        return '1.0.0'


def skip_body_lines(start_line, report_lines):
    curr_line = start_line
    while (len(report_lines[curr_line]) == 0
           or report_lines[curr_line][0] != '='):
        curr_line += 1

    return curr_line


class TestGuruMeditationReport(utils.BaseTestCase):
    def setUp(self):
        super(TestGuruMeditationReport, self).setUp()

        self.curr_g = greenlet.getcurrent()

        self.report = gmr.TextGuruMeditation(FakeVersionObj())

        self.old_stderr = None

    def test_basic_report(self):
        report_lines = self.report.run().split('\n')

        target_str_header = ['========================================================================',  # noqa
                             '====                        Guru Meditation                         ====',  # noqa
                             '========================================================================',  # noqa
                             '||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||',  # noqa
                             '',
                             '',
                             '========================================================================',  # noqa
                             '====                            Package                             ====',  # noqa
                             '========================================================================',  # noqa
                             'product = Sharp Cheddar',
                             'version = 1.0.0',
                             'vendor = Cheese Shoppe',
                             '========================================================================',  # noqa
                             '====                            Threads                             ====',  # noqa
                             '========================================================================']  # noqa

        # first the header and version info...
        self.assertEqual(target_str_header,
                         report_lines[0:len(target_str_header)])

        # followed by at least one thread...
        # NOTE(zqfan): add an optional '-' because sys._current_frames()
        # may return a negative thread id on 32 bit operating system.
        self.assertTrue(re.match(r'------(\s+)Thread #-?\d+\1\s?------',
                                 report_lines[len(target_str_header)]))
        self.assertEqual('', report_lines[len(target_str_header) + 1])

        # followed by more thread stuff stuff...
        curr_line = skip_body_lines(len(target_str_header) + 2, report_lines)

        # followed by at least one green thread
        target_str_gt = ['========================================================================',  # noqa
                         '====                         Green Threads                          ====',  # noqa
                         '========================================================================',  # noqa
                         '------                        Green Thread                        ------',  # noqa
                         '']
        end_bound = curr_line + len(target_str_gt)
        self.assertEqual(target_str_gt,
                         report_lines[curr_line:end_bound])

        # followed by some more green thread stuff
        curr_line = skip_body_lines(curr_line + len(target_str_gt),
                                    report_lines)

        # followed finally by the configuration
        target_str_config = ['========================================================================',  # noqa
                             '====                         Configuration                          ====',  # noqa
                             '========================================================================',  # noqa
                             '']
        end_bound = curr_line + len(target_str_config)
        self.assertEqual(target_str_config,
                         report_lines[curr_line:end_bound])

    def test_reg_persistent_section(self):
        def fake_gen():
            fake_data = {'cheddar': ['sharp', 'mild'],
                         'swiss': ['with holes', 'with lots of holes'],
                         'american': ['orange', 'yellow']}

            return mwdv.ModelWithDefaultViews(data=fake_data)

        gmr.TextGuruMeditation.register_section('Cheese Types', fake_gen)

        report_lines = self.report.run()
        target_lst = ['========================================================================',  # noqa
                      '====                          Cheese Types                          ====',  # noqa
                      '========================================================================',  # noqa
                      'swiss = ',
                      '  with holes',
                      '  with lots of holes',
                      'american = ',
                      '  orange',
                      '  yellow',
                      'cheddar = ',
                      '  sharp',
                      '  mild']
        target_str = '\n'.join(target_lst)
        self.assertIn(target_str, report_lines)

    def test_register_autorun(self):
        gmr.TextGuruMeditation.setup_autorun(FakeVersionObj())
        self.old_stderr = sys.stderr
        sys.stderr = StringIO.StringIO()

        os.kill(os.getpid(), signal.SIGUSR1)
        self.assertIn('Guru Meditation', sys.stderr.getvalue())

    def tearDown(self):
        super(TestGuruMeditationReport, self).tearDown()
        if self.old_stderr is not None:
            sys.stderr = self.old_stderr
