from flask import Blueprint, request, jsonify, render_template
import os
import requests
from datetime import datetime
import uuid

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
    resp = requests.post(url, json=payload, headers=get_headers())
    return resp.json()

def zoho_get(form_link_name, criteria):
    url = f"{ZOHO_DOMAIN}/creator/v2.1/{ZOHO_OWNER}/{ZOHO_APP}/{form_link_name}/records"
    params = {'criteria': criteria}
    resp = requests.get(url, headers=get_headers(), params=params)
    return resp.json()

@qr_bp.route('/generator', methods=['GET'])
def generator():
    return render_template('qr_generator.html')

@qr_bp.route('/qr/generate', methods=['POST'])
def generate_qr():
    data = request.get_json() or {}
    # Mandatory field validation
    required = ['citizen_name', 'citizen_email_id', 'recipient_authority_code', 'application_type', 'expected_turnaround_time']
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({'error': f'Mandatory fields missing: {missing}'}), 400

    # Generate QR ID (same logic as before)
    authority = data.get('recipient_authority_code', 'OTH')
    now = datetime.now()
    date_str = now.strftime('%d%b%y').upper()
    seconds = (now - now.replace(hour=0, minute=0, second=0, microsecond=0)).seconds
    seq = f"{seconds:05d}"
    qr_id = f"TEA-{authority}-{date_str}-{seq}"

    # Prepare submission record
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
        'qr_generation_timestamp': datetime.now().isoformat(),
        'status': 'New'
    }

    # Save to Zoho
    result = zoho_post('Narada_Submissions', record)

    # Generate QR image (same as previous version)
    # ... (keep your existing create_qr_image + base64 logic here - unchanged)

    return jsonify({
        'qr_id': qr_id,
        'image_base64': image_base64,   # your existing base64 variable
        'success': True
    })

@qr_bp.route('/scan/<qr_id>', methods=['GET'])
def scan_dashboard(qr_id):
    # Fetch submission
    criteria = f"qr_id == \"{qr_id}\""
    sub_resp = zoho_get('Narada_Submissions', criteria)
    if not sub_resp.get('data'):
        return render_template('qr_dashboard.html', error="Record not found")
    
    record = sub_resp['data'][0]

    # Auto-log scan event
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

    # Fetch all events for this QR
    events_resp = zoho_get('Narada_Scan_Events', f"qr_id == \"{qr_id}\"")
    events = events_resp.get('data', [])

    return render_template('qr_dashboard.html', 
                           record=record, 
                           events=events,
                           qr_id=qr_id)

# Add /api/update_record endpoint for comments/ETA/status (same as previous version but using Zoho update API)
# ... (full implementation available on next message if needed)

print("✅ Zoho Creator routes loaded successfully")
