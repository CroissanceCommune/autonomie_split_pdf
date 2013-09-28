import logging
from logging import handlers


_INITIALIZED = False
_SYSLOG_HANDLER = None
_LOGFORMAT = \
            "%(asctime)s [pid %(process)s][%(name)-20s]" \
            "[%(levelname)-8s] %(message)s"

def _log_init(config):
    """
    To be called once, after the desired log level is known

    we fetch the log level in the config
    """
    logging.basicConfig(
        level=config.getvalue('loglevel'),
        format=_LOGFORMAT
        )


def mk_logger(name, config):
    global _INITIALIZED, _SYSLOG_HANDLER
    if not _INITIALIZED:
        _log_init(config)
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
