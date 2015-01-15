#!/usr/bin/env python
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
"""Run unit tests for projects that use a library.
"""

from __future__ import print_function

import glob
import os
import subprocess
import sys

from oslo_config import cfg
import oslo_tool_config as tconfig
from pbr import packaging
import pkg_resources


def find_all_projects(repo_root):
    """Scan the checked out repositories for all available projects.
    """
    pattern = os.path.join(repo_root, 'openstack/*')
    candidates = glob.glob(pattern)
    prefix_len = len(repo_root)
    return [
        c[prefix_len:].lstrip('/')
        for c in candidates
        if os.path.isdir(c)
    ]


def find_consuming_projects(lib_name, repo_root, projects):
    """Filter the list of projects to only include entries that use the library.
    """
    for p in projects:
        consumer = False
        for base in packaging.get_requirements_files():
            req_file = os.path.join(repo_root, p, base)
            for req in packaging.parse_requirements([req_file]):
                try:
                    parsed_req = pkg_resources.Requirement.parse(req)
                    req_name = parsed_req.project_name
                except ValueError:
                    continue
                if req_name == lib_name:
                    consumer = True
                    yield p
                    break
            if consumer:
                break
        # else:
        #     print('ignoring %s because it does not use %s' % (p, lib_name))


def main():
    conf = tconfig.get_config_parser()
    conf.register_cli_opt(
        cfg.StrOpt(
            'library-under-test',
            short='l',
            default='',
            help=('the name of the library being tested; '
                  'defaults to current dir'),
        )
    )
    conf.register_cli_opt(
        cfg.BoolOpt(
            'update',
            short='u',
            default=False,
            help='update consumers before running tests',
        )
    )
    conf.register_cli_opt(
        cfg.StrOpt(
            'ref',
            short='r',
            default='HEAD',
            help='the commit reference to test; defaults to HEAD',
        )
    )
    conf.register_cli_opt(
        cfg.MultiStrOpt(
            'env',
            short='e',
            default=['py27', 'pep8'],
            help=('the name of the tox environment to test; '
                  'defaults to py27 and pep8'),
        )
    )
    conf.register_cli_opt(
        cfg.MultiStrOpt(
            'consumer',
            positional=True,
            default=[],
            help='the name of a project to test with; may be repeated',
        )
    )
    tconfig.parse_arguments(conf)

    repo_root = os.path.expanduser(conf.repo_root)

    # Figure out which library is being tested
    lib_name = conf.library_under_test
    if not lib_name:
        print('finding library name')
        lib_name = subprocess.check_output(
            ['python', 'setup.py', '--name']
        ).strip()
        lib_dir = os.getcwd()
    else:
        lib_dir = os.path.join(repo_root, 'openstack', lib_name)
    print('testing %s in %s' % (lib_name, lib_dir))

    projects = set(conf.consumer)
    if not projects:
        # TODO(dhellmann): Need to update this to look at gerrit, so
        # we can check out the projects we want to test with.
        print('defaulting to all projects under %s/openstack' % repo_root)
        projects = find_all_projects(repo_root)

    # Filter out projects that do not require the library under test
    before = len(projects)
    projects = list(find_consuming_projects(lib_name, repo_root, projects))
    after = len(projects)
    if after < before:
        print('ignoring %s projects that do not use %s'
              % (before - after, lib_name))

    projects = list(sorted(projects))
    if not projects:
        print('ERROR: found no projects using %s' % lib_name)
        return 1
    print('preparing to test %s projects' % after)

    # Make sure the lib being tested is set to the reference intended.
    if conf.ref != 'HEAD':
        print('ensuring %s is updated to %s' % (lib_name, conf.ref))
        subprocess.check_call(
            ['git', 'checkout', conf.ref],
            cwd=lib_dir,
        )

    failures = []
    for p in projects:
        print()
        proj_dir = os.path.join(repo_root, p)
        if conf.update:
            print('updating %s with "git pull"' % p)
            subprocess.Popen(
                ['git', 'pull'],
                cwd=proj_dir,
            ).communicate()
        p_log_name = p.split('/')[-1].replace('.', '-')
        for e in conf.env:
            log_name = 'cross-test-%s-%s.log' % (p_log_name, e)
            with open(log_name, 'w') as log_file:
                print('testing %s in %s, logging to %s' % (e, p, log_name),
                      end=' ')
                sys.stdout.flush()
                command = ['./tools/run_cross_tests.sh', proj_dir, e]
                log_file.write('running: %s\n' % ' '.join(command))
                log_file.flush()  # since Popen is going to use the fd directly
                cmd = subprocess.Popen(
                    command,
                    cwd=lib_dir,
                    stdout=log_file,
                    stderr=log_file
                )
                cmd.communicate()
                log_file.write('\nexit code: %s\n' % cmd.returncode)
                if cmd.returncode:
                    print('FAIL')
                    failures.append((p, e, cmd.returncode))
                else:
                    print('PASS')

    if failures:
        print('\nFAILED %d jobs' % len(failures))
        return 1
    print('\nPASSED all jobs')
    return 0


if __name__ == '__main__':
    sys.exit(main())
