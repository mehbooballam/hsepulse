"""Validated, portable company/project branding and report presentation helpers."""
import base64
import html
import io
import json
import re
from copy import deepcopy
from urllib.parse import urlsplit

COMPANY_KEY = 'company_branding'
MAX_LOGO_BYTES = 1024 * 1024
FIELDS = {
    'name': ('Display name', 160), 'website': ('Website', 300),
    'email': ('Contact email', 160), 'phone': ('Contact phone', 80),
    'contact_person': ('Contact person', 160), 'address': ('Address', 600),
    'contact_details': ('Additional contact details', 1200),
}


def upload_logo(content, filename='logo.png'):
    """Decode raster input, strip metadata and store a bounded PNG with transparency."""
    from PIL import Image, ImageOps, UnidentifiedImageError
    if not content or len(content) > MAX_LOGO_BYTES:
        raise ValueError('Choose a PNG or JPEG logo no larger than 1 MB.')
    try:
        with Image.open(io.BytesIO(content)) as source:
            if source.format not in ('PNG', 'JPEG'):
                raise ValueError('Logos must be PNG or JPEG images.')
            if source.width > 4096 or source.height > 4096 or source.width * source.height > 16000000:
                raise ValueError('Logo dimensions must be at most 4096 × 4096 and 16 million pixels.')
            source.load()
            image = ImageOps.exif_transpose(source).convert('RGBA')
            image.thumbnail((1200, 1200))
            output = io.BytesIO(); image.save(output, format='PNG', optimize=True)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValueError('The logo could not be read. Choose a valid PNG or JPEG.') from exc
    encoded = output.getvalue()
    if len(encoded) > MAX_LOGO_BYTES:
        raise ValueError('The optimized logo is too large. Use a simpler or smaller image.')
    return {'data': base64.b64encode(encoded).decode('ascii'), 'mime': 'image/png',
            'filename': str(filename).replace('\\', '/').rsplit('/', 1)[-1][:160],
            'width': image.width, 'height': image.height}


def profile(value=None):
    """Read optional legacy profiles without fetching external resources."""
    if isinstance(value, str):
        try: value = json.loads(value)
        except (ValueError, TypeError): value = {}
    return deepcopy(value) if isinstance(value, dict) else {}


def validate_profile(value):
    if not isinstance(value, dict): raise ValueError('Branding must be a profile object.')
    if set(value) - set(FIELDS) - {'logo'}: raise ValueError('Unknown branding field.')
    for key, (label, limit) in FIELDS.items():
        val = value.get(key, '')
        if not isinstance(val, str) or len(val) > limit:
            raise ValueError(f'{label} must contain no more than {limit} characters.')
    website = value.get('website', '')
    if website:
        parsed = urlsplit(website)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError('Website must be a complete http:// or https:// address.')
    email = value.get('email', '')
    if email and not re.fullmatch(r'[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+', email):
        raise ValueError('Enter a valid contact email address.')
    logo = value.get('logo')
    if logo:
        if not isinstance(logo, dict) or not isinstance(logo.get('data'), str) or len(logo['data']) > 1400000:
            raise ValueError('Invalid logo data.')
        try: raw = base64.b64decode(logo['data'], validate=True)
        except (ValueError, TypeError) as exc: raise ValueError('Invalid logo data.') from exc
        if not raw.startswith(b'\x89PNG\r\n\x1a\n'): raise ValueError('Stored logos must be PNG images.')
        checked = upload_logo(raw, logo.get('filename', 'logo.png'))
        if logo.get('mime') != 'image/png' or any(logo.get(k) != checked[k] for k in ('width', 'height')):
            raise ValueError('Invalid logo metadata.')
    return value


def company_profile(tables):
    return profile(next((r.get('value') for r in tables.get('Settings', []) if r.get('id') == COMPANY_KEY), None))


def project_profile(project):
    return profile(project.get('branding'))


def logo_bytes(value):
    logo = value.get('logo')
    if not logo: return None
    try:
        raw = base64.b64decode(logo['data'], validate=True)
        if logo.get('mime') == 'image/png' and len(raw) <= MAX_LOGO_BYTES: return raw
    except (KeyError, TypeError, ValueError): pass
    return None


def report_profiles(tables, project=None):
    """Closed reports use frozen branding; old closures have an empty profile."""
    source = tables
    if project and project.get('status') == 'Closed':
        source = profile(project.get('closure_context'))
    return {'company': company_profile(source), 'project': project_profile(project or {})}


def text_summary(value):
    result = profile(value)
    if result.get('logo'):
        result['logo'] = 'Included as an image; original data retained in the project-data.json attachment.'
    return json.dumps(result, ensure_ascii=False)


def contact_rows(profiles):
    rows = []
    for level, item in profiles.items():
        for key, (label, _) in FIELDS.items():
            if item.get(key): rows.append((level.title() + ' - ' + label, item[key]))
    return rows


def html_header(profiles, project_name=''):
    """Self-contained report header; no remote image loads or unescaped user HTML."""
    def side(level, fallback):
        item = profiles.get(level, {})
        logo = logo_bytes(item)
        img = '<img alt="'+level+' logo" style="max-width:180px;max-height:72px;object-fit:contain" src="data:image/png;base64,'+base64.b64encode(logo).decode()+'"/>' if logo else ''
        return img + '<div style="font-weight:bold;margin-top:8px">'+html.escape(item.get('name') or fallback)+'</div>'
    header = '<header style="display:flex;justify-content:space-between;align-items:center;gap:32px;border-bottom:2px solid #147d83;padding-bottom:18px;margin-bottom:24px"><div>'+side('company', 'HSE Pulse')+'</div><div style="text-align:right">'+side('project', project_name)+'</div></header>'
    details = contact_rows(profiles)
    if details:
        header += '<section><h2>Report contact details</h2><table>'+''.join('<tr><th style="text-align:left">'+html.escape(k)+'</th><td>'+html.escape(v).replace('\n','<br/>')+'</td></tr>' for k,v in details)+'</table></section>'
    return header


def draw_pdf_header(canvas, profiles, project_name, width=595):
    """Repeated dual branding; preserve aspect ratio and reserve body space."""
    from reportlab.lib.utils import ImageReader
    from reportlab.lib import colors
    from reportlab.pdfbase.pdfmetrics import stringWidth
    canvas.saveState()
    top = 842
    for side, left, fallback in [('company', 48, 'HSE Pulse'), ('project', width - 208, project_name)]:
        item = profiles.get(side, {}); raw = logo_bytes(item)
        if raw:
            im = ImageReader(io.BytesIO(raw)); iw, ih = im.getSize(); scale = min(145/iw, 42/ih)
            canvas.drawImage(im, left if side=='company' else left+160-iw*scale,
                             top-70, width=iw*scale, height=ih*scale, mask='auto')
        name = item.get('name') or fallback
        while stringWidth(name, 'Helvetica-Bold', 9) > 228: name = name[:-2] + '…'
        canvas.setFillColor(colors.HexColor('#164d56')); canvas.setFont('Helvetica-Bold',9)
        if side=='company': canvas.drawString(left, top-86, name)
        else: canvas.drawRightString(width-48, top-86, name)
    canvas.setStrokeColor(colors.HexColor('#c7d4da')); canvas.line(48,top-98,width-48,top-98)
    canvas.restoreState()
