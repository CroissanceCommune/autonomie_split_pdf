#!/bin/sh

set -e
set -u

FILE=$1
PAGE=$2
outfile=`tempfile`
pdftotext -layout -f $PAGE -l $PAGE "${FILE}" $outfile 2>&1 > /dev/null

ANCODE=`awk 'NR==12 {print;}' $outfile | cut -c 71- | tr -d ' '`
echo "ANCODE $ANCODE"
NAME=`awk 'NR==15 {print;}' $outfile | cut -c 125- |sed 's/ *$//'`
if [ x$NAME = x ] ; then # try next line
    NAME=`awk 'NR==14 {print;}' $outfile | cut -c 125- |sed 's/ *$//'`
fi
echo "NAME $NAME"
rm $outfile
