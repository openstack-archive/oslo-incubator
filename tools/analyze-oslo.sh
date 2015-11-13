#!/bin/bash

# This requires gitinspector to be installed
# it can be gotten from:
#
# - https://pypi.python.org/pypi/gitinspector/0.3.2
# - https://github.com/ejwa/gitinspector

# Check out a new copy of a repository and set it up to be a useful
# local copy.
function clone_new {
    typeset repo="$1"
    typeset url="$2"
    echo
    echo "Cloning $repo"
    git clone $url $repo
    return 0
}

# Determine the current branch of a local repository.
function current_branch {
    (cd $1 && git rev-parse --abbrev-ref HEAD)
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

current_dir=`pwd`
base="git://git.openstack.org"
projects=$(ssh review.openstack.org -p 29418 gerrit ls-projects | grep -v 'attic' | grep "oslo")
projects="$projects openstack/taskflow openstack/tooz openstack/cliff openstack/debtcollector"
projects="$projects openstack/futurist openstack/stevedore openstack-dev/cookiecutter"
projects="$projects openstack/automaton"
mkdir -p "oslo_reports"

for repo in $projects; do
    get_one_repo "$repo" "$base/$repo"
    RC=$?
    if [ $RC -ne 0 ] ; then
        echo "Unable to obtain $repo"
    else
        echo
        echo "Producing inspector report for $repo"
        report_base=`basename $repo`
        (cd $repo && gitinspector -F htmlembedded -r -T > "${current_dir}/oslo_reports/${report_base}.html")
    fi
done
