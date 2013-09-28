"""
Concrete implementations of tweakers that split pdf files
"""

from collections import Iterable
import re
from subprocess import Popen, PIPE

from PyPDF2 import PdfFileWriter
from PyPDF2.pdf import Destination

from .tweaker_base import PdfTweaker


class ParseError(Exception):
    pass


class PayrollTweaker(PdfTweaker):
    _DOCTYPE = 'salaire'
    _UNITARY_TIME = 0.1

    _ANCODE_MARKER = re.compile('^ANCODE ')
    _NAME_MARKER = re.compile('^NAME ')

    def split_stream(self, filename, reader, pages_nb):
        self.preprocessor = self.config.getvalue('payroll_preprocessor')
        for pagenb in xrange(pages_nb):
            output = PdfFileWriter()
            ancode, name = self._getinfo(filename, pagenb)
            page = reader.getPage(pagenb)
            output.addPage(page)
            outfname = self.get_outfname(ancode, name)
            with open(outfname, 'w') as wfd:
                self.logger.info("%s - %s -> %s", ancode, name, outfname)
                output.write(wfd)

    def _getinfo(self, filename, pagenb):
        command = [self.preprocessor, filename, '%d' % pagenb]
        process = Popen(command, stdout=PIPE, stderr=PIPE)
        stdout, stderr = process.communicate()
        if process.returncode != 0:
            raise ParseError("Return code of command: %d", process.returncode)
        stdout = stdout.decode('utf-8')
        stdout = stdout.split('\n')
        ancode = self.parse_single_value(stdout[0], self._ANCODE_MARKER)
        name = self.parse_single_value(stdout[1], self._NAME_MARKER)
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

    def split_stream(self, filename, reader, pages_nb):
        outlines = reader.getOutlines()
        self.allpages = []
        for index in xrange(pages_nb):
            current_page = reader.getPage(index)
            self.allpages.append(current_page)
        self.alldata = []

        self.logger.info("Parsing outlines. Output below")
        for entrepreneur, ancode in self.browse(outlines):
            self.alldata.append((entrepreneur, ancode))

        if not self.alldata:
            self.logger.critical("could not parse outlines?!")
            return

        cur_index = 0
        next_index = 1
        while self.last_print_page < pages_nb:
            print_all_remaining = False
            cur_entr, cur_ancode = self.alldata[cur_index]
            if next_index < len(self.alldata):
                next_entr, next_ancode = self.alldata[next_index]
                # may be None here also:
                next_startpage = self.findpage(next_ancode)
            else:
                next_startpage = None
            outfname = self.get_outfname(cur_ancode, cur_entr)

            if next_startpage is None:
                print_all_remaining = True
            self.printpages(print_all_remaining, outfname, next_startpage)
            cur_index = next_index
            next_index += 1

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
