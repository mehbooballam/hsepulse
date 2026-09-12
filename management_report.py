"""Self-contained printable management reports with two-level branding."""
import html
import pandas as pd
from branding import html_header, validate_profile


def management_html(start, end, generated, mode, matrix, alerts, decisions, profiles, project_name=''):
    for value in profiles.values(): validate_profile(value)
    title = (project_name + ' - Management review') if project_name else 'Corporate HSE management review'
    style = 'body{font:14px Arial;padding:32px;color:#183747}table{border-collapse:collapse;width:100%;margin:16px 0}th,td{padding:8px;border:1px solid #ddd;overflow-wrap:anywhere}th{background:#164d56;color:white}img{max-width:100%}@media print{body{padding:0}thead{display:table-header-group}tr{break-inside:avoid}}'
    return ('<!doctype html><html><head><meta charset="utf-8"><title>'+html.escape(title)+'</title><style>'+style+'</style></head><body>'
            +html_header(profiles,project_name)+'<h1>'+html.escape(title)+'</h1><p>'+html.escape(f'{start} to {end} · Generated {generated} · {mode}')
            +'</p><p>Scores are provisional control assurance; review coverage. Alerts show current status. Report contact details apply to this copy.</p>'
            +pd.DataFrame(matrix).to_html(index=False,escape=True)+'<h2>Action required</h2>'
            +pd.DataFrame(alerts[:10]).to_html(index=False,escape=True)+'<h2>Corporate decisions</h2>'
            +pd.DataFrame(decisions).to_html(index=False,escape=True)+'</body></html>')
