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

"""
Concrete implementations of tweakers that split pdf files
"""

import os
import re
from tempfile import mkstemp

from .errors import AutosplitError
from .tweaker_base import Incoherence, PdfTweaker, OutlineTweaker
from . import config
from .log_config import flag_report


class ParseError(AutosplitError):
    pass


class PayrollTweaker(PdfTweaker):
    _TYPE = 'payroll'
    _UNITARY_TIME = 0.1

    _ANCODE_MARKER = re.compile('^ANCODE ')
    _NAME_MARKER = re.compile('^NAME ')

    def __init__(self, *args):
        PdfTweaker.__init__(self, *args)
        self._notfoundpages = 0
        self.preprocessor = self.config.getvalue(('preprocessor', 'payroll'))
        if not os.path.exists(self.preprocessor):
            raise config.Error(
                "payroll preprocessor: %s - file not found"
                % self.preprocessor)

        self.prec_ancode = None
        self.page_nbs = []

    def getprintdata(self, next_index):
        """
        Return arguments passed to addpages
        Check if there is a multiple paged salarysheet and returns the indexes

        :param next_index: The
        """
        if next_index <= len(self.page_nbs):
            return (len(self.page_nbs[next_index - 1]),)
        else:
            raise Exception("Falsy index asked, we don't have so much pages")
            return ()

    def addpages(self, output, startpage, pages_nb):
        """
        Add the pages to the output file
        Called in the parent class tweak process

        :param obj output: A write buffer
        :param int startpage: The page to write from
        :param int pages_nb: The number of pages to write

        :returns: The number of pages we wrote
        """
        startpage = self.last_print_page
        self.logger.debug("addpages starting at %i", startpage)
        for pageno in xrange(pages_nb):
            self.last_print_page = startpage + pageno + 1
            page = self.allpages[self.last_print_page - 1]
            output.addPage(page)
        return pages_nb

    def getdata(self, reader, filename, pages_nb, *args):
        """
        *args are ignored. Some instances of PdfTweaker implement getdata with
        additional arguments
        """

        for pagenb in xrange(pages_nb):
            # Perhaps here, add a try/except ParseError and ignore buggy page
            try:
                ancode, name = self._getinfo(filename, pagenb)
            except Incoherence as e:
                self.logger.critical(
                    "Incoherence error : %s" % e.message
                )
                return False
            except UnicodeDecodeError:
                self.logger.critical(
                    "Cannot extract text. Please check the pdf"
                    "file. For instance 'file -i %s' should not return"
                    "'charset=binary'",
                    filename
                )
                self.logger.critical("output of 'file -i %s':", filename)
                command = ['/usr/bin/file', '-i', filename]
                stdout, stderr, returncode = self.get_command_outputs(command)
                self.logger.critical(stdout.strip())
                return False
            if (name, ancode)not in self.alldata:
                self.alldata.append((name, ancode))

            if self.restrict and pagenb + 1 >= self.restrict:
                self.logger.info(
                    "Stopping the parsing as requested by limit of %d pages",
                    self.restrict
                    )
                return True
        return True

    @staticmethod
    def _get_line_part_after_prefix(line, prefix):
        """
        Return datas in line remaining after prefix

        :param str line: The line to split
        :param str prefix: The prefix to check
        :returns: The remaining line part after prefix
        """
        result = ""
        splitted = line.split(prefix)
        if len(splitted) > 1:
            result = splitted[1]
        return result

    @staticmethod
    def _get_line_part_from_range(line, start, end):
        """
        Return datas in line found between start and end index

        :param str line: The line to manage
        :param int start: The start index
        :param int end: The end index
        :returns: The matched part of the line
        """
        result = ""
        if len(line) > start:
            if end != -1 and len(line) > end:
                result = line[start:end]
            else:
                result = line[start:]
            result = result.strip()
        return result

    def _get_data(self, lines, line_number, start, end, prefix):
        """
        Find datas in lines regarding the given indexes

        :param list lines: the extracted lines
        :param int line_number: The line we should watch in
        :param int start: The column it sould start in
        :param int end: The max column we should find datas in
        :param str prefix: prefix before the datas we look for (start and end
        are prefix-related coordinates)
        """
        result = ''
        if line_number < len(lines):
            line = lines[line_number]
            if prefix:
                line = self._get_line_part_after_prefix(line, prefix)

            result = self._get_line_part_from_range(line, start, end)

        if not result and prefix:
            for line in lines:
                if prefix in line:
                    line = self._get_line_part_after_prefix(line, prefix)
                    result = self._get_line_part_from_range(line, start, end)

        return result

    def _find_datatype(self, datatype, pdf_lines):
        """
        Find the An code in the pdf2str result regarding the provided
        configuration

        :param str datatype: ancode / name used to retrieve the config keys we
        need
        ;param list pdf_lines: the list of lines coming from the pdf
        """
        doctype = self.inputfile.doctype
        # NOTE : Configuration is set with line numbers starting with 1, we move
        # them to 0
        line_num = self.config.getvalue(
            ('payroll', doctype, '%s_line' % datatype)
        ) - 1
        alt_line_num = self.config.getvalue(
            ('payroll', doctype, '%s_alternate_line' % datatype),
            default=0
        ) - 1
        start_column = self.config.getvalue(
            ('payroll', doctype, '%s_column' % datatype)
        ) - 1
        if start_column == -1:
            start_column = 0

        end_column = self.config.getvalue(
            ('payroll', doctype, '%s_end_column' % datatype),
            default=0
        ) - 1
        prefix = self.config.getvalue(
            ('payroll', doctype, '%s_prefix' % datatype),
            default=''
        ).strip()

        result = self._get_data(
            pdf_lines, line_num, start_column, end_column, prefix,
        )
        if not result and alt_line_num != -1:
            result = self._get_data(
                pdf_lines, alt_line_num, start_column, end_column, prefix,
            )
        return result

    def find_name(self, pdf_lines):
        """
        Find the name in the pdf2str result

        :param list pdf_lines: list of lines as str coming from the pdf
        """
        result = self._find_datatype('name', pdf_lines)
        if result:
            for key in ('^Mlle ', '^Mme ', '^M '):
                result = re.sub(key, '', result)
        return result.strip()

    def find_ancode(self, pdf_lines):
        """
        find the ancode in the pdf2str result

        :param list pdf_lines: list of lines as str coming from the pdf
        """
        result = self._find_datatype('ancode', pdf_lines)
        if result:
            result = result.split(' ')[0]
        return result.strip()

    def _getinfo(self, filename, pagenb):
        """
        Return the datas found in the page pagenb of the given file

        :param str filename: The full path to the file
        :param int pagenb: The page number (starting with 0)
        """
        pdf_str = self._get_pdf_str(filename, pagenb)

        pdf_lines = pdf_str.split('\n')

        ancode = self.find_ancode(pdf_lines)
        name = self.find_name(pdf_lines)

        if not (name and ancode):
            flag_report(False)
            if not name:
                field = "Name"
            else:
                field = "Ancode"

            raise AutosplitError(
                (
                    "{} field wasn't correctly extracted."
                    "Compare the lines and columns in the <HOME>/config.yaml"
                    " file the output from the last command (see previous log)"
                ).format(field, filename, pagenb)
            )

        unique_key = u'{0}_{1}'.format(ancode, name)

        if unique_key == self.prec_ancode:
            # multiple successive page
            self.page_nbs[-1].append(pagenb)

        elif unique_key in self.registered_infos:
            # multiple but not successive pages -> Error
            raise Incoherence(
                u'{0} already registered and not joined'.format(unique_key)
            )
        else:
            self.page_nbs.append([pagenb])
            self.prec_ancode = unique_key

        self.registered_infos.add(unique_key)

        self.logger.info("Page %d: %s %s", pagenb, ancode, name)
        return ancode, name

    def _get_pdf_str(self, filename, pagenb):
        """
        Return the pagenb of filename as a simple unicode string
        :param str filename: The path to the pdf
        :param int pagenb: The number of the page
        """
        # Warning: 1 - indexed page number for pdftotext, while the current
        # software and PyPDF2 API use 0 - index.
        pdftotext_pagenb = pagenb + 1

        command = [
            self.preprocessor,
            filename, '%d' % pdftotext_pagenb,
        ]
        stdout, stderr, returncode = self.get_command_outputs(command)
        strcommand = " ".join(command)
        if returncode != 0:
            raise ParseError(
                "Return code of command '%s': %d", (strcommand, returncode)
            )

        stdout = stdout.decode('utf-8')
        if "Error (" in stdout:
            fdesc, temppath = mkstemp(prefix="txt_split_error-")
            with open(temppath, 'w') as tempfd:
                tempfd.write(stdout)
            raise ParseError(
                "pdf splitting failed - txt file dumped as %s - "
                "command was '%s' " % (temppath, strcommand)
            )
        return stdout

    def check_splitpage(self, file_to_check, name, ancode):
        # - is for stdout
        command = ["pdftotext", "-q", "-layout", file_to_check, '-']
        stdout, stderr, returncode = self.get_command_outputs(command)
        # this is utf-8 and python2 thinks it is ascii
        stdout = stdout.decode('utf-8')
        stdout = ' '.join(stdout.split())  # normalize spaces

        if returncode != 0:
            self.logger.critical(
                'While checking correct parsing, pdftotext '
                'exit status is %d', returncode
            )
            return False

        if name not in stdout:
            self.logger.critical(
                'While checking correct parsing, name %s not found '
                'in %s', name, file_to_check
            )
            return False

        if ancode not in stdout:
            self.logger.critical(
                'While checking correct parsing, analytic code %s not found '
                'in %s', ancode, file_to_check
            )
            return False

        return True

    def parse_single_value(self, value, marker_re):
        if not marker_re.match(value):
            raise ParseError(
                "Didn't find expected output marker: "
                "'{pattern}' in '{value}'".format(
                    pattern=marker_re.pattern,
                    value=value,
                )
            )
        return marker_re.sub('', value)


class ResultAndSituationTweaker(OutlineTweaker):
    """
    Implements interface of OutlineTweaker
    Lazy implementation: inheritance.
    We'd rather separate interface and implementation
    """
    _TYPE = 'resultat-tresorerie'
    _UNITARY_TIME = 0.1

    def __init__(self, inputfile):
        self.result = OutlineTweaker(inputfile, filetype='resultat')
        self.situation = OutlineTweaker(inputfile, filetype='tresorerie')

    def tweak(self, pdfstream):
        self.result.tweak(
            pdfstream,
            mainsections_count=1,
            reverse_naming=True
        )
        self.situation.tweak(
            pdfstream,
            skip_sections=1,
            mainsections_count=1,
            reverse_naming=True
        )


DOC_TWEAKERS = dict(
    (klass._TYPE, klass)
    for klass in (
        ResultAndSituationTweaker,
        PayrollTweaker,
        OutlineTweaker,
        )
    )
