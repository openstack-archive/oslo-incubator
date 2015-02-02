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
# Show the latest tags for all Oslo projects as an approximation for
# reporting on which releases exist.

bindir=$(cd $(dirname $0) && pwd)
repodir=$(cd $bindir/../../.. && pwd)

# Make sure no pager is configured so the output is not blocked
export PAGER=

if [ -z "$*" ]
then
    libs=$($bindir/list_oslo_projects.py | egrep -v -e '(oslo.version|cookiecutter|incubator)')
else
    libs="$*"
fi

# Assuming the tags were created in chronological order, get the most
# recent one. This will break if we ever go back and create a patch
# release.
function get_last_tag {
    git for-each-ref --sort=taggerdate --format '%(refname)' refs/tags \
        | sed -e 's|refs/tags/||' \
        | ${bindir}/highest_semver.py
}

function list_versions {
    # Show the tag for each library
    for lib in $*
    do
        the_date=""
        cd $repodir/$lib
        highest_tag=$(get_last_tag)
        if [ -z "$highest_tag" ]
        then
            the_date="9999-99-99 99:99:99 +9999"
            highest_tag="UNRELEASED"
        else
            the_date=$(git log -q --format='format:%ci' -n 1 $highest_tag)
        fi
        echo $the_date $lib $highest_tag
    done
}

list_versions $libs | sort -n
