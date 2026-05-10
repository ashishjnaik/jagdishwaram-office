"""
Jagdishwaram Digital Office — Flask entry point.
सत्यमेव जयते | Vasai 2026

Routes are defined in blueprints/:
  home.py    /              Public portal (home.html)
  hanuman.py /field         Field capture form + Drive sync
             /capture       Lightweight ingest stub
  admin.py   /health /debug /chronicle /login /callback
  narada.py  /generator /qr/generate /scan/<id> /api/*   (Narada QR)
"""

import os

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

from flask import Flask

from blueprints.home import home_bp
from blueprints.hanuman import hanuman_bp
from blueprints.admin import admin_bp
from narada import qr_bp

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'default_secret_for_local_dev')

app.register_blueprint(home_bp)
app.register_blueprint(hanuman_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(qr_bp)

if __name__ == '__main__':
    app.run(debug=True)
