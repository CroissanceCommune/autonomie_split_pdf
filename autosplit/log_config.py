import logging
from logging import handlers
import traceback

from .config import Config


_INITIALIZED = False
_SYSLOG_HANDLER = None
_LOGFORMAT = \
            "%(asctime)s [pid %(process)s][%(name)-20s]" \
            "[%(levelname)-8s] %(message)s"

def _log_init():
    """
    To be called once, after the desired log level is known

    we fetch the log level in the config
    """
    config = Config.getinstance()
    logging.basicConfig(
        level=config.getvalue('loglevel'),
        format=_LOGFORMAT
        )

def log_exception(logger):
    """
    print exception trace lines one by one.

    workaround for my syslog not registering multi lines

    an rsyslog workaround would be
      $EscapeControlCharactersOnReceive off

    another workaround would be the registering of 1 line only with newlines
    substitued (log being harder to read afterwards).
    """
    for line in traceback.format_exc().split('\n'):
        line = line.strip()
        if line:
            logger.debug("exc info: %s", line)

def mk_logger(name):
    """
    returns a logger with the name supplied.
    """
    config = Config.getinstance()
    global _INITIALIZED, _SYSLOG_HANDLER
    if not _INITIALIZED:
        _log_init()
        _INITIALIZED = True
    logger = logging.getLogger(name)
    log_level = config.getvalue('loglevel')
    logger.setLevel(log_level)
    if config.getvalue('use_syslog'):
        if _SYSLOG_HANDLER is None:
            _SYSLOG_HANDLER = handlers.SysLogHandler(address='/dev/log',
                facility=handlers.SysLogHandler.LOG_DAEMON)
            _SYSLOG_HANDLER.setLevel(log_level)
            _SYSLOG_HANDLER.setFormatter(
                logging.Formatter('[%(name)-17s] - '
                '%(levelname)s - %(message)s'))
        logger.addHandler(_SYSLOG_HANDLER)
    return logger
