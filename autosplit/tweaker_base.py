from collections import Iterable
import itertools
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


class Section(object):
    def __init__(self, startpage, title, level):
        self.title = title
        self.startpage = startpage
        self.pages_nb = 1
        self.subsections = None
        self.following_section_startpage = 0
        if level == 0:
            self.section_type = 'main'
        elif level == 1:
            self.section_type = 'entrepreneur'
        elif level == 2:
            self.section_type = 'ancode'
        else:
            logger = mk_logger('autosplit.section')
            logger.critical(
                'unexpected outline structure with more than 3 levels, '
                'startpage: %i, title: %s, level: %i',
                startpage,
                title,
                level
                )

    def compute_pagenb(self, following_section_startpage):
        self.following_section_startpage = following_section_startpage
        self.pages_nb = max(1, following_section_startpage - self.startpage)
        if self.subsections:
            self.subsections[-1].compute_pagenb(following_section_startpage)

    def add_subsections(self, subsections):
        self.subsections = subsections
        subsections[-1].compute_pagenb(self.following_section_startpage)

    def __repr__(self):
        output = u'%3i (%s) - len %i' % (self.startpage, self.title, self.pages_nb)
        if self.subsections:
            output += ': ['
            for subsection in self.subsections:
                output += '  %s' % subsection
            output += '] '
        return output

    def get_contents(self):
        """
        Only works if self.subsections is iterable (ie. not None)
        """
        if self.section_type == 'ancode':
            return self.startpage, self.pages_nb, self.title

        if self.section_type == 'main':
            return itertools.chain(section.get_contents()
                for section in self.subsections)

        #entrepreneur type
        return (section.get_contents() + (self.title,)
            for section in self.subsections)


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
        self.offset = 0
        self.outlinedata = []

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

            self.logger.debug("Now writing files")
            for iteration, printinfo in enumerate(self.split_stream(pages_nb)):
                self.printpages(iteration, *printinfo)

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

    def printpages(self, iteration, pagenb, *args):
        """
        *args are passed to implementation specific addpage(), prepended by
        the PdfFileWriter and pagenb
        """
        output = PdfFileWriter()
        nb_print_pages = self.addpages(output, pagenb, *args)
        if pagenb >= len(self.alldata):
            self.logger.error("printpages() Returning early !")
            return
        name, ancode = self.alldata[iteration]
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

    def split_stream(self, pages_nb):
        return iter(self.outlinedata)


    def getdata(self, reader, filename, pages_nb):
        outlines = reader.getOutlines()

        self.logger.info("Parsing outlines. Output below")
        recursive_outlines = self.browse(outlines, make_offset=True)
        for first_level_section in recursive_outlines:
            if not first_level_section.subsections:
                continue
            for entre_nb, entrepreneur in enumerate(first_level_section.get_contents()):
                for item in entrepreneur:
                    self.logger.debug("startpage:%3i - length: %i - %-7s '%s'",
                        *item)
                    self.outlinedata.append(item + (reader,))
                    self.alldata.append((item[3], item[2]))
        self.logger.info("Found %i entrepreneurs and %i analytic codes",
            entre_nb + 1, len(self.alldata))
        self.logger.info("ETA: %s s", len(self.alldata) * 0.4)
        return True

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

    def addpages(self, output, startpage, pages_nb, ancode, entrepreneur, reader):
        for pageno in xrange(pages_nb):
            self.last_print_page = startpage + pageno
            page = reader.getPage(self.last_print_page)
            output.addPage(page)
        self.logger.debug("addpages: %-7s %s", ancode, entrepreneur)
        return pages_nb


    def register_pages(self, reader, pages_nb):
        """
        original implementation inefficient here
        """
        pass

    def browse(self, outline, level=0, make_offset=False):
        """
        Offset will be calculated once, on the first outline

        Todo: use last document page to specify last section length
        """
        start_ends = []
        previous_section = None
        for destination in outline:
            if isinstance(destination, Destination):
                title = destination.title
                # real pageno is offset
                pageno = destination.page.idnum - self.offset
                if make_offset:
                    # only run once in the parsing
                    self.offset = pageno
                    # correcting the pageno
                    pageno = 0
                    # ensure we never compute this again
                    make_offset = False
                section = Section(pageno, title, level)
                start_ends.append(section)
                if previous_section is not None:
                    previous_section.compute_pagenb(pageno)
                previous_section = section
            elif isinstance(destination, Iterable):
                lower_level_sections = self.browse(destination, level + 1)
                previous_section.add_subsections(lower_level_sections)
            else:
                self.logger.critical(
                    "Unexpected type for a destination: %s",
                    type(destination)
                    )
        return start_ends


