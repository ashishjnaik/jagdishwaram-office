"""
home.py — Public portal and Case Library (Project Kurukshetra).

Routes:
  GET  /                           — home page
  GET  /docs/<filename>            — serve docs directory
  GET  /kurukshetra                — Case Library (passphrase-gated; public subset if no auth)
  POST /kurukshetra/auth           — passphrase submit
  PATCH /api/kurukshetra/<id>/labels   — add/remove authority code or custom label
  PATCH /api/kurukshetra/<id>/context  — update Context & Findings
  PATCH /api/kurukshetra/<id>/date     — set document_date
  PATCH /api/kurukshetra/<id>/private  — toggle is_private flag
  POST  /api/kurukshetra/link          — create a Document Link
  DELETE /api/kurukshetra/link/<link_id> — remove a Document Link
  POST  /api/kurukshetra/rebuild-cache — trigger cache rebuild (auth-gated)
"""

import io
import json
import os
import time
from datetime import datetime, timezone

from flask import (
    Blueprint, jsonify, redirect, render_template,
    request, send_from_directory, session, url_for,
)

home_bp = Blueprint('home', __name__)

_DOCS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'docs'))
_KURUKSHETRA_PASSPHRASE = os.environ.get('KURUKSHETRA_PASSPHRASE', '')

# ── Zoho config ───────────────────────────────────────────────────────────────

_ZOHO_CLIENT_ID     = os.environ.get('ZOHO_CLIENT_ID', '')
_ZOHO_CLIENT_SECRET = os.environ.get('ZOHO_CLIENT_SECRET', '')
_ZOHO_REFRESH_TOKEN = os.environ.get('ZOHO_REFRESH_TOKEN', '')
_ZOHO_OWNER         = os.environ.get('ZOHO_OWNER', '')
_ZOHO_APP_NAME      = os.environ.get('ZOHO_APP_NAME', '')
_ZOHO_ACCOUNTS_URL  = 'https://accounts.zoho.com/oauth/v2/token'

_FORM_ENRICHMENT = 'Case_Library_Enrichment'
_REPORT_ENRICHMENT = 'Case_Library_Enrichment_Report'
_FORM_LINKS = 'Case_Library_Links'
_REPORT_LINKS = 'Case_Library_Links_Report'

# ── Google Drive / cache config ───────────────────────────────────────────────

_GOOGLE_USER_TOKEN     = os.environ.get('GOOGLE_USER_TOKEN', '')
_GOOGLE_QUOTA_USER     = os.environ.get('GOOGLE_QUOTA_USER', '')
_CACHE_FILE_ID         = os.environ.get('CASE_LIBRARY_CACHE_FILE_ID', '')
_CACHE_DRIVE_FOLDER_ID = os.environ.get('CACHE_DRIVE_FOLDER_ID', '')
_CACHE_FILENAME        = 'case_library_cache.json'

# In-memory cache: { 'nodes': [...], 'zoho_b_ids': {...}, 'expires_at': float }
_mem_cache: dict = {}
_CACHE_TTL = 300  # 5 minutes

# ── Zoho OAuth helper ─────────────────────────────────────────────────────────

_zoho_token_cache: dict = {}


def _get_zoho_token() -> str:
    """Return valid Zoho access token, refreshing if expired."""
    now = time.time()
    if _zoho_token_cache.get('token') and _zoho_token_cache.get('expires_at', 0) > now + 60:
        return _zoho_token_cache['token']
    if not all([_ZOHO_CLIENT_ID, _ZOHO_CLIENT_SECRET, _ZOHO_REFRESH_TOKEN]):
        raise RuntimeError('Zoho OAuth env vars not configured')

    import urllib.request, urllib.parse
    data = urllib.parse.urlencode({
        'refresh_token': _ZOHO_REFRESH_TOKEN,
        'client_id': _ZOHO_CLIENT_ID,
        'client_secret': _ZOHO_CLIENT_SECRET,
        'grant_type': 'refresh_token',
    }).encode()
    req = urllib.request.Request(_ZOHO_ACCOUNTS_URL, data=data, method='POST')
    with urllib.request.urlopen(req) as resp:
        body = json.loads(resp.read())
    if 'access_token' not in body:
        raise RuntimeError(f'Zoho token refresh failed: {body}')
    _zoho_token_cache['token'] = body['access_token']
    _zoho_token_cache['expires_at'] = now + body.get('expires_in', 3600)
    return _zoho_token_cache['token']


def _zoho_api_base() -> str:
    return f'https://creator.zoho.com/api/v2/{_ZOHO_OWNER}/{_ZOHO_APP_NAME}'


def _zoho_get(path: str, params: dict = None) -> dict:
    import urllib.request, urllib.parse
    token = _get_zoho_token()
    url = f'{_zoho_api_base()}/{path}'
    if params:
        url += '?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={'Authorization': f'Zoho-oauthtoken {token}'})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def _zoho_post(path: str, body: dict) -> dict:
    import urllib.request
    token = _get_zoho_token()
    data = json.dumps({'data': body}).encode('utf-8')
    req = urllib.request.Request(f'{_zoho_api_base()}/{path}', data=data, method='POST', headers={
        'Authorization': f'Zoho-oauthtoken {token}',
        'Content-Type': 'application/json',
    })
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def _zoho_patch(path: str, body: dict) -> dict:
    import urllib.request
    token = _get_zoho_token()
    data = json.dumps({'data': body}).encode('utf-8')
    req = urllib.request.Request(f'{_zoho_api_base()}/{path}', data=data, method='PATCH', headers={
        'Authorization': f'Zoho-oauthtoken {token}',
        'Content-Type': 'application/json',
    })
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def _zoho_delete(path: str) -> dict:
    import urllib.request
    token = _get_zoho_token()
    req = urllib.request.Request(f'{_zoho_api_base()}/{path}', method='DELETE', headers={
        'Authorization': f'Zoho-oauthtoken {token}',
    })
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def _zoho_fetch_all(report_name: str) -> list:
    """Fetch all records from a Zoho report (handles pagination)."""
    records, page_from, limit = [], 0, 200
    while True:
        resp = _zoho_get(f'report/{report_name}', {'from': page_from, 'limit': limit})
        page = resp.get('data', [])
        records.extend(page)
        if len(page) < limit:
            break
        page_from += limit
    return records


def _ensure_table_b_row(drive_file_id: str) -> str:
    """Ensure Table B has a row for this drive_file_id. Returns Zoho record ID."""
    # Search for existing row
    resp = _zoho_get(f'report/{_REPORT_ENRICHMENT}',
                     {'criteria': f'drive_file_id == "{drive_file_id}"', 'limit': 1})
    existing = resp.get('data', [])
    if existing:
        return existing[0].get('ID', '')
    # Create skeleton row
    result = _zoho_post(f'form/{_FORM_ENRICHMENT}', {
        'drive_file_id': drive_file_id,
        'authority_codes': '',
        'custom_labels': '',
        'is_private': 'false',
        'context_findings': '',
        'document_date': '',
    })
    return result.get('data', {}).get('ID', '')

# ── Drive helpers ─────────────────────────────────────────────────────────────

def _get_drive_service():
    """Return authenticated Drive v3 service."""
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
        scopes = ['https://www.googleapis.com/auth/drive']
        creds = Credentials.from_authorized_user_info(json.loads(_GOOGLE_USER_TOKEN), scopes)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
        return build('drive', 'v3', credentials=creds)
    except Exception as e:
        print(f'Drive service error: {e}')
        return None


def _read_cache_from_drive() -> list | None:
    """Read case_library_cache.json from Drive. Returns parsed list or None."""
    service = _get_drive_service()
    if not service:
        return None

    file_id = _CACHE_FILE_ID
    if not file_id:
        # Try to find by name in the designated folder
        if not _CACHE_DRIVE_FOLDER_ID:
            return None
        q = f"name='{_CACHE_FILENAME}' and '{_CACHE_DRIVE_FOLDER_ID}' in parents and trashed=false"
        res = service.files().list(q=q, fields='files(id)', supportsAllDrives=True).execute()
        files = res.get('files', [])
        if not files:
            return None
        file_id = files[0]['id']

    try:
        content = service.files().get_media(fileId=file_id, supportsAllDrives=True).execute()
        return json.loads(content)
    except Exception as e:
        print(f'Cache read error: {e}')
        return None

# ── Cache layer ───────────────────────────────────────────────────────────────

def _load_cache() -> tuple[list, dict]:
    """
    Return (nodes_for_frontend, zoho_b_id_map).
    nodes_for_frontend: list with _zoho* fields stripped.
    zoho_b_id_map: {drive_file_id: zoho_b_record_id}.
    Uses 5-minute in-memory TTL.
    """
    now = time.time()
    if _mem_cache.get('expires_at', 0) > now:
        return _mem_cache['nodes'], _mem_cache['zoho_b_ids']

    raw = _read_cache_from_drive()
    if not raw:
        # Fallback: empty cache (Zoho forms not yet built or Drive not configured)
        _mem_cache.update({'nodes': [], 'zoho_b_ids': {}, 'expires_at': now + 60})
        return [], {}

    zoho_b_ids = {}
    nodes_clean = []
    for node in raw:
        fid = node.get('id', '')
        zoho_b_ids[fid] = node.get('_zohoBId', '')
        # Strip _zohoBId (and any future _zoho* node-level fields) before sending to frontend.
        # links array is passed through intact — _zohoLinkId is needed by deleteLink() in JS.
        clean = {k: v for k, v in node.items() if not k.startswith('_zoho')}
        clean['links'] = node.get('links', [])
        nodes_clean.append(clean)

    _mem_cache.update({'nodes': nodes_clean, 'zoho_b_ids': zoho_b_ids, 'expires_at': now + _CACHE_TTL})
    return nodes_clean, zoho_b_ids


def _invalidate_cache():
    _mem_cache['expires_at'] = 0

# ── Audit log ─────────────────────────────────────────────────────────────────

def _audit(action: str, drive_file_id: str = ''):
    """Write one audit line to stdout (Railway captures as persistent logs)."""
    import hashlib
    session_id = session.get('_id', 'anon')
    session_hash = hashlib.sha256(str(session_id).encode()).hexdigest()[:12]
    ts = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    print(f'AUDIT | {ts} | {session_hash} | {action} | {drive_file_id}')

# ── Routes: public ────────────────────────────────────────────────────────────

@home_bp.route('/')
def index():
    return render_template('home.html')


@home_bp.route('/docs/<path:filename>')
def serve_docs(filename):
    return send_from_directory(_DOCS_DIR, filename)


@home_bp.route('/kurukshetra', methods=['GET'])
def kurukshetra():
    is_auth = bool(session.get('kurukshetra_auth'))

    if _KURUKSHETRA_PASSPHRASE and not is_auth:
        # Still serve — but only public nodes (is_private=false)
        nodes, _ = _load_cache()
        public_nodes = [n for n in nodes if not n.get('isPrivate', False)]
        _audit('page_load_public')
        return render_template('case_library.html', nodes=public_nodes, is_authenticated=False)

    nodes, _ = _load_cache()
    _audit('page_load_auth')
    return render_template('case_library.html', nodes=nodes, is_authenticated=is_auth)


@home_bp.route('/kurukshetra/auth', methods=['POST'])
def kurukshetra_auth():
    entered = request.form.get('passphrase', '').strip()
    if entered == _KURUKSHETRA_PASSPHRASE:
        session['kurukshetra_auth'] = True
        _audit('auth_success')
        return redirect(url_for('home.kurukshetra'))
    _audit('auth_fail')
    return render_template('kurukshetra_auth.html', error='Incorrect passphrase.')

# ── Routes: Case Library write-back API ──────────────────────────────────────

def _require_auth():
    """Return error response if not authenticated, else None."""
    if not session.get('kurukshetra_auth'):
        return jsonify({'ok': False, 'error': 'Authentication required'}), 403
    return None


@home_bp.route('/api/kurukshetra/<drive_id>/labels', methods=['PATCH'])
def cl_update_labels(drive_id: str):
    err = _require_auth()
    if err:
        return err

    body = request.get_json(silent=True) or {}
    action = body.get('action')  # 'add_authority' | 'remove_authority' | 'add_label' | 'remove_label'
    value  = body.get('value', '').strip()

    if not action or not value:
        return jsonify({'ok': False, 'error': 'action and value required'}), 400

    try:
        # Get current Table B values
        resp = _zoho_get(f'report/{_REPORT_ENRICHMENT}',
                         {'criteria': f'drive_file_id == "{drive_id}"', 'limit': 1})
        existing = resp.get('data', [])

        if existing:
            rec = existing[0]
            zoho_id = rec['ID']
            auth_codes = [c.strip() for c in rec.get('authority_codes', '').split(',') if c.strip()]
            custom_labels = [l.strip() for l in rec.get('custom_labels', '').split(',') if l.strip()]
        else:
            # Create skeleton row first
            zoho_id = _ensure_table_b_row(drive_id)
            auth_codes, custom_labels = [], []

        if action == 'add_authority' and value not in auth_codes:
            auth_codes.append(value)
        elif action == 'remove_authority':
            auth_codes = [c for c in auth_codes if c != value]
        elif action == 'add_label' and value not in custom_labels:
            custom_labels.append(value)
        elif action == 'remove_label':
            custom_labels = [l for l in custom_labels if l != value]

        _zoho_patch(f'form/{_FORM_ENRICHMENT}/{zoho_id}', {
            'authority_codes': ','.join(auth_codes),
            'custom_labels': ','.join(custom_labels),
        })
        _invalidate_cache()
        _audit(f'label_{action}', drive_id)
        return jsonify({'ok': True, 'authorityCodes': auth_codes, 'customLabels': custom_labels})

    except Exception as e:
        print(f'ERROR cl_update_labels: {e}')
        return jsonify({'ok': False, 'error': str(e)}), 500


@home_bp.route('/api/kurukshetra/<drive_id>/context', methods=['PATCH'])
def cl_update_context(drive_id: str):
    err = _require_auth()
    if err:
        return err

    body = request.get_json(silent=True) or {}
    context_findings = body.get('context_findings', '')

    try:
        resp = _zoho_get(f'report/{_REPORT_ENRICHMENT}',
                         {'criteria': f'drive_file_id == "{drive_id}"', 'limit': 1})
        existing = resp.get('data', [])
        if existing:
            zoho_id = existing[0]['ID']
            _zoho_patch(f'form/{_FORM_ENRICHMENT}/{zoho_id}', {'context_findings': context_findings})
        else:
            zoho_id = _ensure_table_b_row(drive_id)
            _zoho_patch(f'form/{_FORM_ENRICHMENT}/{zoho_id}', {'context_findings': context_findings})

        _invalidate_cache()
        _audit('context_update', drive_id)
        return jsonify({'ok': True})

    except Exception as e:
        print(f'ERROR cl_update_context: {e}')
        return jsonify({'ok': False, 'error': str(e)}), 500


@home_bp.route('/api/kurukshetra/<drive_id>/date', methods=['PATCH'])
def cl_update_date(drive_id: str):
    err = _require_auth()
    if err:
        return err

    body = request.get_json(silent=True) or {}
    document_date = body.get('document_date', '').strip()

    try:
        resp = _zoho_get(f'report/{_REPORT_ENRICHMENT}',
                         {'criteria': f'drive_file_id == "{drive_id}"', 'limit': 1})
        existing = resp.get('data', [])
        if existing:
            zoho_id = existing[0]['ID']
            _zoho_patch(f'form/{_FORM_ENRICHMENT}/{zoho_id}', {'document_date': document_date})
        else:
            zoho_id = _ensure_table_b_row(drive_id)
            _zoho_patch(f'form/{_FORM_ENRICHMENT}/{zoho_id}', {'document_date': document_date})

        _invalidate_cache()
        _audit('date_update', drive_id)
        return jsonify({'ok': True})

    except Exception as e:
        print(f'ERROR cl_update_date: {e}')
        return jsonify({'ok': False, 'error': str(e)}), 500


@home_bp.route('/api/kurukshetra/<drive_id>/private', methods=['PATCH'])
def cl_update_private(drive_id: str):
    err = _require_auth()
    if err:
        return err

    body = request.get_json(silent=True) or {}
    is_private = bool(body.get('is_private', False))

    try:
        resp = _zoho_get(f'report/{_REPORT_ENRICHMENT}',
                         {'criteria': f'drive_file_id == "{drive_id}"', 'limit': 1})
        existing = resp.get('data', [])
        if existing:
            zoho_id = existing[0]['ID']
            _zoho_patch(f'form/{_FORM_ENRICHMENT}/{zoho_id}', {'is_private': str(is_private).lower()})
        else:
            zoho_id = _ensure_table_b_row(drive_id)
            _zoho_patch(f'form/{_FORM_ENRICHMENT}/{zoho_id}', {'is_private': str(is_private).lower()})

        _invalidate_cache()
        _audit('private_toggle', drive_id)
        return jsonify({'ok': True, 'isPrivate': is_private})

    except Exception as e:
        print(f'ERROR cl_update_private: {e}')
        return jsonify({'ok': False, 'error': str(e)}), 500


@home_bp.route('/api/kurukshetra/link', methods=['POST'])
def cl_create_link():
    err = _require_auth()
    if err:
        return err

    body = request.get_json(silent=True) or {}
    source_id   = body.get('source_id', '').strip()
    linked_id   = body.get('linked_id', '').strip()
    link_type   = body.get('link_type', '').strip()
    link_details = body.get('link_details', '').strip()

    if not source_id or not linked_id or not link_type:
        return jsonify({'ok': False, 'error': 'source_id, linked_id, and link_type are required'}), 400

    ts = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    try:
        result = _zoho_post(f'form/{_FORM_LINKS}', {
            'source_drive_id': source_id,
            'linked_drive_id': linked_id,
            'link_type': link_type,
            'link_details': link_details,
            'timestamp': ts,
        })
        zoho_link_id = result.get('data', {}).get('ID', '')
        _invalidate_cache()
        _audit('link_create', source_id)
        return jsonify({'ok': True, 'link_id': zoho_link_id, 'timestamp': ts})

    except Exception as e:
        print(f'ERROR cl_create_link: {e}')
        return jsonify({'ok': False, 'error': str(e)}), 500


@home_bp.route('/api/kurukshetra/link/<link_id>', methods=['DELETE'])
def cl_delete_link(link_id: str):
    err = _require_auth()
    if err:
        return err

    try:
        _zoho_delete(f'form/{_FORM_LINKS}/{link_id}')
        _invalidate_cache()
        _audit('link_delete', link_id)
        return jsonify({'ok': True})

    except Exception as e:
        print(f'ERROR cl_delete_link: {e}')
        return jsonify({'ok': False, 'error': str(e)}), 500


@home_bp.route('/api/kurukshetra/rebuild-cache', methods=['POST'])
def cl_rebuild_cache():
    err = _require_auth()
    if err:
        return err

    try:
        import subprocess, sys
        script = os.path.join(os.path.dirname(__file__), '..', 'scripts', 'sync_case_library.py')
        proc = subprocess.Popen(
            [sys.executable, script, '--cache-only'],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
        stdout, _ = proc.communicate(timeout=120)
        _invalidate_cache()
        _audit('cache_rebuild')
        return jsonify({'ok': True, 'output': stdout.decode('utf-8', errors='replace')})

    except Exception as e:
        print(f'ERROR cl_rebuild_cache: {e}')
        return jsonify({'ok': False, 'error': str(e)}), 500
