import os.path
import time
import unicodedata
import re

from PyPDF2 import PdfFileReader, PdfFileWriter

from .file_operations import mkdir_p
from .log_config import mk_logger
from .config import Config


_UNIX_VALID = re.compile('[^\w\s-]')
_NOSPACES = re.compile('[-\s]+')


def unix_sanitize(some_name):
    value = unicodedata.normalize('NFKD', some_name).encode('ascii', 'ignore')
    value = unicode(_UNIX_VALID.sub('', value).strip())
    return _NOSPACES.sub('-', value)


class PdfTweaker(object):

    def __init__(self, year, month):
        self.logger = mk_logger('autosplit.tweaker')
        config = Config.getinstance()
        self.config = config
        self.year = year
        self.month = month
        self.last_print_page = 0
        self.output_dir = os.path.join(self._DOCTYPE, self.year, self.month)
        self.pages_to_process = self.config.getvalue('restrict')

        self.identifiers = {}

    def tweak(self, pdfstream):
        mkdir_p(self.output_dir, self.logger)
        with open(pdfstream.name, 'rb') as duplicate_pdfstream:
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

            self.split_stream(pdfstream.name, inputpdf, pages_nb)

            duration = time.clock() - start
            self.logger.info("Total duration: %s seconds, thank you for your patience",
                duration)

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

    def get_outfname(self, ancode, entrepreneur):
        outfname = '%s_%s' % (ancode, entrepreneur)
        return "%s/%s.pdf" % (self.output_dir, unix_sanitize(outfname))

