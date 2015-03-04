#!/bin/bash
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
#
# Provide a list of the unreleased changes in the oslo libraries.

bindir=$(cd $(dirname $0) && pwd)
repodir=$(cd $bindir/../../.. && pwd)
release_tools=$repodir/openstack-infra/release-tools

# Make sure no pager is configured so the output is not blocked
export PAGER=

if [ -z "$*" ]
then
    libs=$($bindir/list_oslo_projects.py | egrep -v -e '(oslo.version|cookiecutter|incubator)')
else
    libs="$*"
fi

function get_last_tag {
    git for-each-ref --sort=taggerdate --format '%(refname)' refs/tags \
        | sed -e 's|refs/tags/||' \
        | ${bindir}/highest_semver.py
}

# Show the unreleased changes for each library.
for lib in $libs
do
    echo
    cd $repodir/$lib
    prev_tag=$(get_last_tag)
    if [ -z "$prev_tag" ]
    then
        echo "$lib has not yet been released"
    else
        $release_tools/release_notes.py --changes-only $repodir/$lib $prev_tag origin/master
    fi
done
