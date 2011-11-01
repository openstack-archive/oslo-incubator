#!/bin/bash
TOOLS=`dirname $0`
VENV=$TOOLS/../.openstack-common-venv
source $VENV/bin/activate && $@
