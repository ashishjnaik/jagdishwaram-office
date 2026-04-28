from flask import Blueprint, request, jsonify, render_template, send_file
import os
import requests
from datetime import datetime
import uuid
import qrcode
from PIL import Image, ImageDraw
import io
import base64

qr_bp = Blueprint('narada_qr', __name__, url_prefix='/')

# Zoho Config
ZOHO_ACCESS_TOKEN = os.environ.get('ZOHO_ACCESS_TOKEN')
ZOHO_REFRESH_TOKEN = os.environ.get('ZOHO_REFRESH_TOKEN')
ZOHO_OWNER = os.environ.get('ZOHO_OWNER_NAME')
ZOHO_APP = os.environ.get('ZOHO_APP_LINK_NAME')
ZOHO_DOMAIN = os.environ.get('ZOHO_API_DOMAIN', 'https://www.zohoapis.in')

def get_headers():
    return {
        'Authorization': f'Zoho-oauthtoken {ZOHO_ACCESS_TOKEN}',
        'Content-Type': 'application/json'
    }

def zoho_post(form_link_name, data):
    url = f"{ZOHO_DOMAIN}/creator/v2.1/{ZOHO_OWNER}/{ZOHO_APP}/{form_link_name}/records"
    payload = {"data": [data]}
    resp = requests.post(url, json=payload, headers=get_headers(), timeout=10)
    return resp.json()

def zoho_get(form_link_name, criteria):
    url = f"{ZOHO_DOMAIN}/creator/v2.1/{ZOHO_OWNER}/{ZOHO_APP}/{form_link_name}/records"
    params = {'criteria': criteria}
    resp = requests.get(url, headers=get_headers(), params=params, timeout=10)
    return resp.json()

def create_qr_image(short_url):
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=4)
    qr.add_data(short_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
    logo_path = os.path.join(os.path.dirname(__file__), 'static', 'Logo.jpg')
    if os.path.exists(logo_path):
        logo = Image.open(logo_path).convert('RGB')
        logo = logo.resize((80, 80))
        pos = ((img.size[0] - logo.size[0]) // 2, (img.size[1] - logo.size[1]) // 2)
        img.paste(logo, pos)
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

@qr_bp.route('/generator', methods=['GET'])
def generator():
    return render_template('qr_generator.html')

@qr_bp.route('/qr/generate', methods=['POST'])
def generate_qr():
    data = request.get_json() or {}
    required = ['citizen_name', 'citizen_email_id', 'recipient_authority_code', 'application_type', 'expected_turnaround_time']
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({'error': f'Mandatory fields missing: {missing}'}), 400

    authority = data.get('recipient_authority_code', 'OTH')
    now = datetime.now()
    date_str = now.strftime('%d%b%y').upper()
    seconds = (now - now.replace(hour=0, minute=0, second=0, microsecond=0)).seconds
    seq = f"{seconds:05d}"
    qr_id = f"TEA-{authority}-{date_str}-{seq}"

    record = {
        'qr_id': qr_id,
        'citizen_name': data.get('citizen_name'),
        'citizen_email_id': data.get('citizen_email_id'),
        'citizen_contact_number': data.get('citizen_contact_number'),
        'recipient_authority_code': data.get('recipient_authority_code'),
        'application_type': data.get('application_type'),
        'expected_turnaround_time': data.get('expected_turnaround_time'),
        'additional_notes': data.get('additional_notes'),
        'relevant_url': data.get('relevant_url'),
        'qr_generation_timestamp': now.isoformat(),
        'status': 'New'
    }

    zoho_post('Narada_Submissions', record)
    image_base64 = create_qr_image(f"https://dev.jagdishwaram-office.org/scan/{qr_id}")

    return jsonify({'qr_id': qr_id, 'image_base64': image_base64, 'success': True})

@qr_bp.route('/scan/<qr_id>', methods=['GET'])
def scan_dashboard(qr_id):
    criteria = f'qr_id == "{qr_id}"'
    sub_resp = zoho_get('Narada_Submissions', criteria)
    if not sub_resp.get('data'):
        return render_template('qr_dashboard.html', error="Record not found", qr_id=qr_id)

    record = sub_resp['data'][0]

    # Auto-log SCAN event
    event = {
        'event_id': f"EVT-{uuid.uuid4().hex[:8].upper()}",
        'qr_id': qr_id,
        'event_type': 'SCAN',
        'timestamp': datetime.now().isoformat(),
        'ip_address': request.headers.get('X-Forwarded-For', request.remote_addr),
        'user_agent': request.headers.get('User-Agent'),
        'comment_text': '',
        'eta_new': record.get('expected_turnaround_time'),
        'status_new': record.get('status')
    }
    zoho_post('Narada_Scan_Events', event)

    events_resp = zoho_get('Narada_Scan_Events', f'qr_id == "{qr_id}"')
    events = events_resp.get('data', [])

    return render_template('qr_dashboard.html', record=record, events=events, qr_id=qr_id)

@qr_bp.route('/api/update_record', methods=['POST'])
def update_record():
    data = request.get_json() or {}
    qr_id = data.get('qr_id')
    if not qr_id:
        return jsonify({'error': 'qr_id missing'}), 400

    update_data = {}
    if data.get('comment_text'):
        update_data['comment_text'] = data['comment_text']
    if data.get('eta_new'):
        update_data['eta_new'] = data['eta_new']
    if data.get('status_new'):
        update_data['status_new'] = data['status_new']

    if update_data:
        event = {
            'event_id': f"EVT-{uuid.uuid4().hex[:8].upper()}",
            'qr_id': qr_id,
            'event_type': 'UPDATE',
            'timestamp': datetime.now().isoformat(),
            'ip_address': request.headers.get('X-Forwarded-For', request.remote_addr),
            'user_agent': request.headers.get('User-Agent'),
            **update_data
        }
        zoho_post('Narada_Scan_Events', event)

    return jsonify({'success': True})

print("✅ Zoho Creator Narada QR routes loaded successfully (full loop active)")
