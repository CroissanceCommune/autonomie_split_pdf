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

import os, errno


def mkdir_p(path, logger):
    """
    http://stackoverflow.com/questions/600268/mkdir-p-functionality-in-python
    """
    try:
        os.makedirs(path)
    except OSError as exc:
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            fullpath = os.path.join(os.getcwd(), path)
            logger.critical("Error while creating directory %s -see trace" %
                fullpath)
            raise
