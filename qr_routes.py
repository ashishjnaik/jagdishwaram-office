# qr_routes.py - Narada QR Tracking System v1.0 (FINAL)
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

print("✅ qr_routes.py LOADED (FINAL)")

qr_bp = Blueprint('narada_qr', __name__, url_prefix='/')

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

@qr_bp.route('/generator', methods=['GET'])
def generator():
    return render_template('qr_generator.html')

@qr_bp.route('/qr/generate', methods=['POST'])
def generate_qr():
    try:
        data = request.get_json() or {}
        name      = (data.get('name') or '').strip()
        email     = (data.get('email') or '').strip()
        contact   = (data.get('contact') or '').strip()
        authority = (data.get('authority_code') or 'OTHERS').strip()
        sub_type  = (data.get('submission_type') or 'Application').strip()
        eta       = (data.get('eta_date') or '').strip()
        note      = (data.get('additional_note') or '').strip()
        url       = (data.get('url') or '').strip()

        if not all([name, email, eta, note]):
            return jsonify({'error': 'Mandatory fields missing'}), 400

        qr_id = generate_qr_id(authority)
        short_url = f"https://dev.jagdishwaram-office.org/scan/{qr_id}"

        # Save to Google Sheet
        sheet = get_spreadsheet()
        if sheet:
            submissions = sheet.worksheet("submissions")
            submissions.append_row([qr_id, name, email, contact, authority, sub_type, eta, note, url, datetime.now().isoformat(), "Not Yet Received", ""])

        # Generate QR
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

        submissions = sheet.worksheet("submissions")
        records = submissions.get_all_records()

        record = next((r for r in records if r.get('qr_id') == qr_id), None)
        if not record:
            return "QR ID not found", 404

        # Convert timestamp to IST
        try:
            utc_time = datetime.fromisoformat(record.get('qr_generation_timestamp', '').replace('Z', '+00:00'))
            ist = pytz.timezone('Asia/Kolkata')
            ist_time = utc_time.astimezone(ist).strftime('%d/%m/%Y, %I:%M %p IST')
        except:
            ist_time = "Just now"

        return render_template('qr_dashboard.html',
                               qr_id=qr_id,
                               name=record.get('citizen_name', ''),
                               email=record.get('citizen_email_id', ''),
                               contact=record.get('citizen_contact_number', ''),
                               authority=record.get('recipient_authority_code', ''),
                               sub_type=record.get('application_type', ''),
                               eta=record.get('expected_turnaround_time', ''),
                               note=record.get('additional_notes', 'No note provided'),
                               url=record.get('relevant_url', ''),
                               generated=ist_time)
    except Exception as e:
        print(traceback.format_exc())
        return f"Error loading record: {str(e)}", 500
