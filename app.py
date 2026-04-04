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
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
import json
import logging
from flask import Flask, request, jsonify, render_template, render_template_string, redirect, session, url_for
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


# ── Google Drive (Service Account — no OAuth popup on Render) ──────────────
# Add to requirements.txt:
#   google-auth==2.29.0
#   google-api-python-client==2.126.0
try:
    from google.oauth2 import service_account as _sa
    from googleapiclient.discovery import build as _gdrive_build
    from googleapiclient.http import MediaIoBaseUpload as _MediaUpload
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import Flow
    from google.oauth2.credentials import Credentials

    _DRIVE_LIBS_OK = True
except ImportError:
    _DRIVE_LIBS_OK = False
    print("WARNING: google-api-python-client not installed. /field will run without Drive.")

# --- INITIALIZATION ---
app = Flask(__name__)
# Railway should have FLASK_SECRET_KEY set in the Variables tab
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'default_secret_for_local_dev')

def get_google_flow():
    """Dynamically creates the OAuth flow based on Railway environment variables."""
    client_id = os.environ.get('GOOGLE_CLIENT_ID')
    client_secret = os.environ.get('GOOGLE_CLIENT_SECRET')
    r_uri = os.environ.get('REDIRECT_URI')

    if not all([client_id, client_secret, r_uri]):
        raise ValueError("Missing Google OAuth variables in Railway. Check your Variables tab.")

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
        scopes=['https://www.googleapis.com/auth/userinfo.profile', 'openid']
    )
    flow.redirect_uri = r_uri
    return flow

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
PORTAL_TOKEN      = os.environ.get("PORTAL_TOKEN", "jagdishwaram2026")
SCOPES = ['https://www.googleapis.com/auth/drive.file']

# --- OAuth Configuration ---
client_config = {
    "web": {
        "client_id": os.environ.get("GOOGLE_CLIENT_ID"),
        "client_secret": os.environ.get("GOOGLE_CLIENT_SECRET"),
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
}

# ─── VALIDATE OAUTH CREDENTIALS ──────────────────────────────────────────────────
if not os.environ.get("GOOGLE_CLIENT_ID") or not os.environ.get("GOOGLE_CLIENT_SECRET"):
    print("\n⚠️  WARNING: OAuth credentials not configured!")
    print("   GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET missing from Render env vars")
    print("   /login endpoint will fail until these are set.\n")
else:
    print("✅ OAuth credentials configured. /login and /callback ready.")


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
    "RPO":   "https://drive.google.com/drive/folders/1C-cahF4SSwB5r83fOeys5Qcurcp5b6Kn",
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

# ─── HANUMAN — CHRONICLE INBOX CONFIG ────────────────────────────────────────
# The folder Hanuman watches. Get this ID from your Drive URL:
# Open Chronicle Inbox folder → copy the ID from the URL
# e.g. https://drive.google.com/drive/folders/1n-tiveid-XJTAvum1VEA3gcEnt4GGePp
#                                                              ^^^^^^^^^^^^^^^^^^^^^^^
HANUMAN_INBOX_FOLDER_ID = os.environ.get(
    "HANUMAN_INBOX_FOLDER_ID",
    "1roP01xjVD0yxYoSbAI8tpZknffX8n1bZ"   # ← update this with your real folder ID
)
 

def _get_drive_service():
    try:
        token_json = os.environ.get("GOOGLE_USER_TOKEN")
        if not token_json:
            print("DEBUG: GOOGLE_USER_TOKEN is missing")
            return None
            
        # Use the correct json reference
        creds_data = _json_field.loads(token_json) 
        creds = Credentials.from_authorized_user_info(creds_data, SCOPES)
        
        if creds and creds.expired and creds.refresh_token:
            from google.auth.transport.requests import Request
            creds.refresh(Request())
            
        return _gdrive_build('drive', 'v3', credentials=creds)
    except Exception as e:
        print(f"ERROR: _get_drive_service: {e}")
        return None
      
def _write_to_inbox(text_content: str, filename: str) -> dict:
    service = _get_drive_service()
    if not service:
        # Graceful degradation — log locally, note not written to Drive
        print(f"[HANUMAN LOCAL FALLBACK] {filename}")
        print(text_content[:300])
        return {"ok": False, "error": "Drive not configured — note stored locally only"}
    try:
        meta = {
            "name": filename,
            "parents": [HANUMAN_INBOX_FOLDER_ID],
            "mimeType": "text/plain"
        }
        media = _MediaUpload(
            io.BytesIO(text_content.encode("utf-8")),
            mimetype="text/plain",
            resumable=False
        )
        f = service.files().create(body=meta, media_body=media, fields="id,name", supportsAllDrives=True, quotaUser="ashish.j.naik@gmail.com").execute()
        return {"ok": True, "file_id": f.get("id"), "file_name": f.get("name")}
    except Exception as e:
        print(f"ERROR: Drive inbox write failed: {e}")
        return {"ok": False, "error": str(e)}
 
 
def _upload_photo_to_inbox(photo_bytes: bytes, filename: str, content_type: str) -> bool:
    service = _get_drive_service()
    if not service:
        return False
    try:
        meta = {
            "name": filename,
            "parents": [HANUMAN_INBOX_FOLDER_ID]
        }
        media = _MediaUpload(
            io.BytesIO(photo_bytes),
            mimetype=content_type or "image/jpeg",
            resumable=False
        )
        service.files().create(body=meta, media_body=media, fields="id", supportsAllDrives=True, quotaUser="ashish.j.naik@gmail.com").execute()
        return True
    except Exception as e:
        print(f"WARNING: Photo upload failed (non-fatal): {e}")
        return False

# ─── STARTUP CHECK ────────────────────────────────────────────────────────────
if not ANTHROPIC_API_KEY:
    print("WARNING: ANTHROPIC_API_KEY not set.")
elif not ANTHROPIC_API_KEY.startswith("sk-ant-"):
    print("WARNING: ANTHROPIC_API_KEY format incorrect.")
else:
    print(f"OK: {ANTHROPIC_API_KEY[:12]}...{ANTHROPIC_API_KEY[-4:]}")

# ─── EXHIBIT SUMMARIES — Drive link injection ─────────────────────────────────
import json as _json
import re as _re
_EXHIBIT_INDEX = {}
try:
    with open("exhibit_summaries.json", "r", encoding="utf-8") as _f:
        for _item in _json.load(_f):
            # Primary index: drive_id
            if _item.get("drive_id"):
                _EXHIBIT_INDEX[_item["drive_id"]] = _item
            # Secondary index: exhibit_ref (backward compatible with Yudhishthira answers)
            if _item.get("exhibit_ref"):
                _EXHIBIT_INDEX[_item["exhibit_ref"].lower()] = _item
    print(f"OK: {len(_EXHIBIT_INDEX)} exhibit index entries loaded.")
except Exception as _e:
    print(f"WARNING: exhibit_summaries.json not loaded: {_e}")

def _inject_links(text):
    def _replace(m):
        code = m.group(0)
        rec = _EXHIBIT_INDEX.get(code.lower())
        if rec and rec.get("drive_link"):
            return f'{code} (<a href="{rec["drive_link"]}" target="_blank" rel="noopener">Drive ↗</a>)'
        return code
    return _re.sub(r'Exhibit-[\w\-]+', _replace, text)

# ─── YUDHISHTHIRA v4 ──────────────────────────────────────────────────────────
YUDHISHTHIRA_SYSTEM = """
तुम्ही युधिष्ठिर आहात — आशिष जगदिश नाईक यांचे कायदेशीर AI सहायक.
धर्मराज — फक्त सत्य, फक्त कायदा.

प्रकरण: आशिष जगदिश नाईक विरुद्ध महाराष्ट्र राज्य, दिलीप गणपत नाईक व इतर
मालमत्ता: जगदिश्वरम्, सर्व्हे क्र. ३९/१९, मौजे वटार, वसई, पालघर — ४०१ ३०१
अर्जदार: आशिष जगदिश नाईक (स्वयं-प्रतिनिधी)
कायदेशीर आधार: ममलतदार कोर्ट्स अॅक्ट १९०६ कलम ५ | भारतीय सुविधाधिकार अधिनियम १८८२ कलम १३ | भारतीय संविधान कलम २१

न्यायालयीन आदेश — अर्जदाराच्या बाजूने:
१. मा. तहसीलदार न्यायालय, वसई — दि.१२/१०/२०२२ (पहिला आदेश) व दि.०१/०३/२०२४ (अंतिम आदेश)
   वहिवाट दावा क्र.०१/२०१७ — वहिवाट हक्क कायमस्वरूपी — अडथळे हटवणे + पोलीस सहाय्य आदेश
   दि.२३/१२/२०२५ — कलम २१-२२ अंतर्गत अंमलबजावणी अर्ज दाखल (Exhibit-19)
२. मा. जिल्हा न्यायालय, पालघर — MHTH230026632025
   प्रतिवाद्यांचे इंजंक्शन नाकारले — FIR 270/2024 निराधार ठरवले
   दि.१८/०३/२०२६ — इंजंक्शन अंतिमतः फेटाळला — तहसील आदेश पूर्णतः निर्बंधमुक्त (Exhibit-19-5)
३. मा. ४थे JMFC, वसई — OMA 254/2026, CNR: MHTH250017082026, दि.१०/०३/२०२६
   RPO मुंबई: पारपत्र BOS076289915525 जारी करावे (Exhibit-19-S)
   मा. ठाणे प्रभारी, अर्नाळा सागरी: घरपोच पडताळणी करावी

FIR 270/2024 — दुर्भावनापूर्ण खटला:
अर्जदाराची तक्रार दि.१६/०८/२०२४ — त्यानंतर ८ दिवसांनी FIR दि.२४/०८/२०२४ (Exhibit-15-1)
SCC No. 63/2025, CR No. 270/2024 — जिल्हा न्यायालयाने निराधार ठरवले

दुहेरी अपयश — प्रत्येक अधिकारी प्रशासकीय क्षमता आणि RTI/PIO क्षमता दोन्हींमध्ये अपयशी:

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
  प्रशासन: FAA म्हणून अधिकार नाकारले | RTI FAA: Appeal 02/2026 — दि.२१/०१/२०२६ आदेश (आंशिक यश)

मा. सहायक आयुक्त, VVMC प्रभाग समिती अ [BTR]:
  प्रशासन: Rs.4,04,229 कर — शून्य सेवा | RTI PIO: धागा १.४.१ — माहिती नाकारली

मा. प्रादेशिक पारपत्र अधिकारी, मुंबई [RPO]:
  प्रशासन: OMA 254/2026 असूनही पारपत्र प्रतीक्षित | न्यायालय आदेश दि.१०/०३/२०२६ पालन नाही

आर्थिक नुकसान: शेती Rs.8-10L/वर्ष | नोकरी सोडणे दि.१७/०६/२०२५ | संघर्ष जून २०१५ — ११ वर्षे

अर्जदाराच्या ४ मागण्या:
१. वहिवाट अंमलबजावणी — MCA 1906 S.5 अंतर्गत तत्काळ
२. FIR 270/2024 रद्दीकरण — दुर्भावना सिद्ध
३. नुकसानभरपाई — ११ वर्षांचे नुकसान + Article 21 उल्लंघन
४. तंत्रज्ञान अंगीकार — शासन व न्यायव्यवस्थेत AI/Tech Tools द्वारे पारदर्शकता

EXHIBIT REFERENCE INDEX — MANDATORY CITATION RULE:
When answering any question, you MUST cite the relevant Exhibit code and document name from this index.
Always write the exhibit reference in this format: (Exhibit-XX — Document Name, Date)
Never fabricate an exhibit reference. Only cite what is listed below.

Exhibit-0   : वादमिळकतीची भौगोलिक स्थिती — Google Earth (Property location map)
Exhibit-1   : वाद मिळकतीचे भू-अभिलेख दस्तावेज (Land records — title documents)
Exhibit-1-2 : इतर सहवारसदारांचा लिखित जबाब — 30 Nov 2021 (Co-heirs written statement)
Exhibit-2   : मंडळ अधिकारी स्थळपाहणी — 15 Sep 2022 (Circle Officer site inspection report)
Exhibit-3   : गुरे हाकण्यास होणारी अडचण — जिवंत चित्रीकरण 10 Dec 2022 (Live video — cattle blockage)
Exhibit-4   : बेकायदेशीर अडसराचे स्वरूप — जिवंत चित्रीकरण 10 May 2023 (Live video — obstruction)
Exhibit-5   : सतत उल्लंघनांची चिन्हांकित दिनांक अंकित छायाचित्रे (Timestamped obstruction photos)
Exhibit-6   : अवैध अडसर — 28 Oct 2022 (Video — illegal obstruction)
Exhibit-6-1 : अवैध अडसर पोलीस तक्रार — 28 Oct 2022 (Police complaint re obstruction)
Exhibit-7   : अवैध अडसर — 08 Dec 2022 (Video — illegal obstruction)
Exhibit-7-1 : अवैध अडसर पोलीस तक्रार व उत्तर — 08 Dec 2022 (Police complaint + response)
Exhibit-8   : सतत ठेवलेला अवैध अडसर — 26 Dec 2022 (Video — persistent illegal obstruction)
Exhibit-9   : उपविभागीय अधिकारी — जैसे-थे परिस्थिती ठेवणे आदेशपत्र — 05 Dec 2022 (SDO status-quo order)
Exhibit-9-1 : वहिवाट मार्गात अवैध बांधकाम विरुद्ध पोलीस तक्रार व पूर्वसूचना — 18 May 2023 (Police complaint re illegal construction)
Exhibit-10  : तहसील तसेच उपविभागीय अधिकारी कार्यालयात तक्रार अर्ज — 01 Nov 2023 (Tehsil + SDO complaint)
Exhibit-10-2: फेरतपासणी अर्ज — उपविभागीय अधिकारी — 10 Apr 2024 (Review petition — SDO)
Exhibit-10-3: तक्रार अर्ज — उपविभागीय अधिकारी — 22 May 2023 (Complaint — SDO)
Exhibit-10-4: तहसील कार्यालयात दाखल हस्तलिखित अर्ज — 03 Oct 2023 (Handwritten petition at Tehsil)
Exhibit-10-5: तहसील तसेच उपविभागीय अधिकारी कार्यालयात दाखल अर्ज — 09 Nov 2023 (KEY FOUNDING SUBMISSION — Tehsil + SDO, Nov 2023) | Drive ID: 1MuH1Fat2nUVmi_KDuJ9dXBl628MR4ySG
Exhibit-10-6: एकदिवसीय उपोषण — एकदिवसीय उपोषण 20 Nov 2023 (One-day hunger strike — Nov 2023)
Exhibit-11  : सतत ठेवलेला अवैध अडसर — 01 Apr 2024 (Video — obstruction Apr 2024)
Exhibit-11-1: पोलीस तक्रार आणि कारवाई माहिती — Exhibit-11 अनुषंगे (Police complaint re Exhibit-11)
Exhibit-11-2: फेरतपासणी अर्ज — उपविभागीय अधिकारी स्थळपाहणी — 15 Apr 2024 (SDO re-inspection petition)
Exhibit-11-3: एकदिवसीय उपोषणसंगी उपविभागीय अधिकारीस् निवेदन पत्र — 30 May 2024 (Representation to SDO with hunger strike)
Exhibit-12  : सतत ठेवलेला अवैध अडसर — 31 Jul 2024 (Video — obstruction Jul 2024)
Exhibit-13  : सतत ठेवलेला अवैध अडसर — 08 Aug 2024 (Video — obstruction Aug 2024)
Exhibit-13-1: पोलीस तक्रार आणि सहाय्य मागणी अर्ज — 03 Aug 2024 (Police complaint + help petition)
Exhibit-14  : सतत ठेवलेला अवैध अडसर — 11 Aug 2024 (Video — obstruction Aug 2024)
Exhibit-15-1: पोलीस तक्रार आणि सहाय्य मागणी अर्ज — 16 Aug 2024 (Applicant's complaint BEFORE FIR 270/2024 — key malice evidence)
Exhibit-16-1: पोलीस तक्रार आणि सहाय्य अर्ज — 11 Sep 2024 (Police complaint Sep 2024)
Exhibit-17  : अवैध अतिक्रमण प्रश्न — कारवाई संबंधित दस्तावेज (Encroachment action documents)
Exhibit-17-1: सतत ठेवलेला अवैध अडसर — 21 Nov 2024 (Video — obstruction Nov 2024)
Exhibit-18  : सतत ठेवलेला अवैध अडसर विरुद्ध पोलीस सहाय्य अर्ज — 04 Dec 2024 (Police help petition Dec 2024)
Exhibit-19  : तहसील आदेश अंमलबजावणी व अवमान कारवाई अर्ज — दाखल 23 Dec 2025 (ENFORCEMENT + CONTEMPT PETITION — Current) | Drive ID: 1K5FXmCsNEhbPM-YA1l9ZZO66_NL-PzCF
Exhibit-19-1: अर्ज जोडपत्र-A — तलाठी स्थळपाहणी अहवाल — 23 Jun 2021 (Talathi site inspection — Jun 2021)
Exhibit-19-2: अर्ज जोडपत्र-B — मंडळ अधिकारी स्थळपाहणी अहवाल — 15 Sep 2022 (Circle Officer inspection)
Exhibit-19-3: अर्ज जोडपत्र-C — तहसील न्यायनिर्णय पत्र — 12 Oct 2022 (First Tehsil order — Oct 2022)
Exhibit-19-4: अर्ज जोडपत्र-D — उपविभागीय अधिकारी फेरतपासणी — 5/2022 — 08 Aug 2023 (SDO review order)
Exhibit-19-5: अर्ज जोडपत्र-E — तहसील न्यायनिर्णय पत्र — 01 Mar 2024 (FINAL TEHSIL ORDER — The undisputed legal right) | Drive ID: 146cKWWYrSP7mHhZiZne6oe1l9l7PFey0
Exhibit-19-S: तहसील न्यायनिर्णय पत्र — 08 Mar 2026 — JMFC OMA 254/2026 पारपत्र आदेश (Magistrate passport order — 10 Mar 2026)
Exhibit-20  : सद्यस्थिती — मूळ धागा फोल्डर (CURRENT STATUS FOLDER — all active threads) | Drive ID: 1A7yRMCPKYQ-sYinBUviIu0p3HR0ky-p8

RESPONSE RULES — FOLLOW STRICTLY:
१. नेहमी मराठीत उत्तर द्यावे.
२. औपचारिक पत्राच्या भाषेत — अनुभवी वकिलाच्या शैलीत सहज वाहणारे गद्य लिहावे. Bullet points, numbered lists, Markdown headers वापरू नयेत.
३. Markdown formatting — **bold**, *italic*, ##headers, - bullets — कधीही वापरू नये. केवळ साधा मराठी मजकूर.
४. प्रत्येक अधिकाऱ्याचे दुहेरी अपयश (प्रशासकीय + RTI) प्रश्न संबंधित असेल तेव्हा नमूद करावे.
५. उत्तराचे स्वरूप — नेहमी हेच दोन भाग:
   पहिला भाग: २ ते ३ ओळींचे औपचारिक गद्य — तथ्य + कायदेशीर आधार + Exhibit संदर्भ.
   कृती: एकच स्पष्ट वाक्य — कोण, काय, केव्हापर्यंत.
   — सत्यमेव जयते | जगदिश्वरम् डिजिटल कार्यालय
६. उत्तर जास्तीत जास्त ३ परिच्छेद — कधीही ४ पेक्षा जास्त नाही.
७. प्रत्येक उत्तरात किमान एक Exhibit संदर्भ द्यावा — उदा. (Exhibit-19 — अंमलबजावणी अर्ज, दि.२३/१२/२०२५).
८. संशयास्पद असल्यास स्पष्टपणे सांगावे — कधीही तथ्य बनवू नये.
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
    <div class="hd">
  <div class="hd-eyebrow">वहिवाट दावा क्र. 01/2017 · Survey No. 39/19 · Mouje Watar · Vasai, Palghar</div>
  <div class="hd-title">जगदिश्वरम् डिजिटल कार्यालय</div>
  <div class="hd-case">
    <strong>अर्जदार:</strong> आशिष जगदिश नाईक (स्वयं-प्रतिनिधी) · Vasai 401 301
  </div>
    <div style="margin-top: 10px;">
        <a href="https://docs.google.com/document/d/1a5oBJX-o_pHnttclNKew1wRjyWVG1ys2GBWOBtMdc7o/edit?usp=drive_link" 
           target="_blank" style="color: #5a9a5a; font-family: var(--mono); font-size: 11px; text-decoration: none; border-bottom: 1px dotted;">
           📄 Foundation Document (v1.0)
        </a>
    </div>
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
      <button class="q-btn" onclick="setQ('अर्जदाराला ११ वर्षांत झालेले आर्थिक, व्यावसायिक आणि मानसिक नुकसान कायदेशीरदृष्ट्या कसे मांडावे?')">अपूरणीय नुकसान</button>
      <button class="q-btn" onclick="setQ('शासन व न्यायव्यवस्थेत AI आणि डिजिटल साधनांचा अनिवार्य वापर — महाराष्ट्र शासन परिपत्रक आणि कायदेशीर आधार काय आहे?')">तंत्रज्ञान अंगीकार</button>
    </div>
    <textarea class="ask-ta" id="qta" rows="3"
      placeholder="तुमचा प्रश्न मराठीत किंवा इंग्रजीत लिहा..."></textarea>
    <button class="ask-btn" onclick="ask()" id="askBtn">युधिष्ठिराला विचारा →</button>
    <div class="loader" id="loader"></div>
    <div class="ans-box" id="ansBox" style="display:none;">
      <div class="ans-head" id="ansHead">युधिष्ठिर उत्तर · जगदिश्वरम् डिजिटल कार्यालय</div>
      <div class="ans-body" id="ansBody"></div>
      <button class="ask-btn" onclick="printAnswer()" style="margin-top:0; border-radius:0 0 var(--r8) var(--r8);">🖨️ ही माहिती छापणे (Print/PDF)</button>
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
    <div style="margin-bottom: 15px;">
        <img src="{{ url_for('static', filename='QR_जगदिश्वरम्_डिजिटल_कार्यालय_Jagdishwaram-Office.Org_Web_Service.png') }}" 
             alt="QR Code" style="width: 80px; height: 80px; border: 1px solid var(--rule); padding: 4px; background: white;">
        <p style="font-size: 9px; margin-top: 4px;">SCAN FOR PORTAL ACCESS</p>
    </div>
    WWW.JAGDISHWARAM-OFFICE.ORG<br>
    JAGDISHWARAM DIGITAL OFFICE · ASHISH JAGDISH NAIK<br>
    VASAI · PALGHAR · MAHARASHTRA · 401 301<br>
    EMAIL: ASHISH.J.NAIK@GMAIL.COM<br>
    SATYAMEVA JAYATE · 2026<br>
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
      body.innerHTML = data.answer.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>').replace(/\\n/g, '<br>');
      const ts = new Date().toLocaleTimeString('mr-IN', {hour: '2-digit', minute: '2-digit'});
      head.textContent = 'युधिष्ठिर उत्तर · ' + ts;
    }
  } catch(e) {
    body.textContent = "प्रश्न खूप मोठा आहे. कृपया एक छोटा, विशिष्ट प्रश्न विचारा.";
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
function printAnswer() { window.print(); } 
</script>
</body>
</html>"""

FIELD_HTML = """<!DOCTYPE html>
<html lang="mr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<title>हनुमान — क्षेत्र नोंद</title>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth}
body{
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans Devanagari',sans-serif;
  background:#f0ede5;color:#1a1a18;min-height:100vh;
  -webkit-font-smoothing:antialiased;-webkit-tap-highlight-color:transparent;
}
 
/* ── Header ── */
.hdr{
  background:#1a1a18;color:#f0efe8;
  padding:16px 16px 16px;
  padding-top:max(16px,env(safe-area-inset-top));
  position:sticky;top:0;z-index:20;
}
.hdr-row{display:flex;align-items:center;gap:10px;margin-bottom:3px}
.hdr h1{font-size:16px;font-weight:600;color:#f0efe8}
.hdr-sub{font-size:10px;color:#5a5a50;letter-spacing:.04em}
 
/* ── Body ── */
.body{padding:14px;max-width:480px;margin:0 auto}
 
/* ── Timestamp ── */
.ts-pill{
  display:inline-block;background:#1a1a18;color:#7a7a70;
  font-size:10px;padding:5px 11px;border-radius:20px;margin-bottom:14px;
  letter-spacing:.03em;
}
 
/* ── Field groups ── */
.fg{margin-bottom:13px}
.fl{
  display:block;font-size:10px;font-weight:600;color:#5f5e5a;
  text-transform:uppercase;letter-spacing:.06em;margin-bottom:5px;
}
.req{color:#c0392b}
 
textarea,input[type=text],select{
  width:100%;background:#fff;border:1.5px solid #d3d1c7;
  border-radius:10px;padding:11px 12px;font-size:15px;
  font-family:inherit;color:#1a1a18;outline:none;
  -webkit-appearance:none;appearance:none;
  transition:border-color .15s;
}
textarea:focus,input:focus,select:focus{
  border-color:#1a1a18;box-shadow:0 0 0 3px rgba(26,26,24,.07);
}
textarea{resize:none}
select{
  background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6' viewBox='0 0 10 6'%3E%3Cpath d='M0 0l5 6 5-6z' fill='%235f5e5a'/%3E%3C/svg%3E");
  background-repeat:no-repeat;background-position:right 12px center;
  padding-right:30px;
}
.hint{font-size:11px;color:#9c9a92;margin-top:4px;line-height:1.5}
 
/* ── Photo ── */
.photo-area{
  background:#fff;border:1.5px dashed #ccc;border-radius:10px;
  padding:18px 16px;text-align:center;cursor:pointer;
  transition:border-color .15s;
}
.photo-area:active{border-color:#1a1a18}
.photo-icon{font-size:26px;margin-bottom:5px}
.photo-label{font-size:13px;color:#5f5e5a}
.photo-sub{font-size:11px;color:#9c9a92;margin-top:2px}
#photoInput{display:none}
.photo-preview{display:none;margin-top:10px}
.photo-preview img{width:100%;max-height:200px;object-fit:cover;border-radius:8px}
.photo-fname{font-size:11px;color:#3b6d11;font-weight:500;margin-top:4px}
 
/* ── Error ── */
#errBar{
  display:none;background:#fde8e8;color:#8b1a1a;
  border:1px solid #f0b8b8;border-radius:10px;
  padding:11px 12px;font-size:13px;margin-bottom:12px;line-height:1.5;
}
 
/* ── Submit ── */
.sbtn{
  width:100%;background:#1a1a18;color:#fff;border:none;
  border-radius:12px;padding:15px;font-size:15px;font-weight:600;
  cursor:pointer;margin-top:6px;display:flex;align-items:center;
  justify-content:center;gap:8px;transition:opacity .15s;
}
.sbtn:disabled{opacity:.45}
.sbtn:active{opacity:.8}
 
/* ── Success ── */
#successSc{display:none;text-align:center;padding:40px 20px}
.suc-icon{font-size:52px;margin-bottom:16px}
.suc-title{font-size:20px;font-weight:600;margin-bottom:8px}
.suc-sub{font-size:13px;color:#5f5e5a;line-height:1.7;margin-bottom:22px}
.suc-ref{
  background:#fff;border:1px solid #e5e3db;border-radius:10px;
  padding:12px;font-size:12px;color:#5f5e5a;
  margin-bottom:22px;word-break:break-all;text-align:left;
}
.suc-ref strong{display:block;color:#1a1a18;font-size:11px;
  text-transform:uppercase;letter-spacing:.04em;margin-bottom:4px}
.suc-ref .ok{color:#3b6d11;font-weight:500}
.btn-row{display:flex;gap:10px;justify-content:center;flex-wrap:wrap}
.btn-sec{
  padding:11px 20px;background:#fff;border:1.5px solid #1a1a18;
  border-radius:10px;font-size:13px;font-weight:500;
  text-decoration:none;color:#1a1a18;cursor:pointer;
}
.btn-pri{
  padding:11px 20px;background:#1a1a18;border:none;
  border-radius:10px;font-size:13px;font-weight:500;
  color:#fff;cursor:pointer;
}
 
.spacer{height:28px}
</style>
</head>
<body>
 
<div class="hdr">
  <div class="hdr-row">
    <span style="font-size:20px">🙏</span>
    <h1>हनुमान — क्षेत्र नोंद</h1>
  </div>
  <div class="hdr-sub">JAGDISHWARAM DIGITAL OFFICE · CHRONICLE INBOX</div>
</div>
 
<!-- FORM SCREEN -->
<div class="body" id="formSc">
  <div style="height:12px"></div>
  <div class="ts-pill" id="tsPill">⏱ लोड होत आहे...</div>
  <div id="errBar"></div>
 
  <!-- NOTE — Required -->
  <div class="fg">
    <label class="fl" for="noteText">आजची नोंद <span class="req">*</span></label>
    <textarea id="noteText" rows="5"
      placeholder="आज काय झाले? कुठे गेलात? कोणाला भेटलात? काय पाहिले?&#10;(What happened? Where? Who? What did you observe?)"></textarea>
    <div class="hint">मराठी किंवा इंग्रजीत. जितके तपशील तितके उत्तम.</div>
  </div>
 
  <!-- THREAD -->
  <div class="fg">
    <label class="fl" for="threadSel">संबंधित धागा (Thread)</label>
    <select id="threadSel">
      <option value="">-- निवडा (Optional) --</option>
      <option value="MOR">MOR — मा. तहसीलदार न्यायालय, वसई</option>
      <option value="NPS">NPS — मा. उपविभागीय अधिकारी, वसई</option>
      <option value="DMD">DMD — मा. जिल्हाधिकारी, पालघर</option>
      <option value="EAF">EAF — अर्नाळा पोलीस ठाणे</option>
      <option value="AGD">AGD — मा. पोलीस आयुक्त, MBVV</option>
      <option value="RPD">RPD — मा. ACP, नालासोपारा</option>
      <option value="BTR">BTR — VVMC</option>
      <option value="RPO">RPO — मा. प्रादेशिक पारपत्र अधिकारी, मुंबई</option>
      <option value="JUD">JUD — न्यायालय (Court)</option>
      <option value="GENERAL">GENERAL — सर्वसाधारण नोंद</option>
    </select>
  </div>
 
  <!-- LEGAL REF -->
  <div class="fg">
    <label class="fl" for="legalRef">कायदेशीर संदर्भ (Optional)</label>
    <input type="text" id="legalRef"
      placeholder="e.g. तहसीलदार आदेश 01/03/2024 | Exhibit-102 | OMA 254/2026">
    <div class="hint">कोणत्या आदेश, अर्ज किंवा कागदपत्राशी संबंधित?</div>
  </div>
 
  <!-- PHOTO -->
  <div class="fg">
    <label class="fl">छायाचित्र (Optional)</label>
    <div class="photo-area" onclick="document.getElementById('photoInput').click()">
      <div class="photo-icon">📷</div>
      <div class="photo-label">फोटो जोडा — Camera किंवा Gallery</div>
      <div class="photo-sub">JPG · PNG · HEIC · Max 10 MB</div>
    </div>
    <input type="file" id="photoInput" accept="image/*"
           onchange="handlePhoto(this)">
    <div class="photo-preview" id="photoPreview">
      <img id="previewImg" src="" alt="Preview">
      <div class="photo-fname" id="photoFname"></div>
    </div>
  </div>

  <div class="fg">
    <label class="fl">ऑडिओ किंवा व्हिडिओ नोंद (Optional)</label>
    <div class="photo-area" onclick="document.getElementById('audioInput').click()" style="border-style: dashed;">
      <div class="photo-icon">🎙️</div>
      <div class="photo-label">ऑडिओ/व्हिडिओ जोडा — अपनी फाइल से</div>
      <div class="photo-sub">MP3 · MP4 · WAV · Max 50 MB</div>
    </div>
    <input type="file" id="audioInput" accept="audio/*,video/*,,video/*,.m4a,.mp3,.wav"
           onchange="handleAudio(this)">
    <div class="photo-preview" id="audioPreview">
      <div style="padding: 10px; text-align: center;">
        <div id="audioFname" style="font-size: 13px; color: #5f5e5a;"></div>
      </div>
    </div>
  </div>
 
  <!-- ANNOTATION -->
  <div class="fg">
    <label class="fl" for="annotation">वेद व्यासांची टिप्पणी (Your Annotation)</label>
    <textarea id="annotation" rows="3"
      placeholder="हे पुरावे कशाचे आहेत? न्यायालयीन संदर्भात काय महत्त्व?&#10;(What does this evidence prove? Context only you know.)"></textarea>
  </div>
 
  <!-- SUBMIT -->
  <button class="sbtn" id="sbtn" onclick="doSubmit()">
    <span id="sicon">🙏</span>
    <span id="stxt">हनुमानाला पाठवा — Send to Inbox</span>
  </button>
  <div class="spacer"></div>
</div>
 
<!-- SUCCESS SCREEN -->
<div class="body" id="successSc">
  <div class="suc-icon">✅</div>
  <div class="suc-title">हनुमान ने नोंद घेतली</div>
  <div class="suc-sub">
    Chronicle Inbox मध्ये नोंद सुरक्षित झाली.<br>
    पुढील Hanuman sync मध्ये Saraswati प्रक्रिया करेल.
  </div>
  <div class="suc-ref" id="sucRef">
    <strong>संदर्भ क्रमांक</strong>
    <span id="sucRefVal">लोड होत आहे...</span>
  </div>
  <div class="btn-row">
    <a href="/" class="btn-sec">← पोर्टल</a>
    <button class="btn-pri" onclick="resetForm()">+ नवी नोंद</button>
  </div>
</div>
 
<script>
// ── Timestamp (IST) ────────────────────────────────────────────
function updateTS(){
  const n=new Date();
  const s=n.toLocaleString('mr-IN',{
    timeZone:'Asia/Kolkata',day:'2-digit',month:'long',
    year:'numeric',hour:'2-digit',minute:'2-digit',hour12:true
  });
  document.getElementById('tsPill').textContent='⏱ '+s+' IST';
}
updateTS();setInterval(updateTS,30000);
 
// ── Photo preview ──────────────────────────────────────────────
function handlePhoto(inp){
  const f=inp.files[0];if(!f)return;
  if(f.size>10*1024*1024){showErr('फोटो 10MB पेक्षा मोठा आहे.');inp.value='';return;}
  const r=new FileReader();
  r.onload=e=>{
    document.getElementById('previewImg').src=e.target.result;
    document.getElementById('photoFname').textContent='✓ '+f.name;
    document.getElementById('photoPreview').style.display='block';
  };
  r.readAsDataURL(f);
}

// ── Audio preview ──────────────────────────────────────────────
function handleAudio(inp){
  const f=inp.files[0];if(!f)return;
  if(f.size>50*1024*1024){showErr('ऑडिओ/व्हिडिओ 50MB पेक्षा मोठे आहेत.');inp.value='';return;}
  document.getElementById('audioFname').textContent='✓ '+f.name+' ('+Math.round(f.size/1024/1024)+'MB)';
  document.getElementById('audioPreview').style.display='block';
}

// ── Error helpers ──────────────────────────────────────────────
function showErr(m){
  const el=document.getElementById('errBar');
  el.textContent=m;el.style.display='block';window.scrollTo(0,0);
}
function clearErr(){document.getElementById('errBar').style.display='none';}
 
// ── Submit ─────────────────────────────────────────────────────
async function doSubmit(){
  clearErr();
  const note=document.getElementById('noteText').value.trim();
  if(!note){showErr('कृपया आजची नोंद लिहा. ही रकाना अनिवार्य आहे.');return;}
 
  const btn=document.getElementById('sbtn');
  btn.disabled=true;
  document.getElementById('sicon').textContent='⏳';
  document.getElementById('stxt').textContent='पाठवत आहे...';
 
  const fd=new FormData();
  fd.append('note',note);
  fd.append('thread',document.getElementById('threadSel').value);
  fd.append('legal_ref',document.getElementById('legalRef').value.trim());
  fd.append('annotation',document.getElementById('annotation').value.trim());
  const ph=document.getElementById('photoInput').files[0];
  if(ph)fd.append('photo',ph,ph.name);
  const au=document.getElementById('audioInput').files[0];
  if(au)fd.append('audio',au,au.name);
  
  try{
    const res=await fetch('/field/submit',{method:'POST',body:fd});
    const d=await res.json();
    if(d.ok){
      document.getElementById('sucRefVal').innerHTML=
        '<strong>'+d.ref+'</strong>'
        +(d.drive_file?'<br><span class="ok">✓ Drive: '+d.drive_file+'</span>':'')
        +(d.photo_ok?'<br><span class="ok">✓ Photo: '+d.photo_name+'</span>':'');
      document.getElementById('formSc').style.display='none';
      document.getElementById('successSc').style.display='block';
      window.scrollTo(0,0);
    }else{
      showErr('त्रुटी: '+(d.error||'अज्ञात त्रुटी. पुन्हा प्रयत्न करा.'));
      btn.disabled=false;
      document.getElementById('sicon').textContent='🙏';
      document.getElementById('stxt').textContent='हनुमानाला पाठवा — Send to Inbox';
    }
  }catch(e){
    showErr('नेटवर्क त्रुटी. इंटरनेट तपासा आणि पुन्हा प्रयत्न करा.');
    btn.disabled=false;
    document.getElementById('sicon').textContent='🙏';
    document.getElementById('stxt').textContent='हनुमानाला पाठवा — Send to Inbox';
  }
}
 
// ── Reset ──────────────────────────────────────────────────────
function resetForm(){
  ['noteText','legalRef','annotation'].forEach(id=>document.getElementById(id).value='');
  document.getElementById('threadSel').value='';
  document.getElementById('photoInput').value='';
  document.getElementById('photoPreview').style.display='none';
  document.getElementById('formSc').style.display='block';
  document.getElementById('successSc').style.display='none';
  document.getElementById('sbtn').disabled=false;
  document.getElementById('sicon').textContent='🙏';
  document.getElementById('stxt').textContent='हनुमानाला पाठवा — Send to Inbox';
  clearErr();updateTS();window.scrollTo(0,0);
}
</script>
</body>
</html>"""

# ─── OAUTH FLOW CACHE (server memory, not session) ───────────────────────────────
import uuid
oauth_flows = {}  # { flow_id: flow_object }

def save_flow(flow):
    """Store flow in memory, return the ID"""
    flow_id = str(uuid.uuid4())
    oauth_flows[flow_id] = flow
    return flow_id

def get_flow(flow_id):
    """Retrieve flow from memory"""
    return oauth_flows.pop(flow_id, None)  # Remove after use


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
            
        # ANTHROPIC_API_KEY and client initialization assumed here
        if not ANTHROPIC_API_KEY:
            return jsonify({'error': 'API की सेट नाही. Render dashboard तपासा.'}), 500
            
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        
        # --- API Call — two-tier token budget ---
        max_tok = 3000 if len(question) > 120 else 2000
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=max_tok,
            system=YUDHISHTHIRA_SYSTEM,
            messages=[{"role": "user", "content": question}]
        )
        
        # --- Inject Drive links + build response ---
        answer = _inject_links(msg.content[0].text)
        ts_str = datetime.now().strftime('%d/%m/%Y · %I:%M %p IST')
        return jsonify({
            'answer': answer,
            'question': question,
            'timestamp': datetime.now().isoformat(),
            'agent': 'Yudhishthira — युधिष्ठिर',
            'display_timestamp': ts_str
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
        # --- Generic Error Handling (MODIFIED FOR UAT) ---
        print(f"Generic Error during API call: {e}") # Log the error for internal tracking
        # Return a 500 error, but with a specific, actionable message for the user
        return jsonify({'error': "प्रश्न खूप विस्तृत आहे. कृपया एक विशिष्ट, छोटा प्रश्न विचारा."}), 500

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

@app.route('/login')
def login():
    flow = get_google_flow()
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true'
    )
    
    if not hasattr(login, 'flows'):
        login.flows = {}
    login.flows[state] = flow
    
    session['state'] = state
    return redirect(authorization_url)

@app.route('/callback')
def callback():
    """Handle OAuth callback. Retrieve flow from memory using state parameter."""
    try:
        state_id = session.get('state')
        incoming_state = request.args.get('state')
        
        if not state_id or state_id != incoming_state:
            return "State mismatch or session expired. Please restart /login.", 400

        # Retrieve the flow and set the URI before fetching the token
        if not hasattr(login, 'flows') or state_id not in login.flows:
            return "Auth flow expired or session missing. Please restart /login.", 400
            
        flow = login.flows.pop(state_id)
        flow.redirect_uri = os.environ.get('REDIRECT_URI')

        # Execute token exchange
        flow.fetch_token(authorization_response=request.url)
        token_json = flow.credentials.to_json()
              
        # Return as plain HTML so user can copy the JSON
        return f"""
        <html><head><title>जगदिश्वरम् — Token Captured</title>
        <meta charset="UTF-8"></head>
        <body style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 20px; max-width: 800px;">
        <h2 style="color: #2d5016;">✅ Authenticated Successfully!</h2>
        <p>Copy everything in the box below and paste into Railways environment variable <code>GOOGLE_USER_TOKEN</code>:</p>
        <textarea style="width: 100%; height: 400px; border: 1px solid #ccc; padding: 10px; font-family: monospace; font-size: 12px;">{token_json}</textarea>
        <p style="margin-top: 20px;">
        <strong>Next steps:</strong><br>
        1. Copy the JSON above<br>
        2. Go to Railway Dashboard → Environment → Add variable<br>
        3. Key: <code>GOOGLE_USER_TOKEN</code> | Value: [paste JSON]<br>
        4. Save and Redeploy<br>
        5. Visit <a href="/field">/field</a> to test photo + note upload
        </p>
        </body>
        </html>
        """
    except Exception as e:
        return f"""
        <html><head><title>Authentication Error</title>
        <meta charset="UTF-8"></head>
        <body style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 20px;">
        <h2 style="color: #8b1a1a;">❌ Authentication Failed</h2>
        <p><strong>Error:</strong> {str(e)}</p>
        <p>This usually means:</p>
        <ul>
        <li>GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET is incorrect</li>
        <li>The redirect URI doesn't match Google Cloud Console</li>
        <li>You waited too long before completing auth (try again)</li>
        <li>Railway instance restarted (try /login again)</li>
        </ul>
        <p><a href="/login">🔄 Try Again</a></p>
        </body>
        </html>
        """, 400

      
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

# ─── HANUMAN — /field GET ─────────────────────────────────────────────────────
@app.route('/field', methods=['GET'])
def field():
    """Hanuman field note form — mobile-first, PIN-free, direct to Chronicle Inbox."""
    return render_template_string(FIELD_HTML)
 
 
# ─── HANUMAN — /field/submit POST ────────────────────────────────────────────
@app.route('/field/submit', methods=['POST'])
def field_submit():
    """
    Receives the Hanuman field form and writes to Google Drive Chronicle Inbox.
    Option A: No AI processing at submission time. Saraswati processes later.
    """
    try:
        note       = request.form.get('note', '').strip()
        thread     = request.form.get('thread', 'GENERAL').strip() or 'GENERAL'
        legal_ref  = request.form.get('legal_ref', '').strip()
        annotation = request.form.get('annotation', '').strip()
        photo_file = request.files.get('photo')
        audio_file = request.files.get('audio')
 
        if not note:
            return jsonify({'ok': False, 'error': 'नोंद रिकामी आहे'}), 400
 
        # ── Timestamp (Strict IST Enforcement) ──
        ist = pytz.timezone('Asia/Kolkata')
        now_ist = datetime.now(ist)
        ts_file = now_ist.strftime('%Y%m%d_%H%M%S')
        ts_display = now_ist.strftime('%d %B %Y | %I:%M %p IST')
      
        # ── Reference number: HAN-YYYYMMDD-HHMMSS-THREAD ──
        ref       = f"HAN-{ts_file}-{thread}"
        txt_fname = f"{ref}.txt"
 
        # ── Build .txt content for Chronicle Inbox ──
        lines = [
            f"{'═'*56}",
            f"HANUMAN FIELD NOTE",
            f"Reference : {ref}",
            f"Timestamp : {ts_display}",
            f"Thread    : {thread}",
            f"{'═'*56}",
            "",
            "## नोंद (Field Observation)",
            note,
            "",
        ]
        if legal_ref:
            lines += ["## कायदेशीर संदर्भ (Legal Reference)", legal_ref, ""]
        if annotation:
            lines += ["## वेद व्यासांची टिप्पणी (Annotation by Veda Vyasa)", annotation, ""]
        if photo_file and photo_file.filename:
            lines += [f"## छायाचित्र (Photo Attached)", f"Filename: {photo_file.filename}", ""]
        lines += ["─"*56, "जय हनुमान। सत्यमेव जयते।", "─"*56]
 
        txt_content = "\\n".join(lines)
 
        # ── Write text note to Drive inbox ──
        result = _write_to_inbox(txt_content, txt_fname)

        # ── Upload photo if attached ──
        photo_ok = False
        photo_name = ""
        if photo_file and photo_file.filename and result.get('ok'):
            ph_bytes = photo_file.read() # Read once to avoid empty stream
            ph_fname = f"HAN-{ts_file}-{photo_file.filename}"
            ph_ctype = photo_file.content_type or 'image/jpeg'
            photo_ok = _upload_photo_to_inbox(ph_bytes, ph_fname, ph_ctype)
            photo_name = ph_fname if photo_ok else ""

        # ── Upload audio/video if attached ──
        if audio_file and audio_file.filename and result.get('ok'):
            au_bytes = audio_file.read()
            au_fname = f"HAN-{ts_file}-{audio_file.filename}"
            au_ctype = audio_file.content_type or 'audio/mpeg'
            _upload_photo_to_inbox(au_bytes, au_fname, au_ctype)

        return jsonify({
            'ok' : result.get('ok', False),
            'ref' : ref,
            'drive_file': result.get('file_name', ''),
            'photo_ok' : photo_ok,
            'photo_name': photo_name,
            'error' : result.get('error', '')
        })
 
    except Exception as e:
        print(f"ERROR /field/submit: {e}")
        return jsonify({'ok': False, 'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
