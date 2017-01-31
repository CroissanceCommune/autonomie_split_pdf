# -*- coding: utf-8 -*-
# * Copyright (C) 2012-2013 Croissance Commune
# * Authors:
# * Arezki Feth <f.a@majerti.fr>;
# * Miotte Julien <j.m@majerti.fr>;
# * Pettier Gabriel;
# * TJEBBES Gaston <g.t@majerti.fr>
#
# This file is part of Autonomie : Progiciel de gestion de CAE.
#
# Autonomie is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Autonomie is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Autonomie. If not, see <http://www.gnu.org/licenses/>.
#

from collections import Iterable
from subprocess import Popen, PIPE
import os
import shutil
import re
import time
import unicodedata
import unidecode

from PyPDF2 import PdfFileReader, PdfFileWriter
from PyPDF2.pdf import Destination

from .config import Config
from .errors import AutosplitError
from .file_operations import mkdir_p
from .log_config import mk_logger, log_doc, log_errordoc, closing_message
from .section import Section
from .section import VirtualSection


_UNIX_VALID = re.compile('[^\w\s-]')
_NOSPACES = re.compile('[-\s]+')


class Incoherence(AutosplitError):
    pass


def unix_sanitize(some_name):
    value = unicodedata.normalize('NFKD', some_name).encode('ascii', 'ignore')
    value = unicode(_UNIX_VALID.sub('', value).strip())
    return _NOSPACES.sub('-', value)


class PdfTweaker(object):

    def __init__(self, inputfile, filetype=None):
        self.logger = mk_logger('autosplit.tweaker')
        config = Config.getinstance()
        self.config = config
        self.inputfile = inputfile
        self.last_print_page = 0
        if filetype is None:
            filetype = self.inputfile.doctype

        self.output_dir = os.path.join(
            filetype, self.inputfile.year, self.inputfile.month
        )
        self.pages_to_process = self.restrict = self.config.getvalue('restrict')
        self.pb_dir = self.config.getvalue('pb_dir')
        self.offset = 0
        self.outlinedata = []

        # list of all pages, ready for printing/parsing etc.
        self.allpages = []

        # list of (name, ancode)
        self.alldata = []

        self.registered_infos = set()
        self.generated_pages = set()

    def get_doctype(self):
        return self._DOCTYPE

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
        self.logger.debug("Running command %s", " ".join(argv_seq))
        process = self.make_process(argv_seq)
        stdout, stderr = process.communicate()
        returncode = process.returncode
        return stdout, stderr, returncode

    def tweak(
        self,
        pdfstream,
        skip_sections=0,
        mainsections_count=None,
        reverse_naming=False
    ):
        """
        :param int skip_sections: In order to handle several
            documents in the same file, I introduced skip_sections:
            this tells the parser that previous sections have been handled
            by another parser
        :param int mainsections_count: same purpose as above. If None:
        :param bool reverse_naming : defaults to False.
            for Port-Parallele - outline is reversed
            (analytic code / entr_name)
        """
        self.logger.debug("Writing to {0}".format(self.output_dir))
        mkdir_p(self.output_dir, self.logger)
        filename = pdfstream.name
        with open(filename, 'rb') as duplicate_pdfstream:
            inputpdf = PdfFileReader(duplicate_pdfstream)

            pages_nb = inputpdf.getNumPages()
            if not self.pages_to_process:
                # 0 means no restriction
                self.pages_to_process = pages_nb

            self.logger.info("%s has %d pages", filename, pages_nb)
            self.logger.info(
                "Estimated time for completion of %d pages on "
                "an average computer: %.f seconds. Please stand by while "
                "the parsing takes place.",
                self.pages_to_process,
                self._UNITARY_TIME*self.pages_to_process
                )
            start = time.clock()

            self.register_pages(inputpdf, pages_nb)
            if not self.getdata(
                    inputpdf,
                    filename,
                    pages_nb,
                    skip_sections,
                    mainsections_count,
            ):
                self.logger.critical(
                    "No data could be extracted! "
                    "Not splitting, sorry"
                )
                return

            self.logger.debug("Now writing files")

            did_print = False
            for iteration, printinfo in enumerate(self.split_stream(pages_nb)):
                self.printpages(
                    iteration,
                    *printinfo,
                    reverse_naming=reverse_naming
                )
                did_print = True

            if not did_print:
                self.logger.critical("No page of output!")

            duration = time.clock() - start

            closing_message(self.logger, duration)

    def getdata(*args, **kwargs):
        raise NotImplementedError()

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
        if not outputs_nb:
            self.logger.critical("No data collected? Strange")
            return
        self.logger.debug("Expected documents nb: %d", outputs_nb)
        for iteration in xrange(outputs_nb):
            printdata = self.getprintdata(next_index)
            self.logger.debug("printdata %s", printdata)
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

    def printpages(self, iteration, pagenb, *args, **kwargs):
        """
        *args are passed to implementation specific addpage(), prepended by
        the PdfFileWriter and pagenb
        :param bool reverse_naming: keyword arg
            * False by default:
              files are named after analytic code, then name
            * when True, the name and analytic code were reversed in the
              outline, so we correct that here.

        """
        reverse_naming = kwargs.get('reverse_naming', False)

        output = PdfFileWriter()
        nb_print_pages = self.addpages(output, pagenb, *args)
        name, ancode = self.alldata[iteration]
        if reverse_naming:
            outfname = self.get_outfname(name, ancode)
        else:
            outfname = self.get_outfname(ancode, name)

        if outfname in self.generated_pages:
            raise Incoherence("Already generated file with path {}".format(
                outfname
                )
            )
        self.generated_pages.add(outfname)
        with open(outfname, 'wb') as wfd:
            log_doc(self.logger, nb_print_pages, outfname)
            output.write(wfd)

        if not self.check_splitpage(outfname, name, ancode):
            newdest = os.path.join(self.pb_dir, os.path.basename(outfname))
            log_errordoc(self.logger, nb_print_pages, newdest)
            self.logger.critical(
                "Check failed for %s. Moved to %s",
                outfname,
                newdest
            )
            if not os.path.isdir(self.pb_dir):
                os.mkdir(self.pb_dir)
            shutil.move(outfname, newdest)

    def get_outfname(self, ancode, entrepreneur):
        outfname = '%s_%s' % (ancode, entrepreneur)
        return "%s/%s.pdf" % (self.output_dir, unix_sanitize(outfname))

    def check_splitpage(self, file_to_check, name, ancode):
        """
        Subclass this method in tweakers.

        :returns: bool

        It is the responsibility of this method to log.
        """
        return True


class OutlineTweaker(PdfTweaker):
    _TYPE = 'outline'
    _UNITARY_TIME = 0.1

    def split_stream(self, pages_nb):
        if not self.outlinedata:
            self.logger.critical("No data collected in outline? Strange")
        return iter(self.outlinedata)

    def getdata(
        self,
        reader,
        filename,
        pages_nb,
        skip_sections=0,
        mainsections_count=None
    ):
        """
        :param int skip_sections: see :func:`tweak`
        :param int mainsections_count: see :func:`tweak`
        """

        outlines = reader.getOutlines()
        logger = mk_logger('autosplit.getdata')
        no_entr_name = self.config.getvalue('no_entr_name')
        if no_entr_name:
            logger.critical(
                "Single level outline (no_entr_name) : cannot infer"
                " entrepreneur name"
            )

        logger.info("Parsing outlines. Output below")
        recursive_outlines = self.browse(outlines, no_entr_name=no_entr_name)
        logger.info("Browsed outlines")

        entre_nb = 0
        for first_level_section in recursive_outlines:
            self.logger.debug("Entering a 1st level section")
            if not first_level_section.subsections:
                logger.debug("Section is empty, skipping")
                continue
            if skip_sections:
                logger.debug("Skipping section as configured")
                skip_sections -= 1
                continue
            if mainsections_count is not None:
                mainsections_count -= 1
                if mainsections_count < 0:
                    logger.debug("This was the last section.")
                    return True

            for entre_nb, entrepreneur in enumerate(first_level_section.get_contents()):
                self.logger.debug("Entering a 2nd level section")
                for item in entrepreneur:
                    self._browse_ancode_level(item, reader, logger)
                logger.debug("End of a 2nd level section")
            logger.debug("End of a 1st level section")

        logger.info(
            "Found %i entrepreneurs and %i analytic codes",
            entre_nb + 1,
            len(self.alldata)
        )
        logger.info("ETA: %s s", len(self.alldata) * 0.4)
        return True

    def _browse_ancode_level(self, outline_item, reader, logger):
        """
        :param tuple outline_item:
        """
        assert all(value >= 0 for value in outline_item[:2]), \
            "section contents: startpage:%3i - length: %i - %-7s '%s'" \
            % outline_item

        logger.debug(
            "startpage:%3i - length: %i - %-7s '%s'", *outline_item
        )
        self.outlinedata.append(outline_item + (reader,))
        self.alldata.append((outline_item[3], outline_item[2]))
        unique_key = u'{0}_{1}'.format(
            unidecode.unidecode(outline_item[3]),
            unidecode.unidecode(outline_item[2])
        )
        self.logger.debug("unique_key: %s", unique_key)
        if unique_key in self.registered_infos:
            raise Incoherence('{0} already registered'.format(
                unique_key
                )
            )
        self.registered_infos.add(unique_key)

    def get_section_boundaries(self):
        assert self.section_pages, "section_pages was 0 or None"
        for index, startpageno in enumerate(self.section_pages):
            if startpageno >= self.last_print_page:
                try:
                    start = self.section_pages[index - 1]
                except IndexError:
                    start = 0
                finally:
                    break
        else:
            assert False, \
                "Current 'last_print_page' is {0} " \
                "and section_pagenos: {1}".format(
                    self.last_print_page,
                    self.section_pages
                )

        return start, startpageno

    def getprintdata(self, next_index):
        print_all_remaining = False
        section_start, section_end = self.get_section_boundaries()
        if self.restrict > section_end + 1:
            self.restrict = section_end + 1  # suboptimal: should be set ONCE
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

    def addpages(
        self,
        output,
        startpage,
        pages_nb,
        ancode,
        entrepreneur,
        reader
    ):
        for pageno in xrange(pages_nb):
            self.last_print_page = startpage + pageno
            assert startpage >= 0, "Start page = %s" % startpage
            assert pageno >= 0, "Page no = %s" % pageno
            page = reader.getPage(self.last_print_page)
            output.addPage(page)
        self.logger.debug("addpages: %-7s %s", ancode, entrepreneur)
        return pages_nb

    def register_pages(self, reader, pages_nb):
        """
        original implementation inefficient here
        """
        pass

    def browse(
        self,
        outline,
        level=0,
        previous_section=None,
        no_entr_name=False
    ):
        """
        Offset will be calculated once, on the first outline

        Todo: use last document page to specify last section length

        :param outline: browseable PyPDF2 document outline
        :param int level: how deep we are in recursion
        :param Section previous_section: this recursive function tells itself
        the last built section
        """
        if no_entr_name and level == 1:
            # Skip level 1 when there is no_entr_name
            # Hack for appuy
            level = 2

        container_section = None

        start_ends = []
        for destination in outline:
            if isinstance(destination, Destination):
                if previous_section is None:
                    # happens only once in the parsing
                    # set offset
                    self.offset = destination.page.idnum
                    self.logger.debug(
                        "Page numbers are offset by %i",
                        self.offset
                    )
                section = _destination2section(
                    destination,
                    level,
                    previous_section,
                    self.offset
                )
                previous_section = section
                start_ends.append(section)
                self.logger.debug("Done reading section: %s", section)
            elif isinstance(destination, Iterable):
                if no_entr_name:
                    # again, the hack for appuy
                    # Make a virtual section when needed
                    if container_section is None:
                        container_section = VirtualSection(previous_section)
                    previous_section.add_subsections([container_section])
                else:
                    container_section = previous_section
                self.logger.debug(
                    "Reading section container (parent=%s)",
                    previous_section
                )
                lower_level_sections = self.browse(
                    destination, level + 1,
                    previous_section=container_section,
                    no_entr_name=no_entr_name,
                    )
                container_section.add_subsections(lower_level_sections)
            else:
                self.logger.critical(
                    "Unexpected type for a destination: %s",
                    type(destination)
                    )
        return start_ends


def _destination2section(destination, level, previous_section, offset):
    """
    :param Destination destination:
    :param int level:
    :param Section previous_section: None or Section
    """
    section = Section(destination, level, previous_section, offset)
    pageno = section.startpage

    assert pageno >= 0, \
        "computed pageno: {:d}, - with idnum {:d} and offset: {:d}".format(
            pageno, destination.page.idnum, offset
        )

    if previous_section is not None:
        previous_section.compute_page_info(pageno)

    return section
