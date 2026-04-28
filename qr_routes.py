from flask import Blueprint, request, jsonify, render_template
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
ZOHO_OWNER = os.environ.get('ZOHO_OWNER_NAME')
ZOHO_APP = os.environ.get('ZOHO_APP_LINK_NAME')
ZOHO_DOMAIN = os.environ.get('ZOHO_API_DOMAIN', 'https://www.zohoapis.in')

def get_headers():
    return {'Authorization': f'Zoho-oauthtoken {ZOHO_ACCESS_TOKEN}', 'Content-Type': 'application/json'}

def zoho_get(form_link_name, criteria=''):
    url = f"{ZOHO_DOMAIN}/creator/v2.1/{ZOHO_OWNER}/{ZOHO_APP}/{form_link_name}/records"
    params = {'criteria': criteria} if criteria else {}
    resp = requests.get(url, headers=get_headers(), params=params, timeout=10)
    print(f"[DEBUG] Zoho GET {form_link_name} → Status: {resp.status_code}")
    return resp.json()

@qr_bp.route('/api/config', methods=['GET'])
def get_config():
    try:
        auth_resp = zoho_get('Config_Authority_Registry')
        authorities = [{'code': item.get('authority_registry_code'), 'name': item.get('authority_name')} 
                      for item in auth_resp.get('data', [])]

        type_resp = zoho_get('Config_Submission_Types')
        submission_types = [{'code': item.get('submission_type_code'), 'name': item.get('submission_type_name')} 
                           for item in type_resp.get('data', [])]

        print(f"[DEBUG] Config loaded → Authorities: {len(authorities)}, Types: {len(submission_types)}")
        return jsonify({'authorities': authorities, 'submission_types': submission_types})
    except Exception as e:
        print(f"[ERROR] /api/config failed: {str(e)}")
        return jsonify({'error': str(e), 'authorities': [], 'submission_types': []}), 500

# ... (keep all other routes exactly as in the previous full version: /generator, /qr/generate, /scan/<qr_id>, /api/update_record, create_qr_image, etc.)

print("✅ Zoho QR routes loaded with DEBUG config")
