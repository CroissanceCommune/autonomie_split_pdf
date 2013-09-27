#!/bin/sh

FILE=$1
PAGE=$2
outfile=`tempfile`
pdftotext -layout -f $PAGE -l $PAGE "${FILE}" $outfile
awk 'NR==12 {print;}' $outfile | cut -c 71- | tr -d ' '
awk 'NR==15 {print;}' $outfile | cut -c 125- |sed 's/ *$//'

rm $outfile
