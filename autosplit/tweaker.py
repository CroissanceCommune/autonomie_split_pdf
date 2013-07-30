from tempfile import mkdtemp
from cStringIO import StringIO
from lxml import etree
import time

from pdfminer.pdfinterp import PDFResourceManager, process_pdf
from pdfminer.converter import TextConverter, XMLConverter
from pdfminer.layout import LAParams

from .log_config import mk_logger


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
        raise NotImplementedError()


    def write_pages(self, pdf, workdir):
        for index, page in enumerate(pdf.pages):
            text = page.extractText()
            print '[%3i]' % index, text
            writer = PdfFileWriter()

class PayrollTweaker(PdfTweaker):

    def search(self, page):
        for textbox in page.xpath("textbox"):
            bbox_value = textbox.get("bbox", None)
            if not bbox_value.startswith("196"):
                # I'd rather use an xpath like
                # 'textbox[bbox="196.560,684.911,234.526,692.693"]'
                # than this if statement, # but I can't get it to work :'(
                continue
            analytic_code = ''.join(etext.text
                for etext in textbox.xpath('textline[1]/text')
                ).strip()
            self.logger.debug("guessing name: %s in bbox %s", analytic_code, bbox_value)
            return analytic_code

    def tweak(self, pdfstream):
        tree = self._toxml(pdfstream)
        for index, page in enumerate(tree.xpath('/pages/page')):
            self.logger.debug("Page %s", index + 1)
            analytic_code = self.search(page)
            if analytic_code is None or not analytic_code.isalnum():
                debug_fname = 'debug.xml'
                self.logger.critical("invalid analytic_code read: %s",
                analytic_code)
                with open(debug_fname, 'w') as debug_fd:
                    debug_fd.write(etree.tostring(page))
                self.logger.critical("error decoding analytic code, "
                    "page dumped to %s", debug_fname)
                self.logger.critical("Now halting for analysis")
                import sys
                sys.exit(4)
            self.logger.info("found analytic_code: %s", analytic_code)
#        print bigstring
        return
