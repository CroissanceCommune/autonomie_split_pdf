"""
Concrete implementations of tweakers that split pdf files
"""

from collections import Iterable
import re
from subprocess import Popen, PIPE

from PyPDF2.pdf import Destination

from .tweaker_base import PdfTweaker


class ParseError(Exception):
    pass


class PayrollTweaker(PdfTweaker):
    _DOCTYPE = 'salaire'
    _UNITARY_TIME = 0.1

    _ANCODE_MARKER = re.compile('^ANCODE ')
    _NAME_MARKER = re.compile('^NAME ')

    def __init__(self, *args):
        PdfTweaker.__init__(self, *args)
        self.preprocessor = self.config.getvalue(('payroll', 'preprocessor'))

    def addpages(self, output, pagenb):
        page = self.allpages[pagenb]
        output.addPage(page)
        self.last_print_page += 1
        return 1

    def getdata(self, reader, filename, pages_nb):

        for pagenb in xrange(pages_nb):
            # Perhaps here, add a try/except ParseError and ignore buggy page
            ancode, name = self._getinfo(filename, pagenb)
            self.alldata.append((name, ancode))
            if self.restrict and pagenb + 1 >= self.restrict:
                self.logger.info(
                    "Stopping the parsing as requested by limit of %d pages",
                    self.restrict
                    )
                return True
        return True

    def _getinfo(self, filename, pagenb):

        # Warning: 1 - indexed page number for pdftotext, while the current
        # software and PyPDF2 API use 0 - index.
        pdftotext_pagenb = pagenb + 1

        command = [self.preprocessor, filename, '%d' % pdftotext_pagenb]
        try:
            process = Popen(command, stdout=PIPE, stderr=PIPE)
        except OSError:
            self.logger.critical(
                    "Error while trying to run '%s'",
                    ' '.join(command))
            raise
        stdout, stderr = process.communicate()
        if process.returncode != 0:
            raise ParseError("Return code of command: %d", process.returncode)
        stdout = stdout.decode('utf-8')
        stdout_lines = stdout.split('\n')
        ancode = self.parse_single_value(stdout_lines[0], self._ANCODE_MARKER)
        name = self.parse_single_value(stdout_lines[1], self._NAME_MARKER)

        if not name:
            name = "NO_NAME_FOUND"

        self.logger.info("Page %d: %s %s", pagenb, ancode, name)
        return ancode, name

    def parse_single_value(self, value, marker_re):
        if not marker_re.match(value):
            raise ParseError("Didn't find expected output marker")
        return marker_re.sub('', value)


class SituationTweaker(PdfTweaker):
    _DOCTYPE = 'tresorerie'
    _UNITARY_TIME = 0.1

    def getdata(self, reader, filename, pages_nb):
        outlines = reader.getOutlines()

        self.logger.info("Parsing outlines. Output below")
        for entrepreneur, ancode in self.browse(outlines):
            self.alldata.append((entrepreneur, ancode))

        if self.alldata:
            return True

        self.logger.critical("could not parse outlines?!")
        return False

    def getprintdata(self, next_index):
        print_all_remaining = False
        if next_index < len(self.alldata):
            next_entr, next_ancode = self.alldata[next_index]
            # may be None here also:
            next_startpage = self.findpage(next_ancode)
        else:
            next_startpage = None

        if next_startpage is None:
            print_all_remaining = True
        return print_all_remaining, next_startpage

    def findpage(self, ancode):
        for index, page in enumerate(self.allpages[self.last_print_page:]):
            text = page.extractText()
            if ancode in text:
                return self.allpages.index(page)
            if index > 10:
                self.logger.info(
                    "Browsed 10 pages without finding code %s,"
                    "search aborted", ancode)
                return None
        return None

    def addpages(self, output, current_page, print_all_remaining, next_startpage):
        """
        :arg bool print_all_remaining: should we print all the remainder (stop
        splitting)
        :arg int next_startpage: page until which we print

        I think there is a bug in the content of alldata, but it seems to work
        """

        if print_all_remaining:
            for index, page in enumerate(self.allpages[self.last_print_page:]):
                output.addPage(page)
                self.last_print_page += 1
            return index + 1

        if self.last_print_page == next_startpage:
            self.logger.warning(
                "2 analytic codes on page %d (%s and %s)",
                self.last_print_page, *[
                    self.alldata[pnum][1] for pnum in (self.last_print_page,
                    self.last_print_page + 1)
                    ]
                )
            output.addPage(self.allpages[self.last_print_page])
            return 1

        for page in self.allpages[self.last_print_page:next_startpage]:
            output.addPage(page)
            self.last_print_page += 1
        return next_startpage - self.last_print_page + 1

    def browse(
            self,
            outline,
            level=0,
            maintitle='',
            entrepreneur=''
            ):
        """
        Recurses through outlines, yielding only when we have anaytic codes

        Yields tuple: entrepreneur, analytic code
        """
        for destination in outline:
            if isinstance(destination, Destination):
                title = destination.title
                if level == 2:
                    yield entrepreneur, title
                    continue
                if level == 0:
                    maintitle = title
                elif level == 1:
                    entrepreneur = title
                self.logger.info("%s- %s", '|'*(level + 1), title)
            else:
                if isinstance(destination, Iterable):
                    for item in self.browse(
                            destination,
                            level + 1,
                            maintitle,
                            entrepreneur
                            ):
                        yield item
                else:
                    self.logger.warning(
                        "Skipping entry of type %s" %
                        type(destination)
                        )


class ResultTweaker(PdfTweaker):
    _DOCTYPE = 'resultat'
    _UNITARY_TIME = 0.1

DOC_TWEAKERS = {
    'salaire': PayrollTweaker,
    'tresorerie': SituationTweaker,
    'resultat': ResultTweaker
    }
