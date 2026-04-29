"""
qr_routes.py - Narada QR Tracking System (Zoho Creator JDO backend)

Canonical naming table (DO NOT DRIFT)
-------------------------------------
HTML id            | JSON key                   | Zoho field link name      | Form/Report
-------------------+----------------------------+---------------------------+--------------------
citizen_name       | citizen_name               | citizen_name              | Narada_Submissions
citizen_email_id   | citizen_email_id           | citizen_email_id          | Narada_Submissions
citizen_contact... | citizen_contact_number     | citizen_contact_number    | Narada_Submissions
authority_code     | recipient_authority_code   | recipient_authority_code  | Narada_Submissions
submission_type    | application_type           | application_type          | Narada_Submissions
eta_date           | expected_turnaround_time   | expected_turnaround_time  | Narada_Submissions
additional_note    | additional_notes           | additional_notes          | Narada_Submissions
url                | relevant_url               | relevant_url              | Narada_Submissions
(server)           | qr_id                      | qr_id                     | Narada_Submissions
(server)           | qr_generation_timestamp    | qr_generation_timestamp   | Narada_Submissions
(server)           | status                     | status                    | Narada_Submissions

Date formats expected by Zoho:
  date     -> dd-MMM-yyyy           (e.g. 30-Apr-2026)
  datetime -> dd-MMM-yyyy HH:mm:ss  (e.g. 30-Apr-2026 14:35:09)
"""

# Canonical status values - MUST match Narada_Submissions.status dropdown
# choices in Zoho Creator AND Narada_Scan_Events.status_new choices.
# Source of truth: Config_Status_Report (master list).
VALID_STATUSES = (
    'Not Yet Received',
    'SUBMITTED',
    'IN PROGRESS',
    'REJECTED',
    'SILENCED',
    'COMPLETED',
)
DEFAULT_STATUS = 'Not Yet Received'

from flask import Blueprint, request, jsonify, render_template
import os
import time
import requests
from datetime import datetime
import qrcode
from PIL import Image
import io
import base64
import traceback
import pytz

qr_bp = Blueprint('narada_qr', __name__, url_prefix='/')

IST = pytz.timezone('Asia/Kolkata')

# Zoho Config (from Railway env vars)
ZOHO_OWNER = os.environ.get('ZOHO_OWNER_NAME')
ZOHO_APP = os.environ.get('ZOHO_APP_LINK_NAME')
ZOHO_DOMAIN = os.environ.get('ZOHO_API_DOMAIN', 'https://www.zohoapis.in')

# OAuth refresh-token flow
ZOHO_CLIENT_ID = os.environ.get('ZOHO_CLIENT_ID')
ZOHO_CLIENT_SECRET = os.environ.get('ZOHO_CLIENT_SECRET')
ZOHO_REFRESH_TOKEN = os.environ.get('ZOHO_REFRESH_TOKEN')
ZOHO_ACCOUNTS_DOMAIN = os.environ.get('ZOHO_ACCOUNTS_DOMAIN', 'https://accounts.zoho.in')

_token_cache = {'token': None, 'expires_at': 0}


# ---------------------------------------------------------------------------
# Zoho helpers
# ---------------------------------------------------------------------------

def get_access_token():
    now = time.time()
    if _token_cache['token'] and _token_cache['expires_at'] > now + 60:
        return _token_cache['token']

    if not (ZOHO_CLIENT_ID and ZOHO_CLIENT_SECRET and ZOHO_REFRESH_TOKEN):
        raise RuntimeError("Missing Zoho OAuth env vars")

    resp = requests.post(
        f"{ZOHO_ACCOUNTS_DOMAIN}/oauth/v2/token",
        params={
            'refresh_token': ZOHO_REFRESH_TOKEN,
            'client_id': ZOHO_CLIENT_ID,
            'client_secret': ZOHO_CLIENT_SECRET,
            'grant_type': 'refresh_token',
        },
        timeout=10,
    )
    body = resp.json()
    if 'access_token' not in body:
        raise RuntimeError(f"Zoho token refresh failed: HTTP {resp.status_code} {body}")
    _token_cache['token'] = body['access_token']
    _token_cache['expires_at'] = now + int(body.get('expires_in', 3600))
    print(f"[zoho] Refreshed access token, valid for {body.get('expires_in', 3600)}s")
    return _token_cache['token']


def get_headers():
    return {
        'Authorization': f'Zoho-oauthtoken {get_access_token()}',
        'Content-Type': 'application/json',
    }


def zoho_get(report_link_name, criteria='', max_records=200):
    url = f"{ZOHO_DOMAIN}/creator/v2.1/data/{ZOHO_OWNER}/{ZOHO_APP}/report/{report_link_name}"
    params = {'max_records': max_records}
    if criteria:
        params['criteria'] = criteria
    resp = requests.get(url, headers=get_headers(), params=params, timeout=15)
    return resp.json()


def zoho_post(form_link_name, data):
    url = f"{ZOHO_DOMAIN}/creator/v2.1/data/{ZOHO_OWNER}/{ZOHO_APP}/form/{form_link_name}"
    payload = {"data": data}
    resp = requests.post(url, json=payload, headers=get_headers(), timeout=15)
    return resp.json()


def zoho_patch(report_link_name, record_id, data):
    """Update an existing record. v2.1: PATCH /data/.../report/{report}/{id}"""
    url = f"{ZOHO_DOMAIN}/creator/v2.1/data/{ZOHO_OWNER}/{ZOHO_APP}/report/{report_link_name}/{record_id}"
    payload = {"data": data}
    resp = requests.patch(url, json=payload, headers=get_headers(), timeout=15)
    return resp.json()


# ---------------------------------------------------------------------------
# Date helpers - Zoho expects dd-MMM-yyyy
# ---------------------------------------------------------------------------

def to_zoho_date(iso_date):
    """Convert 'YYYY-MM-DD' (HTML date input) -> 'DD-MMM-YYYY' (Zoho)."""
    if not iso_date:
        return ''
    try:
        return datetime.strptime(iso_date, '%Y-%m-%d').strftime('%d-%b-%Y')
    except ValueError:
        return iso_date  # already in some other format; let Zoho complain


def to_zoho_datetime(dt):
    """datetime -> 'DD-MMM-YYYY HH:MM:SS' for Zoho datetime fields."""
    return dt.strftime('%d-%b-%Y %H:%M:%S')


def display_date(zoho_date):
    """Zoho '30-Apr-2026' -> 'DD-MMM-YY' for the dashboard."""
    if not zoho_date:
        return ''
    try:
        return datetime.strptime(zoho_date, '%d-%b-%Y').strftime('%d-%b-%y')
    except ValueError:
        return zoho_date


# ---------------------------------------------------------------------------
# QR helpers
# ---------------------------------------------------------------------------

def get_ist_now():
    return datetime.now(IST)


def generate_event_id():
    return f"EVT-{int(get_ist_now().timestamp())}"


def generate_qr_id(authority_code):
    """TEA-{Authority}-DDMMMYY-NNNNN (sequence = seconds since IST midnight)"""
    now = get_ist_now()
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    seq = f"{int((now - midnight).total_seconds()):05d}"
    return f"TEA-{authority_code}-{now.strftime('%d%b%y').upper()}-{seq}"


def create_qr_image(short_url):
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=4)
    qr.add_data(short_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#1a365d", back_color="white").convert('RGB')
    logo_path = os.path.join(os.path.dirname(__file__), 'static', 'Logo.jpg')
    if os.path.exists(logo_path):
        logo = Image.open(logo_path).resize((80, 80))
        pos = ((img.size[0] - logo.size[0]) // 2, (img.size[1] - logo.size[1]) // 2)
        img.paste(logo, pos)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode('utf-8')


def log_scan_event(qr_id, event_type="SCAN", comment_text="", eta_new="", status_new=""):
    """Append one row to Narada_Scan_Events. Best-effort; never raises."""
    try:
        ip = request.headers.get('X-Forwarded-For', request.remote_addr) or 'Unknown'
        ua = request.headers.get('User-Agent', 'Unknown')[:1000]  # Zoho text field cap
        record = {
            'event_id': generate_event_id(),
            'qr_id': qr_id,
            'event_type': event_type,
            'timestamp': to_zoho_datetime(get_ist_now()),
            'ip_address': ip,
            'user_agent': ua,
            'comment_text': comment_text,
        }
        if eta_new:
            record['eta_new'] = to_zoho_date(eta_new)
        if status_new:
            record['status_new'] = status_new
        return zoho_post('Narada_Scan_Events', record)
    except Exception as e:
        print(f"[scan_event] log failed: {e}")
        return None


def fetch_submission(qr_id):
    """Return (record_id, record_dict) for a qr_id, or (None, None) if not found."""
    # Zoho criteria string syntax
    criteria = f'qr_id == "{qr_id}"'
    resp = zoho_get('Narada_Submissions_Report', criteria=criteria, max_records=1)
    rows = resp.get('data', [])
    if not rows:
        return None, None
    row = rows[0]
    return row.get('ID'), row


def fetch_events(qr_id, limit=200):
    criteria = f'qr_id == "{qr_id}"'
    resp = zoho_get('Narada_Scan_Events_Report', criteria=criteria, max_records=limit)
    events = resp.get('data', []) or []
    # newest first
    events.sort(key=lambda e: e.get('timestamp', ''), reverse=True)
    return events


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@qr_bp.route('/generator', methods=['GET'])
def generator():
    return render_template('qr_generator.html')


@qr_bp.route('/api/config', methods=['GET'])
def get_config():
    try:
        auth = zoho_get('Config_Authority_Registry_Report')
        types = zoho_get('Config_Submission_Types_Report')
        statuses_resp = zoho_get('Config_Status_Report')

        authorities = [
            {'code': r.get('authority_registry_code'), 'name': r.get('authority_name')}
            for r in auth.get('data', [])
            if r.get('authority_registry_code')
        ]
        submission_types = [
            {'code': r.get('submission_type_code'), 'name': r.get('submission_type_name')}
            for r in types.get('data', [])
            if r.get('submission_type_code')
        ]
        statuses = [r.get('Status') for r in statuses_resp.get('data', []) if r.get('Status')]

        return jsonify({
            'authorities': authorities,
            'submission_types': submission_types,
            'statuses': statuses or ['Not Yet Received', 'SUBMITTED', 'IN PROGRESS', 'REJECTED', 'SILENCED', 'COMPLETED'],
        })
    except Exception as e:
        print('[config] error:', traceback.format_exc())
        return jsonify({'error': str(e)}), 500


@qr_bp.route('/qr/generate', methods=['POST'])
def generate_qr():
    try:
        data = request.get_json() or {}

        citizen_name = (data.get('citizen_name') or '').strip()
        citizen_email = (data.get('citizen_email_id') or '').strip()
        citizen_contact = (data.get('citizen_contact_number') or '').strip()
        authority = (data.get('recipient_authority_code') or 'OTH').strip()
        app_type = (data.get('application_type') or 'APPL').strip()
        eta = (data.get('expected_turnaround_time') or '').strip()
        notes = (data.get('additional_notes') or '').strip()
        url = (data.get('relevant_url') or '').strip()

        if not all([citizen_name, citizen_email, eta, notes]):
            return jsonify({'error': 'Mandatory fields missing'}), 400

        qr_id = generate_qr_id(authority)
        now_ist = get_ist_now()

        record = {
            'qr_id': qr_id,
            'citizen_name': citizen_name,
            'citizen_email_id': citizen_email,
            'recipient_authority_code': authority,
            'application_type': app_type,
            'expected_turnaround_time': to_zoho_date(eta),
            'additional_notes': notes,
            'qr_generation_timestamp': to_zoho_datetime(now_ist),
            'status': DEFAULT_STATUS,
        }
        if citizen_contact:
            record['citizen_contact_number'] = citizen_contact
        if url:
            record['relevant_url'] = url

        zoho_resp = zoho_post('Narada_Submissions', record)
        print(f"[generate] zoho insert response: {zoho_resp}")

        if zoho_resp.get('code') and zoho_resp.get('code') != 3000:
            # Zoho convention: code 3000 = success
            return jsonify({'error': 'Failed to save submission', 'zoho': zoho_resp}), 500

        # Log GENERATE event (non-blocking)
        log_scan_event(qr_id, event_type='GENERATE', comment_text='QR generated')

        short_url = f"https://dev.jagdishwaram-office.org/scan/{qr_id}"
        image_base64 = create_qr_image(short_url)

        return jsonify({
            'qr_id': qr_id,
            'short_url': short_url,
            'image_base64': image_base64,
            'download_name': f"QR-{qr_id}.png",
            'success': True,
        })
    except Exception as e:
        print('[generate] error:', traceback.format_exc())
        return jsonify({'error': str(e)}), 500


@qr_bp.route('/scan/<qr_id>', methods=['GET'])
def scan_dashboard(qr_id):
    try:
        record_id, record = fetch_submission(qr_id)
        if not record:
            return f"QR ID {qr_id} not found", 404

        # Log this scan (best-effort)
        log_scan_event(qr_id, event_type='SCAN')

        events = fetch_events(qr_id)

        return render_template(
            'qr_dashboard.html',
            qr_id=qr_id,
            name=record.get('citizen_name', ''),
            email=record.get('citizen_email_id', ''),
            contact=record.get('citizen_contact_number', ''),
            authority=record.get('recipient_authority_code', ''),
            sub_type=record.get('application_type', ''),
            eta=display_date(record.get('expected_turnaround_time', '')),
            eta_iso=record.get('expected_turnaround_time', ''),
            note=record.get('additional_notes', ''),
            url=record.get('relevant_url', ''),
            status=record.get('status', 'Not Yet Received'),
            events=events,
        )
    except Exception as e:
        print('[scan] error:', traceback.format_exc())
        return f"Error loading record: {e}", 500


@qr_bp.route('/api/update_record', methods=['POST'])
def update_record():
    try:
        data = request.get_json() or {}
        qr_id = (data.get('qr_id') or '').strip()
        comment = (data.get('comment') or '').strip()
        eta_new = (data.get('eta') or '').strip()        # ISO yyyy-mm-dd from <input type="date">
        status_new = (data.get('status') or '').strip()

        if not qr_id:
            return jsonify({'error': 'qr_id missing'}), 400

        if status_new and status_new not in VALID_STATUSES:
            return jsonify({
                'error': f"Invalid status '{status_new}'. Must be one of: {', '.join(VALID_STATUSES)}"
            }), 400

        record_id, record = fetch_submission(qr_id)
        if not record:
            return jsonify({'error': 'Submission not found'}), 404

        # Decide whether anything actually changed -> patch the submission
        current_eta_iso = ''
        try:
            current_eta_iso = datetime.strptime(record.get('expected_turnaround_time', ''), '%d-%b-%Y').strftime('%Y-%m-%d')
        except ValueError:
            pass
        current_status = record.get('status', '')

        patch_payload = {}
        if eta_new and eta_new != current_eta_iso:
            patch_payload['expected_turnaround_time'] = to_zoho_date(eta_new)
        if status_new and status_new != current_status:
            patch_payload['status'] = status_new

        patched = False
        if patch_payload:
            patch_resp = zoho_patch('Narada_Submissions_Report', record_id, patch_payload)
            print(f"[update] patch response: {patch_resp}")
            patched = True

        # Append event (UPDATE if values changed, COMMENT if just a comment, otherwise NOOP-comment)
        if patched:
            event_type = 'UPDATE'
        elif comment:
            event_type = 'COMMENT'
        else:
            return jsonify({'success': True, 'message': 'No changes to log'}), 200

        log_scan_event(
            qr_id,
            event_type=event_type,
            comment_text=comment,
            eta_new=eta_new if 'expected_turnaround_time' in patch_payload else '',
            status_new=status_new if 'status' in patch_payload else '',
        )

        return jsonify({'success': True, 'patched': patched, 'event_type': event_type})
    except Exception as e:
        print('[update] error:', traceback.format_exc())
        return jsonify({'error': str(e)}), 500


print("✅ ZOHO QR ROUTES LOADED (end-to-end: generate, scan, update)")
