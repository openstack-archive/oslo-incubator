#!/bin/bash
#
# Use this script to prune a copy of oslo-incubator when graduating
# modules to a brand new library.
#
# To use:
#
#  1. Clone a copy of the oslo-incubator repository to be manipulated.
#  2. Choose the new library name. For "oslo.foo", the argument to the
#     script is "foo".
#  3. cd into the copy of oslo-incubator to be changed.
#  4. Run graduate.sh, passing the library name and the names of all
#     directories and files to be saved (only code and tests, no project
#     configuration):
#
#       ../oslo-incubator/tools/graduate.sh foo openstack/common/foo.py tests/unit/test_foo.py ...
#
#   5. Clean up the results a bit by hand to make the tests work
#      (update dependencies, etc.).
#

# Stop if there are any command failures
set -e

bindir=$(dirname $0)
tmpdir=$(mktemp -d -t oslo-graduate.XXXX)
mkdir -p $tmpdir
logfile=$tmpdir/output.log
echo "Logging to $logfile"

# Redirect stdout/stderr to tee to write the log file
# (borrowed from verbose mode handling in devstack)
exec 1> >( awk '
                {
                    cmd ="date +\"%Y-%m-%d %H:%M:%S \""
                    cmd | getline now
                    close("date +\"%Y-%m-%d %H:%M:%S \"")
                    sub(/^/, now)
                    print
                    fflush()
                }' | tee "$logfile" ) 2>&1

function count_commits {
    echo
    echo "Have $(git log --oneline | wc -l) commits"
}

set -x

# Handle arguments
new_lib="$1"
shift
files_to_keep="$@"

# FIXME(dhellmann): Make sure they are not running the tool in the
# same copy of the repository where it lives.

# Filter the repository history down
${bindir}/filter_git_history.sh $files_to_keep

# Move things around
echo "Moving files into place..."
if [[ -d openstack/common/$new_lib ]]; then
    git mv openstack/common/$new_lib oslo_${new_lib}
else
    git mv openstack/common oslo_${new_lib}
fi
rmdir openstack
if [[ -d tests ]]; then
    git mv tests/* oslo_${new_lib}/tests/
    rmdir tests
fi

# Fix imports after moving files
echo "Fixing imports..."
if [[ -d oslo_${new_lib} ]]; then
    find . -name '*.py' -exec sed -i "s/openstack.common.${new_lib}/oslo_${new_lib}/" {} \;
else
    find . -name '*.py' -exec sed -i "s/openstack.common/oslo_${new_lib}/" {} \;
fi

# Bring in any missing files based on the cookiecutter template
$bindir/apply_cookiecutter.sh $new_lib

# Commit the work we have done so far. Changes to make
# it work will be applied on top.
git add .
git commit -m "exported from oslo-incubator by graduate.sh"

echo "The scratch files and logs from the export are in: $tmpdir"
echo "The next step is to make the tests work."
