import os

from flask import Blueprint, render_template, send_from_directory

home_bp = Blueprint('home', __name__)

_DOCS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'docs'))


@home_bp.route('/')
def index():
    return render_template('home.html')


@home_bp.route('/docs/<path:filename>')
def serve_docs(filename):
    return send_from_directory(_DOCS_DIR, filename)
