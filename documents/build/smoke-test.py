import subprocess
from docx import Document
from pypdf import PdfReader
import pdfplumber, reportlab, openpyxl, pptx, PIL

document = Document()
document.add_paragraph('Sandbox document smoke test')
document.save('/tmp/smoke.docx')
subprocess.run(['libreoffice', '-env:UserInstallation=file:///tmp/lo-profile', '--headless', '--convert-to', 'pdf', '--outdir', '/tmp', '/tmp/smoke.docx'], check=True)
assert len(PdfReader('/tmp/smoke.pdf').pages) == 1
for command in [['pdftotext', '-v'], ['tesseract', '--version']]:
    subprocess.run(command, check=True)
print('Office conversion, PDF parsing and OCR tools passed')
