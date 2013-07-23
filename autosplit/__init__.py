from .config import Config, DEFAULT_CONFIGFILE
from .log_config import mk_logger
from .tweaker import PdfTweaker


def main():
    """
    Method to call from the command line. Parses sys.argv arguments.
    """
    import argparse
    import logging

    parser = argparse.ArgumentParser(description='Process some integers.')
    parser.add_argument('filenames', type=argparse.FileType('r'), help='pdf filename',
                        nargs='+')
    parser.add_argument('-c', '--configfile', help='configuration file, '
    'defaults to %s' % DEFAULT_CONFIGFILE,
            default=None, type=argparse.FileType('r'))
    parser.add_argument('-v', '--verbose', action='store_const', const=True,
                        help='verbose output', default=False)

    arguments = parser.parse_args()
    config = Config(arguments)
    logging.basicConfig(level=config.getvalue('loglevel'),
                        format="%(asctime)s [%(name)-20s] %(message)s")
    logger = mk_logger("autosplit.main", config)

    logger.info("Verbosity set to %s", config.getvalue("verbosity"))

    tweaker = PdfTweaker(config)
    for pdfstream in arguments.filenames:
        #argparse has already open the files
        logger.info('Loading PDF %s', pdfstream.name)
        tweaker.tweak(pdfstream)

__all__ = 'PdfTweaker', 'Config'
