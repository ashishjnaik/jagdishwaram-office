# qr_routes.py - Narada QR Tracking System v1.0
# Full end-to-end: Generator + Scan Dashboard + Comment Logging

from flask import Blueprint, render_template, request, jsonify, send_file
import qrcode
from PIL import Image, ImageDraw
import io
import os
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
import json

qr_bp = Blueprint('qr', __name__, url_prefix='/')

# Google Sheets Setup (Service Account)
def get_sheets_client():
    json_str = os.environ.get('NARADA_QR_SERVICE_ACCOUNT_JSON')
    if not json_str:
        raise ValueError("NARADA_QR_SERVICE_ACCOUNT_JSON not set in Railway")
    creds_dict = json.loads(json_str)
    scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return gspread.authorize(creds)

def get_spreadsheet():
    client = get_sheets_client()
    spreadsheet_id = os.environ.get('NARADA_QR_SPREADSHEET_ID')
    return client.open_by_key(spreadsheet_id)

# Next sequence number (global incremental)
def get_next_sequence():
    sheet = get_spreadsheet()
    submissions = sheet.worksheet("submissions")
    records = submissions.get_all_records()
    if not records:
        return 1
    max_seq = max((int(r.get('sequence', 0)) for r in records), default=0)
    return max_seq + 1

# Generate QR ID: TEA-{AUTH_CODE}-{YYYY}-{SEQUENCE}
def generate_qr_id(authority_code):
    year = datetime.now().year
    seq = get_next_sequence()
    return f"TEA-{authority_code}-{year}-{seq:04d}"

# Create QR image with logo
def create_qr_image(qr_url, logo_path="static/Logo.jpg"):
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=4)
    qr.add_data(qr_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#1a365d", back_color="white").convert('RGB')
    
    # Add logo if exists
    if os.path.exists(logo_path):
        logo = Image.open(logo_path)
        logo = logo.resize((80, 80))
        pos = ((img.size[0] - logo.size[0]) // 2, (img.size[1] - logo.size[1]) // 2)
        img.paste(logo, pos, mask=logo if logo.mode == 'RGBA' else None)
    return img

@qr_bp.route('/generator', methods=['GET'])
def generator():
    """Your exact mock-up screen"""
    return render_template('qr_generator.html')

@qr_bp.route('/api/qr/generate', methods=['POST'])
def generate_qr():
    data = request.get_json()
    name = data.get('name', '').strip()
    email = data.get('email', '').strip()
    contact = data.get('contact', '').strip()
    authority = data.get('authority', 'OTHERS')
    sub_type = data.get('submission_type', 'Application')
    eta = data.get('eta', '')
    note = data.get('note', '').strip()

    if not all([name, email, eta, note]):
        return jsonify({'error': 'Mandatory fields missing'}), 400

    qr_id = generate_qr_id(authority)
    short_url = f"https://www.jagdishwaram-office.org/scan/{qr_id}"

    # Save to submissions sheet
    sheet = get_spreadsheet()
    submissions = sheet.worksheet("submissions")
    submissions.append_row([
        qr_id, name, email, contact, authority, sub_type,
        eta, note, datetime.now().isoformat(), "Not Yet Received", ""
    ])

    # Generate QR image
    img = create_qr_image(short_url)
    img_io = io.BytesIO()
    img.save(img_io, 'PNG')
    img_io.seek(0)

    return jsonify({
        'qr_id': qr_id,
        'short_url': short_url,
        'download_name': f"QR-{qr_id}.png"
    })

@qr_bp.route('/scan/<qr_id>', methods=['GET'])
def scan_dashboard(qr_id):
    """Full dashboard with history + comment box"""
    sheet = get_spreadsheet()
    submissions = sheet.worksheet("submissions")
    scan_events = sheet.worksheet("scan_events")
    
    record = None
    for row in submissions.get_all_records():
        if row.get('qr_id') == qr_id:
            record = row
            break

    if not record:
        return "QR ID not found", 404

    # Get scan history and comments
    logs = [r for r in scan_events.get_all_records() if r.get('qr_id') == qr_id]

    return render_template('qr_dashboard.html', record=record, logs=logs, qr_id=qr_id)

@qr_bp.route('/api/comment', methods=['POST'])
def post_comment():
    data = request.get_json()
    qr_id = data.get('qr_id')
    comment = data.get('comment', '').strip()
    author = data.get('author', 'HITL/Authority')

    if not qr_id or not comment:
        return jsonify({'error': 'Missing data'}), 400

    sheet = get_spreadsheet()
    scan_events = sheet.worksheet("scan_events")
    scan_events.append_row([qr_id, datetime.now().isoformat(), author, comment, ""])

    return jsonify({'status': 'success'})

# Public search fallback
@qr_bp.route('/search', methods=['GET'])
def public_search():
    qr_id = request.args.get('qr_id')
    if qr_id:
        return scan_dashboard(qr_id)
    return render_template('qr_generator.html')  # fallback
