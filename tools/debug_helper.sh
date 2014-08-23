#!/bin/bash

# To utilize this file, add the following to tox.ini:
#[testenv:debug]
#commands = {toxinidir}/tools/debug_helper.sh {posargs}

# To run with tox:
#tox -e debug
#tox -e debug test_notifications
#tox -e debug test_notifications.NotificationsTestCase
#tox -e debug test_notifications.NotificationsTestCase.test_send_notification

TMP_DIR=`mktemp -d` || exit 1
trap "rm -rf $TMP_DIR" EXIT

ALL_TESTS=$TMP_DIR/all_tests
TESTS_TO_RUN=$TMP_DIR/tests_to_run

PACKAGENAME=$(python setup.py --name)

python -m testtools.run discover -t ./ ./$PACKAGENAME/tests --list > $ALL_TESTS

if [ "$1" ]; then
    grep "$1" < $ALL_TESTS > $TESTS_TO_RUN
else
    mv $ALL_TESTS $TESTS_TO_RUN
fi

STANDARD_THREADS=1 python -m testtools.run discover --load-list $TESTS_TO_RUN
