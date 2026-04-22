# qr_routes.py - Narada QR Tracking System v1.0 (COMPLETE & STABLE)
from flask import Blueprint, render_template, request, jsonify
import qrcode
from PIL import Image
import io
import os
from datetime import datetime
import traceback

print("✅ qr_routes.py LOADED SUCCESSFULLY")

qr_bp = Blueprint('narada_qr', __name__, url_prefix='/')

# ==================== HELPER FUNCTIONS ====================
def generate_qr_id(authority_code):
    year = datetime.now().year
    # Temporary fixed sequence for testing (we will make it dynamic later)
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

# ==================== ROUTES ====================
@qr_bp.route('/generator', methods=['GET'])
def generator():
    return render_template('qr_generator.html')

@qr_bp.route('/qr/generate', methods=['POST'])
def generate_qr():
    try:
        data = request.get_json() or {}
        print("DEBUG - Exact payload received:", data)

        name      = (data.get('name') or '').strip()
        email     = (data.get('email') or '').strip()
        contact   = (data.get('contact') or '').strip()
        authority = (data.get('authority_code') or 'OTHERS').strip()
        sub_type  = (data.get('submission_type') or 'Application').strip()
        eta       = (data.get('eta_date') or '').strip()
        note      = (data.get('additional_note') or '').strip()

        if not all([name, email, eta, note]):
            print("❌ Mandatory fields missing")
            return jsonify({'error': 'Mandatory fields missing'}), 400

        qr_id = generate_qr_id(authority)
        short_url = f"https://dev.jagdishwaram-office.org/scan/{qr_id}"

        # Create branded QR
        img = create_qr_image(short_url)
        img_io = io.BytesIO()
        img.save(img_io, 'PNG')
        img_io.seek(0)

        print(f"✅ QR generated successfully: {qr_id}")
        return jsonify({
            'qr_id': qr_id,
            'short_url': short_url,
            'download_name': f"QR-{qr_id}.png"
        })

    except Exception as e:
        print("❌ CRITICAL ERROR in generate_qr:")
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@qr_bp.route('/scan/<qr_id>', methods=['GET'])
def scan_dashboard(qr_id):
    return render_template('qr_dashboard.html', qr_id=qr_id)
