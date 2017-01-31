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

if hash tempfile 2>/dev/null
then
    # debian
    outfile=`tempfile`
else
    # Fedora
    outfile=`mktemp`
fi

pdftotext -q -layout -f $PAGE -l $PAGE "${FILE}" $outfile

cat ${outfile}
rm ${outfile}
