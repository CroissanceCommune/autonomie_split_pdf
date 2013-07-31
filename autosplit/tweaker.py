from cStringIO import StringIO
from lxml import etree
import re
from tempfile import mkdtemp
import time
import unicodedata

from pdfminer.pdfinterp import PDFResourceManager, process_pdf
from pdfminer.converter import TextConverter, XMLConverter
from pdfminer.layout import LAParams

from .log_config import mk_logger


_UNIX_VALID = re.compile('[^\w\s-]')
_NOSPACES = re.compile('[-\s]+')


def unix_sanitize(some_name):
    value = unicodedata.normalize('NFKD', some_name).encode('ascii', 'ignore')
    value = unicode(_UNIX_VALID.sub('', value).strip())
    return _NOSPACES.sub('-', value)


class PdfTweaker(object):
    def __init__(self, config):
        self.logger = mk_logger('autosplit.tweaker', config)
        self.config = config
        self.rsrcmgr = PDFResourceManager()
        self.laparams = LAParams()

    def _toxml(self, pdfstream):
        retstr = StringIO()
#        self.logger.debug("Converting to text")
#        device = TextConverter(rsrcmgr, retstr, codec='utf-8', laparams=laparams)
        self.logger.debug("Converting to xml")
        start_time = time.clock()
        device = XMLConverter(self.rsrcmgr, retstr, codec='utf-8',
        laparams=self.laparams)

        process_pdf(self.rsrcmgr, device, pdfstream,
            maxpages=self.config.getvalue('restrict'))
        pdfstream.close()
        device.close()
        duration = time.clock() - start_time
        self.logger.debug("Conversion to xml took %s seconds.", duration)
#        bigstring = retstr.getvalue()
        retstr.seek(0)
        tree = etree.parse(retstr)
        retstr.close()
        return tree

    def tweak(self, pdfstream):
        identifiers = tuple(self.get_identifiers(pdfstream))
#        pdfstream.seek(0)





    def write_pages(self, pdf, workdir):
        for index, page in enumerate(pdf.pages):
            text = page.extractText()
            print '[%3i]' % index, text
            writer = PdfFileWriter()

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
        self.logger.debug("xpath expression: %s", xpath_expr[0])
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
        self.analytic = analytic
        self.name = name
        self.logger.info("Payroll: page %d, analytic_code: %s, for %s",
            p_index, analytic, name)


regexpNS = "http://exslt.org/regular-expressions"


class PayrollTweaker(PdfTweaker):
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

    def get_identifiers(self, pdfstream):
        pdfstream.seek(0)
        tree = self._toxml(pdfstream)
        for index, page in enumerate(tree.xpath('/pages/page')):
            self.logger.info("Page %s", index + 1)
            analytic_code = self.search(page, 'analytic_code')
            name = self.search(page, 'name')
            yield PaySheet(index + 1, analytic_code, name, self.config)


class AutosplitError(Exception): pass


class ValueNotFound(AutosplitError): pass
