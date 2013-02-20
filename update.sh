#!/bin/bash

# Make some coffee and read https://code.launchpad.net/bugs/951197

VENV=.update-venv

[ -d $VENV ] || virtualenv -q --no-site-packages $VENV

. $VENV/bin/activate

python setup.py install

python update.py $*
