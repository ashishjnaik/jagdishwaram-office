"""
Narada QR Tracking System — Flask Routes v1.0
Add this file to jagdishwaram-office root
"""

import uuid
import qrcode
from io import BytesIO
from PIL import Image
import gspread
from google.oauth2.service_account import Credentials
from flask import Blueprint, request, jsonify, send_file, render_template, redirect
from datetime import datetime
import pytz
import os

qr_bp = Blueprint('qr', __name__)

# Config from Railway environment
SPREADSHEET_ID = os.environ.get("NARADA_QR_SPREADSHEET_ID")
PREFIX = os.environ.get("NARADA_QR_PREFIX", "TEA")

gc = gspread.authorize(
    Credentials.from_service_account_file("service_account.json", 
    scopes=["https://www.googleapis.com/auth/spreadsheets"])
)
sheet = gc.open_by_key(SPREADSHEET_ID)

def get_submissions(): return sheet.worksheet("submissions")
def get_events(): return sheet.worksheet("scan_events")
def get_config(): return sheet.worksheet("config")

def get_next_sequence():
    cfg = get_config()
    val = cfg.acell('C1').value or 0
    next_val = int(val) + 1
    cfg.update('C1', next_val)
    return f"{next_val:04d}"

def make_qr_id(auth_code):
    year = datetime.now(pytz.timezone('Asia/Kolkata')).year
    return f"{PREFIX}-{auth_code}-{year}-{get_next_sequence()}"

@qr_bp.route('/qr/generate', methods=['POST'])
def generate():
    data = request.get_json()
    required = ['name', 'email', 'eta_date', 'additional_note']
    for f in required:
        if not data.get(f): return jsonify({"error": f"Missing {f}"}), 400

    qr_id = make_qr_id(data.get('authority_code', 'MOR'))
    now = datetime.now(pytz.timezone('Asia/Kolkata')).isoformat()

    get_submissions().append_row([
        qr_id, now, data['name'], data['email'],
        data.get('contact', ''), data.get('authority_code', 'MOR'),
        data.get('submission_type', 'RTI'), data['eta_date'],
        data['additional_note'][:800],
        f"https://narada.jagdishwaram-office.org/scan/{qr_id}"
    ])

    # Generate QR
    qr = qrcode.QRCode(version=1, box_size=10, border=2, error_correction=qrcode.constants.ERROR_CORRECT_H)
    qr.add_data(f"https://narada.jagdishwaram-office.org/scan/{qr_id}")
    qr.make(fit=True)
    img = qr.make_image(fill_color="#1a365d", back_color="white").convert('RGB')

    try:
        logo = Image.open("logo.png").convert("RGBA")
        logo = logo.resize((60, 60))
        pos = ((img.size[0]-60)//2, (img.size[1]-60)//2)
        img.paste(logo, pos, logo)
    except: pass

    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png", download_name=f"QR-{qr_id}.png")

@qr_bp.route('/qr/scan/<qr_id>')
def scan(qr_id):
    recs = get_submissions().get_all_records()
    record = next((r for r in recs if r.get('qr_id') == qr_id), None)
    if not record: return "Not found", 404

    events = [e for e in get_events().get_all_records() if e.get('qr_id') == qr_id]
    return render_template('qr_dashboard.html', record=record, history=events, qr_id=qr_id)

@qr_bp.route('/qr/comment', methods=['POST'])
def comment():
    d = request.get_json()
    get_events().append_row([
        f"EVT-{uuid.uuid4().hex[:8]}", d['qr_id'], "COMMENT",
        datetime.now(pytz.timezone('Asia/Kolkata')).isoformat(),
        d.get('actor', 'Citizen'), d.get('comment', '')
    ])
    return jsonify({"ok": True})