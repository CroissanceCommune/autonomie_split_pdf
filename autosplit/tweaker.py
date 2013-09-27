import os.path
import re
import time
import unicodedata
from collections import Iterable

from PyPDF2 import PdfFileWriter, PdfFileReader
from PyPDF2.pdf import Destination

from .file_operations import mkdir_p
from .log_config import mk_logger


_UNIX_VALID = re.compile('[^\w\s-]')
_NOSPACES = re.compile('[-\s]+')


def unix_sanitize(some_name):
    value = unicodedata.normalize('NFKD', some_name).encode('ascii', 'ignore')
    value = unicode(_UNIX_VALID.sub('', value).strip())
    return _NOSPACES.sub('-', value)


class PdfTweaker(object):

    def __init__(self, config, year, month):
        self.logger = mk_logger('autosplit.tweaker', config)
        self.config = config
        self.year = year
        self.month = month
        self.last_print_page = 0
        self.output_dir = os.path.join(self._DOCTYPE, self.year, self.month)
        self.pages_to_process = self.config.getvalue('restrict')

        self.identifiers = {}

    def tweak(self, pdfstream):
        mkdir_p(self.output_dir, self.logger)
        with open(pdfstream.name, 'r') as duplicate_pdfstream:
            inputpdf = PdfFileReader(duplicate_pdfstream)

            pages_nb = inputpdf.getNumPages()
            if not self.pages_to_process:
                # 0 means no restriction
                self.pages_to_process = pages_nb

            self.logger.info("%s has %d pages", pdfstream.name, pages_nb)
            self.logger.info("Estimated time for completion of %d pages on "
            "an average computer: %.f seconds. Please stand while the parsing"
            " takes place.", self.pages_to_process, self._UNITARY_TIME*self.pages_to_process)

            start = time.clock()

            self.split_stream(inputpdf, pages_nb)

            duration = time.clock() - start
            self.logger.info("Total duration: %s seconds, thank you for your patience",
                duration)

    def split_stream(self, reader, pages_nb):
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
            outfname = '%s_%s' % (cur_ancode, cur_entr)
            outfname = "%s/%s.pdf" % (self.output_dir, unix_sanitize(outfname))

            if next_startpage is None:
                print_all_remaining = True
            self.printpages(print_all_remaining, outfname, next_startpage)
            cur_index = next_index
            next_index += 1

    def printpages(self, print_all_remaining, outfname, next_startpage):
        output = PdfFileWriter()
        nb_print_pages = 1
        if print_all_remaining:
            for page in self.allpages[self.last_print_page:]:
                output.addPage(page)
                nb_print_pages += 1
                self.last_print_page += 1
        else:
            if self.last_print_page == next_startpage:
                self.logger.warning("2 analytic codes on page %d",
                    self.last_print_page)
                output.addPage(self.allpages[self.last_print_page])
            else:
                nb_print_pages = next_startpage - self.last_print_page
                for page in self.allpages[self.last_print_page:next_startpage]:
                    output.addPage(page)
                    self.last_print_page += 1
        with open(outfname, 'w') as wfd:
            self.logger.info("%d page(s) -> %s", nb_print_pages, outfname)
            output.write(wfd)


    def findpage(self, ancode):
        for index, page in enumerate(self.allpages[self.last_print_page:]):
            text = page.extractText()
            if ancode in text:
                return self.allpages.index(page)
            if index > 10:
                self.logger.info("Browsed 10 pages without finding code %s,"
                "search aborted", ancode)
                return None
        return None


    def browse(self, outline,
        level=0,
        maintitle='',
        entrepreneur=''):
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
                    for item in self.browse(destination,
                        level + 1,
                        maintitle,
                        entrepreneur):
                        yield item
                else:
                    self.logger.warning("Skipping entry of type %s" %
                        type(destination))



class PayrollTweaker(PdfTweaker):
    _DOCTYPE = 'salaire'
    _UNITARY_TIME = 0.1
    pass

class SituationTweaker(PdfTweaker):
    _DOCTYPE = 'tresorerie'
    _UNITARY_TIME = 0.1
    pass

class ResultTweaker(PdfTweaker):
    _DOCTYPE = 'resultat'
    _UNITARY_TIME = 0.1
    pass

DOC_TWEAKERS = {'salaire': PayrollTweaker, 'tresorerie': SituationTweaker,
    'resultat': ResultTweaker}
