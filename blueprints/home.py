import os

from flask import Blueprint, render_template, send_from_directory, session, request, redirect, url_for

home_bp = Blueprint('home', __name__)

_DOCS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'docs'))
_KURUKSHETRA_PASSPHRASE = os.environ.get('KURUKSHETRA_PASSPHRASE', '')


@home_bp.route('/')
def index():
    return render_template('home.html')


@home_bp.route('/docs/<path:filename>')
def serve_docs(filename):
    return send_from_directory(_DOCS_DIR, filename)


@home_bp.route('/kurukshetra', methods=['GET'])
def kurukshetra():
    if _KURUKSHETRA_PASSPHRASE and not session.get('kurukshetra_auth'):
        return render_template('kurukshetra_auth.html')
    return render_template('case_library.html')


@home_bp.route('/kurukshetra/auth', methods=['POST'])
def kurukshetra_auth():
    entered = request.form.get('passphrase', '').strip()
    if entered == _KURUKSHETRA_PASSPHRASE:
        session['kurukshetra_auth'] = True
        return redirect(url_for('home.kurukshetra'))
    return render_template('kurukshetra_auth.html', error='Incorrect passphrase.')
