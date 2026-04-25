from pathlib import Path
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase import pdfmetrics
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak

root = Path('/Users/peng/Documents/trae_projects/TremorGuard')
source = root / 'output/pdf/tremorguard_2h_lecture_script.md'
out = root / 'output/pdf/tremorguard_2h_lecture_script.pdf'

pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))

styles = getSampleStyleSheet()
base_font = 'STSong-Light'

styles.add(ParagraphStyle(
    name='CJKTitle',
    parent=styles['Title'],
    fontName=base_font,
    fontSize=22,
    leading=28,
    alignment=TA_CENTER,
    textColor=HexColor('#0f172a'),
    spaceAfter=10,
))
styles.add(ParagraphStyle(
    name='CJKSubtitle',
    parent=styles['Heading2'],
    fontName=base_font,
    fontSize=13,
    leading=18,
    alignment=TA_CENTER,
    textColor=HexColor('#334155'),
    spaceAfter=18,
))
styles.add(ParagraphStyle(
    name='CJKH1',
    parent=styles['Heading1'],
    fontName=base_font,
    fontSize=16,
    leading=22,
    textColor=HexColor('#0f172a'),
    spaceBefore=12,
    spaceAfter=8,
))
styles.add(ParagraphStyle(
    name='CJKH2',
    parent=styles['Heading2'],
    fontName=base_font,
    fontSize=13,
    leading=18,
    textColor=HexColor('#1e293b'),
    spaceBefore=10,
    spaceAfter=6,
))
styles.add(ParagraphStyle(
    name='CJKBody',
    parent=styles['BodyText'],
    fontName=base_font,
    fontSize=10.5,
    leading=16,
    alignment=TA_LEFT,
    textColor=HexColor('#334155'),
    spaceAfter=5,
))
styles.add(ParagraphStyle(
    name='CJKBullet',
    parent=styles['BodyText'],
    fontName=base_font,
    fontSize=10.5,
    leading=15,
    leftIndent=12,
    firstLineIndent=-10,
    textColor=HexColor('#334155'),
    spaceAfter=3,
))
styles.add(ParagraphStyle(
    name='CJKSmall',
    parent=styles['BodyText'],
    fontName=base_font,
    fontSize=9,
    leading=13,
    alignment=TA_CENTER,
    textColor=HexColor('#64748b'),
    spaceBefore=12,
))


def esc(text: str) -> str:
    return (
        text.replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
        .replace('\n', '<br/>')
    )


def add_page_number(canvas, doc):
    canvas.setFont(base_font, 9)
    canvas.setFillColor(HexColor('#64748b'))
    canvas.drawCentredString(A4[0] / 2, 10 * mm, f'TremorGuard 讲课稿  第 {doc.page} 页')


story = []
lines = source.read_text(encoding='utf-8').splitlines()
first_h1 = True
for raw in lines:
    line = raw.rstrip()
    if not line:
        story.append(Spacer(1, 4))
        continue
    if line == '---':
        story.append(Spacer(1, 6))
        story.append(PageBreak())
        continue
    if line.startswith('# '):
        text = esc(line[2:].strip())
        if first_h1:
            story.append(Spacer(1, 20))
            story.append(Paragraph(text, styles['CJKTitle']))
            first_h1 = False
        else:
            story.append(Paragraph(text, styles['CJKH1']))
        continue
    if line.startswith('## '):
        story.append(Paragraph(esc(line[3:].strip()), styles['CJKH1']))
        continue
    if line.startswith('### '):
        story.append(Paragraph(esc(line[4:].strip()), styles['CJKH2']))
        continue
    if line.startswith('#### '):
        story.append(Paragraph(esc(line[5:].strip()), styles['CJKBody']))
        continue
    if line.startswith('- '):
        story.append(Paragraph(f'• {esc(line[2:].strip())}', styles['CJKBullet']))
        continue
    numbered = False
    for i in range(1, 10):
        prefix = f'{i}. '
        if line.startswith(prefix):
            story.append(Paragraph(esc(line), styles['CJKBullet']))
            numbered = True
            break
    if numbered:
        continue
    story.append(Paragraph(esc(line), styles['CJKBody']))

story.append(Spacer(1, 10))
story.append(Paragraph('打印建议：A4 单面打印；如需课堂批注，可选择双倍行距版本另行导出。', styles['CJKSmall']))

doc = SimpleDocTemplate(
    str(out),
    pagesize=A4,
    leftMargin=18 * mm,
    rightMargin=18 * mm,
    topMargin=18 * mm,
    bottomMargin=18 * mm,
    title='TremorGuard 2 小时详细讲课稿',
    author='Codex',
)
doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)
print(out)
