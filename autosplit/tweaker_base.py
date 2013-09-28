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

    def register_pages(self, reader, pages_nb):
        self.allpages = []
        for index in xrange(pages_nb):
            current_page = reader.getPage(index)
            self.allpages.append(current_page)

    def printpages(self, outfname, *args):
        """
        all args are passed to implementation specific addpage().
        """
        output = PdfFileWriter()
        nb_print_pages = self.addpages(output, *args)
        with open(outfname, 'w') as wfd:
            self.logger.info("%d page(s) -> %s", nb_print_pages, outfname)
            output.write(wfd)

    def get_outfname(self, ancode, entrepreneur):
        outfname = '%s_%s' % (ancode, entrepreneur)
        return "%s/%s.pdf" % (self.output_dir, unix_sanitize(outfname))

