"""Complete, paginated project closure PDF with vector charts and evidence."""
import base64
from collections import Counter, defaultdict
from datetime import date, datetime
import io
import json
from xml.sax.saxutils import escape as xml_escape
import enterprise as e


def closure_pdf(tables, project):
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.utils import ImageReader
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, LongTable, TableStyle, PageBreak, Image
    from reportlab.graphics.shapes import Drawing, Rect, String

    if project.get('status') != 'Closed':
        raise ValueError('A closure report is available only for a closed project.')
    now = datetime.fromisoformat(project['closed_at'])
    context = json.loads(project['closure_context'])
    scoped = {table: [r for r in tables.get(table, []) if r.get('Project', r.get('project')) == project['id']]
              for table in (*e.FORMS, 'Evidence', 'AlertState')}
    t = {**scoped, **context, 'Projects': [project]}
    dates = [str(r.get('Date') or r.get('Date Raised') or '')[:10] for table in e.FORMS for r in t[table]]
    dates = [date.fromisoformat(d) for d in dates if d]
    start = min(dates + [now.date()])
    # Include every dated record, even a planned activity after closure.
    end = max(dates + [now.date()])
    metrics = e.metrics(t, start, now.date(), project['id'], now=now)
    alerts = e.alerts(t, now)
    output = io.BytesIO()
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='Cell', fontName='Helvetica', fontSize=8, leading=11, wordWrap='CJK'))
    styles.add(ParagraphStyle(name='SmallNote', fontName='Helvetica', fontSize=9, leading=13))
    story = []
    def p(value, style='Cell'):
        text = json.dumps(value, ensure_ascii=False, sort_keys=True) if isinstance(value, (list, dict)) else str(value if value is not None else 'Not reported')
        return Paragraph(xml_escape(text).replace('\n', '<br/>'), styles[style])
    def heading(text):
        story.extend([Spacer(1, 10), p(text, 'Heading2')])
    def table(headers, rows, widths):
        data = [[p(c) for c in headers]] + [[p(c) for c in row] for row in rows]
        grid = LongTable(data, colWidths=widths, repeatRows=1, splitInRow=1, hAlign='LEFT')
        grid.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#dbece8')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f3f6f8')]),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('GRID', (0, 0), (-1, -1), .3, colors.HexColor('#c7d4da')),
            ('LEFTPADDING', (0, 0), (-1, -1), 7), ('RIGHTPADDING', (0, 0), (-1, -1), 7),
            ('TOPPADDING', (0, 0), (-1, -1), 5), ('BOTTOMPADDING', (0, 0), (-1, -1), 5)]))
        story.append(grid)
    def chart(title, values, maximum=None):
        heading(title)
        if not values:
            story.append(p('No records reported.', 'SmallNote')); return
        width = 499
        d = Drawing(width, len(values) * 23 + 22)
        scale = maximum or max([float(v) for _, v in values] + [1]) or 1
        for i, (label, value) in enumerate(values):
            y = d.height - 24 - i * 23
            d.add(String(0, y + 3, label, fontName='Helvetica', fontSize=8))
            d.add(Rect(190, y, max(0, min(265, 265 * float(value) / scale)), 13, fillColor=colors.HexColor('#168563'), strokeColor=None))
            d.add(String(463, y + 3, f'{value:,.1f}' if isinstance(value, float) else str(value), fontSize=8))
        story.append(d)

    story.append(p('HSE PULSE', 'Heading2'))
    story.append(p('Project completion & closure report', 'Title'))
    story.append(p(project['name'], 'Heading1'))
    table(['Project detail', 'Value'], [(k, v) for k, v in project.items() if k != 'closure_context'], [145, 354])
    heading('Scope and interpretation')
    story.append(p(f'All saved project records are included, dated {start} to {end}. KPIs cover {start} through closure on {now.date()}; time-sensitive indicators are evaluated at {now.isoformat()}. Future-dated plans are retained in the registers. Missing values are not evidence of compliance. Closure does not automatically resolve outstanding actions.', 'SmallNote'))
    story.append(p('TRIR = recordables × 200,000 / man-hours; LTIFR = LTI × 1,000,000 / man-hours; severity = lost workdays × 1,000,000 / man-hours. Rates require exposure reports for each incident date. Assurance is the equal-weight mean of available control percentages; missing controls are excluded and coverage is shown. The score is provisional, not a certification.', 'SmallNote'))
    heading('KPI summary at closure')
    table(['Indicator', 'Value'], [(k, f'{v:,.2f}' if isinstance(v, float) else v) for k, v in metrics.items() if k != 'controls'], [300, 199])
    chart('Control assurance (%)', [(k, v) for k, v in metrics['controls'].items() if v is not None], 100)
    story.append(p('Unreported control areas: ' + (', '.join(k for k, v in metrics['controls'].items() if v is None) or 'None'), 'SmallNote'))
    chart('Incident types', sorted(Counter(r.get('Incident Type') or 'Unspecified' for r in t['05_INCIDENTS']).items()))
    chart('Corrective action status', sorted(Counter(r.get('Status') or 'Unspecified' for r in t['08_ACTIONS']).items()))
    months = defaultdict(float)
    for r in t['03_DAILY_REPORT']:
        months[str(r.get('Date', 'Undated'))[:7]] += e.n(r, 'Man-hours')
    for offset in range(0, len(months), 18):
        chart('Monthly exposure (man-hours)', sorted(months.items())[offset:offset + 18])
    heading('Outstanding alerts at closure')
    if alerts:
        table(['Level', 'Register / record', 'Issue', 'Responsible'], [(a['Level'], a['Register'] + ' / ' + a['Record'], a['Issue'], a['Responsible']) for a in alerts], [45, 145, 209, 100])
    else: story.append(p('No alert rules triggered at closure.'))
    heading('Register inventory')
    table(['Register', 'Records'], [(e.LABELS[table], len(t[table])) for table in e.FORMS], [400, 99])
    for name in (*e.FORMS, 'AlertState', 'Standards', 'Settings'):
        rows = t[name]
        if rows: story.append(PageBreak())
        heading(e.LABELS.get(name, name))
        if not rows:
            story.append(p('No records reported.')); continue
        for index, record in enumerate(rows, 1):
            heading(f"{index}. {record.get('Record ID') or record.get('id', '')}")
            # Field/value tables retain all fields without squeezing wide registers.
            keys = list(dict.fromkeys(e.SCHEMAS.get(name, []) + list(record)))
            table(['Field', 'Value'], [(key, record.get(key, '')) for key in keys], [145, 354])
    story.append(PageBreak())
    heading('Uploaded evidence')
    groups = defaultdict(list)
    for record in t['Evidence']:
        groups[record['id'].rsplit('-', 1)[0]].append(record)
    if not groups: story.append(p('No uploaded evidence. External evidence URLs are listed in the record tables; remote content is not downloaded.'))
    for key, chunks in sorted(groups.items()):
        chunks.sort(key=lambda r: int(r['chunk']))
        heading(chunks[0].get('filename', key))
        for chunk in chunks:
            table(['Evidence metadata', 'Value'], [(k, v) for k, v in chunk.items() if k != 'content'], [145, 354])
        try:
            raw = base64.b64decode(''.join(c['content'] for c in chunks), validate=True)
            w, h = ImageReader(io.BytesIO(raw)).getSize()
            factor = min(499 / w, 500 / h, 1)
            story.append(Image(io.BytesIO(raw), width=w * factor, height=h * factor))
        except Exception:
            story.append(p('Evidence could not be rendered. Original chunks are preserved in the attached project data.'))
    def footer(canvas, doc):
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(colors.HexColor('#536777'))
        canvas.drawString(48, 25, 'HSE Pulse | Project closure report')
        canvas.drawRightString(547, 25, f'Page {doc.page}')
    SimpleDocTemplate(output, pagesize=(595, 842), rightMargin=48, leftMargin=48,
                      topMargin=42, bottomMargin=42, title=project['name'] + ' - Closure report').build(story, onFirstPage=footer, onLaterPages=footer)
    # Lossless appendix also preserves Unicode, original evidence bytes and additional fields.
    from pypdf import PdfReader, PdfWriter
    writer = PdfWriter(clone_from=PdfReader(io.BytesIO(output.getvalue())))
    writer.add_attachment('project-data.json', json.dumps(t, ensure_ascii=False, indent=2).encode('utf-8'))
    final = io.BytesIO(); writer.write(final)
    return final.getvalue()
