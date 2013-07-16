#!/usr/bin/env bash

print_hint() {
    echo "Try \`${0##*/} --help' for more information." >&2
}

USEVENV=false

PARSED_OPTIONS=$(getopt -n "${0##*/}" -o hVb:p:o: \
        --long help,virtual-env,base-dir:,package-name:,output-dir: -- "$@")

if [ $? != 0 ] ; then print_hint ; exit 1 ; fi

eval set -- "$PARSED_OPTIONS"

while true; do
    case "$1" in
        -h|--help)
            echo "${0##*/} [options]"
            echo ""
            echo "options:"
            echo "-h, --help                show brief help"
            echo "-V, --virtual-env         create virtual environment"
            echo "-b, --base-dir=DIR        project base directory (required)"
            echo "-p, --package-name=NAME   project package name"
            echo "-o, --output-dir=DIR      file output directory"
            exit 0
            ;;
        -V|--virtual-env)
            shift
            USEVENV=true
            ;;
        -b|--base-dir)
            shift
            BASEDIR=`echo $1 | sed -e 's/\/*$//g'`
            shift
            ;;
        -p|--package-name)
            shift
            PACKAGENAME=`echo $1`
            shift
            ;;
        -o|--output-dir)
            shift
            OUTPUTDIR=`echo $1 | sed -e 's/\/*$//g'`
            shift
            ;;
        --)
            break
            ;;
    esac
done

if [ -z $BASEDIR ] || ! [ -d $BASEDIR ]
then
    echo "${0##*/}: missing project base directory" >&2 ; print_hint ; exit 1
fi

PACKAGENAME=${PACKAGENAME:-${BASEDIR##*/}}

OUTPUTDIR=${OUTPUTDIR:-$BASEDIR/etc}
if ! [ -d $OUTPUTDIR ]
then
    echo "${0##*/}: cannot access \`$OUTPUTDIR': No such file or directory" >&2
    exit 1
fi

OSLOBASEDIR=$(dirname "$0")/../..

if $USEVENV
then
    VENV=$OSLOBASEDIR/.update-venv
    [ -d $VENV ] || virtualenv -qq --no-site-packages $VENV
    . $VENV/bin/activate
    pip install -q -r $BASEDIR/requirements.txt
fi

BASEDIRESC=`echo $BASEDIR | sed -e 's/\//\\\\\//g'`
FILES=$(find $BASEDIR/$PACKAGENAME -type f -name "*.py" ! -path "*/tests/*" \
        -exec grep -l "Opt(" {} + | sed -e "s/^$BASEDIRESC\///g" | sort -u)

export EVENTLET_NO_GREENDNS=yes

MODULEPATH=$OSLOBASEDIR/openstack/common/config/generator.py
OUTPUTFILE=$OUTPUTDIR/$PACKAGENAME.conf.sample
PYTHONPATH=$OSLOBASEDIR/:$BASEDIR/:$PYTHONPATH python $MODULEPATH $FILES > $OUTPUTFILE
