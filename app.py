"""
JAGDISHWARAM DIGITAL OFFICE
Flask Server | Render.com Deployment
सत्यमेव जयते | Vasai 2026

Routes:
  /          Public case portal
  /ask       Yudhishthira API
  /chronicle Saraswati API
  /capture   Evidence capture API
  /health    Health check
  /debug     API key validation
"""

import os
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string
import anthropic

app = Flask(__name__)

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
PORTAL_TOKEN      = os.environ.get("PORTAL_TOKEN", "jagdishwaram2026")

# ─── CONFIRMED DRIVE URLS ─────────────────────────────────────────────────────
DRIVE = {
    "ROOT":  "https://drive.google.com/drive/folders/1TyYJPzRcvm1Xw6pkzcePL7TYEwhYWrmY",
    "EX20":  "https://drive.google.com/drive/folders/1A7yRMCPKYQ-sYinBUviIu0p3HR0ky-p8",
    "MOR":   "https://drive.google.com/drive/folders/15vOGf-lwDj2vaoMyMBPQw8igYIrPrzcx",
    "DMD":   "https://drive.google.com/drive/folders/1ivErLtUoyDtOSfHhrSEd1m0AyvmxBT_C",
    "AGD":   "https://drive.google.com/drive/folders/1B3jG1HzxDzVKEtleu_5S_1et_TBcuyYR",
    "EAF":   "https://drive.google.com/drive/folders/195psu2cGsQVhMXOylhkQaV5G2-U6O5Ek",
    "RPD":   "https://drive.google.com/drive/folders/1XfeT_ePcmVpx_-h4SoqFqUv0gtPvFTzF",
    "BTR":   "https://drive.google.com/drive/folders/1-JlBXzydWTrvLUPQSuDG64l642s4_KlM",
    "NPS":   "https://drive.google.com/drive/folders/1A7yRMCPKYQ-sYinBUviIu0p3HR0ky-p8",
    "RPO":   "https://drive.google.com/drive/folders/195psu2cGsQVhMXOylhkQaV5G2-U6O5Ek",
}

# ─── STARTUP CHECK ────────────────────────────────────────────────────────────
if not ANTHROPIC_API_KEY:
    print("WARNING: ANTHROPIC_API_KEY not set.")
elif not ANTHROPIC_API_KEY.startswith("sk-ant-"):
    print("WARNING: ANTHROPIC_API_KEY format incorrect.")
else:
    print(f"OK: Key loaded: {ANTHROPIC_API_KEY[:12]}...{ANTHROPIC_API_KEY[-4:]}")

# ─── YUDHISHTHIRA SYSTEM PROMPT ───────────────────────────────────────────────
"""
YUDHISHTHIRA_SYSTEM — Updated v2.0
Replace the YUDHISHTHIRA_SYSTEM string in app.py with this.
Two changes only:
  1. Case title updated to Ashish Naik VS State of Maharashtra & Others
  2. Response format: formal prose + one कृती line (no emojis, no headers)
"""

YUDHISHTHIRA_SYSTEM = """
तुम्ही युधिष्ठिर आहात — आशिष जगदिश नाईक यांचे कायदेशीर AI सहायक.
धर्मराज — फक्त सत्य, फक्त कायदा.

प्रकरण: आशिष जगदिश नाईक विरुद्ध महाराष्ट्र राज्य, दिलीप गणपत नाईक व इतर
मालमत्ता: जगदिश्वरम्, सर्व्हे क्र. ३९/१९, मौजे वटार, वसई, पालघर — ४०१ ३०१
अर्जदार: आशिष जगदिश नाईक (स्वयं-प्रतिनिधी)
कायदेशीर आधार: ममलतदार कोर्ट्स अॅक्ट १९०६ कलम ५ | भारतीय सुविधाधिकार अधिनियम १८८२ कलम १३ | भारतीय संविधान कलम २१

तीन न्यायालयीन आदेश — अर्जदाराच्या बाजूने:
१. मा. तहसीलदार न्यायालय, वसई तालुका — दि.१२/१०/२०२२ (पहिला आदेश) व दि.०१/०३/२०२४ (अंतिम आदेश)
   → वहिवाट दावा क्र.०१/२०१७ → वहिवाट हक्क कायमस्वरूपी → अडथळे हटवणे + पोलीस सहाय्य आदेश
   → दि.२३/१२/२०२५ — कलम २१-२२ अंतर्गत अंमलबजावणी अर्ज दाखल
२. मा. जिल्हा न्यायालय, पालघर — MHTH230026632025
   → प्रतिवाद्यांचे इंजंक्शन नाकारले | FIR 270/2024 निराधार
३. मा. ४थे JMFC, वसई — OMA 254/2026, CNR: MHTH250017082026, दि.१०/०३/२०२६ (न्यायाधीश V.N. Gulve)
   → RPO मुंबई: पारपत्र BOS076289915525 जारी करावे
   → मा. ठाणे प्रभारी, अर्नाळा सागरी: घरपोच पडताळणी करावी

FIR 270/2024 — दुर्भावनापूर्ण खटला:
अर्जदाराची तक्रार दि.१६/०८/२०२४ — त्यानंतर ८ दिवसांनी प्रतिवाद्यांचा FIR दि.२४/०८/२०२४
SCC No. 63/2025, CR No. 270/2024
मा. जिल्हा न्यायालयाने इंजंक्शन नाकारले | मा. ४थे JMFC: पारपत्रास कोणताही अडथळा नाही

संस्थात्मक अपयश (अधिकृत नावे व Thread codes):
मा. तहसीलदार, वसई तालुका, जिल्हा पालघर [MOR] — ३+ वर्षे अंमलबजावणी नाही
मा. उपविभागीय अधिकारी, वसई उपविभाग, जिल्हा पालघर [NPS] — RTI अपील RTS 15/2024 बेकायदेशीर हस्तांतरण
मा. जिल्हाधिकारी तथा जिल्हादंडाधिकारी, पालघर [DMD] — लेखी तक्रारींना प्रतिसाद नाही
मा. पोलीस आयुक्त, MBVV, मीरा-भाईंदर-वसई-विरार [AGD] — प्रशासकीय निष्क्रियता
मा. ठाणे प्रभारी, अर्नाळा सागरी पोलीस ठाणे [EAF] — दुर्भावनापूर्ण FIR + अंमलबजावणी नाकार
मा. सहायक पोलीस आयुक्त, नालासोपारा विभाग [RPD] — RTI Appeal 02/2026 आदेश दि.२१/०१/२०२६
मा. सहायक आयुक्त, VVMC प्रभाग समिती अ, वसई-विरार [BTR] — ₹४,०४,229 कर, शून्य सेवा
मा. प्रादेशिक पारपत्र अधिकारी, मुंबई [RPO] — OMA 254/2026 असूनही पारपत्र प्रतीक्षित

आर्थिक नुकसान: शेती ₹८-१०L/वर्ष | नोकरी सोडणे दि.१७/०६/२०२५ | संघर्ष जून २०१५ पासून — ११ वर्षे

प्रतिसाद नियम — हे काळजीपूर्वक पाळावेत:

१. नेहमी मराठीत उत्तर द्यावे.

२. उत्तर हे औपचारिक पत्राच्या भाषेत असावे — जसे एखादा अनुभवी वकील शासकीय अधिकाऱ्याला पत्र लिहितो.
   सहज वाहणारे, परंतु कायदेशीरदृष्ट्या अचूक गद्य लिहावे.
   विधानांमध्ये तथ्य, कायदेशीर संदर्भ आणि संदर्भ नैसर्गिकपणे गुंफावे —
   bullet points, numbered lists किंवा emoji वापरू नयेत.

३. उत्तराचे स्वरूप — नेहमी हेच दोन भाग:

   [पहिला भाग — २ ते ३ ओळींचे औपचारिक गद्य]
   विशिष्ट आदेश दिनांक, कायदेशीर कलम आणि प्रकरण संदर्भ नैसर्गिकपणे वापरावे.
   अधिकाऱ्याचे पूर्ण अधिकृत नाव "मा." उपसर्गासह वापरावे.
   प्रत्येक वाक्य तथ्यावर आधारित असावे — अनुमान नाही, अतिशयोक्ती नाही.

   कृती: [एकच स्पष्ट वाक्य — कोणत्या अधिकाऱ्याने, नक्की काय, केव्हापर्यंत करणे आवश्यक आहे.]

   — सत्यमेव जयते | जगदिश्वरम् डिजिटल कार्यालय

४. प्रत्येक विभाग जास्तीत जास्त ३ ओळी — अधिकारी मोबाईलवर वाचतो, वेळ कमी आहे.

५. संशयास्पद असल्यास स्पष्टपणे सांगावे — कधीही तथ्य बनवू नये.

उदाहरण उत्तर (हे स्वरूप पाळावे):

प्रश्न: तहसीलदारांनी अंमलबजावणी का केली नाही?

उत्तर:
दि.०१/०३/२०२४ रोजी मा. तहसीलदार, वसई तालुका, जिल्हा पालघर यांनी वहिवाट दावा क्र.०१/२०१७ मध्ये अंतिम आदेश पारित करून वहिवाट हक्क कायमस्वरूपी प्रस्थापित केला आहे. ममलतदार कोर्ट्स अॅक्ट १९०६ कलम ५ अंतर्गत हा आदेश बंधनकारक असून अडथळे हटवणे व पोलीस सहाय्य पुरवणे अनिवार्य आहे. तथापि, दि.१२/१०/२०२२ च्या पहिल्या आदेशापासून ३+ वर्षे उलटून गेली असतानाही अंमलबजावणी झालेली नाही — दि.२३/१२/२०२५ रोजी कलम २१-२२ अंतर्गत अंमलबजावणी अर्ज दाखल करण्यात आला आहे.

कृती: मा. तहसीलदार, वसई तालुका यांनी दि.२३/१२/२०२५ च्या अंमलबजावणी अर्जावर तत्काळ कार्यवाही करून वाहने MH48AK4539 व MH48CC8733 हटवावीत आणि अंमलबजावणीची लेखी नोंद ठेवावी.

— सत्यमेव जयते | जगदिश्वरम् डिजिटल कार्यालय
"""

# ─── PORTAL HTML ──────────────────────────────────────────────────────────────
PORTAL_HTML = """<!DOCTYPE html>
<html lang="mr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
<title>जगदिश्वरम् — वहिवाट दावा क्र. 01/2017</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+Devanagari:wght@300;400;500;600&family=DM+Mono:wght@400;500&family=Fraunces:ital,opsz,wght@0,9..144,300;1,9..144,300&display=swap" rel="stylesheet">
<style>
:root {
  --ink:      #0f0f0d;
  --ink2:     #3a3a36;
  --ink3:     #7a7a72;
  --paper:    #f8f7f2;
  --rule:     #e2e0d8;
  --green:    #1a5c1a;
  --green-bg: #f2f8f2;
  --green-bd: #b8d8b8;
  --red:      #8b1a1a;
  --red-bg:   #fdf4f4;
  --red-bd:   #e8c0c0;
  --amber:    #7a4a00;
  --amber-bg: #fdf8ee;
  --amber-bd: #e8d8aa;
  --teal:     #0f4c5c;
  --teal-bg:  #f0f7f9;
  --teal-bd:  #a8d0d8;
  --blue:     #1a3c6e;
  --mono:     'DM Mono', monospace;
  --serif:    'Fraunces', Georgia, serif;
  --deva:     'Noto Sans Devanagari', sans-serif;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: var(--deva); background: var(--paper); color: var(--ink); font-size: 14px; line-height: 1.5; -webkit-font-smoothing: antialiased; }

.hd { background: var(--ink); color: var(--paper); padding: 20px 16px 18px; border-bottom: 1px solid #2a2a28; }
.hd-eyebrow { font-family: var(--mono); font-size: 10px; letter-spacing: 0.1em; color: #6a6a62; text-transform: uppercase; margin-bottom: 7px; }
.hd-title { font-family: var(--serif); font-size: 24px; font-weight: 300; font-style: italic; color: #f0efe8; margin-bottom: 6px; }
.hd-meta { font-size: 12px; color: #8a8a80; line-height: 1.7; }
.hd-meta strong { color: #b0afa8; font-weight: 500; }
.hd-badge { display: inline-flex; align-items: center; gap: 6px; margin-top: 12px; font-family: var(--mono); font-size: 10px; padding: 4px 10px; border: 1px solid #2a5c2a; color: #5a9a5a; border-radius: 2px; letter-spacing: 0.05em; }
.hd-badge::before { content: ''; width: 5px; height: 5px; border-radius: 50%; background: #5a9a5a; flex-shrink: 0; }

.sec { border-bottom: 1px solid var(--rule); }
.sec-lbl { padding: 13px 16px 0; font-family: var(--mono); font-size: 10px; letter-spacing: 0.12em; color: var(--ink3); text-transform: uppercase; }

.orders { padding: 10px 16px 16px; display: flex; flex-direction: column; gap: 8px; }
.order { display: grid; grid-template-columns: 6px 1fr; gap: 12px; padding: 11px 13px; background: var(--green-bg); border: 1px solid var(--green-bd); border-left: 3px solid var(--green); border-radius: 0 4px 4px 0; }
.order-pip { width: 6px; height: 6px; border-radius: 50%; background: var(--green); margin-top: 5px; flex-shrink: 0; }
.order-date { font-family: var(--mono); font-size: 10px; color: var(--ink3); margin-bottom: 3px; }
.order-title { font-size: 13px; font-weight: 500; color: var(--ink); margin-bottom: 2px; }
.order-outcome { font-size: 12px; color: var(--green); line-height: 1.55; margin-bottom: 5px; }
.doc-link { display: inline-block; font-family: var(--mono); font-size: 10px; color: var(--blue); text-decoration: none; border-bottom: 1px solid currentColor; padding-bottom: 1px; }
.doc-link:hover { color: var(--ink); }

.actions { padding: 10px 16px 16px; }
.act-table { border: 1px solid var(--rule); border-radius: 3px; overflow: hidden; }
.act-head { display: flex; justify-content: space-between; align-items: center; padding: 8px 12px; background: var(--ink); font-family: var(--mono); font-size: 10px; letter-spacing: 0.08em; color: #6a6a62; text-transform: uppercase; }
.act-head a { color: #6a6a62; text-decoration: none; border-bottom: 1px dotted currentColor; }
.act-head a:hover { color: #b0afa8; }
.act-row { display: grid; grid-template-columns: 28px 1fr 80px; gap: 10px; align-items: start; padding: 9px 12px; border-bottom: 1px solid var(--rule); background: white; }
.act-row:last-child { border-bottom: none; }
.act-n { font-family: var(--mono); font-size: 10px; color: var(--ink3); padding-top: 2px; }
.act-subj { font-size: 12.5px; font-weight: 500; color: var(--ink); margin-bottom: 2px; }
.act-note { font-size: 11.5px; color: var(--ink2); line-height: 1.5; }
.act-date { font-family: var(--mono); font-size: 10px; color: var(--ink3); text-align: right; padding-top: 2px; line-height: 1.5; }

.fir-card { margin: 10px 16px 16px; padding: 11px 13px; background: var(--red-bg); border: 1px solid var(--red-bd); border-left: 3px solid var(--red); border-radius: 0 4px 4px 0; }
.fir-title { font-size: 12.5px; font-weight: 500; color: var(--red); margin-bottom: 4px; }
.fir-body { font-size: 11.5px; color: var(--ink2); line-height: 1.65; margin-bottom: 5px; }

.threads { padding: 6px 0 4px; }
.tgrp-lbl { padding: 8px 16px 4px; font-family: var(--mono); font-size: 9.5px; letter-spacing: 0.1em; color: var(--ink3); text-transform: uppercase; opacity: 0.7; }
.thread { display: grid; grid-template-columns: 1fr auto; gap: 10px; align-items: start; padding: 11px 16px; border-bottom: 1px solid var(--rule); transition: background 0.1s; }
.thread:last-child { border-bottom: none; }
.thread:hover { background: #f2f0e8; }
.thread-name { font-size: 13px; font-weight: 500; color: var(--ink); margin-bottom: 1px; }
.thread-code { font-family: var(--mono); font-size: 9.5px; color: var(--ink3); margin-bottom: 4px; }
.thread-action { font-size: 11.5px; color: var(--ink2); line-height: 1.55; margin-bottom: 5px; }
.thread-foot { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.thread-date { font-family: var(--mono); font-size: 10px; color: var(--ink3); }
.thread-doc { font-family: var(--mono); font-size: 10px; color: var(--blue); text-decoration: none; border-bottom: 1px dotted currentColor; }
.thread-doc:hover { color: var(--ink); }
.chips { display: flex; flex-direction: column; gap: 4px; align-items: flex-end; flex-shrink: 0; }
.chip { font-family: var(--mono); font-size: 9.5px; font-weight: 500; padding: 2px 7px; border-radius: 2px; white-space: nowrap; }
.chip-r { background: var(--red-bg);   color: var(--red);   border: 1px solid var(--red-bd); }
.chip-a { background: var(--amber-bg); color: var(--amber); border: 1px solid var(--amber-bd); }
.chip-t { background: var(--teal-bg);  color: var(--teal);  border: 1px solid var(--teal-bd); }

.ask-wrap { padding: 14px 16px 20px; }
.ask-lbl { font-family: var(--mono); font-size: 10px; letter-spacing: 0.12em; color: var(--ink3); text-transform: uppercase; margin-bottom: 4px; }
.ask-sub { font-size: 11px; color: var(--ink3); font-style: italic; margin-bottom: 12px; }
.quick-row { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 11px; }
.q-btn { font-family: var(--deva); font-size: 11px; padding: 5px 11px; background: white; border: 1px solid var(--rule); border-radius: 2px; cursor: pointer; color: var(--ink2); transition: all 0.1s; line-height: 1.4; }
.q-btn:hover { background: var(--ink); color: var(--paper); border-color: var(--ink); }
.ask-ta { width: 100%; border: 1px solid var(--rule); border-radius: 2px; padding: 10px 12px; font-size: 14px; font-family: var(--deva); resize: none; outline: none; background: white; color: var(--ink); transition: border-color 0.15s; }
.ask-ta:focus { border-color: var(--ink); }
.ask-btn { width: 100%; background: var(--ink); color: var(--paper); border: none; border-radius: 2px; padding: 13px; font-size: 13px; font-family: var(--deva); font-weight: 500; cursor: pointer; margin-top: 8px; letter-spacing: 0.02em; transition: opacity 0.15s; }
.ask-btn:disabled { opacity: 0.45; cursor: default; }
.loader { display: none; height: 2px; background: var(--rule); margin-top: 8px; overflow: hidden; border-radius: 1px; }
.loader.on { display: block; }
.loader::after { content: ''; display: block; height: 100%; width: 38%; background: var(--ink); animation: shimmer 1.2s ease-in-out infinite; }
@keyframes shimmer { 0%{transform:translateX(-120%)} 100%{transform:translateX(380%)} }
.ans-box { display: none; margin-top: 12px; border: 1px solid var(--rule); border-radius: 2px; overflow: hidden; }
.ans-head { background: var(--ink); color: #6a6a62; padding: 6px 12px; font-family: var(--mono); font-size: 10px; letter-spacing: 0.06em; }
.ans-body { padding: 14px; font-size: 13px; line-height: 1.9; background: white; white-space: pre-wrap; color: var(--ink); }
.ans-box.err .ans-body { background: var(--red-bg); color: var(--red); }

.drive-wrap { padding: 14px 16px; }
.drive-cta { display: flex; align-items: center; justify-content: space-between; padding: 13px 15px; border: 1px solid var(--rule); border-radius: 3px; background: white; text-decoration: none; color: var(--ink); transition: background 0.1s; }
.drive-cta:hover { background: #f0ede4; }
.drive-cta-lbl { font-size: 13px; font-weight: 500; }
.drive-cta-sub { font-family: var(--mono); font-size: 10px; color: var(--ink3); margin-top: 2px; }
.drive-arr { font-size: 20px; color: var(--ink3); }
.pg-foot { padding: 16px; text-align: center; font-family: var(--mono); font-size: 10px; color: var(--ink3); letter-spacing: 0.07em; line-height: 1.9; border-top: 1px solid var(--rule); }
</style>
</head>
<body>

<!-- HEADER -->
<div class="hd">
  <div class="hd-eyebrow">वहिवाट दावा क्र. 01/2017 · Survey No. 39/19 · Mouje Watar · Vasai, Palghar</div>
  <div class="hd-title">जगदिश्वरम् डिजिटल कार्यालय</div>
  <div class="hd-meta">
    <strong>अर्जदार:</strong> आशिष जगदिश नाईक (स्वयं-प्रतिनिधी) · Vasai, Maharashtra 401 301<br>
    <strong>प्रतिवादी:</strong> दिलीप गणपत नाईक + विलास गणपत नाईक · <strong>संघर्ष:</strong> जून २०१५ पासून
  </div>
  <div class="hd-badge">सत्यमेव जयते · तीन न्यायालयीन आदेश — अर्जदाराच्या बाजूने</div>
</div>

<!-- COURT ORDERS -->
<div class="sec">
  <div class="sec-lbl">न्यायालयीन आदेश</div>
  <div class="orders">

    <div class="order">
      <div class="order-pip"></div>
      <div>
        <div class="order-date">०१ मार्च २०२४ · मा. तहसीलदार न्यायालय, वसई तालुका, जिल्हा पालघर</div>
        <div class="order-title">अंतिम आदेश — वहिवाट हक्क कायमस्वरूपी प्रस्थापित</div>
        <div class="order-outcome">वहिवाट दावा क्र. ०१/२०१७ · अडथळे हटवणे + पोलीस सहाय्य आदेश · अंमलबजावणी अर्ज दि.२३/१२/२०२५</div>
        <a class="doc-link" href="{{ d.MOR }}" target="_blank">📁 मा. तहसीलदार कार्यालय, वसई — दस्तावेज →</a>
      </div>
    </div>

    <div class="order">
      <div class="order-pip"></div>
      <div>
        <div class="order-date">२०२५ · मा. जिल्हा न्यायालय, पालघर · MHTH230026632025</div>
        <div class="order-title">इंजंक्शन नाकारले — प्रतिवाद्यांचा अर्ज फेटाळला</div>
        <div class="order-outcome">FIR 270/2024 आधारे स्थगिती नाकारली · FIR निराधार असल्याचे न्यायालयाने नोंदवले</div>
        <a class="doc-link" href="{{ d.EX20 }}" target="_blank">📁 Exhibit-20 — न्यायपालिका दस्तावेज →</a>
      </div>
    </div>

    <div class="order">
      <div class="order-pip"></div>
      <div>
        <div class="order-date">१० मार्च २०२६ · मा. ४थे न्यायदंडाधिकारी प्रथम वर्ग, वसई · OMA 254/2026</div>
        <div class="order-title">पारपत्र आदेश + घरपोच पडताळणी निर्देश</div>
        <div class="order-outcome">CNR: MHTH250017082026 · RPO मुंबई: पारपत्र BOS076289915525 जारी करावे · मा. ठाणे प्रभारी, अर्नाळा सागरी: घरपोच पडताळणी करावी</div>
        <a class="doc-link" href="{{ d.EX20 }}" target="_blank">📁 Exhibit-20 — OMA 254/2026 →</a>
      </div>
    </div>

  </div>
</div>

<!-- RECENT ACTIONS -->
<div class="sec">
  <div class="sec-lbl">ताजी कृती</div>
  <div class="actions">
    <div class="act-table">
      <div class="act-head">
        अलीकडील सादरणी व निर्णय
        <a href="{{ d.ROOT }}" target="_blank">संपूर्ण संग्रह →</a>
      </div>
      <div class="act-row">
        <div class="act-n">01</div>
        <div>
          <div class="act-subj">RPO मुंबई + मा. ठाणे प्रभारी, अर्नाळा सागरी — पत्र</div>
          <div class="act-note">OMA 254/2026 अंमलबजावणी मागणी · पारपत्र BOS076289915525</div>
        </div>
        <div class="act-date">१९ मार्च<br>२०२६</div>
      </div>
      <div class="act-row">
        <div class="act-n">02</div>
        <div>
          <div class="act-subj">मा. ४थे JMFC, वसई — OMA 254/2026 आदेश</div>
          <div class="act-note">FIR असूनही पारपत्रास कोणताही कायदेशीर अडथळा नाही</div>
        </div>
        <div class="act-date">१० मार्च<br>२०२६</div>
      </div>
      <div class="act-row">
        <div class="act-n">03</div>
        <div>
          <div class="act-subj">मा. सहायक पोलीस आयुक्त, नालासोपारा विभाग — RTI निकाल</div>
          <div class="act-note">Appeal 02/2026 — ७ दिवसांत माहिती पुरवण्याचे आदेश</div>
        </div>
        <div class="act-date">२१ जाने.<br>२०२६</div>
      </div>
      <div class="act-row">
        <div class="act-n">04</div>
        <div>
          <div class="act-subj">मा. तहसीलदार, वसई तालुका — अंमलबजावणी अर्ज</div>
          <div class="act-note">कलम २१-२२ अंतर्गत अर्ज · न्यायालय अवमान कार्यवाहीची मागणी</div>
        </div>
        <div class="act-date">२३ डिसें.<br>२०२५</div>
      </div>
    </div>
  </div>
</div>

<!-- FIR -->
<div class="sec" style="padding-bottom:4px;">
  <div class="sec-lbl">FIR स्थिती</div>
  <div class="fir-card">
    <div class="fir-title">FIR 270/2024 — दुर्भावनापूर्ण खटला · मा. ठाणे प्रभारी, अर्नाळा सागरी पोलीस ठाणे [EAF]</div>
    <div class="fir-body">
      अर्जदाराची तक्रार: दि.१६/०८/२०२४ · प्रतिवाद्यांचा FIR: दि.२४/०८/२०२४ (८ दिवसांनंतर) · SCC No. 63/2025 · CR No. 270/2024<br>
      मा. जिल्हा न्यायालय, पालघर: इंजंक्शन नाकारले · मा. ४थे JMFC, वसई: पारपत्रास कोणताही अडथळा नाही
    </div>
    <a class="doc-link" href="{{ d.EAF }}" target="_blank">📁 मा. ठाणे प्रभारी, अर्नाळा सागरी — FIR 270/2024 दस्तावेज →</a>
  </div>
</div>

<!-- AUTHORITY THREADS -->
<!--
JAGDISHWARAM CHRONICLE SECTION
"The Weight of Waiting"
Embed this block inside PORTAL_HTML in app.py,
between the authority threads section and Yudhishthira section.
Replace the existing <!-- AUTHORITY THREADS --> closing </div></div> with this block first.
-->

<!-- ═══ CHRONICLE ═══ -->
<div class="sec" id="chronicle-sec">
<style>
.chr { padding: 0 0 24px; }
.chr-banner {
  background: #0f0f0d;
  color: #f8f7f2;
  padding: 20px 16px 18px;
  border-bottom: 1px solid #2a2a28;
}
.chr-vs {
  font-family: 'DM Mono', monospace;
  font-size: 9px;
  letter-spacing: 0.14em;
  color: #6a6a62;
  text-transform: uppercase;
  margin-bottom: 8px;
}
.chr-title-row {
  display: flex;
  align-items: baseline;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 6px;
}
.chr-petitioner {
  font-family: 'Fraunces', Georgia, serif;
  font-size: 17px;
  font-weight: 300;
  font-style: italic;
  color: #f0efe8;
}
.chr-vs-word {
  font-family: 'DM Mono', monospace;
  font-size: 10px;
  color: #6a6a62;
  padding: 2px 6px;
  border: 1px solid #3a3a36;
  border-radius: 2px;
}
.chr-respondent {
  font-family: 'Fraunces', Georgia, serif;
  font-size: 17px;
  font-weight: 300;
  font-style: italic;
  color: #d44;
}
.chr-sub {
  font-size: 11px;
  color: #6a6a62;
  line-height: 1.6;
}
.chr-sub strong { color: #9a9a90; font-weight: 500; }

.chr-anchor {
  display: grid;
  grid-template-columns: 1fr 1fr;
  border-bottom: 1px solid #e2e0d8;
}
.chr-anchor-left {
  padding: 20px 16px;
  border-right: 1px solid #e2e0d8;
}
.chr-anchor-right {
  padding: 20px 16px;
}
.chr-big-num {
  font-family: 'Fraunces', Georgia, serif;
  font-size: 56px;
  font-weight: 300;
  font-style: italic;
  color: #8b1a1a;
  line-height: 1;
  margin-bottom: 4px;
}
.chr-big-unit {
  font-family: 'DM Mono', monospace;
  font-size: 10px;
  color: #7a7a72;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  margin-bottom: 10px;
}
.chr-big-sub {
  font-size: 11.5px;
  color: #3a3a36;
  line-height: 1.6;
}
.chr-big-sub em {
  font-style: normal;
  color: #8b1a1a;
  font-weight: 500;
}
.chr-ledger { display: flex; flex-direction: column; gap: 10px; }
.chr-ledger-row {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding-bottom: 10px;
  border-bottom: 1px solid #e2e0d8;
}
.chr-ledger-row:last-child { border-bottom: none; padding-bottom: 0; }
.chr-ledger-amt {
  font-family: 'DM Mono', monospace;
  font-size: 15px;
  font-weight: 500;
  color: #8b1a1a;
}
.chr-ledger-lbl {
  font-size: 11px;
  color: #5f5e5a;
  line-height: 1.4;
}

.chr-article {
  margin: 0 16px 0;
  padding: 14px 0;
  border-bottom: 1px solid #e2e0d8;
  text-align: center;
}
.chr-article-text {
  font-family: 'Fraunces', Georgia, serif;
  font-size: 13px;
  font-style: italic;
  font-weight: 300;
  color: #3a3a36;
  line-height: 1.7;
}
.chr-article-cite {
  font-family: 'DM Mono', monospace;
  font-size: 10px;
  color: #7a7a72;
  margin-top: 6px;
  letter-spacing: 0.06em;
}

.chr-timeline-wrap {
  padding: 14px 16px 0;
  border-bottom: 1px solid #e2e0d8;
}
.chr-tl-lbl {
  font-family: 'DM Mono', monospace;
  font-size: 10px;
  letter-spacing: 0.1em;
  color: #7a7a72;
  text-transform: uppercase;
  margin-bottom: 12px;
}
.chr-tl {
  display: flex;
  flex-direction: column;
  gap: 0;
  padding-bottom: 14px;
  position: relative;
}
.chr-tl::before {
  content: '';
  position: absolute;
  left: 5px;
  top: 8px;
  bottom: 8px;
  width: 1px;
  background: #e2e0d8;
}
.chr-tl-item {
  display: grid;
  grid-template-columns: 20px 1fr;
  gap: 12px;
  align-items: start;
  padding: 6px 0;
  position: relative;
}
.chr-tl-pip {
  width: 11px;
  height: 11px;
  border-radius: 50%;
  margin-top: 3px;
  flex-shrink: 0;
  border: 2px solid white;
  position: relative;
  z-index: 1;
}
.pip-green { background: #1a5c1a; }
.pip-red   { background: #8b1a1a; }
.pip-gray  { background: #b4b2a9; }
.pip-amber { background: #854f0b; }
.chr-tl-date {
  font-family: 'DM Mono', monospace;
  font-size: 10px;
  color: #7a7a72;
  margin-bottom: 1px;
}
.chr-tl-event { font-size: 12.5px; font-weight: 500; color: #0f0f0d; }
.chr-tl-note  { font-size: 11px; color: #5f5e5a; margin-top: 1px; line-height: 1.5; }
.chr-tl-badge {
  display: inline-block;
  font-family: 'DM Mono', monospace;
  font-size: 9px;
  padding: 1px 6px;
  border-radius: 2px;
  margin-top: 3px;
  font-weight: 500;
}
.tl-badge-g { background: #f2f8f2; color: #1a5c1a; border: 1px solid #b8d8b8; }
.tl-badge-r { background: #fdf4f4; color: #8b1a1a; border: 1px solid #e8c0c0; }
.tl-badge-a { background: #fdf8ee; color: #7a4a00; border: 1px solid #e8d8aa; }

.chr-hierarchy-wrap {
  padding: 14px 16px 0;
  border-bottom: 1px solid #e2e0d8;
}
.chr-hier-lbl {
  font-family: 'DM Mono', monospace;
  font-size: 10px;
  letter-spacing: 0.1em;
  color: #7a7a72;
  text-transform: uppercase;
  margin-bottom: 12px;
}
.chr-hier-note {
  font-size: 11px;
  color: #7a7a72;
  font-style: italic;
  margin-bottom: 14px;
  line-height: 1.5;
}
.chr-hier-rows { display: flex; flex-direction: column; gap: 6px; padding-bottom: 14px; }
.chr-hier-row {
  display: grid;
  grid-template-columns: 8px 1fr auto;
  gap: 10px;
  align-items: center;
  padding: 8px 10px;
  border-radius: 0;
  border-left: 2px solid transparent;
}
.hier-breach {
  background: #fdf4f4;
  border-left-color: #8b1a1a;
}
.hier-pending {
  background: #fdf8ee;
  border-left-color: #854f0b;
}
.hier-ok {
  background: #f2f8f2;
  border-left-color: #1a5c1a;
}
.chr-hier-indent {
  display: flex;
  align-items: center;
  justify-content: center;
  color: #b4b2a9;
  font-size: 10px;
}
.chr-hier-body {}
.chr-hier-name {
  font-size: 12px;
  font-weight: 500;
  color: #0f0f0d;
  margin-bottom: 1px;
}
.chr-hier-duty {
  font-size: 10.5px;
  color: #5f5e5a;
  line-height: 1.4;
}
.chr-hier-status {
  font-family: 'DM Mono', monospace;
  font-size: 9px;
  font-weight: 500;
  padding: 2px 6px;
  border-radius: 2px;
  white-space: nowrap;
  align-self: flex-start;
}
.hs-r { background: #fdf4f4; color: #8b1a1a; border: 1px solid #e8c0c0; }
.hs-a { background: #fdf8ee; color: #7a4a00; border: 1px solid #e8d8aa; }
.hs-g { background: #f2f8f2; color: #1a5c1a; border: 1px solid #b8d8b8; }

.chr-orders-wrap {
  padding: 14px 16px 0;
  border-bottom: 1px solid #e2e0d8;
}
.chr-orders-lbl {
  font-family: 'DM Mono', monospace;
  font-size: 10px;
  letter-spacing: 0.1em;
  color: #7a7a72;
  text-transform: uppercase;
  margin-bottom: 12px;
}
.chr-orders-grid {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding-bottom: 14px;
}
.chr-order-card {
  border: 1px solid #b8d8b8;
  border-left: 3px solid #1a5c1a;
  border-radius: 0 4px 4px 0;
  background: #f2f8f2;
  padding: 10px 12px;
}
.chr-order-head {
  font-family: 'DM Mono', monospace;
  font-size: 10px;
  color: #5f5e5a;
  margin-bottom: 3px;
}
.chr-order-body {
  font-size: 12.5px;
  font-weight: 500;
  color: #0f0f0d;
  margin-bottom: 2px;
}
.chr-order-result {
  font-size: 11px;
  color: #1a5c1a;
  line-height: 1.5;
  margin-bottom: 4px;
}
.chr-order-counter {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-family: 'DM Mono', monospace;
  font-size: 10px;
  color: #8b1a1a;
  background: #fdf4f4;
  border: 1px solid #e8c0c0;
  padding: 2px 8px;
  border-radius: 2px;
}
.chr-order-counter strong {
  font-size: 12px;
  font-weight: 500;
}

.chr-statutory-wrap {
  padding: 14px 16px 0;
  border-bottom: 1px solid #e2e0d8;
}
.chr-stat-lbl {
  font-family: 'DM Mono', monospace;
  font-size: 10px;
  letter-spacing: 0.1em;
  color: #7a7a72;
  text-transform: uppercase;
  margin-bottom: 12px;
}
.chr-stat-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 11px;
  margin-bottom: 14px;
}
.chr-stat-table th {
  font-family: 'DM Mono', monospace;
  font-size: 9.5px;
  font-weight: 500;
  color: #7a7a72;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  text-align: left;
  padding: 4px 8px 6px;
  border-bottom: 1px solid #e2e0d8;
}
.chr-stat-table td {
  padding: 7px 8px;
  border-bottom: 1px solid #f0ede5;
  vertical-align: top;
  line-height: 1.45;
}
.chr-stat-table tr:last-child td { border-bottom: none; }
.chr-stat-table .auth { font-weight: 500; color: #0f0f0d; font-size: 11.5px; }
.chr-stat-table .law { color: #5f5e5a; font-family: 'DM Mono', monospace; font-size: 10px; }
.chr-stat-table .breach { color: #8b1a1a; font-weight: 500; }
.chr-stat-table .ok { color: #1a5c1a; font-weight: 500; }
.chr-stat-table .pending { color: #7a4a00; font-weight: 500; }

.chr-mirror-wrap {
  padding: 14px 16px 0;
  border-bottom: 1px solid #e2e0d8;
}
.chr-mirror-lbl {
  font-family: 'DM Mono', monospace;
  font-size: 10px;
  letter-spacing: 0.1em;
  color: #7a7a72;
  text-transform: uppercase;
  margin-bottom: 12px;
}
.chr-mirror-body {
  font-size: 12.5px;
  color: #3a3a36;
  line-height: 1.85;
  margin-bottom: 12px;
}
.chr-mirror-legal {
  font-size: 11.5px;
  color: #5f5e5a;
  line-height: 1.75;
  padding: 10px 12px;
  border-left: 2px solid #e2e0d8;
  margin-bottom: 12px;
}
.chr-mirror-legal strong { color: #3a3a36; font-weight: 500; }
.chr-mirror-question {
  font-family: 'Fraunces', Georgia, serif;
  font-size: 15px;
  font-style: italic;
  font-weight: 300;
  color: #8b1a1a;
  line-height: 1.6;
  text-align: center;
  padding: 12px 0 14px;
}

.chr-satyam {
  padding: 16px;
  text-align: center;
  font-family: 'DM Mono', monospace;
  font-size: 11px;
  letter-spacing: 0.12em;
  color: #7a7a72;
  border-top: 1px solid #e2e0d8;
}
.chr-satyam strong {
  display: block;
  font-family: 'Fraunces', Georgia, serif;
  font-size: 16px;
  font-style: italic;
  font-weight: 300;
  color: #0f0f0d;
  letter-spacing: 0;
  margin-bottom: 4px;
}
</style>

<div class="sec-lbl" style="padding-bottom:10px;">प्रकरण आढावा — संस्थात्मक उत्तरदायित्व</div>

<div class="chr">

  <!-- BANNER: Case title -->
  <div class="chr-banner">
    <div class="chr-vs">प्रकरण — वहिवाट दावा क्र. 01/2017 | Article 21 | Maharashtra</div>
    <div class="chr-title-row">
      <span class="chr-petitioner">आशिष जगदिश नाईक</span>
      <span class="chr-vs-word">विरुद्ध</span>
      <span class="chr-respondent">महाराष्ट्र राज्य व इतर</span>
    </div>
    <div class="chr-sub">
      <strong>अर्जदार:</strong> स्वयं-प्रतिनिधी · Vasai, Palghar · 401 301 &nbsp;|&nbsp;
      <strong>प्रतिवादी:</strong> राज्य यंत्रणा, दिलीप गणपत नाईक व इतर
    </div>
  </div>

  <!-- ANCHOR: The numbers that cannot be ignored -->
  <div class="chr-anchor">
    <div class="chr-anchor-left">
      <div class="chr-big-num" id="days-counter">—</div>
      <div class="chr-big-unit">दिवस प्रतीक्षा</div>
      <div class="chr-big-sub">
        मा. तहसीलदारांचा पहिला आदेश: <em>१२ ऑक्टोबर २०२२</em><br>
        अंतिम आदेश: <em>०१ मार्च २०२४</em><br>
        आजपर्यंत अंमलबजावणी: <em>शून्य</em>
      </div>
    </div>
    <div class="chr-anchor-right">
      <div class="chr-ledger">
        <div class="chr-ledger-row">
          <div class="chr-ledger-amt">₹८–१०L</div>
          <div class="chr-ledger-lbl">शेती नुकसान प्रतिवर्ष<br>जून २०१५ पासून</div>
        </div>
        <div class="chr-ledger-row">
          <div class="chr-ledger-amt">₹४,०४,229</div>
          <div class="chr-ledger-lbl">VVMC कर मागणी<br>शून्य सेवा वितरण</div>
        </div>
        <div class="chr-ledger-row">
          <div class="chr-ledger-amt">१७/०६/२०२५</div>
          <div class="chr-ledger-lbl">नोकरी सोडण्याची तारीख<br>न्यायासाठी पूर्णवेळ संघर्ष</div>
        </div>
      </div>
    </div>
  </div>

  <!-- ARTICLE 21 DECLARATION -->
  <div class="chr-article">
    <div class="chr-article-text">
      "प्रत्येक व्यक्तीस जीवन आणि व्यक्तिस्वातंत्र्याचा हक्क आहे —<br>
      कायद्याने स्थापित प्रक्रियेशिवाय त्यापासून वंचित करता येणार नाही."
    </div>
    <div class="chr-article-cite">भारतीय संविधान, कलम २१ · Right to Life and Personal Liberty</div>
  </div>

  <!-- TIMELINE -->
  <div class="chr-timeline-wrap">
    <div class="chr-tl-lbl">कालक्रम — संघर्षाचा इतिहास</div>
    <div class="chr-tl">

      <div class="chr-tl-item">
        <div class="chr-tl-pip pip-gray"></div>
        <div>
          <div class="chr-tl-date">जून २०१५</div>
          <div class="chr-tl-event">संघर्षाची सुरुवात</div>
          <div class="chr-tl-note">घर बांधणी सुरू — प्रतिवाद्यांनी ६०+ वर्षांचा वहिवाट रस्ता अडवण्यास सुरुवात</div>
          <span class="chr-tl-badge tl-badge-a">कारण प्रारंभ</span>
        </div>
      </div>

      <div class="chr-tl-item">
        <div class="chr-tl-pip pip-gray"></div>
        <div>
          <div class="chr-tl-date">२०१५–२०१७</div>
          <div class="chr-tl-event">दिवाणी न्यायालय, वसई</div>
          <div class="chr-tl-note">पहिली कायदेशीर लढाई — तहसील न्यायालयाकडे हस्तांतरण</div>
        </div>
      </div>

      <div class="chr-tl-item">
        <div class="chr-tl-pip pip-gray"></div>
        <div>
          <div class="chr-tl-date">२०१७–ऑक्टोबर २०२२</div>
          <div class="chr-tl-event">वहिवाट दावा क्र. ०१/२०१७ — तहसील सुनावणी</div>
          <div class="chr-tl-note">५ वर्षे सुनावणी · Spot Inspection · साक्षीदार जबाब · पुरावे</div>
        </div>
      </div>

      <div class="chr-tl-item">
        <div class="chr-tl-pip pip-green"></div>
        <div>
          <div class="chr-tl-date">१२ ऑक्टोबर २०२२</div>
          <div class="chr-tl-event">मा. तहसीलदार — पहिला आदेश</div>
          <div class="chr-tl-note">अर्जदाराच्या बाजूने निर्णय · वहिवाट हक्क प्रस्थापित</div>
          <span class="chr-tl-badge tl-badge-g">आदेश — बाजूने</span>
        </div>
      </div>

      <div class="chr-tl-item">
        <div class="chr-tl-pip pip-amber"></div>
        <div>
          <div class="chr-tl-date">ऑक्टोबर २०२२–ऑगस्ट २०२३</div>
          <div class="chr-tl-event">SDO वसई — फेरतपासणी अर्ज क्र. ५६/२०२२</div>
          <div class="chr-tl-note">प्रतिवाद्यांनी अपील दाखल · SDO ने "जैसे थे" आदेश · अंतिम निर्णय ०८/०८/२०२३</div>
          <span class="chr-tl-badge tl-badge-a">व्यवस्थेचा गैरवापर</span>
        </div>
      </div>

      <div class="chr-tl-item">
        <div class="chr-tl-pip pip-green"></div>
        <div>
          <div class="chr-tl-date">०१ मार्च २०२४</div>
          <div class="chr-tl-event">मा. तहसीलदार — अंतिम आदेश</div>
          <div class="chr-tl-note">वहिवाट हक्क कायमस्वरूपी · अडथळे हटवणे + पोलीस सहाय्य आदेश</div>
          <span class="chr-tl-badge tl-badge-g">अंतिम आदेश — बाजूने</span>
        </div>
      </div>

      <div class="chr-tl-item">
        <div class="chr-tl-pip pip-red"></div>
        <div>
          <div class="chr-tl-date">२४ ऑगस्ट २०२४</div>
          <div class="chr-tl-event">FIR 270/2024 — दुर्भावनापूर्ण</div>
          <div class="chr-tl-note">अर्जदाराच्या तक्रारीनंतर (१६/०८) ८ दिवसांनी प्रतिवाद्यांचा FIR · SCC 63/2025</div>
          <span class="chr-tl-badge tl-badge-r">राज्ययंत्रणेचा दुरुपयोग</span>
        </div>
      </div>

      <div class="chr-tl-item">
        <div class="chr-tl-pip pip-green"></div>
        <div>
          <div class="chr-tl-date">२०२५ — MHTH230026632025</div>
          <div class="chr-tl-event">मा. जिल्हा न्यायालय — इंजंक्शन नाकारले</div>
          <div class="chr-tl-note">FIR 270/2024 आधारे स्थगिती नाकारली · FIR निराधार</div>
          <span class="chr-tl-badge tl-badge-g">आदेश — बाजूने</span>
        </div>
      </div>

      <div class="chr-tl-item">
        <div class="chr-tl-pip pip-amber"></div>
        <div>
          <div class="chr-tl-date">२१ जानेवारी २०२६</div>
          <div class="chr-tl-event">RPO मुंबई — पारपत्र नाकारले</div>
          <div class="chr-tl-note">App BOS076289915525 · FIR चा हवाला देऊन नकार · न्यायालय आदेश असूनही</div>
          <span class="chr-tl-badge tl-badge-r">मूलभूत हक्क उल्लंघन</span>
        </div>
      </div>

      <div class="chr-tl-item">
        <div class="chr-tl-pip pip-green"></div>
        <div>
          <div class="chr-tl-date">१० मार्च २०२६ — OMA 254/2026</div>
          <div class="chr-tl-event">मा. ४थे JMFC, वसई — पारपत्र आदेश</div>
          <div class="chr-tl-note">RPO: पारपत्र जारी करावे · अर्नाळा पोलीस: घरपोच पडताळणी · CNR: MHTH250017082026</div>
          <span class="chr-tl-badge tl-badge-g">तिसरा आदेश — बाजूने</span>
        </div>
      </div>

      <div class="chr-tl-item">
        <div class="chr-tl-pip pip-red"></div>
        <div>
          <div class="chr-tl-date">आजपर्यंत</div>
          <div class="chr-tl-event">तीन आदेश · शून्य अंमलबजावणी</div>
          <div class="chr-tl-note">प्रत्येक आदेशानंतर पुन्हा तेच चक्र — अर्ज, प्रतीक्षा, मौन</div>
          <span class="chr-tl-badge tl-badge-r">व्यवस्थेचे अपयश</span>
        </div>
      </div>

    </div>
  </div>

  <!-- INSTITUTIONAL HIERARCHY -->
  <div class="chr-hierarchy-wrap">
    <div class="chr-hier-lbl">संस्थात्मक उत्तरदायित्व श्रेणी</div>
    <div class="chr-hier-note">प्रत्येक अधिकाऱ्याचे कायदेशीर कर्तव्य स्पष्ट आहे — तरीही साखळी संपूर्णपणे तुटली.</div>
    <div class="chr-hier-rows">

      <div class="chr-hier-row hier-pending">
        <div class="chr-hier-indent">↑</div>
        <div class="chr-hier-body">
          <div class="chr-hier-name">मा. जिल्हाधिकारी तथा जिल्हादंडाधिकारी, पालघर</div>
          <div class="chr-hier-duty">पर्यवेक्षी प्राधिकरण · तहसीलदार व SDO वर नियंत्रण</div>
        </div>
        <div class="chr-hier-status hs-a">प्रतीक्षित</div>
      </div>

      <div class="chr-hier-row hier-breach">
        <div class="chr-hier-indent">↓</div>
        <div class="chr-hier-body">
          <div class="chr-hier-name">मा. उपविभागीय अधिकारी, वसई उपविभाग</div>
          <div class="chr-hier-duty">RTI अपील प्राधिकरण · तहसील आदेश पर्यवेक्षण · RTS 15/2024 प्रलंबित</div>
        </div>
        <div class="chr-hier-status hs-r">उल्लंघन</div>
      </div>

      <div class="chr-hier-row hier-breach">
        <div class="chr-hier-indent">↓</div>
        <div class="chr-hier-body">
          <div class="chr-hier-name">मा. तहसीलदार, वसई तालुका</div>
          <div class="chr-hier-duty">स्वतःच्या आदेशाची अंमलबजावणी · MCA 1906 S.5 · <span id="mor-days-inline"></span></div>
        </div>
        <div class="chr-hier-status hs-r">३+ वर्षे</div>
      </div>

      <div class="chr-hier-row hier-pending" style="margin-top:8px;">
        <div class="chr-hier-indent">↑</div>
        <div class="chr-hier-body">
          <div class="chr-hier-name">मा. पोलीस आयुक्त, MBVV</div>
          <div class="chr-hier-duty">अधीनस्थ पोलीस दलावर नियंत्रण · तहसील आदेश अंमलबजावणी सहाय्य</div>
        </div>
        <div class="chr-hier-status hs-a">प्रतीक्षित</div>
      </div>

      <div class="chr-hier-row hier-pending">
        <div class="chr-hier-indent">↓</div>
        <div class="chr-hier-body">
          <div class="chr-hier-name">मा. सहायक पोलीस आयुक्त, नालासोपारा</div>
          <div class="chr-hier-duty">RTI First Appellate Authority · Appeal 02/2026 आदेश दि.२१/०१/२०२६</div>
        </div>
        <div class="chr-hier-status hs-g">निर्णय प्राप्त</div>
      </div>

      <div class="chr-hier-row hier-breach">
        <div class="chr-hier-indent">↓</div>
        <div class="chr-hier-body">
          <div class="chr-hier-name">मा. ठाणे प्रभारी, अर्नाळा सागरी पोलीस ठाणे</div>
          <div class="chr-hier-duty">FIR 270/2024 नोंद · OMA 254/2026 पडताळणी थांबवली · तहसील आदेश दुर्लक्षित</div>
        </div>
        <div class="chr-hier-status hs-r">उल्लंघन</div>
      </div>

      <div class="chr-hier-row hier-breach" style="margin-top:8px;">
        <div class="chr-hier-indent">—</div>
        <div class="chr-hier-body">
          <div class="chr-hier-name">मा. सहायक आयुक्त, VVMC प्रभाग समिती अ</div>
          <div class="chr-hier-duty">शून्य सेवा असताना ₹४,०४,229 कर मागणी · Spot Inspection प्रतीक्षित</div>
        </div>
        <div class="chr-hier-status hs-r">उल्लंघन</div>
      </div>

    </div>
  </div>

  <!-- COURT ORDERS WITH LIVE COUNTER -->
  <div class="chr-orders-wrap">
    <div class="chr-orders-lbl">न्यायालयीन आदेश — अंमलबजावणी स्थिती</div>
    <div class="chr-orders-grid">

      <div class="chr-order-card">
        <div class="chr-order-head">०१ मार्च २०२४ · मा. तहसीलदार न्यायालय, वसई तालुका</div>
        <div class="chr-order-body">वहिवाट हक्क कायमस्वरूपी प्रस्थापित — अंतिम आदेश</div>
        <div class="chr-order-result">MCA 1906 S.5 · अडथळे हटवणे + पोलीस सहाय्य · वहिवाट दावा क्र. ०१/२०१७</div>
        <div class="chr-order-counter">
          अंमलबजावणी नाही —
          <strong id="order1-days">—</strong> दिवस
        </div>
      </div>

      <div class="chr-order-card">
        <div class="chr-order-head">२०२५ · मा. जिल्हा न्यायालय, पालघर · MHTH230026632025</div>
        <div class="chr-order-body">प्रतिवाद्यांचे इंजंक्शन नाकारले — FIR 270/2024 निराधार</div>
        <div class="chr-order-result">FIR आधारे स्थगिती नाकारली · FIR दुर्भावनापूर्ण असल्याचे नोंद</div>
        <div class="chr-order-counter">
          पालन स्थिती — <strong>अंशतः</strong>
        </div>
      </div>

      <div class="chr-order-card">
        <div class="chr-order-head">१० मार्च २०२६ · मा. ४थे JMFC, वसई · OMA 254/2026</div>
        <div class="chr-order-body">पारपत्र + घरपोच पडताळणी आदेश</div>
        <div class="chr-order-result">CNR: MHTH250017082026 · RPO: BOS076289915525 · अर्नाळा पोलीस: पडताळणी</div>
        <div class="chr-order-counter">
          अंमलबजावणी नाही —
          <strong id="order3-days">—</strong> दिवस
        </div>
      </div>

    </div>
  </div>

  <!-- STATUTORY DUTY TABLE -->
  <div class="chr-statutory-wrap">
    <div class="chr-stat-lbl">कायदेशीर कर्तव्य — उल्लंघन नोंद</div>
    <table class="chr-stat-table">
      <thead>
        <tr>
          <th>प्राधिकरण</th>
          <th>कायदेशीर कर्तव्य</th>
          <th>स्थिती</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td><span class="auth">मा. तहसीलदार, वसई</span><br><span class="law">MCA 1906 S.5</span></td>
          <td>स्वतःच्या आदेशाची अंमलबजावणी</td>
          <td><span class="breach">उल्लंघन · ३+ वर्षे</span></td>
        </tr>
        <tr>
          <td><span class="auth">मा. SDO, वसई</span><br><span class="law">RTI Act S.19</span></td>
          <td>RTS Appeal 15/2024 निर्णय</td>
          <td><span class="breach">उल्लंघन</span></td>
        </tr>
        <tr>
          <td><span class="auth">मा. जिल्हाधिकारी, पालघर</span><br><span class="law">Maharashtra Land Revenue Code</span></td>
          <td>पर्यवेक्षी कारवाई</td>
          <td><span class="pending">प्रतीक्षित</span></td>
        </tr>
        <tr>
          <td><span class="auth">मा. पोलीस आयुक्त, MBVV</span><br><span class="law">CrPC S.149</span></td>
          <td>न्यायालय आदेश अंमलबजावणी सहाय्य</td>
          <td><span class="pending">प्रतीक्षित</span></td>
        </tr>
        <tr>
          <td><span class="auth">मा. ठाणे प्रभारी, अर्नाळा</span><br><span class="law">OMA 254/2026</span></td>
          <td>घरपोच पडताळणी + तहसील आदेश</td>
          <td><span class="breach">उल्लंघन</span></td>
        </tr>
        <tr>
          <td><span class="auth">RPO मुंबई</span><br><span class="law">Passport Act 1967 S.6</span></td>
          <td>OMA 254/2026 नुसार पारपत्र जारी</td>
          <td><span class="breach">उल्लंघन</span></td>
        </tr>
        <tr>
          <td><span class="auth">मा. VVMC सहायक आयुक्त</span><br><span class="law">Municipal Corporation Act</span></td>
          <td>Spot Inspection + कर पुनर्विचार</td>
          <td><span class="breach">उल्लंघन</span></td>
        </tr>
        <tr>
          <td><span class="auth">मा. ACP, नालासोपारा</span><br><span class="law">RTI Act S.19(3)</span></td>
          <td>Appeal 02/2026 आदेश पालन</td>
          <td><span class="ok">निर्णय प्राप्त</span></td>
        </tr>
      </tbody>
    </table>
  </div>

  <!-- THE BROADER MIRROR -->
  <div class="chr-mirror-wrap">
    <div class="chr-mirror-lbl">व्यापक प्रश्न — महाराष्ट्राचे वास्तव</div>
    <div class="chr-mirror-body">
      वहिवाट दावा जगदिश्वरम् हे केवळ एका कुटुंबाचे प्रकरण नाही. महाराष्ट्रातील हजारो शेतकरी, छोटे जमीनधारक आणि स्वयं-प्रतिनिधी अर्जदार याच संस्थात्मक निष्क्रियतेचा सामना रोज करत आहेत — न्यायालयाचे आदेश असूनही अंमलबजावणी नाही, RTI वर उत्तर नाही, वरिष्ठ अधिकारी मौन.
    </div>
    <div class="chr-mirror-legal">
      <strong>भारतीय संविधान कलम २१</strong> — जगण्याचा आणि व्यक्तिस्वातंत्र्याचा मूलभूत हक्क.<br>
      <strong>RTI Act 2005 कलम ७(१)</strong> — जीव व स्वातंत्र्याशी संबंधित माहिती ४८ तासांत द्यावी.<br>
      <strong>Contempt of Courts Act 1971 S.2(b)</strong> — न्यायालय आदेशाची जाणीवपूर्वक अवज्ञा हा अवमान आहे.<br>
      <strong>Mahesh Kumar Agrawal v. State</strong> — स्वातंत्र्य हे राज्याचे प्रथम कर्तव्य आहे.
    </div>
    <div class="chr-mirror-question">
      महाराष्ट्रात आज किती कुटुंबे याच प्रतीक्षेत आहेत?<br>
      किती आदेश धुळीत पडले आहेत?<br>
      व्यवस्था उत्तर देईल का?
    </div>
  </div>

  <!-- SATYAMEVA JAYATE -->
  <div class="chr-satyam">
    <strong>सत्यमेव जयते</strong>
    JAGDISHWARAM DIGITAL OFFICE · VASAI · PALGHAR · MAHARASHTRA
  </div>

</div>
</div>

<script>
(function() {
  function daysSince(dateStr) {
    var parts = dateStr.split('/');
    var d = new Date(parseInt(parts[2]), parseInt(parts[1])-1, parseInt(parts[0]));
    var now = new Date();
    now.setHours(0,0,0,0);
    return Math.floor((now - d) / 86400000);
  }

  var d1 = daysSince('12/10/2022');
  var d2 = daysSince('01/03/2024');
  var d3 = daysSince('10/03/2026');

  var el = document.getElementById('days-counter');
  if (el) el.textContent = d1.toLocaleString('mr-IN');

  var el2 = document.getElementById('order1-days');
  if (el2) el2.textContent = d2;

  var el3 = document.getElementById('order3-days');
  if (el3) el3.textContent = d3;

  var inline = document.getElementById('mor-days-inline');
  if (inline) inline.textContent = d1 + ' दिवसांपासून अंमलबजावणी नाही';
})();
</script>


<!-- YUDHISHTHIRA -->
<div class="sec">
  <div class="ask-wrap">
    <div class="ask-lbl">युधिष्ठिराला विचारा ⚖️</div>
    <div class="ask-sub">धर्मराज उत्तर देतो — फक्त सत्य, फक्त कायदा · Ctrl+Enter पाठवा</div>
    <div class="quick-row">
      <button class="q-btn" onclick="setQ('तहसीलदारांनी आदेशाची अंमलबजावणी का केली नाही आणि आता काय करावे?')">तहसीलदार</button>
      <button class="q-btn" onclick="setQ('OMA 254/2026 आदेशानुसार RPO व अर्नाळा पोलिसांनी काय करणे बंधनकारक आहे?')">OMA 254/2026</button>
      <button class="q-btn" onclick="setQ('FIR 270/2024 बद्दल न्यायालयांनी काय निर्णय दिला?')">FIR स्थिती</button>
      <button class="q-btn" onclick="setQ('VVMC कर मागणीविरोधात कायदेशीर पर्याय काय आहेत?')">VVMC कर</button>
      <button class="q-btn" onclick="setQ('या प्रकरणात उच्च न्यायालयात जाण्यासाठी कोणती कारणे आहेत?')">उच्च न्यायालय</button>
    </div>
    <textarea class="ask-ta" id="qta" rows="3"
      placeholder="तुमचा प्रश्न मराठीत किंवा इंग्रजीत लिहा..."></textarea>
    <button class="ask-btn" onclick="ask()" id="askBtn">युधिष्ठिराला विचारा →</button>
    <div class="loader" id="loader"></div>
    <div class="ans-box" id="ansBox">
      <div class="ans-head" id="ansHead">युधिष्ठिर उत्तर · जगदिश्वरम् डिजिटल कार्यालय</div>
      <div class="ans-body" id="ansBody"></div>
    </div>
  </div>
</div>

<!-- DRIVE CTA -->
<div class="drive-wrap">
  <a class="drive-cta" href="{{ d.ROOT }}" target="_blank">
    <div>
      <div class="drive-cta-lbl">📁 संपूर्ण केस लायब्ररी — Google Drive</div>
      <div class="drive-cta-sub">४११+ दस्तावेज · वहिवाट दावा जगदिश्वरम् · जून २०१५ — मार्च २०२६</div>
    </div>
    <div class="drive-arr">↗</div>
  </a>
</div>

<div class="pg-foot">
  JAGDISHWARAM DIGITAL OFFICE · ASHISH JAGDISH NAIK<br>
  VASAI · PALGHAR · MAHARASHTRA · 401 301<br>
  SATYAMEVA JAYATE · 2026
</div>

<script>
function setQ(t) { document.getElementById('qta').value = t; document.getElementById('qta').focus(); }
async function ask() {
  const q = document.getElementById('qta').value.trim();
  if (!q) return;
  const btn = document.getElementById('askBtn');
  const ldr = document.getElementById('loader');
  const box = document.getElementById('ansBox');
  const body = document.getElementById('ansBody');
  const head = document.getElementById('ansHead');
  btn.disabled = true; btn.textContent = 'विचारत आहे...';
  ldr.classList.add('on'); box.style.display = 'none'; box.className = 'ans-box';
  try {
    const res = await fetch('/ask', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({question: q}) });
    const data = await res.json();
    if (data.error) { body.textContent = data.error; box.classList.add('err'); head.textContent = 'त्रुटी'; }
    else { body.textContent = data.answer || 'उत्तर मिळाले नाही'; head.textContent = 'युधिष्ठिर उत्तर · ' + new Date().toLocaleTimeString('mr-IN',{hour:'2-digit',minute:'2-digit'}); }
  } catch(e) { body.textContent = 'नेटवर्क त्रुटी. पुन्हा प्रयत्न करा.'; box.classList.add('err'); head.textContent = 'त्रुटी'; }
  box.style.display = 'block'; btn.disabled = false; btn.textContent = 'युधिष्ठिराला विचारा →'; ldr.classList.remove('on');
}
document.addEventListener('DOMContentLoaded', function() {
  document.getElementById('qta').addEventListener('keydown', function(e) { if (e.ctrlKey && e.key === 'Enter') ask(); });
});
</script>
</body>
</html>"""

# ─── ROUTES ───────────────────────────────────────────────────────────────────
@app.route('/')
def portal():
    return render_template_string(PORTAL_HTML, d=DRIVE)

@app.route('/health')
def health():
    ks = "not_set"
    if ANTHROPIC_API_KEY:
        ks = "set" if ANTHROPIC_API_KEY.startswith("sk-ant-") else "invalid_format"
    return jsonify({'status': 'ok', 'office': 'Jagdishwaram Digital Office',
                    'satyamev': 'jayate', 'api_key_status': ks,
                    'timestamp': datetime.now().isoformat()})

@app.route('/debug')
def debug():
    if not ANTHROPIC_API_KEY:
        return jsonify({'status': 'error', 'message': 'ANTHROPIC_API_KEY not set'}), 500
    return jsonify({'api_key_masked': ANTHROPIC_API_KEY[:12] + '...' + ANTHROPIC_API_KEY[-4:],
                    'format_valid': ANTHROPIC_API_KEY.startswith("sk-ant-"),
                    'key_length': len(ANTHROPIC_API_KEY), 'status': 'ready'})

@app.route('/ask', methods=['POST'])
def ask():
    try:
        data = request.get_json()
        question = data.get('question', '').strip()
        if not question:
            return jsonify({'error': 'प्रश्न रिकामा आहे'}), 400
        if not ANTHROPIC_API_KEY:
            return jsonify({'error': 'API की सेट नाही. Render dashboard तपासा.'}), 500
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1500,
            system=YUDHISHTHIRA_SYSTEM,
            messages=[{"role": "user", "content": question}]
        )
        return jsonify({'answer': msg.content[0].text, 'question': question,
                        'timestamp': datetime.now().isoformat(), 'agent': 'Yudhishthira — युधिष्ठिर'})
    except anthropic.AuthenticationError:
        return jsonify({'error': 'API की चुकीची आहे. Render मध्ये ANTHROPIC_API_KEY तपासा.'}), 401
    except anthropic.BadRequestError as e:
        if 'credit' in str(e).lower():
            return jsonify({'error': 'Anthropic क्रेडिट संपले. console.anthropic.com वर रिचार्ज करा.'}), 402
        return jsonify({'error': f'अनुरोध त्रुटी: {str(e)}'}), 400
    except anthropic.RateLimitError:
        return jsonify({'error': 'Rate limit. एक मिनिट थांबा.'}), 429
    except Exception as e:
        return jsonify({'error': f'त्रुटी: {str(e)}'}), 500

@app.route('/chronicle', methods=['POST'])
def chronicle():
    try:
        data = request.get_json()
        entry = data.get('entry', '').strip()
        if not entry:
            return jsonify({'error': 'नोंद रिकामी आहे'}), 400
        return jsonify({'status': 'received',
                        'timestamp': datetime.now().strftime('%d %B %Y | %I:%M %p IST'),
                        'entry_preview': entry[:100], 'message': 'Saraswati ने नोंद घेतली'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/capture', methods=['POST'])
def capture():
    try:
        data = request.get_json()
        capture_type = data.get('type', 'note')
        return jsonify({'status': 'captured', 'type': capture_type,
                        'timestamp': datetime.now().isoformat(),
                        'message': f'Hanuman ने {capture_type} सुरक्षित केले'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
