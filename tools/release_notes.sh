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
#
# Usage: release_notes.sh <repo_name> starttag endrev
#
# Example: release_notes.sh ../openstack/oslo.config 1.4.0 HEAD

bindir=$(cd $(dirname $0) && pwd)
repodir=$(cd $bindir/../../.. && pwd)

lib=$1
start_rev=$2
end_rev=$3

range="${start_rev}..${end_rev}"

cd $repodir/$lib

echo "$lib  $range"
echo
git log --no-color --oneline --no-merges $range
echo
echo "  diffstat (except docs and test files):"
echo
git diff --stat --no-color $range | egrep -v '(/tests/|^ doc)'
echo
echo "  Requirements updates:"
echo
git diff -U0 --no-color $range *requirements*.txt | sed -e 's/^/ /g'
