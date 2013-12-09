#!/usr/bin/env bash

TEMPDIR=`mktemp -d`
CFGFILE=${PROJECT_NAME}.conf.sample

tools/config/generate_sample.sh -b ./ -p ${PROJECT_NAME} -o ${TEMPDIR}

if ! diff ${TEMPDIR}/${CFGFILE} etc/${PROJECT_NAME}/${CFGFILE}
then
   echo "E: ${PROJECT_NAME}.conf.sample is not up to date, please run tools/config/generate_sample.sh"
   exit 42
fi
