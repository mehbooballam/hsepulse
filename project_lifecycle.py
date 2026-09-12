"""Project lifecycle rules shared by UI and server-side mutation boundaries."""
import json
from datetime import datetime
from domain import TZ

TERMINAL = {'Closed', 'Deleted'}
STATUSES = ['Active', 'Inactive', 'On Hold', 'Closed', 'Deleted']


def validate_changes(tables, changes):
    projects = {p['id']: p for p in tables.get('Projects', [])}
    for table, rows in changes.items():
        current = {r['id']: r for r in tables.get(table, [])}
        for row in rows:
            previous = current.get(row['id'], {})
            merged = {**previous, **row}
            if table == 'Projects':
                status = merged.get('status', 'Active')
                if previous.get('status') == 'Deleted':
                    raise ValueError('Deleted projects cannot be changed or reused.')
                if previous.get('status') == 'Closed' and status != 'Deleted':
                    raise ValueError('Closed projects are read-only.')
                if status not in STATUSES or not str(merged.get('name', '')).strip():
                    raise ValueError('Enter a project name and valid status.')
                if status in TERMINAL and not previous:
                    raise ValueError('Create the project before closing or deleting it.')
                if status == 'Closed' and not all(merged.get(k) for k in ('closed_at', 'closed_by', 'closure_notes', 'closure_context')):
                    raise ValueError('Completion requires closure details.')
                if status == 'Deleted' and not all(merged.get(k) for k in ('deleted_at', 'deleted_by')):
                    raise ValueError('Deletion requires recorded confirmation.')
            else:
                for record in (previous, merged):
                    project = record.get('Project', record.get('project'))
                    if projects.get(project, {}).get('status') in TERMINAL:
                        raise ValueError('Closed or deleted projects are read-only.')
                    if any(p['id'] == project and p.get('status') in TERMINAL for p in changes.get('Projects', [])):
                        raise ValueError('Save operational changes before closing the project.')


def close_project(project, tables, actor, notes):
    if not notes.strip():
        raise ValueError('Enter completion notes, including any outstanding handover items.')
    return {**project, 'status': 'Closed', 'closed_at': datetime.now(TZ).isoformat(),
            'closed_by': actor, 'closure_notes': notes.strip(),
            'closure_context': json.dumps({k: tables.get(k, []) for k in ('Settings', 'Standards')})}


def delete_project(project, actor):
    return {**project, 'status': 'Deleted', 'deleted_at': datetime.now(TZ).isoformat(), 'deleted_by': actor}


def visible_tables(tables):
    deleted = {p['id'] for p in tables.get('Projects', []) if p.get('status') == 'Deleted'}
    return {table: [r for r in rows if not (table == 'Projects' and r['id'] in deleted)
                    and r.get('Project', r.get('project')) not in deleted]
            for table, rows in tables.items()}
