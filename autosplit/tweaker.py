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
    _DOCTYPE = 'salaire'
    _UNITARY_TIME = 0.1

    _ANCODE_MARKER = re.compile('^ANCODE ')
    _NAME_MARKER = re.compile('^NAME ')

    def __init__(self, *args):
        PdfTweaker.__init__(self, *args)
        self._notfoundpages = 0
        self.preprocessor = self.config.getvalue(('payroll', 'preprocessor'))
        if not os.path.exists(self.preprocessor):
            raise config.Error(
                "payroll preprocessor: %s - file not found"
                % self.preprocessor)

    def addpages(self, output, pagenb):
        self.logger.debug("addpages for %i", pagenb)
        page = self.allpages[pagenb]
        output.addPage(page)
        self.last_print_page += 1
        return 1

    def getdata(self, reader, filename, pages_nb, *args):
        """
        *args are ignored. Some instances of PdfTweaker implement getdata with
        additional arguments
        """

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

        command = [
            self.preprocessor,
            filename, '%d' % pdftotext_pagenb,
            ]
        stdout, stderr, returncode = self.get_command_outputs(command)
        strcommand = " ".join(command)
        if returncode != 0:
            raise ParseError("Return code of command '%s': %d", (strcommand, returncode))
        stdout = stdout.decode('utf-8')
        if "Error (" in stdout:
            fdesc, temppath = mkstemp(prefix="txt_split_error-")
            with open(temppath, 'w') as tempfd:
                tempfd.write(stdout)
            raise ParseError("pdf splitting failed - txt file dumped as %s - command was '%s' "
                % (temppath, strcommand))
        stdout_lines = stdout.split('\n')
        ancode = self.parse_single_value(stdout_lines[0], self._ANCODE_MARKER)
        name = self.parse_single_value(stdout_lines[1], self._NAME_MARKER)

        if not name:
            name = "NO_NAME_FOUND"
            self._notfoundpages += 1
            flag_report(False)

        unique_key = u'{0}_{1}_{2}'.format(pagenb, ancode, name)
        if unique_key in self.registered_infos:
            raise Incoherence(u'{0} already registered'.format(unique_key))
        self.registered_infos.add(unique_key)

        self.logger.info("Page %d: %s %s", pagenb, ancode, name)
        return ancode, name

    def check_splitpage(self, file_to_check, name, ancode):
        command = ["pdftotext", "-q", "-layout", file_to_check, '-'] # - is for stdout
        stdout, stderr, returncode = self.get_command_outputs(command)
        stdout = stdout.decode('utf-8')  # this is utf-8 and python2 thinks it is ascii
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


class SituationTweaker(OutlineTweaker):
    _DOCTYPE = 'tresorerie'
    _UNITARY_TIME = 0.1


class ResultTweaker(OutlineTweaker):
    _DOCTYPE = 'resultat'
    _UNITARY_TIME = 0.1


class ResultAndSituationTweaker(OutlineTweaker):
    """
    Implements interface of OutlineTweaker
    Lazy implementation: inheritance.
    We'd rather separate interface and implementation
    """
    _DOCTYPE = 'resultat-tresorerie'
    _UNITARY_TIME = 0.1

    def __init__(self, inputfile):
        self.result = ResultTweaker(inputfile)
        self.situation = SituationTweaker(inputfile)

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
    (klass._DOCTYPE, klass)
    for klass in (
        SituationTweaker,
        ResultTweaker,
        ResultAndSituationTweaker,
        PayrollTweaker
        )
    )
