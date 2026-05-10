"""
Admin + housekeeping routes.
  /health    — uptime check
  /debug     — env validation (internal use)
  /chronicle — Saraswati stub (POST, receives text entries)
  /login     — initiates Google OAuth flow (generates GOOGLE_USER_TOKEN for Hanuman Drive access)
  /callback  — OAuth callback; returns token JSON for pasting into Railway env vars
"""
import os
import uuid
from datetime import datetime

from flask import Blueprint, jsonify, redirect, request, session

admin_bp = Blueprint('admin', __name__)

# In-memory store for OAuth flows (keyed by state UUID).
# Lives for the duration of the OAuth round-trip only.
_oauth_flows = {}


def _get_google_flow():
    """Build a Google OAuth Flow from Railway env vars."""
    client_id = os.environ.get('GOOGLE_CLIENT_ID')
    client_secret = os.environ.get('GOOGLE_CLIENT_SECRET')
    redirect_uri = os.environ.get('REDIRECT_URI')

    if not all([client_id, client_secret, redirect_uri]):
        raise ValueError(
            "Missing Google OAuth env vars (GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET / REDIRECT_URI)."
        )

    from google_auth_oauthlib.flow import Flow
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=[
            'https://www.googleapis.com/auth/userinfo.profile',
            'openid',
            'https://www.googleapis.com/auth/drive.file',
            'https://www.googleapis.com/auth/drive',
        ],
    )
    flow.redirect_uri = redirect_uri
    return flow


# ── /health ──────────────────────────────────────────────────────────────────

@admin_bp.route('/health')
def health():
    return jsonify({
        'status': 'ok',
        'office': 'Jagdishwaram Digital Office',
        'case': 'Ashish Jagdish Naik VS State of Maharashtra & Others',
        'satyamev': 'jayate',
        'timestamp': datetime.now().isoformat(),
    })


# ── /debug ───────────────────────────────────────────────────────────────────

@admin_bp.route('/debug')
def debug():
    hanuman_inbox = os.environ.get('HANUMAN_INBOX_FOLDER_ID', '')
    google_token  = 'SET' if os.environ.get('GOOGLE_USER_TOKEN') else 'NOT_SET'
    client_id     = 'SET' if os.environ.get('GOOGLE_CLIENT_ID') else 'NOT_SET'
    return jsonify({
        'hanuman_inbox_folder': 'SET' if hanuman_inbox else 'NOT_SET',
        'google_user_token': google_token,
        'google_client_id': client_id,
        'status': 'ready',
    })


# ── /chronicle ───────────────────────────────────────────────────────────────
# Saraswati stub — receives structured text entries; full pipeline TBD.

@admin_bp.route('/chronicle', methods=['POST'])
def chronicle():
    try:
        data = request.get_json()
        entry = data.get('entry', '').strip()
        if not entry:
            return jsonify({'error': 'नोंद रिकामी आहे'}), 400
        return jsonify({
            'status': 'received',
            'timestamp': datetime.now().strftime('%d %B %Y | %I:%M %p IST'),
            'entry_preview': entry[:100],
            'message': 'Saraswati ने नोंद घेतली',
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── /login ───────────────────────────────────────────────────────────────────
# Purpose: one-time OAuth dance to capture GOOGLE_USER_TOKEN for Railway env.
# Hanuman uses that token to write files to Google Drive Chronicle Inbox.

@admin_bp.route('/login')
def login():
    flow = _get_google_flow()
    auth_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent',
    )
    _oauth_flows[state] = flow
    session['state'] = state
    return redirect(auth_url)


# ── /callback ────────────────────────────────────────────────────────────────

@admin_bp.route('/callback')
def callback():
    try:
        state_id = session.get('state')
        incoming_state = request.args.get('state')

        if not state_id or state_id != incoming_state:
            return 'State mismatch or session expired. Please restart /login.', 400

        flow = _oauth_flows.pop(state_id, None)
        if not flow:
            return 'Auth flow expired or session missing. Please restart /login.', 400

        flow.redirect_uri = os.environ.get('REDIRECT_URI')
        flow.fetch_token(authorization_response=request.url)
        token_json = flow.credentials.to_json()

        return f"""
        <html><head><title>जगदिश्वरम् — Token Captured</title><meta charset="UTF-8"></head>
        <body style="font-family:-apple-system,BlinkMacSystemFont,sans-serif;margin:20px;max-width:800px">
        <h2 style="color:#2d5016">✅ Authenticated Successfully!</h2>
        <p>Copy everything in the box below and paste into Railway environment variable
           <code>GOOGLE_USER_TOKEN</code>:</p>
        <textarea style="width:100%;height:400px;border:1px solid #ccc;padding:10px;
                         font-family:monospace;font-size:12px">{token_json}</textarea>
        <p style="margin-top:20px">
          <strong>Next steps:</strong><br>
          1. Copy the JSON above<br>
          2. Railway Dashboard → Variables → add <code>GOOGLE_USER_TOKEN</code><br>
          3. Save and Redeploy<br>
          4. Visit <a href="/field">/field</a> to test Hanuman field sync
        </p></body></html>
        """
    except Exception as e:
        return f"""
        <html><head><title>Authentication Error</title><meta charset="UTF-8"></head>
        <body style="font-family:-apple-system,BlinkMacSystemFont,sans-serif;margin:20px">
        <h2 style="color:#8b1a1a">❌ Authentication Failed</h2>
        <p><strong>Error:</strong> {str(e)}</p>
        <p>Common causes: wrong client credentials, mismatched redirect URI, stale session.
           <a href="/login">🔄 Try Again</a></p>
        </body></html>
        """, 400
