"""
JAGDISHWARAM DIGITAL OFFICE
Flask Server | Render.com Deployment
सत्यमेव जयते | Vasai 2026

आशिष जगदिश नाईक विरुद्ध महाराष्ट्र राज्य, दिलीप गणपत नाईक व इतर

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

# ─── DRIVE URLS — Sprint 1 verified ──────────────────────────────────────────
# Parent folders
# Subfolder convention: KEY_A = administrative track, KEY_R = RTI track
DRIVE = {
    "ROOT":  "https://drive.google.com/drive/folders/1TyYJPzRcvm1Xw6pkzcePL7TYEwhYWrmY",
    "EX20":  "https://drive.google.com/drive/folders/1A7yRMCPKYQ-sYinBUviIu0p3HR0ky-p8",
    "JUD":   "https://drive.google.com/drive/folders/1zFxgB8IhqG5e6z8EszGeZ3D0Hu9tmmsC",
    "MOR":   "https://drive.google.com/drive/folders/15vOGf-lwDj2vaoMyMBPQw8igYIrPrzcx",
    "NPS":   "https://drive.google.com/drive/folders/17mspg1td0gY-liVJPEPDI5K5spyBYCGH",
    "DMD":   "https://drive.google.com/drive/folders/1ivErLtUoyDtOSfHhrSEd1m0AyvmxBT_C",
    "AGD":   "https://drive.google.com/drive/folders/1B3jG1HzxDzVKEtleu_5S_1et_TBcuyYR",
    "EAF":   "https://drive.google.com/drive/folders/195psu2cGsQVhMXOylhkQaV5G2-U6O5Ek",
    "RPD":   "https://drive.google.com/drive/folders/1XfeT_ePcmVpx_-h4SoqFqUv0gtPvFTzF",
    "BTR":   "https://drive.google.com/drive/folders/1-JlBXzydWTrvLUPQSuDG64l642s4_KlM",
    "RPO":   "https://drive.google.com/drive/folders/195psu2cGsQVhMXOylhkQaV5G2-U6O5Ek",
    # Admin subfolders (धागा क्र X)
    "MOR_A": "https://drive.google.com/drive/folders/13RPxnVzQiYAIKYTAEt4T7HMRWuQIvkmc",
    "NPS_A": "https://drive.google.com/drive/folders/17Isin4co9W7gigqPtq3U5s4rTLllhwCq",
    "DMD_A": "https://drive.google.com/drive/folders/1td1ikWCD-BdzL0o0OMnjuAmQEkWkPp4P",
    "AGD_A": "https://drive.google.com/drive/folders/1yLlq3LGsREHFB1yBFCGoHf5zEbEg6tV0",
    "EAF_A": "https://drive.google.com/drive/folders/1t_mPXPj8kuV13fMa3mpCaX7TED_T0PGO",
    "RPD_A": "https://drive.google.com/drive/folders/1bfRlPEKagCHh2Mzrl4Wef8mPJiy_gtMd",
    "BTR_A": "https://drive.google.com/drive/folders/1WSwGe_SuzfafNyxXZ3OflZuCw7f7taQ7",
    # RTI subfolders (धागा क्र X.X.१)
    "MOR_R": "https://drive.google.com/drive/folders/17aVbuG6fvt7PoEqxZw6de-O_WbCXlxMk",
    "NPS_R": "https://drive.google.com/drive/folders/1yNvC7rL_8s1_uEXJFgfTY7-x5UGEJfua",
    "DMD_R": "https://drive.google.com/drive/folders/1CCzfKVY8xQeOnaxS9Dx10F-2SuhaCiOW",
    "AGD_R": "https://drive.google.com/drive/folders/1fSIDdA0HQKQmwJtIPY1je7DWn7CAsKEs",
    "EAF_R": "https://drive.google.com/drive/folders/1Q30xJk8TkzxgIHHiV85wdysfLSRATDLe",
    "RPD_R": "https://drive.google.com/drive/folders/1t9rknxkJ9jBSJYf2xCT9y-rr-jBkDDeV",
    "BTR_R": "https://drive.google.com/drive/folders/1BgBxxhmj0qt3FWS5sddQH4XKO7CWamrp",
}

# ─── STARTUP CHECK ────────────────────────────────────────────────────────────
if not ANTHROPIC_API_KEY:
    print("WARNING: ANTHROPIC_API_KEY not set.")
elif not ANTHROPIC_API_KEY.startswith("sk-ant-"):
    print("WARNING: ANTHROPIC_API_KEY format incorrect.")
else:
    print(f"OK: {ANTHROPIC_API_KEY[:12]}...{ANTHROPIC_API_KEY[-4:]}")

# ─── YUDHISHTHIRA v3 ──────────────────────────────────────────────────────────
YUDHISHTHIRA_SYSTEM = """
तुम्ही युधिष्ठिर आहात — आशिष जगदिश नाईक यांचे कायदेशीर AI सहायक.
धर्मराज — फक्त सत्य, फक्त कायदा.

प्रकरण: आशिष जगदिश नाईक विरुद्ध महाराष्ट्र राज्य, दिलीप गणपत नाईक व इतर
मालमत्ता: जगदिश्वरम्, सर्व्हे क्र. ३९/१९, मौजे वटार, वसई, पालघर — ४०१ ३०१
अर्जदार: आशिष जगदिश नाईक (स्वयं-प्रतिनिधी)
कायदेशीर आधार: ममलतदार कोर्ट्स अॅक्ट १९०६ कलम ५ | भारतीय सुविधाधिकार अधिनियम १८८२ कलम १३ | भारतीय संविधान कलम २१

न्यायालयीन आदेश व महत्त्वाचे निर्णय — अर्जदाराच्या बाजूने:
१. मा. तहसीलदार न्यायालय, वसई — दि.१२/१०/२०२२ (पहिला आदेश) व दि.०१/०३/२०२४ (अंतिम आदेश)
   → वहिवाट दावा क्र.०१/२०१७ → वहिवाट हक्क कायमस्वरूपी → अडथळे हटवणे + पोलीस सहाय्य आदेश
   → दि.२३/१२/२०२५ — कलम २१-२२ अंतर्गत अंमलबजावणी अर्ज दाखल
२. मा. जिल्हा न्यायालय, पालघर — MHTH230026632025
   → प्रतिवाद्यांचे इंजंक्शन नाकारले | FIR 270/2024 निराधार
   → दि.१८/०३/२०२६ — इंजंक्शन अर्ज अंतिमतः फेटाळला — तहसील आदेशावरील सर्व दिवाणी निर्बंध हटले
   → परिणाम: दि.०१/०३/२०२४ चा वहिवाट आदेश आता पूर्णतः कायदेशीररित्या निर्बंधमुक्त आहे
३. मा. ४थे JMFC, वसई — OMA 254/2026, CNR: MHTH250017082026, दि.१०/०३/२०२६
   → RPO मुंबई: पारपत्र BOS076289915525 जारी करावे
   → मा. ठाणे प्रभारी, अर्नाळा सागरी: घरपोच पडताळणी करावी

FIR 270/2024 — दुर्भावनापूर्ण खटला:
अर्जदाराची तक्रार दि.१६/०८/२०२४ — त्यानंतर ८ दिवसांनी प्रतिवाद्यांचा FIR दि.२४/०८/२०२४
SCC No. 63/2025, CR No. 270/2024 — मा. जिल्हा न्यायालयाने निराधार ठरवले

दुहेरी अपयश — प्रत्येक अधिकारी दोन क्षमतांमध्ये अपयशी:
(एकच अधिकारी प्रशासकीय क्षमतेत आदेश अंमलात आणत नाही, आणि PIO/FAA क्षमतेत RTI माहितीही देत नाही)

मा. तहसीलदार, वसई तालुका, जिल्हा पालघर [MOR]:
  प्रशासन: दि.०१/०३/२०२४ आदेश — ३+ वर्षे अंमलबजावणी नाही | RTI PIO: धागा १.३.१ — माहिती नाकारली

मा. उपविभागीय अधिकारी, वसई उपविभाग [NPS]:
  प्रशासन: RTS Appeal 15/2024 निर्णय नाही, बेकायदेशीर हस्तांतरण | RTI FAA: धागा १.२.१ — माहिती नाकारली

मा. जिल्हाधिकारी तथा जिल्हादंडाधिकारी, पालघर [DMD]:
  प्रशासन: पर्यवेक्षी कारवाई नाही | RTI FAA: धागा १.१ — माहिती नाकारली

मा. पोलीस आयुक्त, MBVV [AGD]:
  प्रशासन: अधीनस्थांना निर्देश नाही | RTI PIO: धागा २.१ — माहिती नाकारली

मा. ठाणे प्रभारी, अर्नाळा सागरी पोलीस ठाणे [EAF]:
  प्रशासन: FIR 270/2024 दाखल + तहसील आदेश अंमल नाही | RTI PIO: धागा २.३.१ — माहिती नाकारली

मा. सहायक पोलीस आयुक्त, नालासोपारा [RPD]:
  प्रशासन: FAA म्हणून अधिकार नाकारले | RTI FAA: Appeal 02/2026 आदेश — दि.२१/०१/२०२६ आदेश दिला (आंशिक यश)

मा. सहायक आयुक्त, VVMC प्रभाग समिती अ [BTR]:
  प्रशासन: ₹४,०४,229 कर — शून्य सेवा | RTI PIO: धागा १.४.१ — माहिती नाकारली

आर्थिक नुकसान: शेती ₹८-१०L/वर्ष | नोकरी सोडणे दि.१७/०६/२०२५ | संघर्ष जून २०१५ — ११ वर्षे

अर्जदाराच्या ४ मागण्या (न्यायालयीन स्तरावर नोंदवलेल्या):
१. वहिवाट अंमलबजावणी — MCA 1906 S.5 अंतर्गत तत्काळ
२. FIR 270/2024 रद्दीकरण — दुर्भावना सिद्ध
३. नुकसानभरपाई — ११ वर्षांचे नुकसान + Article 21 उल्लंघन
४. तंत्रज्ञान अंगीकार — शासन व न्यायव्यवस्थेत AI/Tech Tools द्वारे पारदर्शकता, उत्तरदायित्व व कार्यक्षमता

प्रतिसाद नियम:
१. नेहमी मराठीत उत्तर द्यावे.
२. औपचारिक पत्राच्या भाषेत — अनुभवी वकिलाच्या शैलीत गद्य लिहावे.
३. प्रत्येक अधिकाऱ्याचे दुहेरी अपयश (प्रशासकीय + RTI) नमूद करावे जेव्हा प्रश्न संबंधित असेल.
४. उत्तराचे स्वरूप — नेहमी हेच दोन भाग:
   [२-३ ओळींचे औपचारिक गद्य — तथ्य + कायदा + दुहेरी अपयश संदर्भ]
   कृती: [एकच वाक्य — कोण, काय, केव्हा]
   — सत्यमेव जयते | जगदिश्वरम् डिजिटल कार्यालय
५. प्रत्येक विभाग जास्तीत जास्त ३ ओळी.
६. संशयास्पद असल्यास स्पष्टपणे सांगावे.


# CASE FILE INDEX AND DEFINITIONS
## Critical Exhibit Reference Table:
This table maps short-code identifiers to the definitive legal documents and file IDs within the Google Drive. ALWAYS use these references when citing facts.

| Short Code | Document Title & Date | Google Drive File ID |
| :--------- | :---------------------------------------------------------------------------------------------------------------------------------------- | :---------------------------------- |
| Exhibit-19 | Enforcement Petition (Filed 23 December 2025) - [Content is Current] | 1K5FXmCsNEhbPM-YA1l9ZZO66_NL-PzCF/view?usp=drive_link |
| Exhibit-20 | Current Status Folder (Ongoing Status Reports) - [Content is Ongoing] | 1A7yRMCPKYQ-sYinBUviIu0p3HR0ky-p8 |
| Exhibit-10-5| Tehsil Submission (Filed 09 November 2023) - [Key Founding Document] | 1MuH1Fat2nUVmi_KDuJ9dXBl628MR4ySG |
| मूळ धागा  | Final Order on Vahivat Dawa (Dated 01 March 2024) - [The Undisputed Legal Right] | 146cKWWYrSP7mHhZiZne6oe1l9l7PFey0 |
## Core Strategic Failures:
- **Dual-Capacity Failure:** The authority's documented failure to act in their primary (administrative) capacity and their secondary (RTI Appellate) capacity, creating a system deadlock.
- **4th Demand (Technology Adoption):** The formal demand requiring the authority to use modern, documented digital tools (like this portal) to manage public records, as mandated by the e-governance policy.

"""

# ─── PORTAL HTML ──────────────────────────────────────────────────────────────
PORTAL_HTML = """<!DOCTYPE html>
<html lang="mr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
<meta name="theme-color" content="#0f0f0d">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="जगदिश्वरम्">
<title>जगदिश्वरम् — वहिवाट दावा क्र. 01/2017</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+Devanagari:wght@300;400;500;600&family=DM+Mono:wght@400;500&family=Fraunces:ital,opsz,wght@0,9..144,300;1,9..144,300&display=swap" rel="stylesheet">
<style>
:root {
  --ink:       #0f0f0d;
  --ink2:      #3a3a36;
  --ink3:      #7a7a72;
  --paper:     #f6f5f0;
  --card:      #ffffff;
  --rule:      #e8e6de;
  --green:     #1a5c1a;
  --green-bg:  #f0f9f0;
  --green-bd:  #b0d8b0;
  --red:       #8b1a1a;
  --red-bg:    #fdf3f3;
  --red-bd:    #e0b8b8;
  --amber:     #7a4a00;
  --amber-bg:  #fdf7ea;
  --amber-bd:  #e0d0a0;
  --teal:      #0f4c5c;
  --teal-bg:   #eef6f9;
  --teal-bd:   #a0c8d8;
  --blue:      #1a3c6e;
  --indigo:    #2d2a7a;
  --indigo-bg: #f0effc;
  --indigo-bd: #c0bef0;
  --mono: 'DM Mono', monospace;
  --serif: 'Fraunces', Georgia, serif;
  --deva: 'Noto Sans Devanagari', sans-serif;
  --r4: 4px; --r8: 8px; --r12: 12px;
}
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
html { scroll-behavior: smooth; }
body {
  font-family: var(--deva);
  background: var(--paper);
  color: var(--ink);
  font-size: 15px;
  line-height: 1.55;
  -webkit-font-smoothing: antialiased;
  -webkit-tap-highlight-color: transparent;
}
a { -webkit-tap-highlight-color: transparent; }

/* ── HEADER ── */
.hd {
  background: var(--ink);
  color: #f0efe8;
  padding: 20px 16px 20px;
  padding-top: max(20px, env(safe-area-inset-top));
}
.hd-eyebrow {
  font-family: var(--mono);
  font-size: 10px;
  letter-spacing: 0.12em;
  color: #5a5a52;
  text-transform: uppercase;
  margin-bottom: 8px;
}
.hd-title {
  font-family: var(--serif);
  font-size: 26px;
  font-weight: 300;
  font-style: italic;
  color: #f0efe8;
  margin-bottom: 6px;
  line-height: 1.2;
}
.hd-case {
  font-size: 12px;
  color: #7a7a70;
  line-height: 1.7;
  margin-bottom: 2px;
}
.hd-case strong { color: #a0a098; font-weight: 500; }
.hd-vs {
  display: flex;
  align-items: baseline;
  gap: 8px;
  flex-wrap: wrap;
  margin: 10px 0 0;
}
.hd-petitioner {
  font-family: var(--serif);
  font-size: 14px;
  font-style: italic;
  font-weight: 300;
  color: #c8c7c0;
}
.hd-vs-pill {
  font-family: var(--mono);
  font-size: 9px;
  padding: 2px 7px;
  border: 1px solid #3a3a32;
  color: #5a5a52;
  border-radius: var(--r4);
  letter-spacing: 0.06em;
}
.hd-respondent {
  font-family: var(--serif);
  font-size: 14px;
  font-style: italic;
  font-weight: 300;
  color: #cc5555;
}
.hd-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-top: 14px;
  font-family: var(--mono);
  font-size: 10px;
  padding: 5px 12px;
  border: 1px solid #223a22;
  color: #5a9a5a;
  border-radius: var(--r4);
  letter-spacing: 0.05em;
}
.hd-badge-dot {
  width: 5px; height: 5px;
  border-radius: 50%;
  background: #5a9a5a;
  flex-shrink: 0;
}

/* ── PAGE LAYOUT ── */
.page-body { padding: 0 0 32px; }
.sec { border-bottom: 1px solid var(--rule); }
.sec-lbl {
  padding: 16px 16px 0;
  font-family: var(--mono);
  font-size: 10px;
  letter-spacing: 0.12em;
  color: var(--ink3);
  text-transform: uppercase;
}

/* ── COURT ORDERS ── */
.orders { padding: 12px 16px 16px; display: flex; flex-direction: column; gap: 10px; }
.order {
  background: var(--card);
  border: 1px solid var(--green-bd);
  border-left: 3px solid var(--green);
  border-radius: 0 var(--r8) var(--r8) 0;
  padding: 12px 14px;
}
.order-date {
  font-family: var(--mono);
  font-size: 10px;
  color: var(--ink3);
  margin-bottom: 3px;
}
.order-title {
  font-size: 13.5px;
  font-weight: 500;
  color: var(--ink);
  margin-bottom: 3px;
  line-height: 1.4;
}
.order-result {
  font-size: 12px;
  color: var(--green);
  line-height: 1.6;
  margin-bottom: 6px;
}
.order-alert {
  font-size: 11.5px;
  color: var(--indigo);
  background: var(--indigo-bg);
  border: 1px solid var(--indigo-bd);
  border-radius: var(--r4);
  padding: 5px 9px;
  margin-bottom: 6px;
  line-height: 1.5;
}
.doc-link {
  display: inline-block;
  font-family: var(--mono);
  font-size: 10px;
  color: var(--blue);
  text-decoration: none;
  border-bottom: 1px solid currentColor;
  padding-bottom: 1px;
  min-height: 24px;
  line-height: 24px;
}
.doc-link:hover { color: var(--ink); }

/* ── RECENT ACTIONS ── */
.actions { padding: 12px 16px 16px; }
.act-card {
  background: var(--card);
  border: 1px solid var(--rule);
  border-radius: var(--r8);
  overflow: hidden;
}
.act-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 9px 14px;
  background: var(--ink);
  font-family: var(--mono);
  font-size: 10px;
  letter-spacing: 0.08em;
  color: #5a5a52;
  text-transform: uppercase;
}
.act-head a {
  color: #5a5a52;
  text-decoration: none;
  border-bottom: 1px dotted currentColor;
}
.act-row {
  display: grid;
  grid-template-columns: 26px 1fr 72px;
  gap: 10px;
  align-items: start;
  padding: 10px 14px;
  border-bottom: 1px solid var(--rule);
}
.act-row:last-child { border-bottom: none; }
.act-n {
  font-family: var(--mono);
  font-size: 10px;
  color: var(--ink3);
  padding-top: 2px;
}
.act-subj {
  font-size: 13px;
  font-weight: 500;
  color: var(--ink);
  margin-bottom: 2px;
  line-height: 1.4;
}
.act-note { font-size: 12px; color: var(--ink2); line-height: 1.5; }
.act-date {
  font-family: var(--mono);
  font-size: 10px;
  color: var(--ink3);
  text-align: right;
  padding-top: 2px;
  line-height: 1.6;
}
.act-row.act-new { background: #fdfcf5; }
.act-new-badge {
  display: inline-block;
  font-family: var(--mono);
  font-size: 8.5px;
  padding: 1px 5px;
  background: var(--indigo-bg);
  color: var(--indigo);
  border: 1px solid var(--indigo-bd);
  border-radius: 2px;
  margin-left: 5px;
  vertical-align: middle;
}

/* ── FIR ── */
.fir-wrap { padding: 0 16px 16px; }
.fir-card {
  background: var(--red-bg);
  border: 1px solid var(--red-bd);
  border-left: 3px solid var(--red);
  border-radius: 0 var(--r8) var(--r8) 0;
  padding: 12px 14px;
}
.fir-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--red);
  margin-bottom: 5px;
  line-height: 1.4;
}
.fir-body {
  font-size: 12px;
  color: var(--ink2);
  line-height: 1.7;
  margin-bottom: 6px;
}

/* ── AUTHORITY THREADS ── */
.threads-wrap { padding: 12px 16px 16px; display: flex; flex-direction: column; gap: 10px; }
.tgrp-lbl {
  font-family: var(--mono);
  font-size: 9.5px;
  letter-spacing: 0.1em;
  color: var(--ink3);
  text-transform: uppercase;
  padding-top: 4px;
}
.tcard {
  background: var(--card);
  border: 1px solid var(--rule);
  border-radius: var(--r8);
  overflow: hidden;
}
.tcard-head {
  padding: 11px 14px 9px;
  border-bottom: 1px solid var(--rule);
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 8px;
}
.tcard-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--ink);
  line-height: 1.4;
  flex: 1;
}
.tcard-code {
  font-family: var(--mono);
  font-size: 9px;
  color: var(--ink3);
  margin-top: 2px;
}
.dual-badge {
  font-family: var(--mono);
  font-size: 9px;
  font-weight: 500;
  padding: 3px 7px;
  background: var(--red-bg);
  color: var(--red);
  border: 1px solid var(--red-bd);
  border-radius: 20px;
  white-space: nowrap;
  flex-shrink: 0;
}
.ok-badge {
  font-family: var(--mono);
  font-size: 9px;
  font-weight: 500;
  padding: 3px 7px;
  background: var(--teal-bg);
  color: var(--teal);
  border: 1px solid var(--teal-bd);
  border-radius: 20px;
  white-space: nowrap;
  flex-shrink: 0;
}
.tcard-track {
  display: grid;
  grid-template-columns: 60px 1fr auto;
  gap: 8px;
  align-items: start;
  padding: 8px 14px;
  border-bottom: 1px solid #f4f2ea;
}
.tcard-track:last-of-type { border-bottom: none; }
.track-lbl {
  font-family: var(--mono);
  font-size: 9px;
  letter-spacing: 0.06em;
  color: var(--ink3);
  text-transform: uppercase;
  padding-top: 2px;
  line-height: 1.4;
}
.track-action {
  font-size: 12px;
  color: var(--ink2);
  line-height: 1.5;
}
.chip {
  font-family: var(--mono);
  font-size: 9px;
  font-weight: 500;
  padding: 2px 7px;
  border-radius: 2px;
  white-space: nowrap;
  flex-shrink: 0;
}
.chip-r { background: var(--red-bg);   color: var(--red);   border: 1px solid var(--red-bd); }
.chip-a { background: var(--amber-bg); color: var(--amber); border: 1px solid var(--amber-bd); }
.chip-g { background: var(--green-bg); color: var(--green); border: 1px solid var(--green-bd); }
.chip-t { background: var(--teal-bg);  color: var(--teal);  border: 1px solid var(--teal-bd); }
.tcard-foot {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 14px;
  border-top: 1px solid var(--rule);
  background: #faf9f5;
  flex-wrap: wrap;
}
.tcard-date {
  font-family: var(--mono);
  font-size: 10px;
  color: var(--ink3);
  flex: 1;
}
.tcard-links { display: flex; gap: 10px; }
.tcard-link {
  font-family: var(--mono);
  font-size: 10px;
  color: var(--blue);
  text-decoration: none;
  border-bottom: 1px dotted currentColor;
  min-height: 32px;
  line-height: 32px;
}
.tcard-link:hover { color: var(--ink); }

/* ── DEMANDS ── */
.demands-wrap { padding: 12px 16px 20px; }
.demands-intro {
  font-size: 12px;
  color: var(--ink3);
  line-height: 1.7;
  margin-bottom: 14px;
  font-style: italic;
}
.demands-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
.demand-card {
  background: var(--card);
  border: 1px solid var(--rule);
  border-radius: var(--r8);
  padding: 14px 13px;
}
.demand-num {
  font-family: var(--mono);
  font-size: 10px;
  color: var(--ink3);
  margin-bottom: 6px;
  letter-spacing: 0.06em;
}
.demand-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--ink);
  margin-bottom: 4px;
  line-height: 1.3;
}
.demand-sub {
  font-size: 11px;
  color: var(--ink3);
  line-height: 1.5;
}
.demand-card-4 {
  grid-column: 1 / -1;
  background: var(--indigo-bg);
  border: 1px solid var(--indigo-bd);
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 12px;
  align-items: start;
}
.demand-4-content {}
.demand-4-new {
  font-family: var(--mono);
  font-size: 8.5px;
  padding: 3px 8px;
  background: var(--indigo);
  color: white;
  border-radius: 20px;
  white-space: nowrap;
  margin-top: 2px;
  letter-spacing: 0.04em;
}
.demand-card-4 .demand-num { color: var(--indigo); }
.demand-card-4 .demand-title { color: var(--indigo); }
.demand-card-4 .demand-sub { color: var(--indigo); opacity: 0.75; }

/* ── YUDHISHTHIRA ── */
.ask-wrap { padding: 14px 16px 20px; }
.ask-lbl {
  font-family: var(--mono);
  font-size: 10px;
  letter-spacing: 0.12em;
  color: var(--ink3);
  text-transform: uppercase;
  margin-bottom: 4px;
}
.ask-sub {
  font-size: 12px;
  color: var(--ink3);
  font-style: italic;
  margin-bottom: 14px;
  line-height: 1.5;
}
.quick-row {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  margin-bottom: 12px;
}
.q-btn {
  font-family: var(--deva);
  font-size: 12px;
  padding: 7px 12px;
  background: var(--card);
  border: 1px solid var(--rule);
  border-radius: var(--r8);
  cursor: pointer;
  color: var(--ink2);
  transition: all 0.1s;
  line-height: 1.4;
  min-height: 36px;
}
.q-btn:hover, .q-btn:active { background: var(--ink); color: #f0efe8; border-color: var(--ink); }
.ask-ta {
  width: 100%;
  border: 1px solid var(--rule);
  border-radius: var(--r8);
  padding: 12px 14px;
  font-size: 15px;
  font-family: var(--deva);
  resize: none;
  outline: none;
  background: var(--card);
  color: var(--ink);
  transition: border-color 0.15s;
  line-height: 1.55;
}
.ask-ta:focus { border-color: var(--ink); }
.ask-btn {
  width: 100%;
  background: var(--ink);
  color: #f0efe8;
  border: none;
  border-radius: var(--r8);
  padding: 14px;
  font-size: 14px;
  font-family: var(--deva);
  font-weight: 500;
  cursor: pointer;
  margin-top: 9px;
  letter-spacing: 0.02em;
  transition: opacity 0.15s;
  min-height: 48px;
}
.ask-btn:disabled { opacity: 0.4; cursor: default; }
.loader {
  display: none;
  height: 2px;
  background: var(--rule);
  margin-top: 9px;
  overflow: hidden;
  border-radius: 1px;
}
.loader.on { display: block; }
.loader::after {
  content: '';
  display: block;
  height: 100%;
  width: 35%;
  background: var(--ink);
  animation: shimmer 1.2s ease-in-out infinite;
}
@keyframes shimmer { 0%{transform:translateX(-150%)} 100%{transform:translateX(450%)} }
.ans-box {
  display: none;
  margin-top: 12px;
  background: var(--card);
  border: 1px solid var(--rule);
  border-radius: var(--r8);
  overflow: hidden;
}
.ans-head {
  background: var(--ink);
  color: #5a5a52;
  padding: 7px 14px;
  font-family: var(--mono);
  font-size: 10px;
  letter-spacing: 0.06em;
}
.ans-body {
  padding: 14px;
  font-size: 13.5px;
  line-height: 1.9;
  white-space: pre-wrap;
  color: var(--ink);
}
.ans-box.err .ans-body { background: var(--red-bg); color: var(--red); }

/* ── DRIVE FOOTER ── */
.drive-wrap { padding: 14px 16px 16px; }
.drive-cta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border: 1px solid var(--rule);
  border-radius: var(--r8);
  background: var(--card);
  text-decoration: none;
  color: var(--ink);
  transition: background 0.1s;
  min-height: 60px;
}
.drive-cta:hover { background: #f0ede4; }
.drive-lbl { font-size: 13.5px; font-weight: 500; margin-bottom: 2px; }
.drive-sub { font-family: var(--mono); font-size: 10px; color: var(--ink3); }
.drive-arr { font-size: 22px; color: var(--ink3); }

/* ── PAGE FOOTER ── */
.pg-foot {
  padding: 18px 16px;
  padding-bottom: max(18px, env(safe-area-inset-bottom));
  text-align: center;
  font-family: var(--mono);
  font-size: 10px;
  color: var(--ink3);
  letter-spacing: 0.07em;
  line-height: 1.9;
  border-top: 1px solid var(--rule);
}
</style>
</head>
<body>

<!-- ═══ HEADER ═══ -->
<div class="hd">
  <div class="hd-eyebrow">वहिवाट दावा क्र. 01/2017 · Survey No. 39/19 · Mouje Watar · Vasai, Palghar</div>
  <div class="hd-title">जगदिश्वरम् डिजिटल कार्यालय</div>
  <div class="hd-case">
    <strong>अर्जदार:</strong> आशिष जगदिश नाईक (स्वयं-प्रतिनिधी) · Vasai 401 301
  </div>
  <div class="hd-vs">
    <span class="hd-petitioner">आशिष जगदिश नाईक</span>
    <span class="hd-vs-pill">विरुद्ध</span>
    <span class="hd-respondent">महाराष्ट्र राज्य व इतर</span>
  </div>
  <div class="hd-badge">
    <span class="hd-badge-dot"></span>
    सत्यमेव जयते · तीन न्यायालयीन आदेश — अर्जदाराच्या बाजूने
  </div>
</div>

<div class="page-body">

<!-- ═══ COURT ORDERS ═══ -->
<div class="sec">
  <div class="sec-lbl">न्यायालयीन आदेश</div>
  <div class="orders">

    <div class="order">
      <div class="order-date">०१ मार्च २०२४ · मा. तहसीलदार न्यायालय, वसई तालुका, जिल्हा पालघर</div>
      <div class="order-title">अंतिम आदेश — वहिवाट हक्क कायमस्वरूपी प्रस्थापित</div>
      <div class="order-result">वहिवाट दावा क्र. ०१/२०१७ · अडथळे हटवणे + पोलीस सहाय्य आदेश · अंमलबजावणी अर्ज दि.२३/१२/२०२५</div>
      <div class="order-alert">दि.१८/०३/२०२६ — मा. जिल्हा न्यायालयाने इंजंक्शन अंतिमतः फेटाळले. हा आदेश आता पूर्णतः निर्बंधमुक्त आहे.</div>
      <a class="doc-link" href="{{ d.MOR }}" target="_blank">📁 मा. तहसीलदार कार्यालय — दस्तावेज →</a>
    </div>

    <div class="order">
      <div class="order-date">१८ मार्च २०२६ · मा. जिल्हा न्यायालय, पालघर · MHTH230026632025</div>
      <div class="order-title">इंजंक्शन अंतिमतः नाकारले — तहसील आदेश निर्बंधमुक्त</div>
      <div class="order-result">FIR 270/2024 आधारे सर्व दिवाणी स्थगिती नाकारली · आता कोणताही कायदेशीर अडथळा शिल्लक नाही</div>
      <a class="doc-link" href="{{ d.JUD }}" target="_blank">📁 न्यायपालिका — जिल्हा न्यायालय दस्तावेज →</a>
    </div>

    <div class="order">
      <div class="order-date">१० मार्च २०२६ · मा. ४थे न्यायदंडाधिकारी प्रथम वर्ग, वसई · OMA 254/2026</div>
      <div class="order-title">पारपत्र आदेश + घरपोच पडताळणी निर्देश</div>
      <div class="order-result">CNR: MHTH250017082026 · RPO मुंबई: BOS076289915525 जारी करावे · अर्नाळा पोलीस: पडताळणी करावी</div>
      <a class="doc-link" href="{{ d.JUD }}" target="_blank">📁 न्यायपालिका — OMA 254/2026 →</a>
    </div>

  </div>
</div>

<!-- ═══ RECENT ACTIONS ═══ -->
<div class="sec">
  <div class="sec-lbl">ताजी कृती</div>
  <div class="actions">
    <div class="act-card">
      <div class="act-head">
        अलीकडील सादरणी व निर्णय
        <a href="{{ d.ROOT }}" target="_blank">संपूर्ण संग्रह →</a>
      </div>
      <div class="act-row act-new">
        <div class="act-n">01</div>
        <div>
          <div class="act-subj">मा. जिल्हा न्यायालय — इंजंक्शन अंतिम निकाल<span class="act-new-badge">नवीन</span></div>
          <div class="act-note">FIR 270/2024 आधारे सर्व दिवाणी स्थगिती फेटाळली · तहसील आदेश आता पूर्णतः निर्बंधमुक्त</div>
        </div>
        <div class="act-date">१८ मार्च<br>२०२६</div>
      </div>
      <div class="act-row">
        <div class="act-n">02</div>
        <div>
          <div class="act-subj">RPO मुंबई + मा. ठाणे प्रभारी, अर्नाळा — पत्र</div>
          <div class="act-note">OMA 254/2026 अंमलबजावणी मागणी · पारपत्र BOS076289915525</div>
        </div>
        <div class="act-date">१९ मार्च<br>२०२६</div>
      </div>
      <div class="act-row">
        <div class="act-n">03</div>
        <div>
          <div class="act-subj">मा. ४थे JMFC, वसई — OMA 254/2026 आदेश</div>
          <div class="act-note">FIR असूनही पारपत्रास कोणताही कायदेशीर अडथळा नाही</div>
        </div>
        <div class="act-date">१० मार्च<br>२०२६</div>
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

<!-- ═══ FIR ═══ -->
<div class="sec" style="padding-bottom:4px;">
  <div class="sec-lbl">FIR स्थिती</div>
  <div class="fir-wrap" style="padding-top:10px;">
    <div class="fir-card">
      <div class="fir-title">FIR 270/2024 — दुर्भावनापूर्ण खटला · मा. ठाणे प्रभारी, अर्नाळा सागरी पोलीस ठाणे [EAF]</div>
      <div class="fir-body">
        अर्जदाराची तक्रार: दि.१६/०८/२०२४ · प्रतिवाद्यांचा FIR: दि.२४/०८/२०२४ (८ दिवसांनंतर)<br>
        SCC No. 63/2025 · CR No. 270/2024<br>
        मा. जिल्हा न्यायालय: इंजंक्शन नाकारले · मा. ४थे JMFC: पारपत्रास अडथळा नाही · दि.१८/०३/२०२६: FIR निराधार सिद्ध
      </div>
      <a class="doc-link" href="{{ d.EAF }}" target="_blank">📁 मा. ठाणे प्रभारी, अर्नाळा — FIR 270/2024 दस्तावेज →</a>
    </div>
  </div>
</div>

<!-- ═══ AUTHORITY THREADS ═══ -->
<div class="sec">
  <div class="sec-lbl">अपेक्षित कृती — दुहेरी अपयश नोंद</div>
  <div class="threads-wrap">

    <div class="tgrp-lbl">महसूल प्रशासन</div>

    <div class="tcard">
      <div class="tcard-head">
        <div>
          <div class="tcard-name">मा. तहसीलदार, वसई तालुका, जिल्हा पालघर</div>
          <div class="tcard-code">Thread MOR · तहसील कार्यालय, वसई</div>
        </div>
        <span class="dual-badge">दुहेरी अपयश</span>
      </div>
      <div class="tcard-track">
        <div class="track-lbl">प्रशासन</div>
        <div class="track-action">दि.०१/०३/२०२४ अंतिम आदेश — ३+ वर्षे अंमलबजावणी नाही · MH48AK4539, MH48CC8733 हटवणे बाकी · दि.१८/०३/२०२६ नंतर कोणताही कायदेशीर अडथळा नाही</div>
        <span class="chip chip-r">उल्लंघन</span>
      </div>
      <div class="tcard-track">
        <div class="track-lbl">RTI / PIO</div>
        <div class="track-action">धागा १.३.१ — माहिती अधिकार उत्तर नाकारले · तेच अधिकारी PIO क्षमतेत माहिती देणे टाळत आहेत</div>
        <span class="chip chip-r">उल्लंघन</span>
      </div>
      <div class="tcard-foot">
        <span class="tcard-date">शेवटचा पत्रव्यवहार: डिसेंबर २०२५</span>
        <div class="tcard-links">
          <a class="tcard-link" href="{{ d.MOR_A }}" target="_blank">📁 प्रशासन</a>
          <a class="tcard-link" href="{{ d.MOR_R }}" target="_blank">📁 RTI</a>
        </div>
      </div>
    </div>

    <div class="tcard">
      <div class="tcard-head">
        <div>
          <div class="tcard-name">मा. उपविभागीय अधिकारी, वसई उपविभाग, जिल्हा पालघर</div>
          <div class="tcard-code">Thread NPS · उपविभागीय कार्यालय, वसई</div>
        </div>
        <span class="dual-badge">दुहेरी अपयश</span>
      </div>
      <div class="tcard-track">
        <div class="track-lbl">प्रशासन</div>
        <div class="track-action">RTS Appeal 15/2024 वर निर्णय नाही · वहिवाट फेरतपासणी दावा क्र.५६/२०२२ — बेकायदेशीर हस्तांतरण</div>
        <span class="chip chip-r">उल्लंघन</span>
      </div>
      <div class="tcard-track">
        <div class="track-lbl">RTI / FAA</div>
        <div class="track-action">धागा १.२.१ — प्रथम अपिलीय प्राधिकरण म्हणून माहिती देण्याचे कर्तव्य नाकारले</div>
        <span class="chip chip-r">उल्लंघन</span>
      </div>
      <div class="tcard-foot">
        <span class="tcard-date">शेवटचा पत्रव्यवहार: २०२४</span>
        <div class="tcard-links">
          <a class="tcard-link" href="{{ d.NPS_A }}" target="_blank">📁 प्रशासन</a>
          <a class="tcard-link" href="{{ d.NPS_R }}" target="_blank">📁 RTI</a>
        </div>
      </div>
    </div>

    <div class="tcard">
      <div class="tcard-head">
        <div>
          <div class="tcard-name">मा. जिल्हाधिकारी तथा जिल्हादंडाधिकारी, पालघर</div>
          <div class="tcard-code">Thread DMD · जिल्हाधिकारी कार्यालय, पालघर</div>
        </div>
        <span class="dual-badge">दुहेरी अपयश</span>
      </div>
      <div class="tcard-track">
        <div class="track-lbl">प्रशासन</div>
        <div class="track-action">तहसीलदार व SDO च्या अपयशावर पर्यवेक्षी कारवाई नाही · उच्चस्तरीय लेखी तक्रार — कोणतीही दखल नाही</div>
        <span class="chip chip-a">प्रतीक्षित</span>
      </div>
      <div class="tcard-track">
        <div class="track-lbl">RTI / FAA</div>
        <div class="track-action">धागा १.१ — जिल्हाधिकारी स्तरावर माहिती अधिकार उत्तर प्रतीक्षित</div>
        <span class="chip chip-a">प्रतीक्षित</span>
      </div>
      <div class="tcard-foot">
        <span class="tcard-date">शेवटचा पत्रव्यवहार: २०२५</span>
        <div class="tcard-links">
          <a class="tcard-link" href="{{ d.DMD_A }}" target="_blank">📁 प्रशासन</a>
          <a class="tcard-link" href="{{ d.DMD_R }}" target="_blank">📁 RTI</a>
        </div>
      </div>
    </div>

    <div class="tgrp-lbl">पोलीस प्रशासन</div>

    <div class="tcard">
      <div class="tcard-head">
        <div>
          <div class="tcard-name">मा. पोलीस आयुक्त, MBVV, मीरा-भाईंदर-वसई-विरार</div>
          <div class="tcard-code">Thread AGD · पोलीस आयुक्तालय, MBVV</div>
        </div>
        <span class="dual-badge">दुहेरी अपयश</span>
      </div>
      <div class="tcard-track">
        <div class="track-lbl">प्रशासन</div>
        <div class="track-action">अधीनस्थ पोलीस दलाला तहसील आदेश अंमलबजावणीसाठी निर्देश देणे बाकी · CrPC S.149 कर्तव्य</div>
        <span class="chip chip-a">प्रतीक्षित</span>
      </div>
      <div class="tcard-track">
        <div class="track-lbl">RTI / PIO</div>
        <div class="track-action">धागा २.१ — पोलीस आयुक्तालय स्तरावर माहिती अधिकार उत्तर प्रतीक्षित</div>
        <span class="chip chip-a">प्रतीक्षित</span>
      </div>
      <div class="tcard-foot">
        <span class="tcard-date">शेवटचा पत्रव्यवहार: २०२५</span>
        <div class="tcard-links">
          <a class="tcard-link" href="{{ d.AGD_A }}" target="_blank">📁 प्रशासन</a>
          <a class="tcard-link" href="{{ d.AGD_R }}" target="_blank">📁 RTI</a>
        </div>
      </div>
    </div>

    <div class="tcard">
      <div class="tcard-head">
        <div>
          <div class="tcard-name">मा. ठाणे प्रभारी, अर्नाळा सागरी पोलीस ठाणे</div>
          <div class="tcard-code">Thread EAF · अर्नाळा सागरी पोलीस ठाणे</div>
        </div>
        <span class="dual-badge">दुहेरी अपयश</span>
      </div>
      <div class="tcard-track">
        <div class="track-lbl">प्रशासन</div>
        <div class="track-action">OMA 254/2026 — घरपोच पडताळणी + तहसील आदेश अंमलबजावणी बाकी · FIR 270/2024 दाखल करून व्यवस्थेचा दुरुपयोग केला</div>
        <span class="chip chip-r">उल्लंघन</span>
      </div>
      <div class="tcard-track">
        <div class="track-lbl">RTI / PIO</div>
        <div class="track-action">धागा २.३.१ — FIR व अंमलबजावणी संदर्भात माहिती अधिकार उत्तर नाकारले</div>
        <span class="chip chip-r">उल्लंघन</span>
      </div>
      <div class="tcard-foot">
        <span class="tcard-date">शेवटचा पत्रव्यवहार: १९ मार्च २०२६</span>
        <div class="tcard-links">
          <a class="tcard-link" href="{{ d.EAF_A }}" target="_blank">📁 प्रशासन</a>
          <a class="tcard-link" href="{{ d.EAF_R }}" target="_blank">📁 RTI</a>
        </div>
      </div>
    </div>

    <div class="tcard">
      <div class="tcard-head">
        <div>
          <div class="tcard-name">मा. सहायक पोलीस आयुक्त, नालासोपारा विभाग</div>
          <div class="tcard-code">Thread RPD · ACP कार्यालय, नालासोपारा</div>
        </div>
        <span class="ok-badge">निर्णय प्राप्त</span>
      </div>
      <div class="tcard-track">
        <div class="track-lbl">प्रशासन</div>
        <div class="track-action">FAA क्षमतेत RTI Appeal 02/2026 — दि.२१/०१/२०२६ आदेश: ७ दिवसांत माहिती द्यावी</div>
        <span class="chip chip-t">आदेश दिला</span>
      </div>
      <div class="tcard-track">
        <div class="track-lbl">RTI / FAA</div>
        <div class="track-action">धागा २.२.१ — Appeal 02/2026 निकाल अनुकूल · आदेशाचे पालन तपासणी सुरू</div>
        <span class="chip chip-t">पालन तपासणी</span>
      </div>
      <div class="tcard-foot">
        <span class="tcard-date">शेवटचा पत्रव्यवहार: २१ जानेवारी २०२६</span>
        <div class="tcard-links">
          <a class="tcard-link" href="{{ d.RPD_A }}" target="_blank">📁 प्रशासन</a>
          <a class="tcard-link" href="{{ d.RPD_R }}" target="_blank">📁 RTI</a>
        </div>
      </div>
    </div>

    <div class="tgrp-lbl">महानगरपालिका</div>

    <div class="tcard">
      <div class="tcard-head">
        <div>
          <div class="tcard-name">मा. सहायक आयुक्त, VVMC प्रभाग समिती अ, वसई-विरार</div>
          <div class="tcard-code">Thread BTR · VVMC प्रभाग समिती अ कार्यालय</div>
        </div>
        <span class="dual-badge">दुहेरी अपयश</span>
      </div>
      <div class="tcard-track">
        <div class="track-lbl">प्रशासन</div>
        <div class="track-action">₹४,०४,229 कर मागणी — शून्य सेवा वितरण (VT02/338) · Spot Inspection Report प्रतीक्षित</div>
        <span class="chip chip-r">उल्लंघन</span>
      </div>
      <div class="tcard-track">
        <div class="track-lbl">RTI / PIO</div>
        <div class="track-action">धागा १.४.१ — VVMC सेवा वितरण संदर्भात माहिती अधिकार उत्तर नाकारले</div>
        <span class="chip chip-r">उल्लंघन</span>
      </div>
      <div class="tcard-foot">
        <span class="tcard-date">शेवटचा पत्रव्यवहार: २०२५</span>
        <div class="tcard-links">
          <a class="tcard-link" href="{{ d.BTR_A }}" target="_blank">📁 प्रशासन</a>
          <a class="tcard-link" href="{{ d.BTR_R }}" target="_blank">📁 RTI</a>
        </div>
      </div>
    </div>

  </div>
</div>

<!-- ═══ DEMANDS ═══ -->
<div class="sec">
  <div class="sec-lbl">अर्जदाराच्या मागण्या</div>
  <div class="demands-wrap">
    <div class="demands-intro">
      या प्रकरणात न्यायासाठी केवळ कायदेशीर दिलासा पुरेसा नाही —
      ज्या व्यवस्थेने अपयश दाखवले, त्या व्यवस्थेला जबाबदार धरणे हे या लढ्याचे अंतिम उद्दिष्ट आहे.
    </div>
    <div class="demands-grid">
      <div class="demand-card">
        <div class="demand-num">०१</div>
        <div class="demand-title">वहिवाट अंमलबजावणी</div>
        <div class="demand-sub">MCA 1906 S.5 · ३+ वर्षांच्या उल्लंघनाची तत्काळ दुरुस्ती</div>
      </div>
      <div class="demand-card">
        <div class="demand-num">०२</div>
        <div class="demand-title">FIR रद्दीकरण</div>
        <div class="demand-sub">FIR 270/2024 रद्द · दुर्भावना सिद्ध झाली आहे</div>
      </div>
      <div class="demand-card">
        <div class="demand-num">०३</div>
        <div class="demand-title">नुकसानभरपाई</div>
        <div class="demand-sub">११ वर्षे × ₹८-१०L/वर्ष · Article 21 उल्लंघन · नोकरी सोडणे</div>
      </div>
      <div class="demand-card demand-card-4">
        <div class="demand-4-content">
          <div class="demand-num">०४</div>
          <div class="demand-title">तंत्रज्ञान अंगीकार</div>
          <div class="demand-sub">शासन व न्यायव्यवस्थेत AI व डिजिटल साधनांचा अनिवार्य वापर — पारदर्शकता, उत्तरदायित्व आणि कार्यक्षमता निर्माण करण्यासाठी</div>
        </div>
        <div class="demand-4-new">अपरक्राम्य मागणी</div>
      </div>
    </div>
  </div>
</div>

<!-- ═══ YUDHISHTHIRA ═══ -->
<div class="sec">
  <div class="ask-wrap">
    <div class="ask-lbl">युधिष्ठिराला विचारा ⚖️</div>
    <div class="ask-sub">धर्मराज उत्तर देतो — फक्त सत्य, फक्त कायदा · Ctrl+Enter / ⌘+Enter</div>
    <div class="quick-row">
      <button class="q-btn" onclick="setQ('दि.१८/०३/२०२६ च्या जिल्हा न्यायालयाच्या निर्णयाचा अर्थ काय आणि आता तहसीलदारांनी काय करणे बंधनकारक आहे?')">१८ मार्च आदेश</button>
      <button class="q-btn" onclick="setQ('तहसीलदार प्रशासन आणि RTI दोन्ही क्षमतांमध्ये अपयशी ठरले — याचे कायदेशीर परिणाम काय?')">दुहेरी अपयश</button>
      <button class="q-btn" onclick="setQ('OMA 254/2026 आदेशानुसार RPO व अर्नाळा पोलिसांनी काय करणे बंधनकारक आहे?')">OMA 254/2026</button>
      <button class="q-btn" onclick="setQ('FIR 270/2024 च्या दुर्भावनाबाबत न्यायालयांनी काय सांगितले?')">FIR स्थिती</button>
      <button class="q-btn" onclick="setQ('उच्च न्यायालयात Article 226 याचिका दाखल करण्यासाठी कोणती कारणे आहेत?')">उच्च न्यायालय</button>
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

<!-- ═══ DRIVE ═══ -->
<div class="drive-wrap">
  <a class="drive-cta" href="{{ d.ROOT }}" target="_blank">
    <div>
      <div class="drive-lbl">📁 संपूर्ण केस लायब्ररी — Google Drive</div>
      <div class="drive-sub">४११+ दस्तावेज · वहिवाट दावा जगदिश्वरम् · जून २०१५ — मार्च २०२६</div>
    </div>
    <div class="drive-arr">↗</div>
  </a>
</div>

</div>

<!-- ═══ FOOTER ═══ -->
<div class="pg-foot">
  JAGDISHWARAM DIGITAL OFFICE · ASHISH JAGDISH NAIK<br>
  VASAI · PALGHAR · MAHARASHTRA · 401 301<br>
  SATYAMEVA JAYATE · 2026
  www.jagdishwaram-office.org · Email ashish.j.naik@gmail.com
</div>

<script>
function setQ(t) {
  document.getElementById('qta').value = t;
  document.getElementById('qta').focus();
}
async function ask() {
  const q = document.getElementById('qta').value.trim();
  if (!q) return;
  const btn = document.getElementById('askBtn');
  const ldr = document.getElementById('loader');
  const box = document.getElementById('ansBox');
  const body = document.getElementById('ansBody');
  const head = document.getElementById('ansHead');
  btn.disabled = true;
  btn.textContent = 'विचारत आहे...';
  ldr.classList.add('on');
  box.style.display = 'none';
  box.className = 'ans-box';
  try {
    const res = await fetch('/ask', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({question: q})
    });
    const data = await res.json();
    if (data.error) {
      body.textContent = data.error;
      box.classList.add('err');
      head.textContent = 'त्रुटी';
    } else {
      body.textContent = data.answer || 'उत्तर मिळाले नाही';
      const ts = new Date().toLocaleTimeString('mr-IN', {hour: '2-digit', minute: '2-digit'});
      head.textContent = 'युधिष्ठिर उत्तर · ' + ts;
    }
  } catch(e) {
    body.textContent = 'नेटवर्क त्रुटी. पुन्हा प्रयत्न करा.';
    box.classList.add('err');
    head.textContent = 'त्रुटी';
  }
  box.style.display = 'block';
  btn.disabled = false;
  btn.textContent = 'युधिष्ठिराला विचारा →';
  ldr.classList.remove('on');
}
document.addEventListener('DOMContentLoaded', function() {
  document.getElementById('qta').addEventListener('keydown', function(e) {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') ask();
  });
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
    return jsonify({
        'status': 'ok',
        'office': 'Jagdishwaram Digital Office',
        'case': 'Ashish Jagdish Naik VS State of Maharashtra & Others',
        'satyamev': 'jayate',
        'api_key_status': ks,
        'timestamp': datetime.now().isoformat()
    })

@app.route('/debug')
def debug():
    if not ANTHROPIC_API_KEY:
        return jsonify({'status': 'error', 'message': 'ANTHROPIC_API_KEY not set'}), 500
    return jsonify({
        'api_key_masked': ANTHROPIC_API_KEY[:12] + '...' + ANTHROPIC_API_KEY[-4:],
        'format_valid': ANTHROPIC_API_KEY.startswith("sk-ant-"),
        'key_length': len(ANTHROPIC_API_KEY),
        'status': 'ready'
    })

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
        return jsonify({
            'answer': msg.content[0].text,
            'question': question,
            'timestamp': datetime.now().isoformat(),
            'agent': 'Yudhishthira — युधिष्ठिर'
        })
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
        return jsonify({
            'status': 'received',
            'timestamp': datetime.now().strftime('%d %B %Y | %I:%M %p IST'),
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
        return jsonify({
            'status': 'captured',
            'type': capture_type,
            'timestamp': datetime.now().isoformat(),
            'message': f'Hanuman ने {capture_type} सुरक्षित केले'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
