"""
Autosplitter for pdf files
"""

__author__ = "Feth Arezki, Julien Miotte, Gaston Tjebbes"
__copyright__ = "Copyright 2013, Majerti"
__credits__ = ["Feth Arezki", "Julien Miotte", "Gaston Tjebbes"]
__license__ = "AGPLv3"
__version__ = "1RC"
__maintainer__ = "Feth Arezki"
__email__ = "feth@majerti.fr"
__status__ = "Development"


import os.path
import re

from .config import Config, DEFAULT_CONFIGFILE
from .log_config import mk_logger
from .tweaker import DOC_TWEAKERS


_FILENAMESRE = re.compile(
    r'(?P<DOCTYPE>[^_]+)_(?P<YEAR>'
    '[0-9]+)_(?P<MONTH>[^_]+)\.pdf'
    )


def version():
    return 'autosplit version: %s' % __version__


def main():
    """
    Method to call from the command line. Parses sys.argv arguments.
    """
    import argparse
    import logging

    parser = argparse.ArgumentParser(description='Sage files parsing')
    parser.add_argument('files', type=argparse.FileType('r'),
        help='pdf filename named DOCTYPE_YEAR_MONTH.pdf', nargs='+')
    parser.add_argument('-c', '--configfile', help='configuration file, '
    'defaults to %s' % DEFAULT_CONFIGFILE,
            default=None, type=argparse.FileType('r'))
    parser.add_argument('-v', '--verbose', action='store_const', const=True,
                        help='verbose output', default=False)
    parser.add_argument('-r', '--restrict', help="Restrict to n first pages",
                        type=int, default=0)
    parser.add_argument('-V', '--version', action='store_const', const=True,
                        help='version', default=False)

    arguments = parser.parse_args()

    if arguments.version:
        print(version())
        return

    config = Config.getinstance()
    config.load_args(arguments)
    logger = mk_logger("autosplit.main")
    logger.info(version())
    logger.info("Verbosity set to %s", config.getvalue("verbosity"))
    limit = config.getvalue('restrict')
    if limit != 0:
        logger.info("Analysis restricted to pages <= %d", limit)


    #config.save_defaults()
    #return
    for openfile in arguments.files:
        bare_filename = os.path.split(openfile.name)[-1]
        parsed = _FILENAMESRE.match(bare_filename)
        doctype = parsed.group('DOCTYPE')
        year =  parsed.group('YEAR')
        month =  parsed.group('MONTH')
        tweaker = DOC_TWEAKERS[doctype](year, month)

        #argparse has already open the files
        logger.info('Loading PDF "%s"', openfile.name)
        try:
            tweaker.tweak(openfile)
        except:
            logging.exception("Exception not handled by the splitter, that's a"
            "bug, sorry")
            raise

__all__ = 'PdfTweaker', 'Config'
