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

SPECIFIC_CONFIG="$HOME/payroll_rc"

if [ -f ${SPECIFIC_CONFIG} ]
    then
    . ${SPECIFIC_CONFIG}
fi

pdftotext -layout -f $PAGE -l $PAGE "${FILE}" $outfile 2>&1 > /dev/null

ANCODE=`awk "NR==${ANCODE_LINE} {print;}" $outfile |cut -c ${ANCODE_COL}- |sed -e 's/^ \+//' -e 's/ .*//'`
echo "ANCODE $ANCODE"

NAME=`awk 'NR==9 {print;}' $outfile | cut -c ${NAME_COL}- |sed 's/ *$//'`
NAME=`echo ${NAME}|sed -e 's/^ \+//' -e 's/^Mme \+//' -e 's/^Mlle \+//' -e 's/^M \+//'`
echo "NAME $NAME"
rm $outfile
