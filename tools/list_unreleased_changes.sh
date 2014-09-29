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

bindir=$(dirname $0)
repodir=$(cd $bindir/../../.. && pwd)

# Make sure no pager is configured so the output is not blocked
export PAGER=

libs=$($bindir/list_oslo_projects.py | egrep -v -e '(oslo.version|cookiecutter|incubator)')

# Assuming the tags were created in chronological order, get the most
# recent one. This will break if we ever go back and create a patch
# release.
function get_last_tag {
    git for-each-ref --sort=taggerdate --format '%(refname)' refs/tags \
        | tail -n 1 \
        | sed -e 's|refs/tags/||'
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
        range="${prev_tag}..HEAD"
        echo "$lib  $range"
        echo
        git log --oneline --no-merges $range
    fi
done
