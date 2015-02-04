#!/bin/bash
#
# Apply the Oslo cookiecutter template to an existing directory,
# usually as part of the graduation process.

COOKIECUTTER_TEMPLATE_REPO=${COOKIECUTTER_TEMPLATE_REPO:-https://git.openstack.org/openstack-dev/oslo-cookiecutter}

function usage {
    echo "Usage: apply_cookiecutter.sh newlib" 1>&2
}

if [ $# -lt 1 ]
then
    usage
    exit 1
fi

new_lib="$1"

if [[ $new_lib =~ oslo.* ]]
then
    echo "You probably don't want 'oslo' in the lib name." 1>&2
    exit 2
fi

# Set up a virtualenv with cookiecutter
tmpdir=$(mktemp -d -t oslo-cookiecutter.XXXX)
echo "Installing cookiecutter..."
venv=$tmpdir/venv
virtualenv $venv
$venv/bin/python -m pip install cookiecutter
cookiecutter=$venv/bin/cookiecutter

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
