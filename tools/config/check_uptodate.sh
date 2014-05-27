#!/usr/bin/env bash

PROJECT_NAME=${PROJECT_NAME:-oslo}
CFGFILE_NAME=${PROJECT_NAME}.conf.sample
ERROR_MSG_START="${0##*/}: ${PROJECT_NAME}.conf.sample is not up to date."
SCRIPT_PATH=${SCRIPT_PATH:-"${0%%${0##*/}}generate_sample.sh."}
ERROR_MSG=$ERROR_MSG_START"${0##*/}: Please run "$SCRIPT_PATH

if [ -e etc/${PROJECT_NAME}/${CFGFILE_NAME} ]; then
    CFGFILE=etc/${PROJECT_NAME}/${CFGFILE_NAME}
elif [ -e etc/${CFGFILE_NAME} ]; then
    CFGFILE=etc/${CFGFILE_NAME}
else
    echo "${0##*/}: can not find config file"
    exit 1
fi

TEMPDIR=`mktemp -d /tmp/${PROJECT_NAME}.XXXXXX`
trap "rm -rf $TEMPDIR" EXIT

tools/config/generate_sample.sh -b ./ -p ${PROJECT_NAME} -o ${TEMPDIR}

if ! diff -u ${TEMPDIR}/${CFGFILE_NAME} ${CFGFILE}
then
   echo $ERROR_MSG
   exit 1
fi
