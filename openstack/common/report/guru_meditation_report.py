# vim: tabstop=4 shiftwidth=4 softtabstop=4

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

"""Provides Guru Meditation Report

This module defines the actual OpenStack Guru Meditation
Report class.

This can be used in the OpenStack command definition files.
For example, in a nova command module (under nova/cmd):

.. code-block:: python
   :emphasize-lines: 8,9,10

   CONF = cfg.CONF
   # maybe import some options here...

   def main():
       config.parse_args(sys.argv)
       logging.setup('blah')

       TextGuruMeditation.register_section('Some Special Section',
                                           special_section_generator)
       TextGuruMeditation.setup_autorun(version_object)

       server = service.Service.create(binary='some-service',
                                       topic=CONF.some_service_topic)
       service.serve(server)
       service.wait()

Then, you can do

.. code-block:: bash

   $ kill -USR1 $SERVICE_PID

and get a Guru Meditation Report in the file or terminal
where stderr is logged for that given service.
"""

from __future__ import print_function

import signal
import sys

from openstack.common.report.generators import conf as cgen
from openstack.common.report.generators import threading as tgen
from openstack.common.report.generators import version as pgen
from openstack.common.report import report


class GuruMeditation(object):
    """A Guru Meditation Report Mixin/Base Class

    This class is a base class for Guru Meditation Reports.
    It provides facilities for registering sections and
    setting up functionality to auto-run the report on
    a certain signal.

    This class should always be used in conjunction with
    a Report class via multiple inheritance.  It should
    always come first in the class list to ensure the
    MRO is correct.
    """

    def __init__(self, version_obj, *args, **kwargs):
        self.version_obj = version_obj

        super(GuruMeditation, self).__init__(*args, **kwargs)
        self.start_section_index = len(self.sections)

    @classmethod
    def register_section(cls, section_title, generator):
        """Register a New Section

        This method registers a persistent section for the current
        class.

        :param str section_title: the title of the section
        :param generator: the generator for the section
        """

        try:
            cls.persistent_sections.append([section_title, generator])
        except AttributeError:
            cls.persistent_sections = [[section_title, generator]]

    @classmethod
    def setup_autorun(cls, version, signum=signal.SIGUSR1):
        """Set Up Auto-Run

        This method sets up the Guru Meditation Report to automatically
        get dumped to stderr when the given signal is received.

        :param version: the version object for the current product
        :param signum: the signal to associate with running the report
        """

        signal.signal(signum, lambda *args: cls.handle_signal(version, *args))

    @classmethod
    def handle_signal(cls, version, *args):
        """The Signal Handler

        This method (indirectly) handles receiving a registered signal and
        dumping the Guru Meditation Report to stderr.  This method is designed
        to be curried into a proper signal handler by currying out the version
        parameter.

        :param version: the version object for the current product
        """

        try:
            res = cls(version).run()
        except Exception:
            print("Unable to run Guru Meditation Report!",
                  file=sys.stderr)
        else:
            print(res, file=sys.stderr)

    def _readd_sections(self):
        del self.sections[self.start_section_index:]

        self.add_section('Package',
                         pgen.PackageReportGenerator(self.version_obj))

        self.add_section('Threads',
                         tgen.ThreadReportGenerator())

        self.add_section('Green Threads',
                         tgen.GreenThreadReportGenerator())

        self.add_section('Configuration',
                         cgen.ConfigReportGenerator())

        try:
            for section_title, generator in self.persistent_sections:
                self.add_section(section_title, generator)
        except AttributeError:
            pass

    def run(self):
        self._readd_sections()
        return super(GuruMeditation, self).run()


# GuruMeditation must come first to get the correct MRO
class TextGuruMeditation(GuruMeditation, report.TextReport):
    """A Text Guru Meditation Report

    This report is the basic human-readable Guru Meditation Report

    It contains the following sections by default
    (in addition to any registered persistent sections):

    - Package Information

    - Threads List

    - Green Threads List

    - Configuration Options

    :param version_obj: the version object for the current product
    """

    def __init__(self, version_obj):
        super(TextGuruMeditation, self).__init__(version_obj,
                                                 'Guru Meditation')
