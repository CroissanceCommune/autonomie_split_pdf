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
        self._common_init()

    def _common_init(self):

        self.pages_nb = 1
        self.subsections = ()
        self.following_section_startpage = 0
        self.page_nb_definitive = False

    def compute_page_info(self, following_section_startpage):
        self.following_section_startpage = following_section_startpage
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

    def get_contents(self, force_section_type=None):
        """
        Only works if self.subsections is iterable (ie. not None)

        If section is ancode (final recursion) :
            returns a tuple startpage, pages nb, title
        If section is main: returns iterator over said tuples
        If section is entrepreneur: same
        """
        section_type = force_section_type or self.section_type
        if section_type == 'ancode':
            assert self.startpage >= 0, self.startpage
            return self.startpage, self.pages_nb, self.title

        if section_type == 'main':
            return itertools.chain(section.get_contents()
                for section in self.subsections)

        #entrepreneur type
        return (
            section.get_contents() + (self.title,)
            for section in self.subsections
        )


class VirtualSection(Section):
    """
    Hack to accomodate a buggy layout


    A CAE gave me a PDF missing a section level.

    expected layout is
    - main
      - entrepreneurs
        - analytic codes

    Entrepreneur level was missing, we simulate it (baah, I know).
    """

    def __init__(self, parent):
        self.title = u'generic'
        self.startpage = parent.startpage
        if parent.section_type == _MAIN:
            self.section_type = _ENTREPRENEUR
        elif parent.section_type == _ENTREPRENEUR:
            self.section_type = _ANCODE
        else:
            raise AssertionError("parent section type unknown")

        self._common_init()
