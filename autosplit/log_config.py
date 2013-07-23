import logging
from logging import handlers


_SYSLOG_HANDLER = None

def mk_logger(name, config):
    global _SYSLOG_HANDLER
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
