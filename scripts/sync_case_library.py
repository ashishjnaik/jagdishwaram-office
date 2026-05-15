"""
Case Library Sync Pipeline
==========================
Runs nightly (Railway scheduled job, 11:30 PM IST) after Google Apps Script
has refreshed the Google Sheets Case File Index (~11:00 PM IST).

Workflow:
  1. Read Google Sheets → build Table A rows
  2. Wipe Table A via Deluge function, then reload via batch POST (200 rows/call)
  3. Compare Table A IDs against Table B → append skeleton rows for new IDs only
     (Table B is NEVER wiped — existing enrichments are preserved)
  4. Fetch all Table B enrichment rows from Zoho
  5. Fetch all Table C link rows from Zoho
  6. Merge Sheets + B + C → flat JSON array
  7. Write cache JSON to Google Drive

Usage:
  python scripts/sync_case_library.py            # daily nightly run
  python scripts/sync_case_library.py --seed-b   # initial seed: also writes enrichment CSV
                                                  # and inserts any Table B rows not yet present
  python scripts/sync_case_library.py --cache-only  # skip Zoho writes, rebuild cache only
"""

import io
import json
import os
import re
import sys
import time
from datetime import datetime, timezone

# ── Zoho config ───────────────────────────────────────────────────────────────

ZOHO_CLIENT_ID     = os.environ.get('ZOHO_CLIENT_ID', '')
ZOHO_CLIENT_SECRET = os.environ.get('ZOHO_CLIENT_SECRET', '')
ZOHO_REFRESH_TOKEN = os.environ.get('ZOHO_REFRESH_TOKEN', '')
ZOHO_OWNER         = os.environ.get('ZOHO_OWNER', '')
ZOHO_APP_NAME      = os.environ.get('ZOHO_APP_NAME', '')

FORM_BASE         = 'Case_Library_Base'
FORM_ENRICHMENT   = 'Case_Library_Enrichment'
FORM_LINKS        = 'Case_Library_Links'
REPORT_BASE       = 'Case_Library_Base_Report'
REPORT_ENRICHMENT = 'Case_Library_Enrichment_Report'
REPORT_LINKS      = 'Case_Library_Links_Report'

# Zoho datacenter domain — India: zoho.in | US: zoho.com | EU: zoho.eu
ZOHO_DOMAIN       = os.environ.get('ZOHO_DOMAIN', 'zoho.in')
ZOHO_API_BASE     = f'https://creator.{ZOHO_DOMAIN}/creator/v2.1/data/{ZOHO_OWNER}/{ZOHO_APP_NAME}'
ZOHO_ACCOUNTS_URL = f'https://accounts.{ZOHO_DOMAIN}/oauth/v2/token'

# ── Google / Drive config ─────────────────────────────────────────────────────

SHEETS_SPREADSHEET_ID = os.environ.get('SHEETS_SPREADSHEET_ID', '')
SHEETS_SHEET_NAME     = os.environ.get('SHEETS_SHEET_NAME', 'Case File Index')
GOOGLE_USER_TOKEN     = os.environ.get('GOOGLE_USER_TOKEN', '')
GOOGLE_QUOTA_USER     = os.environ.get('GOOGLE_QUOTA_USER', '')
CACHE_DRIVE_FOLDER_ID = os.environ.get('CACHE_DRIVE_FOLDER_ID', '')
CACHE_FILENAME        = 'case_library_cache.json'

# ── Date extraction constants (module-level — not recreated per call) ─────────

_MARATHI_MONTHS = {
    'जानेवारी': '01', 'फेब्रुवारी': '02', 'मार्च': '03',
    'एप्रिल': '04', 'मे': '05', 'जून': '06',
    'जुलै': '07', 'ऑगस्ट': '08', 'सप्टेंबर': '09',
    'ऑक्टोबर': '10', 'नोव्हेंबर': '11', 'डिसेंबर': '12',
}
_DEV_DIGITS = str.maketrans('०१२३४५६७८९', '0123456789')

# ── Zoho OAuth ────────────────────────────────────────────────────────────────

_zoho_token_cache: dict = {}


def get_zoho_access_token() -> str:
    now = time.time()
    if _zoho_token_cache.get('token') and _zoho_token_cache.get('expires_at', 0) > now + 60:
        return _zoho_token_cache['token']
    import urllib.request, urllib.parse
    data = urllib.parse.urlencode({
        'refresh_token': ZOHO_REFRESH_TOKEN,
        'client_id':     ZOHO_CLIENT_ID,
        'client_secret': ZOHO_CLIENT_SECRET,
        'grant_type':    'refresh_token',
    }).encode()
    req = urllib.request.Request(ZOHO_ACCOUNTS_URL, data=data, method='POST')
    with urllib.request.urlopen(req) as resp:
        body = json.loads(resp.read())
    if 'access_token' not in body:
        raise RuntimeError(f'Zoho token refresh failed: {body}')
    _zoho_token_cache['token'] = body['access_token']
    _zoho_token_cache['expires_at'] = now + body.get('expires_in', 3600)
    return _zoho_token_cache['token']


def _zoho_call(req, url: str) -> dict:
    import urllib.error
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        err_body = e.read().decode('utf-8', errors='replace')
        raise RuntimeError(f'Zoho API HTTP {e.code} at {url}\nResponse: {err_body}')


def zoho_get(path: str, params: dict = None) -> dict:
    import urllib.request, urllib.parse
    token = get_zoho_access_token()
    url = f'{ZOHO_API_BASE}/{path}'
    if params:
        url += '?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={'Authorization': f'Zoho-oauthtoken {token}'})
    return _zoho_call(req, url)


def zoho_post(path: str, body: dict) -> dict:
    import urllib.request
    token = get_zoho_access_token()
    url = f'{ZOHO_API_BASE}/{path}'
    data = json.dumps({'data': body}).encode('utf-8')
    req = urllib.request.Request(url, data=data, method='POST', headers={
        'Authorization': f'Zoho-oauthtoken {token}',
        'Content-Type': 'application/json',
    })
    return _zoho_call(req, url)


def zoho_patch(path: str, body: dict) -> dict:
    import urllib.request
    token = get_zoho_access_token()
    url = f'{ZOHO_API_BASE}/{path}'
    data = json.dumps({'data': body}).encode('utf-8')
    req = urllib.request.Request(url, data=data, method='PATCH', headers={
        'Authorization': f'Zoho-oauthtoken {token}',
        'Content-Type': 'application/json',
    })
    return _zoho_call(req, url)


def zoho_delete(path: str) -> dict:
    import urllib.request
    token = get_zoho_access_token()
    url = f'{ZOHO_API_BASE}/{path}'
    req = urllib.request.Request(url, method='DELETE', headers={
        'Authorization': f'Zoho-oauthtoken {token}',
    })
    return _zoho_call(req, url)


def zoho_call_custom_api(custom_api_link_name: str, body: dict = None) -> dict:
    """Invoke a Zoho Creator Custom API endpoint.
    Standalone Deluge functions cannot be called directly via REST API —
    they must first be wrapped as a Custom API in Zoho Creator:
      Microservices → Custom APIs → New Custom API → invoke the Deluge function.
    The endpoint is: https://www.zohoapis.com/creator/custom/{owner}/{custom_api_link_name}
    Authentication: same OAuth token used for data API calls.
    """
    import urllib.request
    token = get_zoho_access_token()
    url = f'https://www.zohoapis.com/creator/custom/{ZOHO_OWNER}/{custom_api_link_name}'
    payload = json.dumps(body or {}).encode('utf-8')
    req = urllib.request.Request(url, data=payload, method='POST', headers={
        'Authorization': f'Zoho-oauthtoken {token}',
        'Content-Type': 'application/json',
    })
    return _zoho_call(req, url)


def zoho_batch_post(form_name: str, records: list[dict]) -> int:
    """POST records to a Zoho form in batches of 200. Returns total successfully added."""
    import urllib.request
    token = get_zoho_access_token()
    url = f'{ZOHO_API_BASE}/form/{form_name}'
    total_added = 0
    batch_size = 200
    for i in range(0, len(records), batch_size):
        batch = records[i:i + batch_size]
        payload = json.dumps({'data': batch}).encode('utf-8')
        req = urllib.request.Request(url, data=payload, method='POST', headers={
            'Authorization': f'Zoho-oauthtoken {token}',
            'Content-Type': 'application/json',
        })
        resp = _zoho_call(req, url)
        result = resp.get('result', {})
        if isinstance(result, dict) and 'added_count' in result:
            added = result['added_count']
            failed = result.get('failed_count', 0)
            if failed:
                print(f'    WARN batch {i//batch_size+1}: {failed} records rejected')
                for fd in result.get('failed_data', [])[:3]:
                    print(f'      {fd}')
        elif isinstance(result, list):
            added = sum(1 for r in result if r.get('code') == 3000)
            failed = len(result) - added
            if failed:
                print(f'    WARN batch {i//batch_size+1}: {failed} failures')
                for r in result[:3]:
                    if r.get('code') != 3000:
                        print(f'      {r}')
        else:
            added = 0
            print(f'    WARN batch {i//batch_size+1}: unrecognised response — {json.dumps(resp)[:200]}')
        total_added += added
        if i + batch_size < len(records):
            time.sleep(0.2)
    return total_added


def zoho_fetch_all_report(report_name: str) -> list[dict]:
    """Fetch all records from a Zoho report, paginating at 200/call.
    Zoho returns HTTP 400/code 9220 or HTTP 404/code 3100 for empty reports — treated as [].
    Zoho wraps around when from > total_records (returns same records again) — guard with
    total_records from response and an empty-page check to prevent infinite loops.
    """
    records = []
    page_from = 0
    limit = 200
    total_known = None  # populated from first response if Zoho includes total_records
    while True:
        try:
            resp = zoho_get(f'report/{report_name}', {'from': page_from, 'limit': limit})
        except RuntimeError as e:
            err = str(e)
            if '9220' in err or 'No records exist' in err or '3100' in err or 'No Data Available' in err:
                break
            raise
        page_records = resp.get('data', [])
        if not page_records:
            break
        if total_known is None and 'total_records' in resp:
            total_known = int(resp['total_records'])
        records.extend(page_records)
        if total_known is not None and len(records) >= total_known:
            break
        if len(page_records) < limit:
            break
        page_from += limit
    return records

# ── Google Sheets ─────────────────────────────────────────────────────────────

def get_sheets_rows() -> list[dict]:
    import gspread
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    token_data = json.loads(GOOGLE_USER_TOKEN)
    # Do not override scopes — use whatever scopes the token was originally granted.
    creds = Credentials.from_authorized_user_info(token_data)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    gc = gspread.authorize(creds)
    ws = gc.open_by_key(SHEETS_SPREADSHEET_ID).worksheet(SHEETS_SHEET_NAME)
    return ws.get_all_records()

# ── Table A mapping ───────────────────────────────────────────────────────────

def _human_size(byte_count) -> str:
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
    return {
        'drive_file_id':      str(row.get('ID', '')).strip(),
        'file_name':          str(row.get('Name', '')).strip(),
        'drive_path':         str(row.get('Folder Path', '')).strip(),
        'drive_created_date': str(row.get('Created Time', '')).strip(),
        'drive_modified_date': str(row.get('Modified Time', '')).strip(),
        'drive_file_size':    _human_size(row.get('Size (Bytes)', '')),
        'drive_mime_type':    str(row.get('MimeType', '')).strip(),
        'drive_url':          str(row.get('URL', '')).strip(),
        'md5_checksum':       str(row.get('MD5 Checksum', '')).strip(),
        'description':        str(row.get('Description', '')).strip(),
    }


def rows_to_tsv(rows: list[dict]) -> str:
    if not rows:
        return ''
    headers = list(rows[0].keys())
    lines = ['\t'.join(headers)]
    for row in rows:
        cells = [
            str(row.get(h, '') or '').replace('\t', ' ').replace('\n', ' ').replace('\r', ' ')
            for h in headers
        ]
        lines.append('\t'.join(cells))
    return '\n'.join(lines)

# ── Date extraction ───────────────────────────────────────────────────────────

def extract_date_from_filename(name: str) -> str | None:
    """Extract YYYY-MM-DD from a filename. Handles Devanagari digit prefixes,
    Marathi month names, DD-MM-YYYY, and year-only fallback.
    """
    if not name:
        return None
    name_ascii = name.translate(_DEV_DIGITS)

    # Pattern 1: YYYY-MM-DD
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

    # Pattern 3: Marathi month names — "DD MonthName YYYY"
    for mname, mnum in _MARATHI_MONTHS.items():
        m = re.search(r'(\d{1,2})\s+' + re.escape(mname) + r'\s+(\d{4})', name_ascii)
        if m:
            d, y = int(m.group(1)), int(m.group(2))
            if 1900 <= y <= 2100 and 1 <= d <= 31:
                return f'{y:04d}-{int(mnum):02d}-{d:02d}'

    # Fallback: year only → YYYY-01-01
    m = re.search(r'\b(19\d{2}|20[0-2]\d)\b', name_ascii)
    if m:
        return f'{m.group(1)}-01-01'

    return None

# ── Table B operations ────────────────────────────────────────────────────────

def get_table_b_drive_ids() -> set[str]:
    """Return set of drive_file_ids already present in Table B."""
    records = zoho_fetch_all_report(REPORT_ENRICHMENT)
    return {r.get('drive_file_id', '') for r in records if r.get('drive_file_id')}


def insert_new_table_b_rows(new_ids: list[str], sheets_rows_by_id: dict[str, dict]) -> int:
    """Insert skeleton Table B rows for drive_file_ids not yet in Table B.
    Only sets drive_file_id, document_date, and is_private — all other fields
    are left for HITL enrichment. Checkbox-with-choices fields omitted (default = unchecked).
    """
    inserted = 0
    for drive_id in new_ids:
        row = sheets_rows_by_id.get(drive_id, {})
        filename = row.get('Name', '')
        doc_date = extract_date_from_filename(filename) or ''
        try:
            zoho_post(f'form/{FORM_ENRICHMENT}', {
                'drive_file_id':   drive_id,
                'document_date':   doc_date,
                # is_private omitted — Zoho Decision Box rejects string values;
                # default (unchecked = public) correct for skeleton rows.
                'authority_codes': '',
                'custom_labels':   '',
                'context_findings': '',
            })
            inserted += 1
            time.sleep(0.1)
        except Exception as e:
            print(f'  WARN: Failed to insert Table B row for {drive_id}: {e}')
    return inserted

# ── Cache build ───────────────────────────────────────────────────────────────

def build_cache_json(sheets_rows: list[dict],
                     table_b_records: list[dict],
                     table_c_records: list[dict]) -> list[dict]:
    b_by_id = {r.get('drive_file_id', ''): r for r in table_b_records if r.get('drive_file_id')}
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
        links = [
            {
                'linkedId':    lk.get('linked_drive_id', ''),
                'linkType':    lk.get('link_type', ''),
                'linkDetails': lk.get('link_details', ''),
                'timestamp':   lk.get('timestamp', ''),
                '_zohoLinkId': lk.get('ID', ''),
            }
            for lk in c_by_source.get(fid, [])
        ]
        # Checkbox-with-choices fields return choice label string ('TRUE'/'FALSE').
        # Decision Box fields return Python True/False or empty string.
        _truthy = ('TRUE', 'true', True, '1', 1, 'yes', 'Yes')
        nodes.append({
            'id':          fid,
            'name':        str(row.get('Name', '')).strip(),
            'path':        str(row.get('Folder Path', '')).strip(),
            'created':     str(row.get('Created Time', '')).strip(),
            'modified':    str(row.get('Modified Time', '')).strip(),
            'size':        _human_size(row.get('Size (Bytes)', '')),
            'mime':        str(row.get('MimeType', '')).strip(),
            'url':         str(row.get('URL', '')).strip(),
            'md5':         str(row.get('MD5 Checksum', '')).strip(),
            'description': str(row.get('Description', '')).strip(),
            # Enrichment from Table B (empty defaults when no B row exists)
            'authorityCodes':       [c.strip() for c in b.get('authority_codes', '').split(',') if c.strip()],
            'customLabels':         [l.strip() for l in b.get('custom_labels', '').split(',') if l.strip()],
            'isPrivate':            b.get('is_private', '') in _truthy,
            'contextFindings':      b.get('context_findings', ''),
            'documentType':         b.get('document_type', ''),
            'documentDate':         b.get('document_date', ''),
            'saraswatiProcessed':   b.get('saraswati_processed', '') in _truthy,
            'sanjayaApproved':      b.get('sanjaya_approved', '') in _truthy,
            'vishwakarmaPublished': b.get('vishwakarma_published', '') in _truthy,
            'links':    links,
            '_zohoBId': b.get('ID', ''),
        })
    return nodes

# ── Drive cache write ─────────────────────────────────────────────────────────

def get_drive_service():
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    creds = Credentials.from_authorized_user_info(json.loads(GOOGLE_USER_TOKEN))
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return build('drive', 'v3', credentials=creds)


def write_cache_to_drive(nodes: list[dict]) -> str:
    from googleapiclient.http import MediaIoBaseUpload
    service = get_drive_service()
    json_bytes = json.dumps(nodes, ensure_ascii=False, indent=None).encode('utf-8')
    media = MediaIoBaseUpload(io.BytesIO(json_bytes), mimetype='application/json', resumable=False)
    query = f"name='{CACHE_FILENAME}' and '{CACHE_DRIVE_FOLDER_ID}' in parents and trashed=false"
    existing = service.files().list(q=query, fields='files(id,name)', supportsAllDrives=True).execute()
    files = existing.get('files', [])
    if files:
        file_id = files[0]['id']
        service.files().update(
            fileId=file_id, media_body=media,
            supportsAllDrives=True, quotaUser=GOOGLE_QUOTA_USER,
        ).execute()
        print(f'  Updated existing cache file: {file_id}')
    else:
        meta = {'name': CACHE_FILENAME, 'parents': [CACHE_DRIVE_FOLDER_ID]}
        result = service.files().create(
            body=meta, media_body=media, fields='id',
            supportsAllDrives=True, quotaUser=GOOGLE_QUOTA_USER,
        ).execute()
        file_id = result['id']
        print(f'  Created new cache file: {file_id}')
        print(f'  ACTION REQUIRED: Set CASE_LIBRARY_CACHE_FILE_ID={file_id} in Railway env vars')
    return file_id


def write_seed_csv_locally(sheets_rows: list[dict]) -> list[dict]:
    """Write case_library_enrichment_seed.csv for HITL reference.
    Returns the row dicts so the caller can batch-POST them to Zoho.
    Checkbox-with-choices fields (saraswati_processed, sanjaya_approved,
    vishwakarma_published) are excluded — Zoho defaults them to unchecked.
    """
    import csv
    fields = ['drive_file_id', 'document_date',
              'authority_codes', 'custom_labels', 'context_findings', 'document_type']
    rows = []
    for row in sheets_rows:
        fid = str(row.get('ID', '')).strip()
        name = str(row.get('Name', '')).strip()
        if not fid:
            continue
        rows.append({
            'drive_file_id':   fid,
            'document_date':   extract_date_from_filename(name) or '',
            # is_private omitted — Zoho Decision Box rejects string values;
            # default (unchecked = public) is correct for initial seed.
            # Set per-document via Flask UI after seeding.
            'authority_codes': '',
            'custom_labels':   '',
            'context_findings': '',
            'document_type':   '',
        })
    path = 'case_library_enrichment_seed.csv'
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f'  Wrote seed CSV: {path} ({len(rows)} rows)')
    return rows

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    seed_b    = '--seed-b'    in sys.argv
    cache_only = '--cache-only' in sys.argv

    missing = [v for v in [
        'ZOHO_CLIENT_ID', 'ZOHO_CLIENT_SECRET', 'ZOHO_REFRESH_TOKEN',
        'ZOHO_OWNER', 'ZOHO_APP_NAME', 'SHEETS_SPREADSHEET_ID',
        'GOOGLE_USER_TOKEN', 'CACHE_DRIVE_FOLDER_ID',
    ] if not os.environ.get(v)]
    if missing:
        print(f'ERROR: Missing required env vars: {", ".join(missing)}')
        sys.exit(1)

    ts = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    print(f'[{ts}] Case Library sync starting...')

    # ── Step 1: Read Google Sheets ──────────────────────────────────────────
    print('[1/5] Reading Google Sheets...')
    sheets_rows = get_sheets_rows()
    print(f'      {len(sheets_rows)} rows read from "{SHEETS_SHEET_NAME}"')
    sheets_rows_by_id = {str(r.get('ID', '')).strip(): r for r in sheets_rows if r.get('ID')}

    seed_rows: list[dict] = []
    if seed_b:
        print('[SEED] Writing enrichment seed CSV for Table B...')
        seed_rows = write_seed_csv_locally(sheets_rows)

    if cache_only:
        print('[CACHE-ONLY] Skipping Zoho writes...')
    else:
        # ── Step 2: Full wipe + reload Table A ─────────────────────────────
        # Table A = complete refresh every run. Wipe via Deluge function
        # (REST API DELETE does not support criteria-based bulk delete).
        # Requires Deluge function 'delete_all_case_library_base' in Zoho JDO app:
        #   void delete_all_case_library_base() {
        #       delete from Case_Library_Base[ID != null];
        #   }
        print('[2/5] Refreshing Table A (Case_Library_Base) — full wipe + reload...')
        table_a_rows = [sheets_row_to_table_a(r) for r in sheets_rows if r.get('ID')]
        tsv_path = 'case_library_base_import.tsv'
        with open(tsv_path, 'w', encoding='utf-8') as f:
            f.write(rows_to_tsv(table_a_rows))
        print(f'      Wrote Table A TSV locally: {tsv_path} ({len(table_a_rows)} rows)')

        table_a_cleared = False
        try:
            # Calls Zoho Custom API that wraps the delete_all_case_library_base Deluge function.
            # Setup: Zoho Creator → Microservices → Custom APIs → delete_case_library_base
            zoho_call_custom_api('delete_case_library_base')
            print(f'      Deleted all existing Table A records (via Custom API)')
            table_a_cleared = True
        except RuntimeError as del_e:
            err = str(del_e)
            if '3100' in err or 'No Data Available' in err or '9220' in err or 'No records exist' in err:
                print(f'      Table A already empty — proceeding to insert')
                table_a_cleared = True
            else:
                # Do NOT insert if delete failed — inserting without clearing causes duplicates.
                print(f'  WARN: Table A delete via Custom API failed — INSERT BLOCKED to prevent duplicates')
                print(f'  Error: {del_e}')
                print(f'  ACTION REQUIRED:')
                print(f'    1. Manually delete all Case_Library_Base records in Zoho UI')
                print(f'    2. Confirm Custom API "delete_case_library_base" exists:')
                print(f'       Zoho Creator → JDO → Microservices → Custom APIs')
                print(f'       It must invoke Deluge function: delete_all_case_library_base')
                print(f'    3. Re-run this script after manual cleanup')

        if table_a_cleared:
            try:
                inserted = zoho_batch_post(FORM_BASE, table_a_rows)
                print(f'      Inserted {inserted} Table A rows')
            except Exception as e:
                print(f'  WARN: Table A batch insert failed (pipeline continues): {e}')
                print(f'  ACTION: Manually import {tsv_path} into Zoho form Case_Library_Base')

        # ── Step 3: Append-only Table B ────────────────────────────────────
        # Table B is NEVER wiped. Only new drive_file_ids get skeleton rows.
        # Existing enrichments (labels, context, flags) are always preserved.
        print('[3/5] Detecting new Drive IDs for Table B...')
        b_existing = get_table_b_drive_ids()

        if seed_b and seed_rows:
            # Seed mode: insert only rows not already in Table B (idempotent re-run safe).
            missing_rows = [r for r in seed_rows if r['drive_file_id'] not in b_existing]
            print(f'      {len(missing_rows)} rows missing from Table B (of {len(seed_rows)} total)')
            if missing_rows:
                print(f'      Uploading {len(missing_rows)} seed rows in batches...')
                inserted = zoho_batch_post(FORM_ENRICHMENT, missing_rows)
                print(f'      Inserted {inserted} Table B seed rows')
            else:
                print(f'      Table B already fully seeded — nothing to insert')
        else:
            # Daily mode: only genuinely new Drive IDs.
            new_ids = [fid for fid in sheets_rows_by_id if fid not in b_existing]
            print(f'      {len(new_ids)} new IDs to append into Table B')
            if new_ids:
                inserted = insert_new_table_b_rows(new_ids, sheets_rows_by_id)
                print(f'      Appended {inserted} new skeleton rows into Table B')

    # ── Step 4: Fetch Table B + C from Zoho ────────────────────────────────
    print('[4/5] Fetching Table B (enrichment) and Table C (links) from Zoho...')
    table_b = zoho_fetch_all_report(REPORT_ENRICHMENT)
    table_c = zoho_fetch_all_report(REPORT_LINKS)
    print(f'      Table B: {len(table_b)} rows | Table C: {len(table_c)} rows')

    # ── Step 5: Build JSON cache + write to Drive ───────────────────────────
    print('[5/5] Building JSON cache and writing to Google Drive...')
    nodes = build_cache_json(sheets_rows, table_b, table_c)
    print(f'      {len(nodes)} nodes in cache')
    file_id = write_cache_to_drive(nodes)

    ts_end = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    print(f'[{ts_end}] Sync complete. Cache file ID: {file_id}')


if __name__ == '__main__':
    main()
