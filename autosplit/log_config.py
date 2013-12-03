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

import datetime
from logging import handlers
import logging
import os
import socket
import traceback

from mailinglogger import SummarisingLogger

from .config import Config


_INITIALIZED = False
_MAILLOG_HANDLER = _SYSLOG_HANDLER = None
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


_MAIL_TEMPLATE = u"""
PDF Splitter for Autonomie.

PID: %(process)s
Time: %(date)s

Following are all messages logged by the process on this run.

%%s
"""


def mk_logger(name):
    """
    returns a logger with the name supplied.
    """
    config = Config.getinstance()
    global _INITIALIZED
    if not _INITIALIZED:
        _log_init(config)
        _INITIALIZED = True
    logger = logging.getLogger(name)
    log_level = config.getvalue('loglevel')
    logger.setLevel(log_level)
    if config.getvalue('use_syslog'):
        _config_syslog(logger, log_level)
    if config.getvalue('log_to_mail'):
        _config_maillog(logger, log_level, config)
    return logger


def _config_syslog(logger, log_level):
    global _SYSLOG_HANDLER
    if _SYSLOG_HANDLER is None:
        _SYSLOG_HANDLER = handlers.SysLogHandler(address='/dev/log',
            facility=handlers.SysLogHandler.LOG_DAEMON)
        _SYSLOG_HANDLER.setLevel(log_level)
        _SYSLOG_HANDLER.setFormatter(
            logging.Formatter('[%(name)-17s %(process)s] - '
            '%(levelname)s - %(message)s'))
    logger.addHandler(_SYSLOG_HANDLER)


def _config_maillog(logger, log_level, config):
    global _MAILLOG_HANDLER
    if _MAILLOG_HANDLER is None:
        mail_subject = config.getvalue(('mail', 'subject')) % {
            'hostname': socket.gethostname(),
        }
        now = datetime.datetime.now()
        mail_template = _MAIL_TEMPLATE % {
            'process': os.getpid(),
            'date': now.strftime("%Y %B %d - %H:%M:%S")
        }
        _MAILLOG_HANDLER = SummarisingLogger(
            config.getvalue(('mail', 'from')),
            config.getvalue(('mail', 'to')),
            mailhost=config.getvalue(('mail', 'host')),
            subject=mail_subject,
            send_level=logging.DEBUG,
            template=mail_template,
        )
        _MAILLOG_HANDLER.setFormatter(
            logging.Formatter('%(levelname)-9s - %(message)s'))
        _MAILLOG_HANDLER.setLevel(log_level)
    logger.addHandler(_MAILLOG_HANDLER)
