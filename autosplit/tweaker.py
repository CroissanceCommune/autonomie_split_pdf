from tempfile import mkdtemp
from cStringIO import StringIO

from pdfminer.pdfinterp import PDFResourceManager, process_pdf
from pdfminer.converter import TextConverter, XMLConverter
from pdfminer.layout import LAParams

from .log_config import mk_logger


class PdfTweaker(object):
    def __init__(self, config):
        self.logger = mk_logger('autosplit.tweaker', config)
        self.config = config

    def tweak(self, pdfstream):
        rsrcmgr = PDFResourceManager()
        retstr = StringIO()
        laparams = LAParams()
        device = TextConverter(rsrcmgr, retstr, codec='utf-8', laparams=laparams)
#        device = XMLConverter(rsrcmgr, retstr, codec='utf-8', laparams=laparams)

        process_pdf(rsrcmgr, device, pdfstream, maxpages=1)
        pdfstream.close()
        device.close()

        bigstring = retstr.getvalue()
        retstr.close()
        print bigstring
        return


        pages_nb = pdf_reader.getNumPages()
        self.logger.debug('%s has %d pages', pdfstream.name, pages_nb)
        if pages_nb < 2:
            self.logger.warning("Pages nb is < 2, nothing can be done")
            return
        tempworkdir = mkdtemp(prefix="autosplit_")
        for tempname in self.write_pages(pdf_reader, tempworkdir):
            good_filename = self.analyse(tempname)
            self.storefile(tempname, good_filename)


    def write_pages(self, pdf, workdir):
        for index, page in enumerate(pdf.pages):
            text = page.extractText()
            print '[%3i]' % index, text
            writer = PdfFileWriter()


