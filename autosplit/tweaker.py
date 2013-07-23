from tempfile import mkdtemp
from cStringIO import StringIO
from lxml import etree

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
#        self.logger.debug("Converting to text")
#        device = TextConverter(rsrcmgr, retstr, codec='utf-8', laparams=laparams)
        self.logger.debug("Converting to xml")
        device = XMLConverter(rsrcmgr, retstr, codec='utf-8', laparams=laparams)

        # FIXME: remove maxpages in production
        process_pdf(rsrcmgr, device, pdfstream, maxpages=3)
        pdfstream.close()
        device.close()
#        bigstring = retstr.getvalue()
        retstr.seek(0)
        tree = etree.parse(retstr)
        retstr.close()
        for index, page in enumerate(tree.xpath('/pages/page')):
            elt_id = 0 if index else 2  # first page has edition date and title
            r = page.xpath('textbox[@id="%d"]/textline/text' % elt_id)
            name = ''.join(etext.text for etext in r).strip()
            if '\n' in name:
                debug_fname = 'debug.xml'
                with open(debug_fname, 'w') as debug_fd:
                    debug_fd.write(etree.tostring(page))
                self.logger.critical("error decoding name, page dumped to %s",
                                    debug_fname)
                self.logger.critical("Now halting for analysis")
                import sys
                sys.exit(4)
            self.logger.info("found name: %s", name)
#        print bigstring
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


