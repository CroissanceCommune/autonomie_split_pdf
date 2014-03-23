import itertools
from .log_config import mk_logger


_LOGGER = None


_MAIN = 'main'
_ENTREPRENEUR = 'entrepreneur'
_ANCODE = 'ancode'
_SECTION_TYPES = _MAIN, _ENTREPRENEUR, _ANCODE


class Section(object):
    def __init__(self, destination, level, previous_section, offset):

        global _LOGGER
        if _LOGGER is None:
            _LOGGER = mk_logger('autosplit.section')

        self.title = destination.title
        self.startpage = destination.page.idnum - offset
        _LOGGER.debug("%s: destination.page.idnum (%i) - offset (%i) = %i",
        self.title,
        destination.page.idnum, offset, self.startpage)

        if level == 0:
            self.section_type = _MAIN
        elif level == 1:
            self.section_type = _ENTREPRENEUR
        elif level == 2:
            self.section_type = _ANCODE
        else:
            _LOGGER.critical(
                'unexpected outline structure with more than 3 levels, '
                'title: %s, level: %i',
                self.title,
                level
                )

        self.pages_nb = 1
        self.subsections = None
        self.following_section_startpage = 0
        self.page_nb_definitive = False

    def _is_sublevel(self, other):
        """
        Whether this is one level lower than other section

        :param Section other:
        :return: bool
        """
        if (self.section_type == _ENTREPRENEUR) \
            and (other.section_type == _MAIN):
            return True
        return (self.section_type == _ANCODE) \
            and (other.section_type == _ENTREPRENEUR)

    def compute_page_info(self, following_section_startpage):
        self.following_section_startpage = following_section_startpage
        _LOGGER.debug("startpage: %i, following_section_startpage: %i",
        self.startpage, following_section_startpage)
        self.pages_nb = max(1, following_section_startpage - self.startpage)
        if self.subsections:
            self.subsections[-1].compute_page_info(following_section_startpage)
        self.page_nb_definitive = True

    def add_subsections(self, subsections):
        """
        subsections musn't be empty. The code can be adapted to support this
        """
        self.subsections = subsections
        subsections[-1].compute_page_info(self.following_section_startpage)
        _LOGGER.debug("section %s - startpage: %i", self.title, self.startpage)
        self.startpage = self.subsections[0].startpage

    def __repr__(self):
        output = u'<section %-12s start: p%3s (%-25s) - len %s>' % (
            self.section_type,
            '%i' % self.startpage \
                if self.startpage or self.page_nb_definitive \
                else '___',
            self.title,
            '[%i]' % self.pages_nb \
                if self.page_nb_definitive \
                else '___',
            )
        if self.subsections:
            output += ': ['
            for subsection in self.subsections:
                output += '  %s' % subsection
            output += '] '
        return output

    def get_contents(self):
        """
        Only works if self.subsections is iterable (ie. not None)
        """
        if self.section_type == 'ancode':
            assert self.startpage >= 0, self.startpage
            return self.startpage, self.pages_nb, self.title

        if self.section_type == 'main':
            return itertools.chain(section.get_contents()
                for section in self.subsections)

        #entrepreneur type
        return (section.get_contents() + (self.title,)
            for section in self.subsections)
