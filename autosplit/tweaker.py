from cStringIO import StringIO
from lxml import etree
import os.path
import re
import time
import unicodedata
from collections import Iterable, defaultdict

from pdfminer.pdftypes import resolve1
from pdfminer.pdfparser import PDFParser, PDFDocument
from pdfminer.pdfinterp import PDFResourceManager, process_pdf
from pdfminer.converter import XMLConverter
from pdfminer.layout import LAParams
from PyPDF2 import PdfFileWriter, PdfFileReader
from PyPDF2.pdf import Destination

from .file_operations import mkdir_p
from .log_config import mk_logger


_UNIX_VALID = re.compile('[^\w\s-]')
_NOSPACES = re.compile('[-\s]+')


def unix_sanitize(some_name):
    value = unicodedata.normalize('NFKD', some_name).encode('ascii', 'ignore')
    value = unicode(_UNIX_VALID.sub('', value).strip())
    return _NOSPACES.sub('-', value)


class PdfTweaker(object):

    _XPATH_EXPR = {}
    def __init__(self, config, year, month):
        self.logger = mk_logger('autosplit.tweaker', config)
        self.config = config
        self.rsrcmgr = PDFResourceManager()
        self.laparams = LAParams()
        self.year = year
        self.month = month
        self.last_print_page = 0
        self.output_dir = os.path.join(self._DOCTYPE, self.year, self.month)
        self.pages_to_process = self.config.getvalue('restrict')
        for index, (name, expr) in enumerate(self._XPATH_EXPR.iteritems()):
            self.logger.debug("[%d] xpath expression for %s: %s", index, name, expr[0])

        self.identifiers = {}


    def _toxml(self, pdfstream, pageno):
        human_pagenb = pageno + 1
        retstr = StringIO()
        self.logger.debug("Converting page %d to xml", human_pagenb)
        start_time = time.clock()
        device = XMLConverter(self.rsrcmgr, retstr, codec='utf-8',
        laparams=self.laparams, pageno=pageno)


        process_pdf(self.rsrcmgr, device, pdfstream, maxpages=1, pagenos=(pageno,))

        device.close()
        duration = time.clock() - start_time
        self.logger.debug("Conversion of page %d to xml took %s seconds.",
            human_pagenb, duration)
        retstr.seek(0)
        tree = etree.parse(retstr)
        retstr.close()
        return tree

    def write_page(self, identifier, inputpdf):
        """
        :note: this func could be called as a callback after get_identifier
        """
        output = PdfFileWriter()
        page_index = identifier.get_index()
        ref = None
        if identifier.append:
            ref = self.identifiers[page_index - 1]
            self.logger.info('Rewriting sheet %d with sheet %d',
                identifier.p_nr, ref.p_nr)
            output.addPage(inputpdf.getPage(ref.get_index()))
        output.addPage(inputpdf.getPage(page_index))
        output_file = os.path.join(self.output_dir,
            identifier.getfilename(other=ref))
        self.logger.debug("Writing %s", output_file)
        outputStream = file(output_file, "wb")
        output.write(outputStream)
        outputStream.close()
        self.logger.info("Wrote %s", output_file)

    def tweak(self, pdfstream):
        mkdir_p(self.output_dir, self.logger)
        with open(pdfstream.name, 'r') as duplicate_pdfstream:
            inputpdf = PdfFileReader(duplicate_pdfstream)

            pages_nb = inputpdf.getNumPages()
            if not self.pages_to_process:
                # 0 means no restriction
                self.pages_to_process = pages_nb

            self.logger.info("%s has %d pages", pdfstream.name, pages_nb)
            self.logger.info("Estimated time for completion of %d pages on "
            "an average computer: %.f seconds. Please stand while the parsing"
            " takes place.", self.pages_to_process, self._UNITARY_TIME*self.pages_to_process)

            start = time.clock()

            with open(pdfstream.name, 'rb') as duplicate_pdfstream:
                reader = PdfFileReader(duplicate_pdfstream)
                outlines = reader.getOutlines()
                self.allpages = []
                for index in xrange(pages_nb):
                    current_page = reader.getPage(index)
                    self.allpages.append(current_page)
                self.alldata = []
                for entrepreneur, ancode in self.browse(outlines):
                    self.alldata.append((entrepreneur, ancode))

                cur_entr, cur_ancode = self.alldata[0]
                next_entr, next_ancode = self.alldata[1]
                outfname = '%s_%s.pdf' % (cur_entr, cur_ancode)
                outfname = "%s/%s" % (self.output_dir, outfname.replace('/', '_'))

                next_startpage = self.findpage(next_ancode)
                if next_startpage is None:
                    # let's print all remaining pages together and stop the
                    # program.
                    pass
                else:
                    output = PdfFileWriter()
                    if self.last_print_page == next_startpage:
                        self.logger.warning("2 analytic codes on page %d",
                            self.last_print_page)
                        output.addPage(self.allpages[self.last_print_page])
                    else:
                        for page in self.allpages[self.last_print_page:next_startpage]:
                            output.addPage(page)
                            self.last_print_page += 1
                    with open(outfname, 'w') as wfd:
                        self.logger.info("|| |-> %s", outfname)
                        output.write(wfd)






                if False:
                    output = PdfFileWriter()
                    target_page = destination.page.getObject()
                    output.addPage(target_page)
                    startoffset = self.findpage(ancode)
                    print "startoffset", startoffset
                    outfname = '%s_%s.pdf' % (entrepreneur, ancode)
                    outfname = "playground/%s" % outfname.replace('/', '_')
                    with open(outfname, 'w') as wfd:
                        self.logger.info("|| |-> %s", outfname)
                        output.write(wfd)
    #                    destination.page.getObject().writeToStream(wfd, '')


            duration = time.clock() - start
            self.logger.info("Total duration: %s seconds, thank you for your patience",
                duration)

    def printpage(self):
        pass
        self.last_print_page += 1

    def findpage(self, ancode):
        for index, page in enumerate(self.allpages[self.last_print_page:]):
            text = page.extractText()
            if ancode in text:
                return self.allpages.index(page)
            if index > 10:
                self.logger.info("Browsed 10 pages without finding code %s,"
                "search aborted", ancode)
                return None
        return None


    def browse(self, outline,
        level=0,
        maintitle='',
        entrepreneur=''):
        """
        Recurses through outlines, yielding only when we have anaytic codes

        Yields tuple: entrepreneur, analytic code
        """
        for destination in outline:
            if isinstance(destination, Destination):
                title = destination.title
                if level == 2:
                    yield entrepreneur, title
                    continue
                if level == 0:
                    maintitle = title
                elif level == 1:
                    entrepreneur = title
                self.logger.info("||%s- %s", ' '*level, title)
            else:
                if isinstance(destination, Iterable):
                    for item in self.browse(destination,
                        level + 1,
                        maintitle,
                        entrepreneur):
                        yield item
                else:
                    self.logger.warning("Skipping entry of type %s" %
                        type(destination))

    def _tweak(self, pdfstream):
        # XXX optim: parse in separate processes/threads

        mkdir_p(self.output_dir, self.logger)

        with open(pdfstream.name, 'r') as duplicate_pdfstream:
            inputpdf = PdfFileReader(duplicate_pdfstream)

            pages_nb = inputpdf.getNumPages()
            if not self.pages_to_process:
                # 0 means no restriction
                self.pages_to_process = pages_nb

            self.logger.info("%s has %d pages", pdfstream.name, pages_nb)
            self.logger.info("Estimated time for completion of %d pages on "
            "an average computer: %.f seconds. Please stand while the parsing"
            " takes place.", self.pages_to_process, self._UNITARY_TIME*self.pages_to_process)

            start = time.clock()
            for index in xrange(self.pages_to_process):
                try:
                    identifier = self.get_identifier(pdfstream, index)
                except ValueNotFound, exc:
                    self.abort(exc)
                self.write_page(identifier, inputpdf)
            duration = time.clock() - start
            self.logger.info("Total duration: %s seconds, thank you for your patience",
                duration)

    def sanitize_validate(self, page, value, value_name):
        """
        Stops the process if the read value is detected incorrect.
        Dumps debug.xml for the current page

        We cannot validate names (known problem in IT) but we should try and
        sanitize input..
        """
        if value is not None:
            return unix_sanitize(value)

        self.logger.critical("invalid %s read: %s", value_name, value)
        raise ValueNotFound()

    def search(self, page, position_name):
        xpath_expr = self._XPATH_EXPR[position_name]
        for textbox in page.xpath(xpath_expr[0], **xpath_expr[1]):
            # sometimes, the first textbox is empty, we iterate.
            value = ''.join(etext.text
                for etext in textbox.xpath('text')
                ).strip()
            sanitized = self.sanitize_validate(page, unicode(value), position_name)

            return sanitized

        self.logger.critical('%s NOT FOUND at position %s', position_name, xpath_expr)
        raise ValueNotFound(page)

    def abort(self, exc):
        page = exc.args[0]
        debug_fname = 'debug-page_%s.xml' % page.get('id', 'PAGE_ID')
        with open(debug_fname, 'w') as debug_fd:
            debug_fd.write(etree.tostring(page))
        self.logger.critical("Aborting, page dumped to %s", debug_fname)
        self.logger.critical("Now halting for analysis")
        import sys
        sys.exit(4)


class Sheet(object):
    def __init__(self, p_nr, analytic, config, append=False):

        """
        :param int p_nr: 1 indexed page number -human numeration
        :param str analytic: analytic code
        :param config: Running config
        :type config: autosplit.config.Config
        """
        self.usertype = self.__class__.__name__.lower()
        self.logger = mk_logger('autosplit.%s' %
            self.usertype, config)
        self.p_nr = p_nr
        self.analytic = analytic or 'PAS-DE-CODE-ANALYTIQUE'
        self.append = append

        self.crea_info()

    def crea_info(self):
        if self.append:
            self.logger.info("page %d will be appended to the previous one")
            return
        self.logger.info("page %d is a %s for analytic_code %s",
            self.p_nr, self.usertype, self.analytic)

    def get_index(self):
        """
        :return: page nb, 0 indexed.
        """
        return self.p_nr - 1

    def _getfilename(self):
        return '%s.pdf' % self.analytic

    def getfilename(self, other=None):
        if other is not None:
            return other.getfilename()
        return self._getfilename()


class PaySheet(Sheet):
    def __init__(self, p_nr, analytic, name, config):
        """
        :param str name: firstname+lastname
        """
        self.name = name
        Sheet.__init__(self, p_nr, analytic, config)

    def crea_info(self):
        self.logger.info("page %d is a paysheet for %s, (analytic_code: %s)",
            self.p_nr, self.name, self.analytic)


    def _getfilename(self):
        return '%s_%s.pdf' % (self.analytic, self.name)


regexpNS = "http://exslt.org/regular-expressions"


class PayrollTweaker(PdfTweaker):
    _UNITARY_TIME = 2.3
    _DOCTYPE = 'salaire'
    _XPATH_EXPR = {
        'name': (
            'textbox[re:match(@bbox, "^[0-9]{3}.560,665.390")]/textline[1]',
            {'namespaces': {'re': regexpNS}}
            ),
        'analytic_code': (
            'textbox[re:match(@bbox, '
            '"^[0-9]{3}.560,684.911,[0-9]{3}.[0-9]{3},692.693")]/textline[1]',
            {'namespaces': {'re': regexpNS}}
            )
        }

    def get_identifier(self, pdfstream, pageindex):
        pdfstream.seek(0)
        tree = self._toxml(pdfstream, pageindex)
        page = tree.xpath('/pages/page')[0]
        self.logger.debug("Parsing XML for page %d", pageindex + 1)
        analytic_code = self.search(page, 'analytic_code')
        name = self.search(page, 'name')
        return PaySheet(pageindex + 1, analytic_code, name, self.config)


class SituationSheet(Sheet):
    pass

class SituationTweaker(PdfTweaker):
    _UNITARY_TIME = 0.4
    _DOCTYPE = 'tresorerie'
    _XPATH_EXPR = {
        'analytic_code': (
            'textbox[re:match(@bbox, '
            '"^25.671,[0-9]{3}.[0-9]{3},[0-9]{2}.[0-9]{3},5[0-9]{2}.[0-9]{3}")]'
            '/textline[1]',
            {'namespaces': {'re': regexpNS}}
            )
        }

    def get_identifier(self, pdfstream, pageindex):
        pdfstream.seek(0)
        tree = self._toxml(pdfstream, pageindex)
        page = tree.xpath('/pages/page')[0]
        self.logger.debug("Parsing XML for page %d", pageindex + 1)
        append = False
        try:
            analytic_code = self.search(page, 'analytic_code')
        except ValueNotFound:
            self.logger.warning('Value of analytic code not found on page %d.'
                'We bet it belongs to the previous page', pageindex + 1)
            analytic_code = None
            append = True
        identifier = SituationSheet(pageindex + 1, analytic_code, self.config,
            append=append)
        self.identifiers[pageindex] = identifier
        return identifier


class ResultSheet(Sheet):
    pass


class ResultTweaker(PdfTweaker):
    _UNITARY_TIME = 1
    _DOCTYPE = 'resultat'
    _XPATH_EXPR = {
        'analytic_code': (
            'textbox[re:match(@bbox, '
            '"^190.431,5[0-9]{2}.[0-9]{3},2[0-9]{2}.[0-9]{3},5[0-9]{2}.[0-9]{3}")]/textline[1]',
            {'namespaces': {'re': regexpNS}}
            )
        }

    I = 0
    def get_identifier(self, pdfstream, pageindex):
        pdfstream.seek(0)
        tree = self._toxml(pdfstream, pageindex)
        page = tree.xpath('/pages/page')[0]
        self.logger.debug("Parsing XML for page %d", pageindex + 1)
        try:
            analytic_code = self.search(page, 'analytic_code')
        except:
            if ResultTweaker.I > 0:
                raise
            ResultTweaker.I += 1
            analytic_code = None
        return ResultSheet(pageindex + 1, analytic_code, self.config)

class AutosplitError(Exception): pass


class ValueNotFound(AutosplitError): pass


DOC_TWEAKERS = {'salaire': PayrollTweaker, 'tresorerie': SituationTweaker,
    'resultat': ResultTweaker}
