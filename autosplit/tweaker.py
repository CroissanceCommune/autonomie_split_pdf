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

import re


from .tweaker_base import PdfTweaker, OutlineTweaker


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
        self.logger.debug("addpages for %i", pagenb)
        page = self.allpages[pagenb]
        output.addPage(page)
        self.last_print_page += 1
        return 1

    def getdata(self, reader, filename, pages_nb):

        for pagenb in xrange(pages_nb):
            # Perhaps here, add a try/except ParseError and ignore buggy page
            try:
                ancode, name = self._getinfo(filename, pagenb)
            except UnicodeDecodeError:
                self.logger.critical("Cannot extract text. Please check the pdf"
                "file. For instance 'file -i %s' should not return"
                "'charset=binary'", filename)
                self.logger.critical("output of 'file -i %s':", filename)
                command = ['/usr/bin/file', '-i', filename]
                stdout, stderr, returncode = self.get_command_outputs(command)
                self.logger.critical(stdout.strip())
                return False
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

        stdout, stderr, returncode = self.get_command_outputs([
            self.preprocessor,
            filename, '%d' % pdftotext_pagenb,
            ])
        if returncode != 0:
            raise ParseError("Return code of command: %d", returncode)
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


class SituationTweaker(OutlineTweaker):
    _DOCTYPE = 'tresorerie'
    _UNITARY_TIME = 0.1


class ResultTweaker(OutlineTweaker):
    _DOCTYPE = 'resultat'
    _UNITARY_TIME = 0.1


DOC_TWEAKERS = {
    'salaire': PayrollTweaker,
    'tresorerie': SituationTweaker,
    'resultat': ResultTweaker
    }
