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
# Check out every active repository from git.openstack.org. For new
# copies, set up git-review. For any existing copies, update their
# remotes and pull changes up to the local master.
#
# This script is based on prior art from mordred on the openstack-dev
# mailing list.
# http://lists.openstack.org/pipermail/openstack-dev/2013-October/017532.html
#
# Usage:
#
#  Check out everything under the current directory:
#    $ clone_openstack.sh
#
#  Check out a specific project (you can list multiple names):
#    $ clone_openstack.sh openstack/oslo-incubator
#

trouble_with=""
branched=""

# Figure out if git-hooks is installed and should be used.
# https://github.com/icefox/git-hooks
which git-hooks 2>&1 > /dev/null
USE_GIT_HOOKS=$?

# Users can set INCLUDE_STACKFORGE=1 if they want to always check out
# new copies of stackforge projects.
INCLUDE_STACKFORGE=${INCLUDE_STACKFORGE:-0}

# If we have any trouble at all working with a repository, report that
# and then record the name for the summary at the end.
function track_trouble {
    if [ $1 -ne 0 ]
    then
        echo "Remembering trouble with $2"
        trouble_with="$trouble_with $2"
    fi
}

# Determine the current branch of a local repository.
function current_branch {
    (cd $1 && git rev-parse --abbrev-ref HEAD)
}

# Print a summary report for any repositories that had trouble
# updating.
function report_trouble {
    if [ ! -z "$trouble_with" ]
    then
        echo
        echo "Had trouble updating:"
        for r in $trouble_with
        do
            echo "  $r - $(current_branch $r)"
        done
    fi
}

# Print a summary report for any repositories that were not on the
# master branch when we updated them.
function report_branched {
    if [ ! -z "$branched" ]
    then
        echo
        echo "Branched repos:"
        for r in $branched
        do
            echo "  $r - $(current_branch $r)"
        done
    fi
}

# Check out a new copy of a repository and set it up to be a useful
# local copy.
function clone_new {
    typeset repo="$1"
    typeset url="$2"
    # Ignore stackforge projects unless told otherwise.
    if [[ $repo =~ ^stackforge/.* ]]
    then
        if [ $INCLUDE_STACKFORGE -ne 1 ]
        then
            return 0
        fi
    fi
    echo
    echo "Cloning $repo"
    git clone $url $repo
    (cd $repo && git review -s)
    if [ $USE_GIT_HOOKS -eq 0 ]
    then
        echo "Configuring git hooks"
        (cd $repo && git hooks --install)
    fi
    return 0
}

# Update an existing copy of a repository, including all remotes and
# pulling into the local master branch if we're on that branch
# already.
function update_existing {
    typeset repo="$1"
    echo
    echo "Updating $repo"
    (cd $repo && git remote update)
    RC=$?
    if [ $RC -ne 0 ]
    then
        return $RC
    fi
    # Only run git pull for repos where I'm not working in a branch.
    typeset b=$(current_branch $repo)
    if [ $b == "master" ]
    then
        if (cd $repo && git diff --exit-code >/dev/null)
        then
            (cd $repo && git pull)
        else
            echo "Skipping pull for master branch with local changes"
            (cd $repo && git status)
        fi
    else
        echo "Skipping pull for branch $b"
        branched="$branched $repo"
    fi
}

# Process a single repository found in gerrit, determining whether it
# exists locally already or not.
function get_one_repo {
    typeset repo="$1"
    typeset url="$2"
    typeset pardir=$(dirname $repo)
    if [ ! -z "$pardir" ]
    then
        mkdir -p $pardir
    fi
    if [ ! -d $repo ] ; then
        clone_new $repo $url
    else
        update_existing $repo
    fi
    RC=$?
    return $RC
}

# If we are given a list of projects on the command line, we will only
# work on those. Otherwise, ask gerrit for the full list of openstack
# projects, ignoring the ones in the attic. Stackforge projects are
# ignored if they do not exist locally, so we include them in the
# output list and check for them when we decide what to do with each
# repository.
projects="$*"
if [ -z "$projects" ]
then
    projects=$(ssh review.openstack.org gerrit ls-projects | grep -v 'attic')
else
    # Go ahead and set things up so we will work with stackforge
    # repositories, in case the caller has specified one on the
    # command line.
    INCLUDE_STACKFORGE=1
fi

for repo in $projects; do
    get_one_repo $repo git://git.openstack.org/$repo
    track_trouble $? $repo
done

report_branched
report_trouble
