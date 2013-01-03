# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2011 OpenStack LLC.
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
Utilities with minimum-depends for use in setup.py
"""

import datetime
import os
import re
import subprocess
import sys

from setuptools.command import sdist


def parse_mailmap(mailmap='.mailmap'):
    mapping = {}
    if os.path.exists(mailmap):
        with open(mailmap, 'r') as fp:
            for l in fp:
                l = l.strip()
                if not l.startswith('#') and ' ' in l:
                    canonical_email, alias = [x for x in l.split(' ')
                                              if x.startswith('<')]
                    mapping[alias] = canonical_email
    return mapping


def canonicalize_emails(changelog, mapping):
    """Takes in a string and an email alias mapping and replaces all
       instances of the aliases in the string with their real email.
    """
    for alias, email in mapping.iteritems():
        changelog = changelog.replace(alias, email)
    return changelog


# Get requirements from the first file that exists
def get_reqs_from_files(requirements_files):
    for requirements_file in requirements_files:
        if os.path.exists(requirements_file):
            with open(requirements_file, 'r') as fil:
                return fil.read().split('\n')
    return []


def parse_requirements(requirements_files=['requirements.txt',
                                           'tools/pip-requires']):
    requirements = []
    for line in get_reqs_from_files(requirements_files):
        # For the requirements list, we need to inject only the portion
        # after egg= so that distutils knows the package it's looking for
        # such as:
        # -e git://github.com/openstack/nova/master#egg=nova
        if re.match(r'\s*-e\s+', line):
            requirements.append(re.sub(r'\s*-e\s+.*#egg=(.*)$', r'\1',
                                line))
        # such as:
        # http://github.com/openstack/nova/zipball/master#egg=nova
        elif re.match(r'\s*https?:', line):
            requirements.append(re.sub(r'\s*https?:.*#egg=(.*)$', r'\1',
                                line))
        # -f lines are for index locations, and don't get used here
        elif re.match(r'\s*-f\s+', line):
            pass
        # argparse is part of the standard library starting with 2.7
        # adding it to the requirements list screws distro installs
        elif line == 'argparse' and sys.version_info >= (2, 7):
            pass
        else:
            requirements.append(line)

    return requirements


def parse_dependency_links(requirements_files=['requirements.txt',
                                               'tools/pip-requires']):
    dependency_links = []
    # dependency_links inject alternate locations to find packages listed
    # in requirements
    for line in get_reqs_from_files(requirements_files):
        # skip comments and blank lines
        if re.match(r'(\s*#)|(\s*$)', line):
            continue
        # lines with -e or -f need the whole line, minus the flag
        if re.match(r'\s*-[ef]\s+', line):
            dependency_links.append(re.sub(r'\s*-[ef]\s+', '', line))
        # lines that are only urls can go in unmolested
        elif re.match(r'\s*https?:', line):
            dependency_links.append(line)
    return dependency_links


def write_requirements():
    venv = os.environ.get('VIRTUAL_ENV', None)
    if venv is not None:
        with open("requirements.txt", "w") as req_file:
            output = subprocess.Popen(["pip", "-E", venv, "freeze", "-l"],
                                      stdout=subprocess.PIPE)
            requirements = output.communicate()[0].strip()
            req_file.write(requirements)


def _run_shell_command(cmd):
    if os.name == 'nt':
        output = subprocess.Popen(["cmd.exe", "/C", cmd],
                                  stdout=subprocess.PIPE)
    else:
        output = subprocess.Popen(["/bin/sh", "-c", cmd],
                                  stdout=subprocess.PIPE)
    out = output.communicate()
    if len(out) == 0:
        return None
    if len(out[0].strip()) == 0:
        return None
    return out[0].strip()


def write_git_changelog():
    """Write a changelog based on the git changelog."""
    new_changelog = 'ChangeLog'
    if not os.getenv('SKIP_WRITE_GIT_CHANGELOG'):
        if os.path.isdir('.git'):
            git_log_cmd = 'git log --stat'
            changelog = _run_shell_command(git_log_cmd)
            mailmap = parse_mailmap()
            with open(new_changelog, "w") as changelog_file:
                changelog_file.write(canonicalize_emails(changelog, mailmap))
    else:
        open(new_changelog, 'w').close()


def generate_authors():
    """Create AUTHORS file using git commits."""
    jenkins_email = 'jenkins@review.(openstack|stackforge).org'
    old_authors = 'AUTHORS.in'
    new_authors = 'AUTHORS'
    if not os.getenv('SKIP_GENERATE_AUTHORS'):
        if os.path.isdir('.git'):
            # don't include jenkins email address in AUTHORS file
            git_log_cmd = ("git log --format='%aN <%aE>' | sort -u | "
                           "egrep -v '" + jenkins_email + "'")
            changelog = _run_shell_command(git_log_cmd)
            mailmap = parse_mailmap()
            with open(new_authors, 'w') as new_authors_fh:
                new_authors_fh.write(canonicalize_emails(changelog, mailmap))
                if os.path.exists(old_authors):
                    with open(old_authors, "r") as old_authors_fh:
                        new_authors_fh.write('\n' + old_authors_fh.read())
    else:
        open(new_authors, 'w').close()


_rst_template = """%(heading)s
%(underline)s

.. automodule:: %(module)s
  :members:
  :undoc-members:
  :show-inheritance:
"""


def get_cmdclass():
    """Return dict of commands to run from setup.py."""

    cmdclass = dict()

    def _find_modules(arg, dirname, files):
        for filename in files:
            if filename.endswith('.py') and filename != '__init__.py':
                arg["%s.%s" % (dirname.replace('/', '.'),
                               filename[:-3])] = True

    class LocalSDist(sdist.sdist):
        """Builds the ChangeLog and Authors files from VC first."""

        def run(self):
            write_git_changelog()
            generate_authors()
            # sdist.sdist is an old style class, can't use super()
            sdist.sdist.run(self)

    cmdclass['sdist'] = LocalSDist

    # If Sphinx is installed on the box running setup.py,
    # enable setup.py to build the documentation, otherwise,
    # just ignore it
    try:
        from sphinx.setup_command import BuildDoc

        class LocalBuildDoc(BuildDoc):
            def generate_autoindex(self):
                print "**Autodocumenting from %s" % os.path.abspath(os.curdir)
                modules = {}
                option_dict = self.distribution.get_option_dict('build_sphinx')
                source_dir = os.path.join(option_dict['source_dir'][1], 'api')
                if not os.path.exists(source_dir):
                    os.makedirs(source_dir)
                for pkg in self.distribution.packages:
                    if '.' not in pkg:
                        os.path.walk(pkg, _find_modules, modules)
                module_list = modules.keys()
                module_list.sort()
                autoindex_filename = os.path.join(source_dir, 'autoindex.rst')
                with open(autoindex_filename, 'w') as autoindex:
                    autoindex.write(""".. toctree::
   :maxdepth: 1

""")
                    for module in module_list:
                        output_filename = os.path.join(source_dir,
                                                       "%s.rst" % module)
                        heading = "The :mod:`%s` Module" % module
                        underline = "=" * len(heading)
                        values = dict(module=module, heading=heading,
                                      underline=underline)

                        print "Generating %s" % output_filename
                        with open(output_filename, 'w') as output_file:
                            output_file.write(_rst_template % values)
                        autoindex.write("   %s.rst\n" % module)

            def run(self):
                if not os.getenv('SPHINX_DEBUG'):
                    self.generate_autoindex()

                for builder in ['html', 'man']:
                    self.builder = builder
                    self.finalize_options()
                    self.project = self.distribution.get_name()
                    self.version = self.distribution.get_version()
                    self.release = self.distribution.get_version()
                    BuildDoc.run(self)
        cmdclass['build_sphinx'] = LocalBuildDoc
    except ImportError:
        pass

    return cmdclass

