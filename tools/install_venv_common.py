# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2013 OpenStack, LLC
# Copyright 2013 IBM Corp.
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

"""Provides methods needed by installation script for OpenStack development
virtual environments.

Synced in from openstack-common
"""

__all__ = ['main']

import argparse
import os
import subprocess
import sys

from oslo.config import cfg


def print_help(venv):
    help = """Development environment setup is complete.

    This project's development uses virtualenv to track and manage Python
    dependencies while in development and testing.

    To activate the virtualenv for the extent of your current shell
    session you can run:

    $ source %s/bin/activate
    """
    print help % (venv)


class InstallVenv(object):

    def __init__(self, root, venv, requirements, test_requirements):
        self.root = root
        self.venv = venv
        self.requirements = requirements
        self.test_requirements = test_requirements

    def die(self, message, *args):
        print >> sys.stderr, message % args
        sys.exit(1)

    def check_python_version(self):
        if sys.version_info < (2, 6):
            self.die("Need Python Version >= 2.6")

    def run_command_with_code(self, cmd, redirect_output=True,
                              check_exit_code=True):
        """Runs a command in an out-of-process shell.

        Returns the output of that command. Working directory is self.root.
        """
        if redirect_output:
            stdout = subprocess.PIPE
        else:
            stdout = None

        proc = subprocess.Popen(cmd, cwd=self.root, stdout=stdout)
        output = proc.communicate()[0]
        if check_exit_code and proc.returncode != 0:
            self.die('Command "%s" failed.\n%s', ' '.join(cmd), output)
        return (output, proc.returncode)

    def run_command(self, cmd, redirect_output=True, check_exit_code=True):
        return self.run_command_with_code(cmd, redirect_output,
                                          check_exit_code)[0]

    def create_virtualenv(self, no_site_packages=True):
        """Creates the virtual environment and installs PIP.

        Creates the virtual environment and installs PIP only into the
        virtual environment.
        """
        if not os.path.isdir(self.venv):
            print 'Creating venv...',
            if no_site_packages:
                self.run_command(['virtualenv', '-q', '--no-site-packages',
                                 self.venv])
            else:
                self.run_command(['virtualenv', '-q', self.venv])
            print 'done.'
        else:
            print "venv already exists..."
            pass

    def pip_install(self, *args):
        self.run_command([os.path.join(self.venv, 'bin', 'pip'),
                         'install', '--upgrade'] + list(args),
                         redirect_output=False)

    def install_dependencies(self):
        print 'Installing dependencies with pip (this can take a while)...'

        if self.requirements:
            self.pip_install('-r', self.requirements)
        if self.test_requirements:
            self.pip_install('-r', self.test_requirements)

    def parse_args(self, argv):
        """Parses command-line arguments."""
        parser = argparse.ArgumentParser()
        parser.add_argument('-n', '--no-site-packages',
                            action='store_true',
                            help="Do not inherit packages from global Python "
                                 "install")
        return parser.parse_args(argv[1:])


def main():

    root = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))

    if os.environ.get('tools_path'):
        root = os.environ['tools_path']
    venv = os.path.join(root, '.venv')
    if os.environ.get('venv'):
        venv = os.environ['venv']

    requirements = None
    test_requirements = None
    if os.path.exists('requirements.txt'):
        requirements = 'requirements.txt'
    else:
        pip_requires = os.path.join(root, 'tools', 'pip-requires')
        if os.path.exists(pip_requires):
            requirements = pip_requires
    if os.path.exists('test-requirements.txt'):
        test_requirements = 'test-requirements.txt'
    else:
        test_requires = os.path.join(root, 'tools', 'test-requires')
        if os.path.exists(test_requires):
            test_requirements = test_requires
    install = InstallVenv(root, venv, requirements, test_requirements)
    options = install.parse_args(sys.argv)
    install.create_virtualenv(no_site_packages=options.no_site_packages)
    install.install_dependencies()
    print_help(venv)

if __name__ == '__main__':
    main()
