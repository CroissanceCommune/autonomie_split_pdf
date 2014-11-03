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
import getpass
from logging import handlers
import logging
import os
import socket
import traceback

from mailinglogger import SummarisingLogger
from mailinglogger.common import SubjectFormatter

from .config import Config


_LOGFORMAT = \
    "%(asctime)s [pid %(process)s][%(name)-20s]" \
    "[%(levelname)-8s] %(message)s"


_UNDEFINED = object()
_FLAGS_STRS = {
    False: '[failed]',
    True: '[success]',
    _UNDEFINED: ''
}


class Session(object):
    def __init__(self):
        self.flagged = _UNDEFINED
        self.docs_nb = 0
        self.maillog_handler = None
        self.syslog_handler = None
        self.initialized = False

    def get_logger(self, config, name):
        if not self.initialized:
            _log_init(config)
            self.initialized = True
        logger = logging.getLogger(name)
        log_level = config.getvalue('loglevel')
        logger.setLevel(log_level)
        if config.getvalue('use_syslog'):
            self._config_syslog(logger, log_level)
        if config.getvalue('log_to_mail'):
            self._config_maillog(logger, log_level, config)
        return logger

    def _config_syslog(self, logger, log_level):
        if self.syslog_handler is None:
            self.syslog_handler = handlers.SysLogHandler(
                address='/dev/log',
                facility=handlers.SysLogHandler.LOG_DAEMON
                )
            self.syslog_handler.setLevel(log_level)
            self.syslog_handler.setFormatter(
                logging.Formatter(
                    '[%(name)-17s %(process)s] - '
                    '%(levelname)s - %(message)s'
                    )
            )
        logger.addHandler(self.syslog_handler)

    def _get_mail_subject(self, config):
        return '{flagstr}[{username}][{documentsnb} docs]{subject}'.format(
            documentsnb=self.docs_nb,
            flagstr=_FLAGS_STRS[self.flagged],
            subject=config.getvalue(('mail', 'subject')) % {
                'hostname': socket.gethostname(),
            },
            username=getpass.getuser(),
        )

    def _config_maillog(self, logger, log_level, config):
        if self.maillog_handler is None:
            mail_subject = self._get_mail_subject(config)
            now = datetime.datetime.now()
            mail_template = _MAIL_TEMPLATE % {
                'process': os.getpid(),
                'date': now.strftime("%Y %B %d - %H:%M:%S"),
                'username': getpass.getuser(),
            }
            self.maillog_handler = SummarisingLogger(
                config.getvalue(('mail', 'from')),
                config.getvalue(('mail', 'to')),
                mailhost=config.getvalue(('mail', 'host')),
                subject=mail_subject,
                send_level=logging.DEBUG,
                template=mail_template,
            )
            self.maillog_handler.setFormatter(
                logging.Formatter('%(levelname)-9s - %(message)s'))
            self.maillog_handler.setLevel(log_level)
        logger.addHandler(self.maillog_handler)


_SESSION = Session()


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

User: %(username)s
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
    return _SESSION.get_logger(config, name)


def log_doc(logger, pagesnb, filename):
    logger.info(
        "%d page(s) -> %s",
        pagesnb,
        filename)
    _SESSION.docs_nb += 1




def flag_report(success):
    """
    :param bool success: whether we succeeded
    """
    if _SESSION.maillog_handler is None:
        # no report
        return
    if _SESSION.flagged is not _UNDEFINED:
        if not _SESSION.flagged:
            # don't erase 'failed' tag
            return

    _SESSION.flagged = success
    config = Config.getinstance()
    _SESSION.maillog_handler.mailer.subject_formatter = SubjectFormatter(
        _SESSION._get_mail_subject(config)
        )
