#!/bin/bash

set -e
set -u

FILE=$1
PAGE=$2
outfile=`tempfile`

# Overwritten in specific config
ANCODE_LINE=11
ANCODE_COL=55
NAME_COL=90
NAME_LINE=9
# the same as above
ALTERNATE_NAME_LINE=9

SPECIFIC_CONFIG="$HOME/payroll_rc"

if [ -f ${SPECIFIC_CONFIG} ]
    then
    . ${SPECIFIC_CONFIG}
fi

pdftotext -q -layout -f $PAGE -l $PAGE "${FILE}" $outfile

ANCODE=`awk "NR==${ANCODE_LINE} {print;}" $outfile |cut -c ${ANCODE_COL}- |sed -e 's/^ \+//' -e 's/ .*//'`
echo "ANCODE $ANCODE"

function getname() {
    _NAME_LINE=${1}
    NAME=`awk "NR==${_NAME_LINE} {print;}" $outfile | cut -c ${NAME_COL}- |sed 's/ *$//'`
    NAME=`echo ${NAME}|sed -e 's/^ \+//' -e 's/^Mme \+//' -e 's/^Mlle \+//' -e 's/^M \+//'`
}

getname ${NAME_LINE}
if [ "x${NAME}" == "x" ]
    then
    getname ${ALTERNATE_NAME_LINE}
fi

echo "NAME $NAME"
rm ${outfile}
