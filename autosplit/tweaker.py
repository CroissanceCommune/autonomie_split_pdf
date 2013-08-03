from cStringIO import StringIO
from lxml import etree
import os.path
import re
import time
import unicodedata

from pdfminer.pdfinterp import PDFResourceManager, process_pdf
from pdfminer.converter import XMLConverter
from pdfminer.layout import LAParams
from pyPdf import PdfFileWriter, PdfFileReader

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
        self.output_dir = os.path.join(self._DOCTYPE, self.year, self.month)
        self.cached_load = False
        self.pages_to_process = self.config.getvalue('restrict')
        for index, (name, expr) in enumerate(self._XPATH_EXPR.iteritems()):
            self.logger.debug("[%d] xpath expression for %s: %s", index, name, expr[0])


    def _toxml(self, pdfstream, pageno=0):
        retstr = StringIO()
        self.logger.debug("Converting to xml")
        start_time = time.clock()
        device = XMLConverter(self.rsrcmgr, retstr, codec='utf-8',
        laparams=self.laparams, pageno=pageno)

        if not self.cached_load:
            self.logger.info("First pass on pdf file is longer. "
            "Next iterations will be faster")
            self.logger.info("Estimated time for completion on "
            "an average computer: %.f seconds. Please stand while the parsing"
            " takes place.", 2.3*self.pages_to_process)

        process_pdf(self.rsrcmgr, device, pdfstream, maxpages=1, pagenos=(pageno,))

        device.close()
        self.cached_load = True
        duration = time.clock() - start_time
        self.logger.debug("Conversion to xml took %s seconds.", duration)
        retstr.seek(0)
        tree = etree.parse(retstr)
        retstr.close()
        return tree

    def write_page(self, index, identifier, inputpdf):
        output = PdfFileWriter()
        output.addPage(inputpdf.getPage(index))
        output_file = os.path.join(self.output_dir, identifier.getfilename())
        self.logger.debug("Writing %s", output_file)
        outputStream = file(output_file, "wb")
        output.write(outputStream)
        outputStream.close()
        self.logger.info("Wrote %s", output_file)

    def tweak(self, pdfstream):
        # XXX optim: parse in separate processes/threads

        mkdir_p(self.output_dir)

        with open(pdfstream.name, 'r') as duplicate_pdfstream:
            inputpdf = PdfFileReader(duplicate_pdfstream)

            pages_nb = inputpdf.getNumPages()
            if not self.pages_to_process:
                # 0 means no restriction
                self.pages_to_process = pages_nb

            self.logger.info("%s has %d pages", pdfstream.name, pages_nb)
            for index in xrange(self.pages_to_process):
                identifier = self.get_identifier(pdfstream, index)
                self.write_page(index, identifier, inputpdf)

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
        self.abort(page)

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
        self.abort(page)

    def abort(self, page):
        debug_fname = 'debug-page_%s.xml' % page.get('id', 'PAGE_ID')
        with open(debug_fname, 'w') as debug_fd:
            debug_fd.write(etree.tostring(page))
        self.logger.critical("Aborting, page dumped to %s", debug_fname)
        self.logger.critical("Now halting for analysis")
        import sys
        sys.exit(4)


class PaySheet(object):
    def __init__(self, p_index, analytic, name, config):
        self.logger = mk_logger('autosplit.payroll', config)
        self.p_index = p_index
        self.analytic = analytic or 'PAS-DE-CODE-ANALYTIQUE'
        self.name = name
        self.logger.info("page %d is a paysheet for %s, (analytic_code: %s)",
            p_index, name, analytic)

    def getfilename(self):
        return '%s_%s.pdf' % (self.analytic, self.name)


regexpNS = "http://exslt.org/regular-expressions"


class PayrollTweaker(PdfTweaker):
    _DOCTYPE = 'salaires'
    _XPATH_EXPR = {
        'name': (
            'textbox[re:match(@bbox, "^[0-9]{3}.560,665.390")]/textline[1]',
            {'namespaces': {'re': regexpNS}}
            ),
        'analytic_code': (
            'textbox[re:match(@bbox, "^[0-9]{3}.560,684.911,[0-9]{3}.[0-9]{3},692.693")]/textline[1]',
            {'namespaces': {'re': regexpNS}}
            )
        }

    def get_identifier(self, pdfstream, pageindex):
        pdfstream.seek(0)
        tree = self._toxml(pdfstream, pageno=pageindex)
        page = tree.xpath('/pages/page')[0]
        self.logger.debug("Parsing XML for page %d", pageindex + 1)
        analytic_code = self.search(page, 'analytic_code')
        name = self.search(page, 'name')
        return PaySheet(pageindex + 1, analytic_code, name, self.config)


class AutosplitError(Exception): pass


class ValueNotFound(AutosplitError): pass


DOC_TWEAKERS = {'salaires': PayrollTweaker}
