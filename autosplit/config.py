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


from copy import deepcopy
import logging
import os.path as ospath
import yaml


DEFAULT_CONFIGFILE = ospath.join(
    ospath.expanduser("~"),
    '.autonomie_pdfsplit.yaml')


_UNSET = object()

class Error(Exception):
    def __init__(self, message):
        self.message = message

class Config(object):
    DEFAULTS = {'verbosity': 'INFO', 'loglevel': 20, 'use_syslog': False,
    'restrict': 0, 'payroll_preprocessor': './payrollpdf2ancode.sh'}

    _INSTANCE = None

    @classmethod
    def getinstance(cls):
        if cls._INSTANCE is None:
            cls._INSTANCE = Config()
        return cls._INSTANCE

    def load_args(self, parsed_args):
        configstream = parsed_args.configfile
        self.confvalues = deepcopy(self.DEFAULTS)
        self.parsed_args = parsed_args

        if configstream:
            self.confvalues.update(yaml.load(configstream))
        self._setverb()

        self.confvalues['restrict'] = self.parsed_args.restrict

    def _setverb(self):
        if self.parsed_args.verbose:
            self.confvalues['verbosity'] = 'DEBUG'

        str_verb = self.confvalues.get('verbosity')

        self.confvalues['loglevel'] = {'DEBUG': logging.DEBUG,
         'INFO': logging.INFO,
         'WARNING': logging.WARNING,
         'ERROR': logging.ERROR,
         'CRITICAL': logging.CRITICAL}[str_verb]

    def save_defaults(self):
        """
        Only called programmatically, to make the example config file
        """
        with open("config.yaml", "w") as confstream:
            confstream.write(yaml.dump(self.confvalues))

    def getvalue(self, name, override=_UNSET):
        if override is not _UNSET:
            return override
        if isinstance(name, basestring):
            value = self.confvalues.get(name, _UNSET)
            if value is _UNSET:
                value = self.DEFAULTS[name]
            return value
        intermediate = self.confvalues
        for item in name:
            intermediate = intermediate[item]
        return intermediate
