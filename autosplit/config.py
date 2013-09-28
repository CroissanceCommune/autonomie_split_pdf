import os.path as ospath
from copy import deepcopy
import logging
import yaml


DEFAULT_CONFIGFILE = ospath.join(
    ospath.expanduser("~"),
    '.autonomie_pdfsplit.yaml')


_UNSET = object()


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

    def getvalue(self, name, override = _UNSET):
        if override is not _UNSET:
            return override
        return self.confvalues.get(name, self.DEFAULTS[name])
