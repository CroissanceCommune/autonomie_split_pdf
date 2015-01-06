#!/bin/bash

# How to find the parameters:
#
# pdftotext -q -layout -f 1 -l 1 file.pdf outfile.txt
# view outfile.txt
# Find the column/line for name (including M, Mme or Mlle) and analytic code
# Take some margin on the left

set -e
set -u

FILE=$1
PAGE=$2
outfile=`tempfile`

# Overwritten in specific config
ANCODE_LINE=11
# the same as above
ALTERNATE_ANCODE_LINE=11
ANCODE_COL=45
ANCODE_MAXCOL=90
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

function getancode() {
    _ANCODE_LINE=${1}
    ANCODE=`awk "NR==${_ANCODE_LINE} {print;}" $outfile |cut -c ${ANCODE_COL}-${ANCODE_MAXCOL} |sed -e 's/^ \+//' -e 's/ .*//'`
    ANCODE=`echo ${ANCODE}|sed -e 's/^ \+//'`
}

function getname() {
    _NAME_LINE=${1}
    NAME=`awk "NR==${_NAME_LINE} {print;}" $outfile | cut -c ${NAME_COL}- |sed 's/ *$//'`
    NAME=`echo ${NAME}|sed -e 's/^ \+//' -e 's/^Mme \+//' -e 's/^Mlle \+//' -e 's/^M \+//'`
}

getancode ${ANCODE_LINE}

if [ "x${ANCODE}" == "x" ]
    then
    getancode ${ALTERNATE_ANCODE_LINE}
fi

echo "ANCODE $ANCODE"

getname ${NAME_LINE}
if [ "x${NAME}" == "x" ]
    then
    getname ${ALTERNATE_NAME_LINE}
fi

echo "NAME $NAME"
rm ${outfile}
