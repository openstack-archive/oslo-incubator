#!/bin/bash
#
# Process the dashboard files and emit the URLs

creator_dir=$1
dashboard_dir=$2

cd $creator_dir

for f in $dashboard_dir/*.dash
do
    echo '----------------------------------------'
    echo $(basename $f .dash)
    echo '----------------------------------------'
    ./gerrit-dash-creator $f
done
