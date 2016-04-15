from __future__ import unicode_literals

import contextlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

from datetime import datetime

import six
import yaml

from prompt_toolkit.contrib.completers import WordCompleter
from prompt_toolkit import prompt
from prompt_toolkit.validation import ValidationError
from prompt_toolkit.validation import Validator

from tqdm import tqdm

OS_PREFIX = 'openstack/'
GIT_BASE = 'https://git.openstack.org/'
RELEASE_REPO = GIT_BASE + "openstack/releases"
NOTES_URL_TPL = 'http://docs.openstack.org/releasenotes/%s/%s.html'
ANNOUNCE_EMAIL = 'openstack-dev@lists.openstack.org'


class NoEmptyValidator(Validator):
    def validate(self, document):
        text = document.text.strip()
        if len(text) == 0:
            raise ValidationError(message='Empty input is not allowed')


class SetValidator(Validator):
    def __init__(self, allowed_values, show_possible=False):
        super(SetValidator, self).__init__()
        self.allowed_values = frozenset(allowed_values)
        self.show_possible = show_possible

    def validate(self, document):
        text = document.text
        if text not in self.allowed_values:
            if self.show_possible:
                raise ValidationError(
                    message='This input is not allowed, '
                            ' please choose from %s' % self.allowed_values)
            else:
                raise ValidationError(
                    message='This input is not allowed')


def clone_a_repo(repo_url, repo_base_path, repo_name):
    repo_path = os.path.join(repo_base_path, repo_name)
    if not os.path.isdir(repo_path):
        cmd = ['git', 'clone', repo_url, repo_name]
        subprocess.check_output(cmd, cwd=repo_base_path,
                                stderr=subprocess.STDOUT)
    return repo_path


@contextlib.contextmanager
def tempdir(**kwargs):
    # This seems like it was only added in python 3.2
    # Make it since its useful...
    # See: http://bugs.python.org/file12970/tempdir.patch
    tdir = tempfile.mkdtemp(**kwargs)
    try:
        yield tdir
    finally:
        shutil.rmtree(tdir)


def filter_changes(changes):
    for line in changes:
        if isinstance(line, six.binary_type):
            line = line.decode("utf8")
        pieces = line.split(" ", 1)
        _sha, descr = pieces
        if descr.startswith("Merge"):
            continue
        else:
            yield line


def maybe_create_release(release_repo_path,
                         last_release, change_lines,
                         latest_cycle, project,
                         short_project, max_changes_show=100):
    if last_release:
        print("%s changes to"
              " release since %s are:"
              % (len(change_lines), last_release['version']))
    else:
        print("%s changes to release are:" % (len(change_lines)))
    for change_line in change_lines[0:max_changes_show]:
        print("  " + change_line)
    leftover_change_lines = change_lines[max_changes_show:]
    if leftover_change_lines:
        print("   and %s more changes..." % len(leftover_change_lines))
    response = prompt(
        'Create a release in %s containing those changes? ' % latest_cycle,
        completer=WordCompleter(['yes', 'no']),
        validator=SetValidator(['yes', 'no'], show_possible=True))
    if response == 'yes':
        newest_release_path = os.path.join(
            release_repo_path, 'deliverables',
            latest_cycle, "%s.yaml" % short_project)
        if os.path.exists(newest_release_path):
            with open(newest_release_path, "rb") as fh:
                newest_release = yaml.safe_load(fh.read())
        else:
            newest_release = {
                'release-notes': NOTES_URL_TPL % (short_project,
                                                  latest_cycle),
                'send-announcements-to': ANNOUNCE_EMAIL,
                'launchpad': short_project,
                'releases': [],
                'include-pypi-link': True,
            }
        possible_hashes = []
        for change_line in change_lines:
            sha, _desc = change_line.split(" ", 1)
            possible_hashes.append(sha)
        version = prompt("Release version: ", validator=NoEmptyValidator())
        highlights = prompt("Highlights: ", multiline=True)
        release_hash = prompt("Hash to release at: ",
                              validator=SetValidator(possible_hashes),
                              completer=WordCompleter(possible_hashes))
        existing_releases = newest_release['releases']
        existing_releases.append({
            'highlights': highlights.strip(),
            'version': version,
            'projects': [{
                'repo': project,
                'hash': release_hash,
            }],
        })
        with open(newest_release_path, 'wb') as fh:
            fh.write(prettify_yaml(newest_release))
            fh.write("# Created by %s\n" % os.path.basename(sys.argv[0]))
            fh.write("# Generated/updated"
                     " on %s\n" % datetime.isoformat(datetime.now()))


def find_last_release_path(release_repo_path,
                           latest_cycle, cycles,
                           project):
    latest_cycle_idx = cycles.index(latest_cycle)
    for a_cycle in reversed(cycles[0:latest_cycle_idx + 1]):
        release_path = os.path.join(release_repo_path, 'deliverables',
                                    a_cycle, "%s.yaml" % project)
        if os.path.isfile(release_path):
            return a_cycle, release_path
    return (None, None)


def prettify_yaml(obj):
    formatted = yaml.safe_dump(obj,
                               line_break="\n",
                               indent=4,
                               explicit_start=True,
                               default_flow_style=False)
    return formatted


def clone_repos(save_dir, project_names):
    repos = {}
    pbar = tqdm(project_names)
    for project, short_project in pbar:
        pbar.set_description(short_project)
        repo_url = GIT_BASE + project
        repos[project] = clone_a_repo(repo_url, save_dir, short_project)
    return repos


def get_projects_names(projects):
    project_names = []
    for project in sorted(projects):
        if project.startswith(OS_PREFIX):
            short_project = project[len(OS_PREFIX):]
        else:
            short_project = project
        project_names.append((project, short_project))
    return project_names


def main():
    if len(sys.argv) < 3:
        base_program = os.path.basename(sys.argv[0])
        print("%s <project-file> <release-repo-dir>" % base_program)
        return
    project_file = sys.argv[1]
    release_repo_path = sys.argv[2]
    cycles = os.listdir(os.path.join(release_repo_path, 'deliverables'))
    cycles = sorted([c for c in cycles if not c.startswith("_")])
    latest_cycle = cycles[-1]
    try:
        with open(project_file) as fh:
            if project_file.endswith(".json"):
                projects = json.loads(fh.read())
            else:
                projects = []
                for line in fh.read().splitlines():
                    line = line.strip()
                    if line.startswith("#"):
                        continue
                    else:
                        projects.append(line)
    except IOError as e:
        print("Please ensure '%s' file exists"
              " and is readable: %s" % (project_file, e))
    else:
        project_names = get_projects_names(projects)
        with tempdir() as tdir:
            print("Cloning %s repos:" % len(project_names))
            repos = clone_repos(tdir, project_names)
            for project, short_project in project_names:
                repo_path = repos[project]
                last_release_cycle, last_release_path = find_last_release_path(
                    release_repo_path, latest_cycle, cycles, short_project)
                if last_release_path is None or last_release_cycle is None:
                    last_release = None
                else:
                    with open(last_release_path, 'rb') as fh:
                        project_releases = yaml.safe_load(fh.read())
                        last_release = project_releases['releases'][-1]
                print("== Analysis of project '%s' ==" % short_project)
                if not last_release:
                    print("It has never had a release.")
                    cmd = ['git', 'log', '--pretty=oneline']
                    output = subprocess.check_output(cmd, cwd=repo_path)
                    output = output.strip()
                    changes = list(filter_changes(output.splitlines()))
                else:
                    print("The last release of project %s"
                          " was:" % short_project)
                    print("  Released in: %s" % last_release_cycle)
                    print("  Version: %s" % last_release['version'])
                    print("  At sha: %s" % last_release['projects'][0]['hash'])
                    cmd = ['git', 'log', '--pretty=oneline',
                           "%s..HEAD" % last_release['projects'][0]['hash']]
                    output = subprocess.check_output(cmd, cwd=repo_path)
                    output = output.strip()
                    changes = list(filter_changes(output.splitlines()))
                if changes:
                    maybe_create_release(release_repo_path,
                                         last_release, changes,
                                         latest_cycle, project,
                                         short_project)
                else:
                    print("  No changes.")

if __name__ == '__main__':
    main()
