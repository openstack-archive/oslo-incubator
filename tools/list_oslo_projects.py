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

import functools
import getpass
import json
import urllib

import requests
from requests.auth import HTTPDigestAuth

import six
from tqdm import tqdm


# Avoid even bother scanning all these projects,
# because we know that oslo doesn't currently own these
# projects.
AUTO_EXCLUDE_PROJECTS = [
    'ansible',
    'barbican',
    'ceilometer',
    'charm',
    'cinder',
    'cookbook-',
    'designate',
    'devstack',
    'fuel',
    'glance',
    'heat',
    'horizon',
    'ironic',
    'keystone',
    'kolla',
    'magnum',
    'manila',
    'mistral',
    'monasca',
    'murano',
    'networking',
    'neutron',
    'openstack-ansible',
    'osops',
    'puppet',
    'python-',
    'sahara',
    'solum',
    'stacktach',
    'swift',
    'tripleo',
    'trove',
    'tuskar',
    'watcher',
    'xstatic',
]
AUTO_EXCLUDE_PREFIXES = [
    'openstack-attic/',
    'openstack-dev/',
    'openstack-infra/',
    'openstack/ironic',
    'openstack/keystone',
    'openstack/neutron',
    'openstack/nova',
    'stackforge-attic/',
    'stackforge/',
]
AUTO_EXCLUDE_PREFIXES.extend([
    "openstack/%s" % project for project in AUTO_EXCLUDE_PROJECTS
])
AUTO_EXCLUDE_PREFIXES.extend([
    "stackforge/%s" % project for project in AUTO_EXCLUDE_PROJECTS
])

GERRIT_URL = u'https://review.openstack.org'
GERRIT_PROJECT_URL = GERRIT_URL + u"/a/projects/"
GERRIT_ACCESS_URL = GERRIT_URL + u"/a/access/"
GERRIT_GROUP_API = GERRIT_URL + u"/a/groups/"

JSON_HEADER = u")]}'"
JSON_HEADER_LEN = len(JSON_HEADER)
ACTIVE_STATE = u'ACTIVE'


def get_gerrit_response(url, user, password):
    """Correctly gets a authed gerrit url and decodes the response."""
    r = requests.get(url, auth=HTTPDigestAuth(user, password))
    r.raise_for_status()
    response = r.text
    if response.startswith(JSON_HEADER):
        response = response[JSON_HEADER_LEN:]
    return json.loads(response)


class ProjectLister(object):
    """Scans gerrit for projects managed by a given group."""

    def __init__(self, user, password):
        self._all_groups = None
        self._all_projects = None
        self._expanded_groups = {}
        self._get_gerrit_response = functools.partial(
            get_gerrit_response, user=user, password=password)

    def _expand_group(self, group_id):
        matched_group_name = None
        matched_group_details = {}
        for group_name, group_details in six.iteritems(self._all_groups):
            if group_details['id'] == group_id:
                matched_group_name = group_name
                matched_group_details = group_details
                break
        if not matched_group_name or not matched_group_details:
            return []
        try:
            return self._expanded_groups[matched_group_name]
        except KeyError:
            full_groups = set([group_id])
            members_url = GERRIT_GROUP_API + group_id + "/groups/"
            included_groups = self._get_gerrit_response(members_url)
            for group_details in included_groups:
                full_groups.add(group_details['id'])
            self._expanded_groups[matched_group_name] = full_groups
            return full_groups

    def _matches_group(self, project_access, desired_group_id):
        for kind, kind_details in six.iteritems(project_access['local']):
            try:
                perms = kind_details["permissions"]
            except KeyError:
                perms = {}
            for entry_kind, entry in six.iteritems(perms):
                for group_id in entry['rules']:
                    if desired_group_id in self._expand_group(group_id):
                        return True
        return False

    def list_projects(self, group):
        if self._all_groups is None:
            self._all_groups = self._get_gerrit_response(GERRIT_GROUP_API)
        target_group = self._all_groups[group]
        if self._all_projects is None:
            self._all_projects = self._get_gerrit_response(GERRIT_PROJECT_URL)
        groups_projects = {}
        project_names = sorted(six.iterkeys(self._all_projects))
        pbar = tqdm(project_names)
        for project in pbar:
            pbar.set_description("Checking if %s is an '%s' managed"
                                 " project" % (project, group))
            should_skip = False
            for disallowed_prefix in AUTO_EXCLUDE_PREFIXES:
                if project.startswith(disallowed_prefix):
                    should_skip = True
                    break
            if should_skip:
                continue
            project_query = "?project=%s" % urllib.quote(project, safe="")
            project_access = self._get_gerrit_response(
                GERRIT_ACCESS_URL + project_query)
            project_access = project_access[project]
            if self._matches_group(project_access, target_group['id']):
                project_url = GERRIT_PROJECT_URL + urllib.quote(project,
                                                                safe="")
                project_details = self._get_gerrit_response(project_url)
                if project_details['state'] == ACTIVE_STATE:
                    groups_projects[project] = project_details
        return groups_projects


def get_input(prompt, secret=False, default=None):
    """Prompts the user for some input."""
    if default is not None:
        prompt = prompt + " [%s]: " % default
    else:
        prompt += ": "
    result = ''
    while len(result) == 0:
        if secret:
            result = getpass.getpass(prompt)
        else:
            result = raw_input(prompt)
        if len(result) == 0 and default is not None:
            result = default
    return result


def main():
    pw = get_input("Please enter your gerrit HTTP password", secret=True)
    user = get_input("Please enter your gerrit username",
                     default=getpass.getuser())
    lister = ProjectLister(user, pw)
    projects = lister.list_projects('oslo-core')
    with open("oslo.json", "wb") as fh:
        fh.write(json.dumps(projects,
                            sort_keys=True, indent=4))
        fh.write("\n")
    print("Projects written to 'oslo.json'")


if __name__ == '__main__':
    main()
