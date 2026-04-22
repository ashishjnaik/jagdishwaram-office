from flask import Blueprint, render_template, request, jsonify
import qrcode
from PIL import Image
import io
import os
from datetime import datetime
import traceback

print("✅ qr_routes.py (MINIMAL) loaded")

qr_bp = Blueprint('narada_qr', __name__, url_prefix='/')

@qr_bp.route('/generator', methods=['GET'])
def generator():
    return render_template('qr_generator.html')

@qr_bp.route('/qr/generate', methods=['POST'])
def generate_qr():
    data = request.get_json() or {}
    print("DEBUG - Received payload:", data)   # Check Railway logs for exact keys

    # Accept ALL possible field names from your HTML form
    name = (data.get('name') or data.get('yourName') or data.get('Your Name') or '').strip()
    email = (data.get('email') or data.get('emailId') or data.get('Your Email ID') or '').strip()
    contact = (data.get('contact') or data.get('contactNo') or '').strip()
    authority = (data.get('authority') or data.get('recipientAuthority') or data.get('Authority') or 'OTHERS').strip()
    sub_type = (data.get('submission_type') or data.get('submissionType') or data.get('Submission Type') or 'Application').strip()
    eta = (data.get('eta') or data.get('ETA') or '').strip()
    note = (data.get('note') or data.get('additionalNote') or data.get('Additional Note') or '').strip()

    if not all([name, email, eta, note]):
        print("❌ Validation failed - missing fields")
        return jsonify({'error': 'Mandatory fields missing'}), 400

    qr_id = generate_qr_id(authority)
    short_url = f"https://dev.jagdishwaram-office.org/scan/{qr_id}"

    # Generate QR (Sheets disabled for now to avoid 502)
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
    return render_template('qr_dashboard.html', qr_id=qr_id)
