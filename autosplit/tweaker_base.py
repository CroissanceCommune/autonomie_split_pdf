from collections import Iterable
from subprocess import Popen, PIPE
import os.path
import re
import time
import unicodedata

from PyPDF2 import PdfFileReader, PdfFileWriter
from PyPDF2.pdf import Destination

from .config import Config
from .file_operations import mkdir_p
from .log_config import mk_logger


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
        self.pages_to_process = self.restrict = self.config.getvalue('restrict')
        self.offset = -1 # -1 stands for uninitialized.
        self.section_pages = []

        # list of all pages, ready for printing/parsing etc.
        self.allpages = []

        # list of (name, ancode)
        self.alldata = []

    def make_process(self, argv_seq):
        try:
            process = Popen(argv_seq, stdout=PIPE, stderr=PIPE)
        except OSError:
            self.logger.critical(
                    "Error while trying to run '%s'",
                    ' '.join(argv_seq))
            raise
        return process

    def get_command_outputs(self, argv_seq):
        """
        :return: stdout and stderr as unicode decodable strings, return code as
        int
        """
        process = self.make_process(argv_seq)
        stdout, stderr = process.communicate()
        returncode = process.returncode
        return stdout, stderr, returncode

    def tweak(self, pdfstream):
        mkdir_p(self.output_dir, self.logger)
        filename = pdfstream.name
        with open(pdfstream.name, 'rb') as duplicate_pdfstream:
            inputpdf = PdfFileReader(duplicate_pdfstream)

            pages_nb = inputpdf.getNumPages()
            if not self.pages_to_process:
                # 0 means no restriction
                self.pages_to_process = pages_nb

            self.logger.info("%s has %d pages", filename, pages_nb)
            self.logger.info(
                "Estimated time for completion of %d pages on "
                "an average computer: %.f seconds. Please stand while "
                "the parsing takes place.",
                self.pages_to_process,
                self._UNITARY_TIME*self.pages_to_process
                )
            start = time.clock()

            self.register_pages(inputpdf, pages_nb)
            if not self.getdata(inputpdf, filename, pages_nb):
                self.logger.critical("No data could be extracted! "
                "Not splitting, sorry")
                return

            for printinfo in self.split_stream(pages_nb):
                self.printpages(*printinfo)

            duration = time.clock() - start
            self.logger.info(
                    "Total processor time: %s seconds, "
                    "thank you for your patience",
                    duration)

    def register_pages(self, reader, pages_nb):
        for index in xrange(pages_nb):
            current_page = reader.getPage(index)
            self.allpages.append(current_page)

    def getprintdata(self, next_index):
        """
        supplies data for addpages()

        default implementation returns empty tuple."""
        return ()

    def split_stream(self, pages_nb):
        cur_index = 0
        next_index = 1
        # last_print_page is updated by addpages()
        outputs_nb = len(self.alldata)
        for iteration in xrange(outputs_nb):
            printdata = self.getprintdata(next_index)
            yield (cur_index,) + printdata
            cur_index = next_index
            next_index += 1
            if self.restrict and self.last_print_page >= self.restrict:
                self.logger.info(
                    "Stopping the parsing as requested by limit of %d pages"
                    " or next section beginning",
                    self.restrict
                    )
                return

    def printpages(self, pagenb, *args):
        """
        *args are passed to implementation specific addpage(), prepended by
        the PdfFileWriter and pagenb
        """
        output = PdfFileWriter()
        nb_print_pages = self.addpages(output, pagenb, *args)
        if pagenb >= len(self.alldata):
            return
        name, ancode = self.alldata[pagenb]
        outfname = self.get_outfname(ancode, name)
        with open(outfname, 'w') as wfd:
            self.logger.info(
                "%d page(s) -> %s",
                nb_print_pages,
                outfname)
            output.write(wfd)

    def get_outfname(self, ancode, entrepreneur):
        outfname = '%s_%s' % (ancode, entrepreneur)
        return "%s/%s.pdf" % (self.output_dir, unix_sanitize(outfname))


class OutlineTweaker(PdfTweaker):

    def getdata(self, reader, filename, pages_nb):
        outlines = reader.getOutlines()

        self.logger.info("Parsing outlines. Output below")
        section_pages = []
        for index, (level, data) in enumerate(self.browse(outlines)):
            if level == 0:
                destination = data
                section_pages.append(destination.page.idnum)
                continue
            elif level != 2:
                continue
            entrepreneur, ancode, page = data
            if self.offset == -1:
                # assumes there is no header
                self.offset = page.idnum
                self.logger.info("Page offset seems to be %i", self.offset)
            self.alldata.append((entrepreneur, ancode))

        if self.offset == -1:
            offset = 0
        else:
            offset = self.offset

        # beware, we speak of 0 indexed pages
        self.section_pages = [value - offset for value in section_pages]

        # perhaps this is buggy but should always work with sage
        self.logger.info("Sections pages seem to be: %s", self.section_pages)

        if self.alldata:
            return True

        self.logger.critical("could not parse outlines?!")
        return False

    def get_section_boundaries(self):
        assert self.section_pages
        for index, startpageno in enumerate(self.section_pages):
            if startpageno >= self.last_print_page:
                try:
                    start = self.section_pages[index - 1]
                except IndexError:
                    start = 0
                finally:
                    break
        else:
            assert False, "Current 'last_print_page' is %i and section_pagenos: %s" %(
                self.last_print_page,
                self.section_pages
            )

        return start, startpageno

    def getprintdata(self, next_index):
        print_all_remaining = False
        section_start, section_end = self.get_section_boundaries()
        if self.restrict > section_end + 1:
            self.restrict = section_end + 1 # suboptimal: should be set ONCE
            # +1 is conservative
        if next_index < len(self.alldata):
            next_entr, next_ancode = self.alldata[next_index]
            # may be None here also:
            next_startpage = self.findpage((next_ancode,))
            if next_startpage is None:
                self.logger.info(
                    "Attempt to rescue: " "was an analytic code ommitted?"
                    )
                rescue_range = next_index + 1, next_index + 10
                rescue_ancodes = [
                    data[1]
                    for data in self.alldata[rescue_range[0]:rescue_range[1]]
                    ]
                self.logger.info("Trying analytic codes %s", rescue_ancodes)
                next_startpage = self.findpage(rescue_ancodes)
                # may still be None!

        else:
            next_startpage = section_end
            print_all_remaining = True

        if next_startpage is None:
            print_all_remaining = True

        return print_all_remaining, next_startpage

    def findpage(self, ancodes):
        for index, page in enumerate(self.allpages[self.last_print_page:]):
            text = page.extractText()
            for ancode in ancodes:
                if ancode in text:
                    return self.allpages.index(page)
            pages_to_browse = 10
            if index > pages_to_browse:
                self.logger.info(
                    "Browsed %d pages without finding code %s,"
                    "search aborted", pages_to_browse, ancodes)
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
            index = 0 # may be undefined this is a fallback value- fixme
            for index, page in enumerate(
                self.allpages[self.last_print_page:self.restrict]):
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
                page = destination.page
                title = destination.title
                if level == 2:
                    yield level, (entrepreneur, title, page)
                    continue
                if level == 0:
                    maintitle = title
                    yield level, destination
                elif level == 1:
                    entrepreneur = title
                    yield level, destination
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

