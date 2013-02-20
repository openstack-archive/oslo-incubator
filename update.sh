#!/bin/bash

VENV=.update-venv

# -qq gets rid of the deprecation warning, in time we can
# remove --no-site-packages as it's the default now
[ -d $VENV ] || virtualenv -qq --no-site-packages $VENV

. $VENV/bin/activate

# need oslo-config for bootstrapping, be quite for UX reasons
pip -q install http://tarballs.openstack.org/oslo-config/oslo-config-2013.1b4.tar.gz

python update.py $*
