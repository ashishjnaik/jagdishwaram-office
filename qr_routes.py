# qr_routes.py - Narada QR Tracking System v1.1 (Comment Logging + Editable ETA/Status)
from flask import Blueprint, render_template, request, jsonify
import qrcode
from PIL import Image
import io
import os
import base64
import json
from datetime import datetime
import traceback
import gspread
from google.oauth2.service_account import Credentials
import pytz

print("✅ qr_routes.py LOADED (v1.1 - Comment Logging + Editable ETA/Status)")

qr_bp = Blueprint('narada_qr', __name__, url_prefix='/')

IST = pytz.timezone('Asia/Kolkata')

def get_sheets_client():
    json_str = os.environ.get('NARADA_QR_SERVICE_ACCOUNT_JSON')
    if not json_str:
        return None
    creds_dict = json.loads(json_str)
    scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return gspread.authorize(creds)

def get_spreadsheet():
    client = get_sheets_client()
    if not client:
        return None
    spreadsheet_id = os.environ.get('NARADA_QR_SPREADSHEET_ID')
    if not spreadsheet_id:
        return None
    return client.open_by_key(spreadsheet_id)

def get_ist_now():
    return datetime.now(IST).isoformat()

def generate_qr_id(authority_code):
    year = datetime.now().year
    return f"TEA-{authority_code}-{year}-0001"

def create_qr_image(qr_url):
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=4)
    qr.add_data(qr_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#1a365d", back_color="white").convert('RGB')
    logo_path = "static/Logo.jpg"
    if os.path.exists(logo_path):
        logo = Image.open(logo_path).resize((80, 80))
        pos = ((img.size[0] - logo.size[0]) // 2, (img.size[1] - logo.size[1]) // 2)
        img.paste(logo, pos, mask=logo if logo.mode == 'RGBA' else None)
    return img

def log_scan_event(sheet, qr_id, event_type="SCAN", comment="", eta_new="", status_new=""):
    try:
        scan_events = sheet.worksheet("scan_events")
        ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        ua = request.headers.get('User-Agent', 'Unknown')
        now_ist = get_ist_now()
        scan_events.append_row([None, qr_id, event_type, now_ist, ip, ua, "", comment, eta_new, status_new])
    except Exception as e:
        print("Scan event log failed:", e)

@qr_bp.route('/generator', methods=['GET'])
def generator():
    return render_template('qr_generator.html')

@qr_bp.route('/qr/generate', methods=['POST'])
def generate_qr():
    try:
        data = request.get_json() or {}
        name = (data.get('name') or '').strip()
        email = (data.get('email') or '').strip()
        contact = (data.get('contact') or '').strip()
        authority = (data.get('authority_code') or 'OTH').strip()
        sub_type = (data.get('submission_type') or 'Application').strip()
        eta = (data.get('eta_date') or '').strip()
        note = (data.get('additional_note') or '').strip()
        url = (data.get('url') or '').strip()

        if not all([name, email, eta, note]):
            return jsonify({'error': 'Mandatory fields missing'}), 400

        qr_id = generate_qr_id(authority)
        short_url = f"https://dev.jagdishwaram-office.org/scan/{qr_id}"

        sheet = get_spreadsheet()
        if sheet:
            submissions = sheet.worksheet("submissions")
            submissions.append_row([qr_id, name, email, contact, authority, sub_type, eta, note, url, get_ist_now(), "Not Yet Received", ""])

        img = create_qr_image(short_url)
        img_io = io.BytesIO()
        img.save(img_io, 'PNG')
        img_io.seek(0)
        image_base64 = base64.b64encode(img_io.getvalue()).decode('utf-8')

        return jsonify({
            'qr_id': qr_id,
            'short_url': short_url,
            'download_name': f"QR-{qr_id}.png",
            'image_base64': image_base64
        })
    except Exception as e:
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@qr_bp.route('/scan/<qr_id>', methods=['GET'])
def scan_dashboard(qr_id):
    try:
        sheet = get_spreadsheet()
        if not sheet:
            return "Sheets not configured", 500

        # Auto-log SCAN event
        log_scan_event(sheet, qr_id, "SCAN")

        submissions = sheet.worksheet("submissions")
        records = submissions.get_all_records()
        record = next((r for r in records if r.get('qr_id') == qr_id), None)
        if not record:
            return "QR ID not found", 404

        # Fetch scan events
        scan_events = sheet.worksheet("scan_events")
        events = [e for e in scan_events.get_all_records() if e.get('qr_id') == qr_id]
        events.sort(key=lambda x: x.get('timestamp_ist', '') or x.get('event_timestamp', ''), reverse=True)

        return render_template('qr_dashboard.html',
                               qr_id=qr_id,
                               name=record.get('citizen_name', ''),
                               email=record.get('citizen_email_id', ''),
                               contact=record.get('citizen_contact_number', ''),
                               authority=record.get('recipient_authority_code', ''),
                               sub_type=record.get('application_type', ''),
                               eta=record.get('expected_turnaround_time', ''),
                               note=record.get('additional_notes', ''),
                               url=record.get('relevant_url', ''),
                               status=record.get('status', 'Not Yet Received'),
                               events=events)
    except Exception as e:
        print(traceback.format_exc())
        return f"Error loading record: {str(e)}", 500

@qr_bp.route('/api/update_record', methods=['POST'])
def update_record():
    try:
        data = request.get_json() or {}
        qr_id = data.get('qr_id')
        comment = (data.get('comment') or '').strip()
        eta_new = (data.get('eta') or '').strip()
        status_new = (data.get('status') or '').strip()

        if not qr_id:
            return jsonify({'error': 'QR ID missing'}), 400

        sheet = get_spreadsheet()
        if not sheet:
            return jsonify({'error': 'Sheets not available'}), 500

        submissions = sheet.worksheet("submissions")
        records = submissions.get_all_records()
        row_idx = next((i for i, r in enumerate(records, start=2) if r.get('qr_id') == qr_id), None)

        if not row_idx:
            return jsonify({'error': 'Record not found'}), 404

        # Update submissions row if ETA or Status changed
        if eta_new or status_new:
            if eta_new:
                submissions.update_cell(row_idx, 7, eta_new)   # expected_turnaround_time
            if status_new:
                submissions.update_cell(row_idx, 11, status_new)  # status column

        # Log event
        log_scan_event(sheet, qr_id, "COMMENT" if comment else "UPDATE",
                       comment=comment, eta_new=eta_new, status_new=status_new)

        return jsonify({'success': True, 'message': 'Update logged successfully'})
    except Exception as e:
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500
