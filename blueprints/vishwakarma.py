from flask import Blueprint, render_template

vishwakarma_bp = Blueprint('vishwakarma', __name__)


@vishwakarma_bp.route('/transparency')
def transparency():
    return render_template('vishwakarma_transparency.html')


@vishwakarma_bp.route('/transparency/palghar-mca')
def palghar_mca():
    return render_template('vishwakarma_palgharmca.html')
