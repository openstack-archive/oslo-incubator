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

COOKIECUTTER_TEMPLATE_REPO=https://git.openstack.org/openstack-dev/oslo-cookiecutter

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

# Set up a virtualenv with cookiecutter
echo "Installing cookiecutter..."
venv=$tmpdir/venv
virtualenv $venv
$venv/bin/python -m pip install cookiecutter
cookiecutter=$venv/bin/cookiecutter

# Build the grep pattern for ignoring files that we want to keep, so
# the prune script does not list them and cause them to be deleted.
keep_pattern="./\(.git\|$(echo $files_to_keep | sed -e 's/ /\\|/g')\)"

pruner="$tmpdir/pruner.sh"
cat >$pruner <<EOF
#!/bin/bash
find . -type f | grep -v "$keep_pattern"
EOF
chmod +x $pruner

# Filter out commits for unrelated files
echo "Pruning commits for unrelated files..."
git filter-branch --tree-filter 'git rm -f $('$pruner')' --prune-empty HEAD

# Find the earliest commit
earliest_commit=$(git log --format='format:%H' $files_to_keep | tail -1)
echo "Resetting git history to start with $earliest_commit"
git show --quiet $earliest_commit

count_commits

# Remove the parent of the earliest commit to make it the first one we
# will keep
echo "Resetting parent of $earliest_commit ..."
git filter-branch -f --parent-filter \
    "test \$GIT_COMMIT = $earliest_commit && echo '' || cat" HEAD

count_commits

# Fix up dates, since we have touched the commits
echo "Fixing committer dates..."
git rebase --committer-date-is-author-date $(git log --format='format:%H' | tail -1)

# Fix up committer, since we have touched the commits
echo "Fixing committer name..."
git filter-branch -f --commit-filter \
    'GIT_COMMITTER_NAME="$GIT_AUTHOR_NAME" GIT_COMMITTER_EMAIL="$GIT_AUTHOR_EMAIL" git commit-tree "$@"' HEAD

# Move things around
echo "Moving files into place..."
git mv openstack oslo
if [[ -d oslo/common/$new_lib ]]; then
    git mv oslo/common/$new_lib oslo/$new_lib
else
    git mv oslo/common oslo/$new_lib
fi

# Fix imports after moving files
echo "Fixing imports..."
if [[ -d oslo/$new_lib ]]; then
    find . -name '*.py' -exec sed -i "s/openstack.common.${new_lib}/oslo.${new_lib}/" {} \;
else
    find . -name '*.py' -exec sed -i "s/openstack.common/oslo.${new_lib}/" {} \;
fi

# Apply the cookiecutter template by building out a fresh copy using
# the name chosen for this library and then copying any parts of the
# results into the local tree, without overwriting files that already
# exist.
git clone $COOKIECUTTER_TEMPLATE_REPO $tmpdir/oslo-cookiecutter
# FIXME(dhellmann): We need a better non-interactive mode for cookiecutter
(cd $tmpdir && $cookiecutter $tmpdir/oslo-cookiecutter) <<EOF
$new_lib
openstack
oslo.${new_lib} library
EOF
rsync -a --verbose --ignore-existing $tmpdir/oslo.${new_lib}/ .

# Stage everything that we have changed so far, but do not commit
# because we don't know if it works.
git add .

echo "Now, you need to make the tests work and commit the results by hand."
