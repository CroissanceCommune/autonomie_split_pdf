import itertools
from .log_config import mk_logger


_LOGGER = None


class Section(object):
    def __init__(self, startpage, title, level):

        global _LOGGER
        if _LOGGER is None:
            _LOGGER = mk_logger('autosplit.section')

        self.title = title
        self.startpage = startpage
        assert self.startpage >= 0, self.startpage
        self.pages_nb = 1
        self.subsections = None
        self.following_section_startpage = 0
        if level == 0:
            self.section_type = 'main'
        elif level == 1:
            self.section_type = 'entrepreneur'
        elif level == 2:
            self.section_type = 'ancode'
        else:
            _LOGGER.critical(
                'unexpected outline structure with more than 3 levels, '
                'startpage: %i, title: %s, level: %i',
                startpage,
                title,
                level
                )

    def compute_pagenb(self, following_section_startpage):
        self.following_section_startpage = following_section_startpage
        self.pages_nb = max(1, following_section_startpage - self.startpage)
        if self.subsections:
            self.subsections[-1].compute_pagenb(following_section_startpage)

    def add_subsections(self, subsections):
        """
        subsections musn't be empty. The code can be adapted to support this
        """
        self.subsections = subsections
        subsections[-1].compute_pagenb(self.following_section_startpage)
        _LOGGER.debug("section %s - startpage: %i", self.title, self.startpage)
        self.startpage = self.subsections[0].startpage

    def __repr__(self):
        output = u'%3i (%s) - len %i' % (self.startpage, self.title, self.pages_nb)
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


