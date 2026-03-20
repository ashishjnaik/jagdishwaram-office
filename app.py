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
YUDHISHTHIRA_SYSTEM = """
तुम्ही युधिष्ठिर आहात — आशिष जगदिश नाईक यांचे कायदेशीर AI सहायक.
धर्मराज — फक्त सत्य, फक्त कायदा.

प्रकरण तथ्ये:
- मालमत्ता: जगदिश्वरम्, सर्व्हे क्र. ३९/१९, मौजे वटार, वसई, पालघर
- अर्जदार: आशिष जगदिश नाईक (स्वयं-प्रतिनिधी)
- प्रतिवादी: दिलीप गणपत नाईक + विलास गणपत नाईक
- कायदेशीर आधार: ममलतदार कोर्ट्स अॅक्ट १९०६ कलम ५ | भारतीय सुविधाधिकार अधिनियम १८८२ कलम १३

तीन न्यायालयीन आदेश — अर्जदाराच्या बाजूने:
१. मा. तहसीलदार, वसई तालुका — दि.०१/०३/२०२४ (वहिवाट दावा क्र.०१/२०१७)
   → वहिवाट हक्क कायमस्वरूपी प्रस्थापित | अडथळे हटवणे + पोलीस सहाय्य आदेश
   → दि.२३/१२/२०२५ — अंमलबजावणी अर्ज कलम २१-२२ अंतर्गत दाखल
२. मा. जिल्हा न्यायालय, पालघर — MHTH230026632025
   → प्रतिवाद्यांचे इंजंक्शन नाकारले | FIR 270/2024 निराधार
३. मा. ४थे JMFC, वसई — OMA 254/2026, CNR: MHTH250017082026, दि.१०/०३/२०२६
   → RPO मुंबई: पारपत्र BOS076289915525 जारी करावे
   → मा. ठाणे प्रभारी, अर्नाळा सागरी: घरपोच पडताळणी करावी

FIR 270/2024 — दुर्भावनापूर्ण खटला:
- अर्जदाराची तक्रार: दि.१६/०८/२०२४ | प्रतिवाद्यांचा FIR: दि.२४/०८/२०२४ (८ दिवसांनंतर)
- SCC No. 63/2025, CR No. 270/2024
- मा. जिल्हा न्यायालय: इंजंक्शन नाकारले | मा. ४थे JMFC: पारपत्रास अडथळा नाही

संस्थात्मक अपयश (अधिकृत नावे):
- मा. तहसीलदार, वसई तालुका, जिल्हा पालघर [MOR]: २४+ महिने अंमलबजावणी नाही
- मा. उपविभागीय अधिकारी, वसई उपविभाग [NPS]: RTI अपील RTS 15/2024 — बेकायदेशीर हस्तांतरण
- मा. जिल्हाधिकारी तथा जिल्हादंडाधिकारी, पालघर [DMD]: लेखी तक्रारींना प्रतिसाद नाही
- मा. पोलीस आयुक्त, MBVV [AGD]: प्रशासकीय निष्क्रियता
- मा. ठाणे प्रभारी, अर्नाळा सागरी पोलीस ठाणे [EAF]: दुर्भावनापूर्ण FIR + अंमलबजावणी नाकार
- मा. सहायक पोलीस आयुक्त, नालासोपारा विभाग [RPD]: RTI Appeal 02/2026 — ७ दिवस माहिती आदेश दि.२१/०१/२०२६
- मा. सहायक आयुक्त, VVMC प्रभाग समिती अ [BTR]: ₹४,०४,२२९ कर — शून्य सेवा
- मा. प्रादेशिक पारपत्र अधिकारी, मुंबई [RPO]: पारपत्र नाकारले — आदेश असूनही

आर्थिक नुकसान: शेती ₹८-१०L/वर्ष | नोकरी सोडणे दि.१७/०६/२०२५ | ११ वर्षे संघर्ष जून २०१५ पासून

प्रतिसाद स्वरूप — प्रत्येक वेळी हे चार भाग वापरावेत:

⚖️ निर्णय / स्थिती:
[एक स्पष्ट तथ्यात्मक विधान. जास्तीत जास्त २ ओळी.]

📋 कायदेशीर आधार:
[विशिष्ट कलम + विशिष्ट आदेश दिनांक/क्रमांक. जास्तीत जास्त २ ओळी.]

🎯 तत्काळ कृती:
[या अधिकाऱ्याने आत्ता नक्की काय करावे. क्रियापद वापरावे. जास्तीत जास्त २ ओळी.]

📁 संदर्भ दस्तावेज:
[कोणता दस्तावेज/फोल्डर/प्रदर्शनी पाहावी. जास्तीत जास्त १ ओळ.]

---
सत्यमेव जयते | जगदिश्वरम् डिजिटल कार्यालय

नियम: नेहमी मराठीत. नेहमी ४ भाग. अधिकाऱ्यांचे पूर्ण अधिकृत नाव मा. सह वापरावे. विशिष्ट कलमे व तारखा. संशयास्पद असल्यास स्पष्ट सांगावे. प्रत्येक विभाग जास्तीत जास्त २ ओळी.
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
<div class="sec">
  <div class="sec-lbl">अपेक्षित कृती — सक्रिय धागे</div>
  <div class="threads">

    <div class="tgrp-lbl">महसूल प्रशासन</div>

    <div class="thread">
      <div>
        <div class="thread-name">मा. तहसीलदार, वसई तालुका, जिल्हा पालघर</div>
        <div class="thread-code">कार्यालय: तहसील कार्यालय, वसई · Thread MOR</div>
        <div class="thread-action">दि.०१/०३/२०२४ च्या अंतिम आदेशाची तत्काळ अंमलबजावणी करावी · वाहने MH48AK4539 व MH48CC8733 हटवावीत · अंमलबजावणी अर्ज दि.२३/१२/२०२५ प्रलंबित आहे</div>
        <div class="thread-foot">
          <span class="thread-date">शेवटचा पत्रव्यवहार: डिसेंबर २०२५</span>
          <a class="thread-doc" href="{{ d.MOR }}" target="_blank">📁 दस्तावेज</a>
        </div>
      </div>
      <div class="chips">
        <span class="chip chip-r">उल्लंघन</span>
        <span class="chip chip-r">२४+ महिने</span>
      </div>
    </div>

    <div class="thread">
      <div>
        <div class="thread-name">मा. उपविभागीय अधिकारी, वसई उपविभाग, जिल्हा पालघर</div>
        <div class="thread-code">कार्यालय: उपविभागीय कार्यालय, वसई · Thread NPS</div>
        <div class="thread-action">RTI अपील RTS Appeal No.15/2024 वर निर्णय द्यावा · वहिवाट फेरतपासणी दावा क्र.५६/२०२२ संदर्भात बेकायदेशीर हस्तांतरण रद्द करावे</div>
        <div class="thread-foot">
          <span class="thread-date">शेवटचा पत्रव्यवहार: २०२४</span>
          <a class="thread-doc" href="{{ d.NPS }}" target="_blank">📁 दस्तावेज</a>
        </div>
      </div>
      <div class="chips">
        <span class="chip chip-r">उल्लंघन</span>
      </div>
    </div>

    <div class="thread">
      <div>
        <div class="thread-name">मा. जिल्हाधिकारी तथा जिल्हादंडाधिकारी, पालघर</div>
        <div class="thread-code">कार्यालय: जिल्हाधिकारी कार्यालय, पालघर · Thread DMD</div>
        <div class="thread-action">मा. तहसीलदार व मा. उपविभागीय अधिकारी यांच्या अपयशावर पर्यवेक्षी कारवाई करावी · उच्चस्तरीय लेखी अर्ज दाखल</div>
        <div class="thread-foot">
          <span class="thread-date">शेवटचा पत्रव्यवहार: २०२५</span>
          <a class="thread-doc" href="{{ d.DMD }}" target="_blank">📁 दस्तावेज</a>
        </div>
      </div>
      <div class="chips">
        <span class="chip chip-a">प्रतीक्षित</span>
      </div>
    </div>

    <div class="tgrp-lbl">पोलीस प्रशासन</div>

    <div class="thread">
      <div>
        <div class="thread-name">मा. पोलीस आयुक्त, MBVV, मीरा-भाईंदर-वसई-विरार</div>
        <div class="thread-code">कार्यालय: पोलीस आयुक्तालय, MBVV · Thread AGD</div>
        <div class="thread-action">तहसील आदेश दि.०१/०३/२०२४ च्या अंमलबजावणीसाठी अधीनस्थ अधिकाऱ्यांना निर्देश द्यावेत · पोलीस संरक्षण व तत्काळ कारवाई करावी</div>
        <div class="thread-foot">
          <span class="thread-date">शेवटचा पत्रव्यवहार: २०२५</span>
          <a class="thread-doc" href="{{ d.AGD }}" target="_blank">📁 दस्तावेज</a>
        </div>
      </div>
      <div class="chips">
        <span class="chip chip-a">प्रतीक्षित</span>
      </div>
    </div>

    <div class="thread">
      <div>
        <div class="thread-name">मा. ठाणे प्रभारी, अर्नाळा सागरी पोलीस ठाणे</div>
        <div class="thread-code">कार्यालय: अर्नाळा सागरी पोलीस ठाणे · Thread EAF</div>
        <div class="thread-action">OMA 254/2026 नुसार घरपोच पडताळणी तत्काळ करावी · दि.०१/०३/२०२४ तहसील आदेशाची अंमलबजावणी करावी · RPO मुंबईस पारपत्र प्रकरणात सहकार्य करावे</div>
        <div class="thread-foot">
          <span class="thread-date">शेवटचा पत्रव्यवहार: १९ मार्च २०२६</span>
          <a class="thread-doc" href="{{ d.EAF }}" target="_blank">📁 दस्तावेज</a>
        </div>
      </div>
      <div class="chips">
        <span class="chip chip-r">उल्लंघन</span>
      </div>
    </div>

    <div class="thread">
      <div>
        <div class="thread-name">मा. सहायक पोलीस आयुक्त, नालासोपारा विभाग</div>
        <div class="thread-code">कार्यालय: ACP कार्यालय, नालासोपारा · Thread RPD</div>
        <div class="thread-action">RTI Appeal 02/2026 आदेश दि.२१/०१/२०२६ नुसार ७ दिवसांत माहिती पुरवण्याचे पालन सुनिश्चित करावे</div>
        <div class="thread-foot">
          <span class="thread-date">शेवटचा पत्रव्यवहार: २१ जानेवारी २०२६</span>
          <a class="thread-doc" href="{{ d.RPD }}" target="_blank">📁 दस्तावेज</a>
        </div>
      </div>
      <div class="chips">
        <span class="chip chip-t">निर्णय प्राप्त</span>
      </div>
    </div>

    <div class="tgrp-lbl">महानगरपालिका</div>

    <div class="thread">
      <div>
        <div class="thread-name">मा. सहायक आयुक्त, VVMC प्रभाग समिती अ, वसई-विरार</div>
        <div class="thread-code">कार्यालय: VVMC प्रभाग समिती अ कार्यालय · Thread BTR</div>
        <div class="thread-action">₹४,०४,२२९ कर मागणी नोटिशीवर लेखी प्रतिवाद स्वीकारावा · Spot Inspection Report सादर करावा · शून्य सेवा वितरण नोंद VT02/338 विचारात घ्यावी</div>
        <div class="thread-foot">
          <span class="thread-date">शेवटचा पत्रव्यवहार: २०२५</span>
          <a class="thread-doc" href="{{ d.BTR }}" target="_blank">📁 दस्तावेज</a>
        </div>
      </div>
      <div class="chips">
        <span class="chip chip-r">उल्लंघन</span>
      </div>
    </div>

  </div>
</div>

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
