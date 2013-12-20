#!/bin/bash

VENV=.update-venv

# -qq gets rid of the deprecation warning, in time we can
# remove --no-site-packages as it's the default now
[ -d $VENV ] || virtualenv -qq --no-site-packages $VENV

. $VENV/bin/activate

# need oslo.config for bootstrapping, be quiet for UX reasons
pip -q install olso.config

python update.py $*
