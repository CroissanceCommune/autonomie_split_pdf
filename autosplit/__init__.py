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
Autosplitter for pdf files
"""

__author__ = "Feth Arezki, Julien Miotte, Gaston Tjebbes"
__copyright__ = "Copyright 2013, Majerti - Port-Parallele"
__credits__ = ["Feth Arezki", "Julien Miotte", "Gaston Tjebbes", "Vinay Sajip"]
__license__ = "GPLv3"
__version__ = "1RC"
__maintainer__ = "Feth Arezki"
__email__ = "feth@majerti.fr"
__status__ = "Development"


import hashlib
import logging
import os.path
import sys

from .config import Config, DEFAULT_CONFIGFILE, Error as ConfigError
from .log_config import log_exception, mk_logger, flag_report
from .tweaker import DOC_TWEAKERS
from .errors import AutosplitError


def get_md5sum(openfile):
    """
    from http://www.pythoncentral.io/hashing-files-with-python/
    """
    BLOCKSIZE = 65536
    hasher = hashlib.md5()
    buf = openfile.read(BLOCKSIZE)
    while len(buf) > 0:
        hasher.update(buf)
        buf = openfile.read(BLOCKSIZE)
    return hasher.hexdigest()


def version():
    return 'autosplit version: %s' % __version__


def main():
    """
    Method to call from the command line. Parses sys.argv arguments.
    """
    import argparse

    parser = argparse.ArgumentParser(description='Sage files parsing')
    parser.add_argument(
        'files',
        type=argparse.FileType('r'),
        help='pdf filename named DOCTYPE_YEAR_MONTH.pdf',
        nargs='+'
        )
    parser.add_argument(
        '-c', '--configfile',
        help='configuration file, defaults to %s' % DEFAULT_CONFIGFILE,
        default=None,
        type=argparse.FileType('r')
        )
    parser.add_argument('-v', '--verbose', action='store_const', const=True,
                        help='verbose output', default=False)
    parser.add_argument('-r', '--restrict', help="Restrict to n first pages",
                        type=int, default=0)
    parser.add_argument('-n', '--no-entr-name',
        help="Doc structure has no names: "
        "it only has analytic codes",
        action='store_true',
        default=False
    )
    parser.add_argument(
        '-V', '--version',
        action='version',
        version="%%(prog)s (pdf split for autonomie version %s)" % __version__
        )

    arguments = parser.parse_args()

    error = None
    config = Config.getinstance()
    try:
        config.load_args(arguments)
    except Exception, exception:
        error = exception

    logger = mk_logger("autosplit.main")
    logger.info(version())
    logger.debug("Command line: %s", sys.argv)
    logger.debug("Parsed arguments: %s", arguments)
    logger.debug("Current working directory: %s", os.getcwd())

    logger.info("Verbosity set to %s", config.getvalue("verbosity"))
    limit = config.getvalue('restrict')

    if limit != 0:
        logger.info("Analysis restricted to pages <= %d", limit)

    if error:
        # We wait until the logger is configured, especially if log_to_mail
        # is True, to get a proper logging of the exception
        logger.error(error)
        log_exception(logger)
        raise AutosplitError(error)

    for inputfile in config.inputfiles:

        logger.info('Loading PDF "%s"', inputfile.filepath)
        logger.info('md5 hash: %s', get_md5sum(open(inputfile.filepath, 'rb')))

        if inputfile.doctype not in DOC_TWEAKERS:
            error_msg = (
                "The filename isn't recognized by autosplit splitters: "
                "{}".format(DOC_TWEAKERS.keys())
            )
            logger.error(error_msg)
            log_exception(logger)
            raise AutosplitError(error_msg)

        try:
            tweaker = DOC_TWEAKERS[inputfile.doctype](inputfile)
        except ConfigError, exception:
            logger.critical(
                "Error in your configuration: %s", exception.message
            )
            log_exception(logger)
            raise
        except Exception, exception:
            logger.critical("Error initializing splitter")
            log_exception(logger)
            flag_report(False)
            raise

        try:
            tweaker.tweak(inputfile.filedescriptor)
        except AutosplitError, error:
            logger.error(error.message)
            flag_report(False)
        except BaseException:
            logger.exception(
                "Exception not handled by the splitter, that's a bug, sorry."
                )
            log_exception(logger)
            flag_report(False)
            raise
        else:
            flag_report(True)
        finally:
            logging.shutdown()

__all__ = 'PdfTweaker', 'Config'
