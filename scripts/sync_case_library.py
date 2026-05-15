"""
Case Library Sync Pipeline
==========================
Runs nightly (Railway scheduled job, 11:30 PM IST) after Google Apps Script
has refreshed the Google Sheets Case File Index (~11:00 PM IST).

Steps:
  1. Read Google Sheets → build Table A rows
  2. Upsert Table A rows into Zoho (drive_file_id as conflict key)
  3. Detect new drive_file_ids not yet in Table B → insert skeleton rows
     (drive_file_id + document_date extracted from filename)
  4. Fetch all Table B enrichment rows from Zoho
  5. Fetch all Table C link rows from Zoho
  6. Merge Sheets + B + C → flat JSON array
  7. Write cache JSON to Google Drive (/Config/Case Library/case_library_cache.json)

Usage:
  python scripts/sync_case_library.py            # full pipeline
  python scripts/sync_case_library.py --seed-b   # also produces enrichment seed CSV for initial Table B import
  python scripts/sync_case_library.py --cache-only  # skip Zoho write, only rebuild cache from existing Zoho data
"""

import io
import json
import os
import re
import sys
import time
from datetime import datetime, timezone

# ── Zoho config ───────────────────────────────────────────────────────────────

ZOHO_CLIENT_ID      = os.environ.get('ZOHO_CLIENT_ID', '')
ZOHO_CLIENT_SECRET  = os.environ.get('ZOHO_CLIENT_SECRET', '')
ZOHO_REFRESH_TOKEN  = os.environ.get('ZOHO_REFRESH_TOKEN', '')
ZOHO_OWNER          = os.environ.get('ZOHO_OWNER', '')
ZOHO_APP_NAME       = os.environ.get('ZOHO_APP_NAME', '')

FORM_BASE        = 'Case_Library_Base'
FORM_ENRICHMENT  = 'Case_Library_Enrichment'
FORM_LINKS       = 'Case_Library_Links'
REPORT_BASE      = 'Case_Library_Base_Report'
REPORT_ENRICHMENT= 'Case_Library_Enrichment_Report'
REPORT_LINKS     = 'Case_Library_Links_Report'

ZOHO_API_BASE = f'https://creator.zoho.com/api/v2/{ZOHO_OWNER}/{ZOHO_APP_NAME}'
ZOHO_ACCOUNTS_URL = 'https://accounts.zoho.com/oauth/v2/token'

# ── Google / Drive config ─────────────────────────────────────────────────────

SHEETS_SPREADSHEET_ID = os.environ.get('SHEETS_SPREADSHEET_ID', '')
SHEETS_SHEET_NAME     = os.environ.get('SHEETS_SHEET_NAME', 'Case File Index')
GOOGLE_USER_TOKEN     = os.environ.get('GOOGLE_USER_TOKEN', '')
GOOGLE_QUOTA_USER     = os.environ.get('GOOGLE_QUOTA_USER', '')
CACHE_DRIVE_FOLDER_ID = os.environ.get('CACHE_DRIVE_FOLDER_ID', '')
CACHE_FILENAME        = 'case_library_cache.json'

# ── Zoho OAuth ────────────────────────────────────────────────────────────────

_zoho_token_cache: dict = {}

def get_zoho_access_token() -> str:
    """Return a valid Zoho access token, refreshing if expired."""
    now = time.time()
    if _zoho_token_cache.get('token') and _zoho_token_cache.get('expires_at', 0) > now + 60:
        return _zoho_token_cache['token']

    import urllib.request, urllib.parse
    data = urllib.parse.urlencode({
        'refresh_token': ZOHO_REFRESH_TOKEN,
        'client_id': ZOHO_CLIENT_ID,
        'client_secret': ZOHO_CLIENT_SECRET,
        'grant_type': 'refresh_token',
    }).encode()
    req = urllib.request.Request(ZOHO_ACCOUNTS_URL, data=data, method='POST')
    with urllib.request.urlopen(req) as resp:
        body = json.loads(resp.read())

    if 'access_token' not in body:
        raise RuntimeError(f'Zoho token refresh failed: {body}')

    _zoho_token_cache['token'] = body['access_token']
    _zoho_token_cache['expires_at'] = now + body.get('expires_in', 3600)
    return _zoho_token_cache['token']


def zoho_get(path: str, params: dict = None) -> dict:
    """GET from Zoho Creator API."""
    import urllib.request, urllib.parse
    token = get_zoho_access_token()
    url = f'{ZOHO_API_BASE}/{path}'
    if params:
        url += '?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={'Authorization': f'Zoho-oauthtoken {token}'})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def zoho_post(path: str, body: dict) -> dict:
    """POST to Zoho Creator API (JSON body)."""
    import urllib.request
    token = get_zoho_access_token()
    url = f'{ZOHO_API_BASE}/{path}'
    data = json.dumps({'data': body}).encode('utf-8')
    req = urllib.request.Request(url, data=data, method='POST', headers={
        'Authorization': f'Zoho-oauthtoken {token}',
        'Content-Type': 'application/json',
    })
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def zoho_patch(path: str, body: dict) -> dict:
    """PATCH a Zoho Creator record."""
    import urllib.request
    token = get_zoho_access_token()
    url = f'{ZOHO_API_BASE}/{path}'
    data = json.dumps({'data': body}).encode('utf-8')
    req = urllib.request.Request(url, data=data, method='PATCH', headers={
        'Authorization': f'Zoho-oauthtoken {token}',
        'Content-Type': 'application/json',
    })
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def zoho_delete(path: str) -> dict:
    """DELETE a Zoho Creator record."""
    import urllib.request
    token = get_zoho_access_token()
    url = f'{ZOHO_API_BASE}/{path}'
    req = urllib.request.Request(url, method='DELETE', headers={
        'Authorization': f'Zoho-oauthtoken {token}',
    })
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def zoho_import_tsv(form_name: str, tsv_content: str, import_type: str = 'upsert',
                    conflict_field: str = 'drive_file_id') -> dict:
    """
    Import TSV data into a Zoho Creator form via the Import API.
    import_type: 'insert' | 'upsert' | 'update'
    Returns Zoho API response dict.
    """
    import urllib.request
    token = get_zoho_access_token()
    url = f'{ZOHO_API_BASE}/form/{form_name}/import'

    # Build multipart/form-data manually
    boundary = 'ZohoBoundary12345'
    lines = []

    def add_field(name, value):
        lines.append(f'--{boundary}')
        lines.append(f'Content-Disposition: form-data; name="{name}"')
        lines.append('')
        lines.append(value)

    def add_file(name, filename, content):
        lines.append(f'--{boundary}')
        lines.append(f'Content-Disposition: form-data; name="{name}"; filename="{filename}"')
        lines.append('Content-Type: text/tab-separated-values')
        lines.append('')
        lines.append(content)

    add_field('import_type', import_type)
    if import_type in ('upsert', 'update'):
        add_field('conflict_field', conflict_field)
    add_file('file', 'data.tsv', tsv_content)
    lines.append(f'--{boundary}--')

    body = '\r\n'.join(lines).encode('utf-8')
    req = urllib.request.Request(url, data=body, method='POST', headers={
        'Authorization': f'Zoho-oauthtoken {token}',
        'Content-Type': f'multipart/form-data; boundary={boundary}',
    })
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def zoho_fetch_all_report(report_name: str) -> list[dict]:
    """Fetch all records from a Zoho report, handling pagination (200 records/call)."""
    records = []
    page_from = 0
    limit = 200
    while True:
        resp = zoho_get(f'report/{report_name}', {'from': page_from, 'limit': limit})
        page_records = resp.get('data', [])
        records.extend(page_records)
        if len(page_records) < limit:
            break
        page_from += limit
    return records

# ── Google Sheets ─────────────────────────────────────────────────────────────

def get_sheets_rows() -> list[dict]:
    """Read all rows from the Case File Index Google Sheet. Returns list of dicts keyed by column header."""
    import gspread
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    token_data = json.loads(GOOGLE_USER_TOKEN)
    scopes = [
        'https://www.googleapis.com/auth/spreadsheets.readonly',
        'https://www.googleapis.com/auth/drive.readonly',
    ]
    creds = Credentials.from_authorized_user_info(token_data, scopes)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())

    gc = gspread.authorize(creds)
    ws = gc.open_by_key(SHEETS_SPREADSHEET_ID).worksheet(SHEETS_SHEET_NAME)
    return ws.get_all_records()

# ── Table A mapping ───────────────────────────────────────────────────────────

def _human_size(byte_count) -> str:
    """Convert byte count to human-readable size string."""
    try:
        b = int(byte_count)
    except (TypeError, ValueError):
        return str(byte_count) if byte_count else '—'
    if b == 0:
        return '0 B'
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if b < 1024:
            return f'{b:.1f} {unit}' if unit != 'B' else f'{b} B'
        b /= 1024
    return f'{b:.1f} PB'


def sheets_row_to_table_a(row: dict) -> dict:
    """Map a Google Sheets row dict to a Table A field dict."""
    size_bytes = row.get('Size (Bytes)', '')
    return {
        'drive_file_id':    str(row.get('ID', '')).strip(),
        'file_name':        str(row.get('Name', '')).strip(),
        'drive_path':       str(row.get('Folder Path', '')).strip(),
        'drive_created_date': str(row.get('Created Time', '')).strip(),
        'drive_modified_date': str(row.get('Modified Time', '')).strip(),
        'drive_file_size':  _human_size(size_bytes),
        'drive_mime_type':  str(row.get('MimeType', '')).strip(),
        'drive_url':        str(row.get('URL', '')).strip(),
        'md5_checksum':     str(row.get('MD5 Checksum', '')).strip(),
        'description':      str(row.get('Description', '')).strip(),
    }


def rows_to_tsv(rows: list[dict]) -> str:
    """Convert list of field dicts to a TSV string (tab-separated, headers on first row)."""
    if not rows:
        return ''
    headers = list(rows[0].keys())
    lines = ['\t'.join(headers)]
    for row in rows:
        cells = []
        for h in headers:
            val = str(row.get(h, '') or '').replace('\t', ' ').replace('\n', ' ').replace('\r', ' ')
            cells.append(val)
        lines.append('\t'.join(cells))
    return '\n'.join(lines)

# ── Date extraction from filenames ────────────────────────────────────────────

_MARATHI_MONTHS = {
    'जानेवारी': '01', 'फेब्रुवारी': '02', 'मार्च': '03',
    'एप्रिल': '04', 'मे': '05', 'जून': '06',
    'जुलै': '07', 'ऑगस्ट': '08', 'सप्टेंबर': '09',
    'ऑक्टोबर': '10', 'नोव्हेंबर': '11', 'डिसेंबर': '12',
}

_DEV_DIGITS = str.maketrans('०१२३४५६७८९', '0123456789')


def extract_date_from_filename(name: str) -> str | None:
    """Extract YYYY-MM-DD from a filename. Returns ISO ASCII date or None.

    Handles: Devanagari YYYY-MM-DD prefix, Marathi month-name format
    (DD MonthName YYYY), DD-MM-YYYY, and year-only fallback.
    Zero month/day values (e.g. 2014-00-00) fall through to year-only.
    """
    if not name:
        return None

    # Translate Devanagari digits to ASCII once; run all patterns on this.
    name_ascii = name.translate(_DEV_DIGITS)

    # Pattern 1: YYYY-MM-DD (most common — Devanagari prefix filenames)
    m = re.search(r'(\d{4})-(\d{2})-(\d{2})', name_ascii)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1900 <= y <= 2100 and 1 <= mo <= 12 and 1 <= d <= 31:
            return f'{y:04d}-{mo:02d}-{d:02d}'

    # Pattern 2: DD-MM-YYYY
    m = re.search(r'(\d{2})-(\d{2})-(\d{4})', name_ascii)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1900 <= y <= 2100 and 1 <= mo <= 12 and 1 <= d <= 31:
            return f'{y:04d}-{mo:02d}-{d:02d}'

    # Pattern 3: Marathi month names — "DD MonthName YYYY" embedded in filename
    # Month names stay untranslated; only surrounding digits are ASCII after translate.
    for mname, mnum in _MARATHI_MONTHS.items():
        m = re.search(r'(\d{1,2})\s+' + re.escape(mname) + r'\s+(\d{4})', name_ascii)
        if m:
            d, y = int(m.group(1)), int(m.group(2))
            if 1900 <= y <= 2100 and 1 <= d <= 31:
                return f'{y:04d}-{int(mnum):02d}-{d:02d}'

    # Fallback: year only → YYYY-01-01 (blank day/month is flagged in UI)
    m = re.search(r'\b(19\d{2}|20[0-2]\d)\b', name_ascii)
    if m:
        return f'{m.group(1)}-01-01'

    return None

# ── Table B operations ────────────────────────────────────────────────────────

def get_table_b_drive_ids() -> dict[str, str]:
    """Return dict of {drive_file_id: zoho_record_id} for all Table B rows."""
    records = zoho_fetch_all_report(REPORT_ENRICHMENT)
    return {r.get('drive_file_id', ''): r.get('ID', '') for r in records if r.get('drive_file_id')}


def insert_new_table_b_rows(new_ids: list[str], sheets_rows_by_id: dict[str, dict]) -> int:
    """Insert skeleton Table B rows for drive_file_ids not yet in Table B."""
    inserted = 0
    for drive_id in new_ids:
        row = sheets_rows_by_id.get(drive_id, {})
        filename = row.get('file_name', row.get('Name', ''))
        doc_date = extract_date_from_filename(filename) or ''
        # Shared=TRUE → visible to public (is_private=false); Shared=FALSE → private.
        # This only applies on first insert; HITL manages the flag via UI thereafter.
        shared = str(row.get('Shared', 'TRUE')).strip().upper()
        is_private = 'false' if shared == 'TRUE' else 'true'
        try:
            zoho_post(f'form/{FORM_ENRICHMENT}', {
                'drive_file_id': drive_id,
                'document_date': doc_date,
                'authority_codes': '',
                'custom_labels': '',
                'is_private': is_private,
                'context_findings': '',
            })
            inserted += 1
            time.sleep(0.1)  # respect Zoho rate limits
        except Exception as e:
            print(f'  WARN: Failed to insert Table B row for {drive_id}: {e}')
    return inserted

# ── Merge to JSON cache ───────────────────────────────────────────────────────

def build_cache_json(sheets_rows: list[dict],
                     table_b_records: list[dict],
                     table_c_records: list[dict]) -> list[dict]:
    """Merge Sheets + Zoho Table B + Zoho Table C into the flat cache JSON array."""
    # Index Table B by drive_file_id
    b_by_id: dict[str, dict] = {}
    for r in table_b_records:
        fid = r.get('drive_file_id', '')
        if fid:
            b_by_id[fid] = r

    # Index Table C by source_drive_id (one source → many links)
    c_by_source: dict[str, list[dict]] = {}
    for r in table_c_records:
        src = r.get('source_drive_id', '')
        if src:
            c_by_source.setdefault(src, []).append(r)

    nodes = []
    for row in sheets_rows:
        fid = str(row.get('ID', '')).strip()
        if not fid:
            continue

        b = b_by_id.get(fid, {})
        links_raw = c_by_source.get(fid, [])

        links = [
            {
                'linkedId':   lk.get('linked_drive_id', ''),
                'linkType':   lk.get('link_type', ''),
                'linkDetails': lk.get('link_details', ''),
                'timestamp':  lk.get('timestamp', ''),
                '_zohoLinkId': lk.get('ID', ''),
            }
            for lk in links_raw
        ]

        size_bytes = row.get('Size (Bytes)', '')

        node = {
            'id':           fid,
            'name':         str(row.get('Name', '')).strip(),
            'path':         str(row.get('Folder Path', '')).strip(),
            'created':      str(row.get('Created Time', '')).strip(),
            'modified':     str(row.get('Modified Time', '')).strip(),
            'size':         _human_size(size_bytes),
            'mime':         str(row.get('MimeType', '')).strip(),
            'url':          str(row.get('URL', '')).strip(),
            'md5':          str(row.get('MD5 Checksum', '')).strip(),
            'description':  str(row.get('Description', '')).strip(),
            # Enrichment (from Table B; defaults to empty/false if no B row)
            'authorityCodes': [c.strip() for c in b.get('authority_codes', '').split(',') if c.strip()],
            'customLabels':   [l.strip() for l in b.get('custom_labels', '').split(',') if l.strip()],
            'isPrivate':      b.get('is_private', False) in (True, 'true', '1', 'True'),
            'contextFindings': b.get('context_findings', ''),
            'documentType':   b.get('document_type', ''),
            'documentDate':   b.get('document_date', ''),
            'saraswatiProcessed': b.get('saraswati_processed', False) in (True, 'true', '1', 'True'),
            'sanjayaApproved':    b.get('sanjaya_approved', False) in (True, 'true', '1', 'True'),
            'vishwakarmaPublished': b.get('vishwakarma_published', False) in (True, 'true', '1', 'True'),
            # Links
            'links': links,
            # Internal: Zoho record IDs — stripped before sending to frontend
            '_zohoBId':  b.get('ID', ''),
        }
        nodes.append(node)

    return nodes

# ── Drive cache write ─────────────────────────────────────────────────────────

def get_drive_service():
    """Return authenticated Drive v3 service using GOOGLE_USER_TOKEN."""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    scopes = ['https://www.googleapis.com/auth/drive']
    creds = Credentials.from_authorized_user_info(json.loads(GOOGLE_USER_TOKEN), scopes)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return build('drive', 'v3', credentials=creds)


def write_cache_to_drive(nodes: list[dict]) -> str:
    """Write the cache JSON to Google Drive. Returns the Drive file ID."""
    from googleapiclient.http import MediaIoBaseUpload

    service = get_drive_service()
    json_bytes = json.dumps(nodes, ensure_ascii=False, indent=None).encode('utf-8')
    media = MediaIoBaseUpload(io.BytesIO(json_bytes), mimetype='application/json', resumable=False)

    # Check if file already exists in the folder
    query = f"name='{CACHE_FILENAME}' and '{CACHE_DRIVE_FOLDER_ID}' in parents and trashed=false"
    existing = service.files().list(q=query, fields='files(id,name)', supportsAllDrives=True).execute()
    files = existing.get('files', [])

    if files:
        # Update existing file
        file_id = files[0]['id']
        service.files().update(
            fileId=file_id, media_body=media,
            supportsAllDrives=True,
            quotaUser=GOOGLE_QUOTA_USER,
        ).execute()
        print(f'  Updated existing cache file: {file_id}')
    else:
        # Create new file
        meta = {'name': CACHE_FILENAME, 'parents': [CACHE_DRIVE_FOLDER_ID]}
        result = service.files().create(
            body=meta, media_body=media, fields='id',
            supportsAllDrives=True,
            quotaUser=GOOGLE_QUOTA_USER,
        ).execute()
        file_id = result['id']
        print(f'  Created new cache file: {file_id}')
        print(f'  ACTION REQUIRED: Set CASE_LIBRARY_CACHE_FILE_ID={file_id} in Railway env vars')

    return file_id


def write_seed_csv_locally(sheets_rows: list[dict]):
    """
    Produce case_library_enrichment_seed.csv for initial Table B import.
    Run once with --seed-b flag; HITL imports this CSV into Zoho Table B manually.
    """
    import csv
    fields = ['drive_file_id', 'document_date', 'authority_codes', 'custom_labels',
              'is_private', 'context_findings', 'document_type',
              'saraswati_processed', 'sanjaya_approved', 'vishwakarma_published']
    rows = []
    for row in sheets_rows:
        fid = str(row.get('ID', '')).strip()
        name = str(row.get('Name', '')).strip()
        if not fid:
            continue
        shared = str(row.get('Shared', 'TRUE')).strip().upper()
        is_private = 'false' if shared == 'TRUE' else 'true'
        rows.append({
            'drive_file_id': fid,
            'document_date': extract_date_from_filename(name) or '',
            'authority_codes': '',
            'custom_labels': '',
            'is_private': is_private,
            'context_findings': '',
            'document_type': '',
            'saraswati_processed': 'false',
            'sanjaya_approved': 'false',
            'vishwakarma_published': 'false',
        })
    path = 'case_library_enrichment_seed.csv'
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f'  Wrote seed CSV: {path} ({len(rows)} rows)')

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    seed_b = '--seed-b' in sys.argv
    cache_only = '--cache-only' in sys.argv

    # Validate required env vars
    missing = [v for v in ['ZOHO_CLIENT_ID', 'ZOHO_CLIENT_SECRET', 'ZOHO_REFRESH_TOKEN',
                            'ZOHO_OWNER', 'ZOHO_APP_NAME', 'SHEETS_SPREADSHEET_ID',
                            'GOOGLE_USER_TOKEN', 'CACHE_DRIVE_FOLDER_ID']
               if not os.environ.get(v)]
    if missing:
        print(f'ERROR: Missing required env vars: {", ".join(missing)}')
        sys.exit(1)

    ts = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    print(f'[{ts}] Case Library sync starting...')

    # ── Step 1: Read Sheets ─────────────────────────────────────────────────
    print('[1/5] Reading Google Sheets...')
    sheets_rows = get_sheets_rows()
    print(f'      {len(sheets_rows)} rows read from "{SHEETS_SHEET_NAME}"')

    sheets_rows_by_id = {str(r.get('ID', '')).strip(): r for r in sheets_rows if r.get('ID')}

    if seed_b:
        print('[SEED] Writing enrichment seed CSV for Table B initial import...')
        write_seed_csv_locally(sheets_rows)

    if cache_only:
        print('[CACHE-ONLY] Skipping Zoho writes...')
    else:
        # ── Step 2: Upsert Table A ──────────────────────────────────────────
        print('[2/5] Upserting Table A (Case_Library_Base) into Zoho...')
        table_a_rows = [sheets_row_to_table_a(r) for r in sheets_rows if r.get('ID')]
        tsv = rows_to_tsv(table_a_rows)
        result = zoho_import_tsv(FORM_BASE, tsv, import_type='upsert', conflict_field='drive_file_id')
        print(f'      Zoho import result: {result.get("message", result)}')

        # ── Step 3: Insert new Table B rows ────────────────────────────────
        print('[3/5] Detecting new Drive IDs for Table B...')
        b_existing = get_table_b_drive_ids()
        new_ids = [fid for fid in sheets_rows_by_id if fid not in b_existing]
        print(f'      {len(new_ids)} new IDs to insert into Table B')
        if new_ids:
            inserted = insert_new_table_b_rows(new_ids, sheets_rows_by_id)
            print(f'      Inserted {inserted} Table B rows')

    # ── Step 4: Fetch Table B + C ───────────────────────────────────────────
    print('[4/5] Fetching Table B (enrichment) and Table C (links) from Zoho...')
    table_b = zoho_fetch_all_report(REPORT_ENRICHMENT)
    table_c = zoho_fetch_all_report(REPORT_LINKS)
    print(f'      Table B: {len(table_b)} rows | Table C: {len(table_c)} rows')

    # ── Step 5: Build and write JSON cache ──────────────────────────────────
    print('[5/5] Building JSON cache and writing to Google Drive...')
    nodes = build_cache_json(sheets_rows, table_b, table_c)
    print(f'      {len(nodes)} nodes in cache')

    file_id = write_cache_to_drive(nodes)

    ts_end = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    print(f'[{ts_end}] Sync complete. Cache file ID: {file_id}')


if __name__ == '__main__':
    main()
