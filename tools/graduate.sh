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

# Build the grep pattern for ignoring files that we want to keep
keep_pattern="\($(echo $files_to_keep | sed -e 's/ /\\|/g')\)"
# Prune all other files in every commit
pruner="git ls-files | grep -v \"$keep_pattern\" | git update-index --force-remove --stdin; git ls-files > /dev/stderr"

# Find all first commits with listed files and find a subset of them that
# predates all others

roots=""
for file in $files_to_keep; do
    file_root="$(git rev-list --reverse HEAD -- $file | head -n1)"
    fail=0
    for root in $roots; do
        if git merge-base --is-ancestor $root $file_root; then
            fail=1
            break
        elif !git merge-base --is-ancestor $file_root $root; then
            new_roots="$new_roots $root"
        fi
    done
    if [ $fail -ne 1 ]; then
        roots="$new_roots $file_root"
    fi
done

# Purge all parents for those commits

set_roots="
if [ '' $(for root in $roots; do echo " -o \"\$GIT_COMMIT\" == '$root' "; done) ]; then
    echo ''
else
    cat
fi"

# Enhance git_commit_non_empty_tree to skip merges with:
# a) either two equal parents (commit that was about to land got purged as well
# as all commits on mainline);
# b) or with second parent being an ancestor to the first one (just as with a)
# but when there are some commits on mainline).
# In both cases drop second parent and let git_commit_non_empty_tree to decide
# if commit worth doing (most likely not).

skip_empty=$(cat << \EOF
if [ $# = 5 ] && git merge-base --is-ancestor $5 $3; then
    git_commit_non_empty_tree $1 -p $3
else
    git_commit_non_empty_tree "$@"
fi
EOF
)

# Filter out commits for unrelated files
echo "Pruning commits for unrelated files..."
git filter-branch --index-filter "$pruner" --parent-filter "$set_roots" --commit-filter "$skip_empty" HEAD

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

# Commit the work we have done so far. Changes to make
# it work will be applied on top.
git add .
git commit -m "exported from oslo-incubator by graduate.sh"

echo "The scratch files and logs from the export are in: $tmpdir"
echo "The next step is to make the tests work."
