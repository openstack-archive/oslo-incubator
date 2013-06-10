from __future__ import print_function
import generators.openstack as osg
from report import TextReport
import signal
import sys


class GuruMeditation(object):
    # class method
    @classmethod
    def register_section(cls, section_title, generator):
        try:
            cls.persistent_sections.append([section_title, generator])
        except AttributeError:
            cls.persistent_sections = [[section_title, generator]]

    @classmethod
    def setup_autorun(cls, version, signum=signal.SIGUSR1):
        signal.signal(signum, lambda *args: cls.handle_signal(version, *args))

    @classmethod
    def handle_signal(cls, version, *args):
        try:
            res = cls(version).run()
            print(res, file=sys.stderr)
        except Exception:
            print("Unable to print Guru Meditation to stderr!",
                  file=sys.stderr)


class TextGuruMeditation(TextReport, GuruMeditation):
    def __init__(self, version_obj):
        super(TextGuruMeditation, self).__init__('Guru Meditation')

        self.add_section('Package',
                         osg.PackageReportGenerator(version_obj))

        self.add_section('Threads',
                         osg.ThreadReportGenerator())

        self.add_section('Green Threads',
                         osg.GreenThreadReportGenerator())

        self.add_section('Configuration',
                         osg.ConfigReportGenerator())

        try:
            for section_title, generator in self.persistent_sections:
                self.add_section(section_title, generator)
        except AttributeError:
            pass
