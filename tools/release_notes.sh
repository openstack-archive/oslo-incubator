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
# Generate a standard set of release notes for a repository.

bindir=$(cd $(dirname $0) && pwd)
repodir=$(cd $bindir/../../.. && pwd)

if [ $# -ne 3 ]
then
    echo "Usage: $0 <lib> <start_rev> <end_rev>"
    echo "  lib       -- library directory, for example 'openstack/cliff'"
    echo "  start_rev -- start revision, for example '1.8.0'"
    echo "  end_rev   -- end revision, for example '1.9.0'"
    exit 1
fi

set -e

lib=$1
start_rev=$2
end_rev=$3

range="${start_rev}..${end_rev}"

cd $repodir/$lib

project=$(basename $lib)
bug_url=$(grep "Bugs" README.rst | cut -f2- -d: | sed -e 's/ //')
lp_url=$(echo "$bug_url" | sed -e 's/bugs.//')
milestone_url="${lp_url}/+milestone/${end_rev}"

cat <<EOF
The Oslo team is pleased to announce the release of
${project} ${end_rev}: $(python setup.py --description)



For more details, please see the git log history below and
 $milestone_url

Please report issues through launchpad:
 $bug_url

----------------------------------------

Changes in $lib  $range

EOF

git log --no-color --oneline --no-merges $range

echo
echo "  diffstat (except docs and test files):"
echo
git diff --stat --no-color $range | egrep -v '(/tests/|^ doc)'

echo
echo "  Requirements updates:"
echo
git diff -U0 --no-color $range *requirements*.txt | sed -e 's/^/ /g'

echo
