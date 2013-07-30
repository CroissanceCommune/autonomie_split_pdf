from .config import Config, DEFAULT_CONFIGFILE
from .log_config import mk_logger
from .tweaker import PayrollTweaker


def main():
    """
    Method to call from the command line. Parses sys.argv arguments.
    """
    import argparse
    import logging

    parser = argparse.ArgumentParser(description='Sage files parsing')
    parser.add_argument('-p', '--payroll', type=argparse.FileType('r'),
        help='pdf filename for pay roll', nargs='+')
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
    if arguments.payroll:
        payroll_tweaker = PayrollTweaker(config)
        for pdfstream in arguments.payroll:
            #argparse has already open the files
            logger.info('Loading PDF "%s"', pdfstream.name)
            payroll_tweaker.tweak(pdfstream)

__all__ = 'PdfTweaker', 'Config'
