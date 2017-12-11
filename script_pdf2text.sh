#!/bin/bash
# Output provided page numbers of the given pdf to stdout

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
