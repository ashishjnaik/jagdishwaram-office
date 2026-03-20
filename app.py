"""
JAGDISHWARAM DIGITAL OFFICE
Flask Server | Render.com Deployment
सत्यमेव जयते | Vasai 2026

Serves:
- /                     → Public case portal (QR code target)
- /ask                  → Yudhishthira API (Marathi answers)
- /chronicle            → Saraswati API (field notes)
- /capture              → Evidence capture API
- /health               → Health check
"""

import os
import json
import pickle
import base64
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string
import anthropic

app = Flask(__name__)

# ─── CONFIGURATION ────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
PORTAL_TOKEN      = os.environ.get("PORTAL_TOKEN", "jagdishwaram2026")
DRIVE_FOLDER_URL  = "https://drive.google.com/drive/folders/1TyYJPzRcvm1Xw6pkzcePL7TYEwhYWrmY"

# ─── CASE CONTEXT ─────────────────────────────────────────────────────────────
YUDHISHTHIRA_SYSTEM = """
तुम्ही युधिष्ठिर आहात — आशिष जगदिश नाईक यांचे कायदेशीर AI सहायक.
You are Yudhishthira — the legal AI assistant of Ashish Jagdish Naik.

CORE CASE FACTS:
- Property: Jagdishwaram, Survey No. 39/19, Mouje Watar, Vasai, Palghar
- Applicant: Ashish Jagdish Naik (Pro Se / स्वयं-प्रतिनिधी)
- Opponents: Dilip Ganpat Naik + Vilas Ganpat Naik (blocking easement)
- Legal basis: Mamlatdar Courts Act 1906 Section 5
- Indian Easements Act 1882 Section 13

THREE COURT ORDERS — ALL IN APPLICANT'S FAVOUR:
1. Tehsildar Vasai final order: 01/03/2024 (वहिवाट दावा क्र.01/2017)
   — Establishes easement permanently
   — Orders obstruction removal
   — Orders police assistance for enforcement
2. District Court: MHTH230026632025
   — Dismisses opponents' injunction
3. Magistrate OMA 254/2026, CNR: MHTH250017082026, dated 10/03/2026
   — 4th JMFC Vasai (Judge V.N. Gulve)
   — Directs RPO Mumbai to issue 10-year passport
   — Directs Arnala Police doorstep verification

FIR 270/2024 — MALICIOUS PROSECUTION:
- Filed by opponents 24/08/2024
- 8 days AFTER applicant's legitimate complaint of 16/08/2024
- SCC No. 63/2025, CR No. 270/2024
- District Court has already dismissed injunction based on this FIR

INSTITUTIONAL FAILURE CHAIN:
- Tehsildar Vasai: Failed to enforce own order for 24+ months
- SDO Vasai: Failed supervisory duty, illegally transferred RTI appeal
- Collector Palghar: Silent despite escalated written complaints
- VVMC: Demands Rs.4,04,229 tax despite zero services (BTR)
- Police Commissioner MBVV: Administrative author of downstream failures
- ACP Nalasopara: Abdicated First Appellate Authority duty
- Arnala Police: Filed malicious FIR 270/2024 against victim family
- RPO Mumbai: Rejected passport citing already-dismissed FIR

FINANCIAL IMPACT:
- Agricultural loss: Rs.8-10 lakhs/year
- Forced employment exit: 17/06/2025
- VVMC tax demand: Rs.4,04,229 (zero services received)
- 11 years of struggle since June 2015

RESPONSE RULES:
1. Always respond in Marathi (मराठी)
2. Cite specific legal sections for every claim
3. Cite specific exhibit numbers or dates when referencing evidence
4. Never fabricate facts — if uncertain, say so clearly
5. Be legally precise and factually grounded
6. Keep answers clear enough to show to an officer on a phone screen
7. End with: "सत्यमेव जयते | जगदिश्वरम् डिजिटल कार्यालय"
"""

# ─── PORTAL HTML ──────────────────────────────────────────────────────────────
PORTAL_HTML = """<!DOCTYPE html>
<html lang="mr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>जगदिश्वरम् — वहिवाट दावा क्र. 01/2017</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: #f5f5f0; color: #1a1a18; }
  .header { background: #1a1a18; color: #f5f5f0; padding: 20px 16px; }
  .header h1 { font-size: 20px; font-weight: 600; margin-bottom: 4px; }
  .header p { font-size: 13px; color: #9c9a92; }
  .satyamev { font-size: 11px; color: #6a6; margin-top: 6px; }
  .section { margin: 16px; }
  .section-title { font-size: 12px; font-weight: 600; color: #5f5e5a;
                   text-transform: uppercase; letter-spacing: 0.5px;
                   margin-bottom: 10px; }
  .card { background: white; border-radius: 10px; padding: 14px;
          margin-bottom: 10px; border: 1px solid #e5e3db; }
  .card-title { font-size: 14px; font-weight: 500; margin-bottom: 4px; }
  .card-sub { font-size: 12px; color: #5f5e5a; line-height: 1.5; }
  .badge { display: inline-block; font-size: 10px; padding: 2px 8px;
           border-radius: 4px; font-weight: 500; margin-top: 6px; }
  .badge-green { background: #eaf3de; color: #3b6d11; }
  .badge-red { background: #fde8e8; color: #8b1a1a; }
  .badge-orange { background: #faeeda; color: #854f0b; }
  .order-item { padding: 10px 0; border-bottom: 1px solid #f0ede5; }
  .order-item:last-child { border: none; padding-bottom: 0; }
  .order-date { font-size: 11px; color: #5f5e5a; margin-bottom: 2px; }
  .order-text { font-size: 13px; font-weight: 500; }
  .order-result { font-size: 12px; color: #3b6d11; margin-top: 2px; }
  .thread { display: flex; justify-content: space-between;
            align-items: center; padding: 8px 0;
            border-bottom: 1px solid #f0ede5; }
  .thread:last-child { border: none; }
  .thread-name { font-size: 13px; }
  .thread-status { font-size: 11px; padding: 2px 8px; border-radius: 4px; }
  .status-breach { background: #fde8e8; color: #8b1a1a; }
  .status-pending { background: #faeeda; color: #854f0b; }
  .ask-box { background: white; border-radius: 10px; padding: 14px;
             border: 1px solid #e5e3db; }
  .ask-box textarea { width: 100%; border: 1px solid #d3d1c7;
                      border-radius: 8px; padding: 10px; font-size: 14px;
                      font-family: inherit; resize: none; outline: none;
                      background: #f9f9f6; }
  .ask-box textarea:focus { border-color: #1a1a18; }
  .ask-btn { width: 100%; background: #1a1a18; color: white;
             border: none; border-radius: 8px; padding: 12px;
             font-size: 14px; font-weight: 500; cursor: pointer;
             margin-top: 8px; }
  .ask-btn:disabled { background: #9c9a92; }
  .answer-box { margin-top: 10px; background: #f0ede5;
                border-radius: 8px; padding: 12px;
                font-size: 13px; line-height: 1.7; display: none; }
  .drive-link { display: block; text-align: center; padding: 12px;
                background: white; border-radius: 10px;
                border: 1px solid #e5e3db; color: #185fa5;
                text-decoration: none; font-size: 13px; font-weight: 500; }
  .footer { text-align: center; padding: 20px; font-size: 11px;
            color: #9c9a92; }
  .loading { display: none; text-align: center; color: #5f5e5a;
             font-size: 13px; padding: 10px; }
</style>
</head>
<body>

<div class="header">
  <h1>जगदिश्वरम् डिजिटल कार्यालय</h1>
  <p>वहिवाट दावा क्र. 01/2017 | सर्व्हे नं. ३९/१९, मौजे वटार, वसई</p>
  <p>अर्जदार: आशिष जगदिश नाईक (स्वयं-प्रतिनिधी)</p>
  <div class="satyamev">सत्यमेव जयते | Vasai, Palghar, Maharashtra</div>
</div>

<div class="section">
  <div class="section-title">न्यायालयीन आदेश — माझ्या बाजूने</div>
  <div class="card">
    <div class="order-item">
      <div class="order-date">01 मार्च 2024</div>
      <div class="order-text">तहसीलदार वसई — अंतिम आदेश</div>
      <div class="order-result">वहिवाट हक्क कायमस्वरूपी प्रस्थापित | अडथळे हटवण्याचे आदेश | पोलीस सहाय्य</div>
      <span class="badge badge-green">अंतिम आदेश — माझ्या बाजूने</span>
    </div>
    <div class="order-item">
      <div class="order-date">2025 — MHTH230026632025</div>
      <div class="order-text">जिल्हा न्यायालय — प्रतिवाद्यांचा अर्ज फेटाळला</div>
      <div class="order-result">FIR 270/2024 आधारे इंजंक्शन नाकारले</div>
      <span class="badge badge-green">माझ्या बाजूने</span>
    </div>
    <div class="order-item">
      <div class="order-date">10 मार्च 2026 — OMA 254/2026</div>
      <div class="order-text">4थे JMFC वसई (न्यायाधीश V.N. Gulve)</div>
      <div class="order-result">पारपत्र जारी करण्याचे आदेश | अर्नाळा पोलीस घरपोच पडताळणी</div>
      <span class="badge badge-green">माझ्या बाजूने</span>
    </div>
  </div>
</div>

<div class="section">
  <div class="section-title">FIR 270/2024 — दुर्भावनापूर्ण खटला</div>
  <div class="card">
    <div class="card-title">अर्नाळा सागरी पोलीस ठाणे</div>
    <div class="card-sub">
      दि. 16/08/2024 — माझी तक्रार दाखल<br>
      दि. 24/08/2024 — प्रतिवाद्यांचा FIR (8 दिवसांनंतर)<br>
      जिल्हा न्यायालयाने इंजंक्शन नाकारले — FIR निराधार सिद्ध
    </div>
    <span class="badge badge-red">दुर्भावनापूर्ण खटला — न्यायालयाने फेटाळला</span>
  </div>
</div>

<div class="section">
  <div class="section-title">संस्थात्मक अपयश — 16 धागे</div>
  <div class="card">
    <div class="thread">
      <div class="thread-name">तहसीलदार वसई (MOR)</div>
      <span class="thread-status status-breach">24+ महिने — अंमलबजावणी नाही</span>
    </div>
    <div class="thread">
      <div class="thread-name">उपविभागीय अधिकारी (NPS)</div>
      <span class="thread-status status-breach">RTI अपील बेकायदेशीर हस्तांतरण</span>
    </div>
    <div class="thread">
      <div class="thread-name">जिल्हाधिकारी पालघर (DMD)</div>
      <span class="thread-status status-pending">उत्तर नाही</span>
    </div>
    <div class="thread">
      <div class="thread-name">VVMC (BTR)</div>
      <span class="thread-status status-breach">₹4,04,229 कर — शून्य सेवा</span>
    </div>
    <div class="thread">
      <div class="thread-name">पोलीस आयुक्त MBVV (AGD)</div>
      <span class="thread-status status-pending">कारवाई नाही</span>
    </div>
    <div class="thread">
      <div class="thread-name">ACP नालासोपारा (RPD)</div>
      <span class="thread-status status-breach">FAA कर्तव्य नाकारले</span>
    </div>
    <div class="thread">
      <div class="thread-name">अर्नाळा पोलीस (EAF)</div>
      <span class="thread-status status-breach">दुर्भावनापूर्ण FIR दाखल</span>
    </div>
    <div class="thread">
      <div class="thread-name">RPO मुंबई (RPO)</div>
      <span class="thread-status status-breach">पारपत्र नाकारले — आदेश असूनही</span>
    </div>
  </div>
</div>

<div class="section">
  <div class="section-title">युधिष्ठिराला विचारा — Ask in Marathi</div>
  <div class="ask-box">
    <textarea id="question" rows="3"
      placeholder="तुमचा प्रश्न मराठीत लिहा... (Type your question in Marathi or English)"></textarea>
    <button class="ask-btn" onclick="askYudhishthira()" id="askBtn">
      युधिष्ठिराला विचारा ⚖️
    </button>
    <div class="loading" id="loading">उत्तर मिळवत आहे...</div>
    <div class="answer-box" id="answer"></div>
  </div>
</div>

<div class="section">
  <div class="section-title">संपूर्ण दस्तावेज — Google Drive</div>
  <a class="drive-link" href="{{ drive_url }}" target="_blank">
    📁 संपूर्ण केस लायब्ररी पाहा — वहिवाट दावा जगदिश्वरम्
  </a>
</div>

<div class="footer">
  जगदिश्वरम् डिजिटल कार्यालय | आशिष जगदिश नाईक<br>
  वसई, पालघर, महाराष्ट्र | सत्यमेव जयते<br>
  Powered by Jagdishwaram AI System | 2026
</div>

<script>
async function askYudhishthira() {
  const q = document.getElementById('question').value.trim();
  if (!q) return;
  
  const btn = document.getElementById('askBtn');
  const loading = document.getElementById('loading');
  const answerBox = document.getElementById('answer');
  
  btn.disabled = true;
  btn.textContent = 'विचारत आहे...';
  loading.style.display = 'block';
  answerBox.style.display = 'none';
  
  try {
    const response = await fetch('/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: q })
    });
    const data = await response.json();
    answerBox.textContent = data.answer || data.error || 'उत्तर मिळाले नाही';
    answerBox.style.display = 'block';
  } catch(e) {
    answerBox.textContent = 'त्रुटी आली. पुन्हा प्रयत्न करा.';
    answerBox.style.display = 'block';
  }
  
  btn.disabled = false;
  btn.textContent = 'युधिष्ठिराला विचारा ⚖️';
  loading.style.display = 'none';
}
</script>
</body>
</html>"""

# ─── ROUTES ───────────────────────────────────────────────────────────────────
@app.route('/')
def portal():
    return render_template_string(
        PORTAL_HTML,
        drive_url=DRIVE_FOLDER_URL
    )

@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'office': 'Jagdishwaram Digital Office',
                    'satyamev': 'jayate'})

@app.route('/ask', methods=['POST'])
def ask():
    try:
        data = request.get_json()
        question = data.get('question', '').strip()
        if not question:
            return jsonify({'error': 'प्रश्न रिकामा आहे'}), 400

        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1500,
            system=YUDHISHTHIRA_SYSTEM,
            messages=[{"role": "user", "content": question}]
        )
        answer = message.content[0].text
        return jsonify({
            'answer': answer,
            'question': question,
            'timestamp': datetime.now().isoformat(),
            'agent': 'Yudhishthira — युधिष्ठिर'
        })
    except Exception as e:
        return jsonify({'error': f'त्रुटी: {str(e)}'}), 500

@app.route('/chronicle', methods=['POST'])
def chronicle():
    try:
        data = request.get_json()
        entry = data.get('entry', '').strip()
        if not entry:
            return jsonify({'error': 'नोंद रिकामी आहे'}), 400
        timestamp = datetime.now().strftime('%d %B %Y | %I:%M %p IST')
        return jsonify({
            'status': 'received',
            'timestamp': timestamp,
            'entry_preview': entry[:100],
            'message': 'Saraswati ने नोंद घेतली'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/capture', methods=['POST'])
def capture():
    try:
        data = request.get_json()
        capture_type = data.get('type', 'note')
        content = data.get('content', '')
        annotation = data.get('annotation', '')
        timestamp = datetime.now().isoformat()
        return jsonify({
            'status': 'captured',
            'type': capture_type,
            'timestamp': timestamp,
            'message': f'Hanuman ने {capture_type} सुरक्षित केले'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
