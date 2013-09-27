#!/bin/sh

set -e
set -u

FILE=$1
PAGE=$2
outfile=`tempfile`
pdftotext -layout -f $PAGE -l $PAGE "${FILE}" $outfile 2>&1 > /dev/null
echo -n "ANCODE "
awk 'NR==12 {print;}' $outfile | cut -c 71- | tr -d ' '
echo -n "NAME "
awk 'NR==15 {print;}' $outfile | cut -c 125- |sed 's/ *$//'

rm $outfile
