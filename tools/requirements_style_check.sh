#!/bin/bash
#
# Enforce the requirement that dependencies are listed in the input
# files in alphabetical order.

# FIXME(dhellmann): This doesn't deal with URL requirements very
# well. We should probably sort those on the egg-name, rather than the
# full line.

function check_file() {
    typeset f=$1

    # We don't care about comment lines.
    grep -v '^#' $f > ${f}.unsorted
    sort -i -f ${f}.unsorted > ${f}.sorted
    diff -c ${f}.unsorted ${f}.sorted
    rc=$?
    rm -f ${f}.sorted ${f}.unsorted
    return $rc
}

exit_code=0
for filename in $@
do
    part_num=`awk 'BEGIN{num=0;FS="\n";RS=""}{num++}{print > "file_"num}END{print num}' $filename`
    index=1
    while [ $index -le $part_num ]
    do
        part_filename="file_"$index
        check_file $part_filename
        if [ $? -ne 0 ]
        then
            echo "Please list requirements in part $index of file $filename in alphabetical order" 1>&2
            exit_code=1
        fi
        index=$(($index+1))
        rm -f $part_filename
    done
done
exit $exit_code
