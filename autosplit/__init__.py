import os.path
import re

from .config import Config, DEFAULT_CONFIGFILE
from .log_config import mk_logger
from .tweaker import DOC_TWEAKERS


_FILENAMESRE = re.compile(r'(?P<DOCTYPE>[^_]+)_(?P<YEAR>'
    '[0-9]+)_(?P<MONTH>[^_]+)\.pdf')


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

    arguments = parser.parse_args()
    config = Config(arguments)
    logging.basicConfig(level=config.getvalue('loglevel'),
                        format="%(asctime)s [%(name)-20s][%(levelname)-8s] %(message)s")
    logger = mk_logger("autosplit.main", config)

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
        tweaker = DOC_TWEAKERS[doctype](config, year, month)

        #argparse has already open the files
        logger.info('Loading PDF "%s"', openfile.name)
        try:
            tweaker.tweak(openfile)
        except:
            logging.exception("Exception not handled by the splitter, that's a"
            "bug, sorry")
            raise

__all__ = 'PdfTweaker', 'Config'
