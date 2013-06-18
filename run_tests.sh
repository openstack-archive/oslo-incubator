#!/bin/bash

# On Linux, testrepository will inspect /proc/cpuinfo to determine how many
# CPUs are present in the machine, and run one worker per CPU.
# Set workers_count=0 if you want to run one worker per CPU.
# workers_count=0

# there are no possibility to run some oslo tests with concurrency > 1
# or separately due to dependencies between tests (see bug 1192207)
workers_count=1
tests_dir="tests/" # directory with tests
egg_info_file="openstack.common.egg-info/entry_points.txt"

# Make our paths available to run_tests_common.sh 
export workers_count 
export tests_dir
export egg_info_file

# run common test script
tools/run_tests_common.sh $*
