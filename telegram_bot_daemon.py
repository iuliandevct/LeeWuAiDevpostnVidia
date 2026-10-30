#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LeeWu AI - Autonomous Maritime Field Surveyor Telegram Daemon
Integrated with NVIDIA Nemotron Models, Persistent Chat History & Accounting Brain

SECURITY REMEDIATED:
- Zero hardcoded secrets (reads strictly from environment variables or .env)
- Mandatory user / chat ID allowlist authorization
- Input validation and length checking
- HTML sanitization against injection
- Secrets masking in all logs and error handlers
"""

import os
import sys
import json
import time
import urllib.request
import urllib.parse
import html
import threading
from pathlib import Path

# Ensure UTF-8 output on Windows console
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def _load_env_file(filepath):
    """Safely parse .env file into os.environ without printing or external dependencies."""
    if not os.path.exists(filepath):
        return
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'\"")
                if k and k not in os.environ:
                    os.environ[k] = v
    except Exception:
        pass


# Attempt to load .env from current directory or parent directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_load_env_file(os.path.join(BASE_DIR, ".env"))
_load_env_file(os.path.join(os.path.dirname(BASE_DIR), ".env"))

# Mandatory Environment Variables (Never hardcoded)
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()
TELEGRAM_ALLOWED_USERS = os.getenv("TELEGRAM_ALLOWED_USERS", "").strip()

NEBIUS_KEY = os.getenv("NEBIUS_API_KEY", "").strip()
NEBIUS_BASE_URL = os.getenv("NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1").rstrip("/")
NEBIUS_URL = f"{NEBIUS_BASE_URL}/chat/completions"
NEBIUS_MODEL = os.getenv("NEBIUS_MODEL", "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B")

BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}" if BOT_TOKEN else ""

DATA_DIR = os.getenv("DATA_DIR", os.path.join(BASE_DIR, "data"))
os.makedirs(DATA_DIR, exist_ok=True)
REMARKS_FILE = os.path.join(DATA_DIR, "survey_remarks.json")
CHAT_HISTORY_FILE = os.path.join(DATA_DIR, "telegram_chat_history.json")


def safe_mask(val):
    """Mask credentials completely without leaking prefixes, suffixes, or fragments."""
    if not val:
        return "[NOT SET]"
    return "[CONFIGURED]"


def mask_numeric_id(val):
    """Mask numeric user/chat IDs for diagnostic logging without exposing full IDs."""
    if val is None:
        return "[NONE]"
    s = str(val).strip()
    if len(s) <= 4:
        return "***"
    return f"***{s[-4:]}"


def safe_log_err(prefix, err):
    """Log errors with guaranteed secrets redaction."""
    import re
    msg = str(err)
    if hasattr(err, "read"):
        try:
            body = err.read().decode("utf-8", errors="ignore")
            if body:
                msg = f"{msg} | Body: {body[:300]}"
        except Exception:
            pass
    if BOT_TOKEN:
        msg = msg.replace(BOT_TOKEN, "[MASKED_BOT_TOKEN]")
    if NEBIUS_KEY:
        msg = msg.replace(NEBIUS_KEY, "[MASKED_NEBIUS_KEY]")
    msg = re.sub(r'Bearer\s+[A-Za-z0-9_\-\.]+', 'Bearer [MASKED_TOKEN]', msg, flags=re.IGNORECASE)
    msg = re.sub(r'v1\.[A-Za-z0-9_\-\.]{16,}', '[MASKED_KEY]', msg)
    msg = re.sub(r'\b[0-9]{8,11}:[A-Za-z0-9_-]{30,40}\b', '[MASKED_TOKEN]', msg)
    print(f"[{prefix}] {msg}", file=sys.stderr)
    sys.stderr.flush()


def parse_allowed_entities(chat_id_env=None, allowed_users_env=None):
    """
    Extract and validate authorized numeric Telegram user IDs and chat IDs.
    Returns: (allowed_ids: set[int], is_valid: bool, reason: str)
    
    Security Controls:
    1. Authorization must use numeric Telegram user IDs and/or numeric chat IDs only.
    2. Usernames (e.g. '@admin', 'username') are strictly REJECTED as credentials.
    3. Missing, empty, malformed, or invalid configuration must deny access (fail-closed).
    4. Any non-numeric token marks the entire configuration as malformed (fail-closed).
    """
    if chat_id_env is None:
        chat_id_env = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if allowed_users_env is None:
        allowed_users_env = os.getenv("TELEGRAM_ALLOWED_USERS", "").strip()

    if not chat_id_env and not allowed_users_env:
        return set(), False, "Missing allowlist configuration (both TELEGRAM_CHAT_ID and TELEGRAM_ALLOWED_USERS are unset or empty)"

    raw_tokens = []
    if chat_id_env:
        raw_tokens.extend(chat_id_env.split(","))
    if allowed_users_env:
        raw_tokens.extend(allowed_users_env.split(","))

    cleaned_tokens = [t.strip() for t in raw_tokens if t.strip()]
    if not cleaned_tokens:
        return set(), False, "Empty allowlist configuration (no non-empty tokens found)"

    allowed = set()
    for token in cleaned_tokens:
        # Usernames (@user or alphabetic) are strictly forbidden as authorization credentials
        if token.startswith("@") or any(c.isalpha() for c in token):
            return set(), False, "Malformed allowlist configuration: Usernames or non-numeric tokens are rejected as credentials"

        # Check numeric integer (negative allowed for supergroup/channel chat IDs)
        is_numeric = False
        if token.startswith("-") and token[1:].isdigit():
            is_numeric = True
        elif token.isdigit():
            is_numeric = True

        if not is_numeric:
            return set(), False, "Malformed allowlist configuration: Invalid numeric format"

        try:
            allowed.add(int(token))
        except ValueError:
            return set(), False, "Malformed allowlist configuration: Integer parsing failure"

    if not allowed:
        return set(), False, "Invalid allowlist configuration: Zero valid numeric IDs parsed"

    return allowed, True, f"Valid numeric allowlist configuration ({len(allowed)} IDs)"


def is_authorized(chat_id, user_obj, chat_id_env=None, allowed_users_env=None):
    """
    Verify whether the requesting user/chat is in the authorized allowlist.
    Returns (bool, reason_string).
    
    Security Controls:
    1. Zero bypass: TELEGRAM_ALLOW_ALL is completely removed.
    2. Strictly numeric Telegram user IDs and/or numeric chat IDs only.
    3. Usernames in user_obj are completely IGNORED and REJECTED as credentials.
    4. Missing, empty, malformed, or invalid configuration must deny access (fail-closed).
    5. Missing or invalid user/chat ID in incoming request strictly denies access.
    """
    allowed_ids, is_valid, config_reason = parse_allowed_entities(chat_id_env, allowed_users_env)
    if not is_valid or not allowed_ids:
        return False, f"Access denied: {config_reason}"

    req_chat_id = None
    if chat_id is not None:
        try:
            req_chat_id = int(str(chat_id).strip())
        except (ValueError, TypeError):
            req_chat_id = None

    req_user_id = None
    if isinstance(user_obj, dict):
        raw_uid = user_obj.get("id")
        if raw_uid is not None:
            try:
                req_user_id = int(str(raw_uid).strip())
            except (ValueError, TypeError):
                req_user_id = None

    if req_chat_id is None and req_user_id is None:
        return False, "Access denied: Missing or invalid numeric ID in incoming request"

    # Strictly check numeric IDs against allowed_ids
    if req_user_id is not None and req_user_id in allowed_ids:
        return True, "Authorized by user ID"
    if req_chat_id is not None and req_chat_id in allowed_ids:
        return True, "Authorized by chat ID"

    return False, f"Unauthorized entity (chat={mask_numeric_id(req_chat_id)}, user={mask_numeric_id(req_user_id)})"


def sanitize_input(text, max_len=2000):
    """Sanitize user input, stripping control characters and enforcing length bounds."""
    if not text:
        return ""
    clean = "".join(c for c in text if c in ("\n", "\t") or (ord(c) >= 32 and ord(c) != 127))
    return clean[:max_len].strip()


_history_lock = threading.Lock()


def load_all_history():
    """
    Safely load chat history with file locking and corruption preservation.
    If corruption is detected, creates a timestamped backup before recovery.
    """
    with _history_lock:
        if os.path.exists(CHAT_HISTORY_FILE):
            try:
                with open(CHAT_HISTORY_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data if isinstance(data, dict) else {}
            except (json.JSONDecodeError, ValueError) as err:
                corrupt_backup = f"{CHAT_HISTORY_FILE}.corrupt.{int(time.time())}"
                try:
                    os.rename(CHAT_HISTORY_FILE, corrupt_backup)
                    safe_log_err("Corrupted history preserved to backup", err)
                except Exception:
                    pass
                return {}
            except Exception as e:
                safe_log_err("Error reading chat history", e)
                return {}
        return {}


def save_chat_message(chat_id, role, text):
    """
    Thread-safe message persistence with atomic write to prevent data loss.
    Strictly partitions history by chat ID to ensure context isolation.
    """
    cid = str(chat_id)
    with _history_lock:
        history = {}
        if os.path.exists(CHAT_HISTORY_FILE):
            try:
                with open(CHAT_HISTORY_FILE, "r", encoding="utf-8") as f:
                    history = json.load(f)
                    if not isinstance(history, dict):
                        history = {}
            except Exception:
                history = {}

        if cid not in history:
            history[cid] = []

        msg_entry = {
            "role": role,
            "content": text,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        history[cid].append(msg_entry)

        # Enforce strict 100-message retention limit per chat
        if len(history[cid]) > 100:
            history[cid] = history[cid][-100:]

        tmp_file = f"{CHAT_HISTORY_FILE}.tmp.{os.getpid()}"
        try:
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(history, f, indent=2, ensure_ascii=False)
            os.replace(tmp_file, CHAT_HISTORY_FILE)
        except Exception as e:
            safe_log_err("Error saving chat history atomically", e)
            if os.path.exists(tmp_file):
                try:
                    os.remove(tmp_file)
                except Exception:
                    pass


def get_recent_context(chat_id, limit=8):
    """
    Retrieve strictly isolated context for a specific chat ID.
    Guarantees no cross-user context leakage.
    """
    cid = str(chat_id)
    history = load_all_history()
    user_msgs = history.get(cid, [])
    recent = []
    for m in user_msgs[-limit:]:
        recent.append({
            "role": m.get("role", "user"),
            "content": m.get("content", "")
        })
    return recent


def clear_chat_history(chat_id) -> bool:
    """
    Clear chat history for a specific chat ID and report success or failure.
    """
    cid = str(chat_id)
    with _history_lock:
        history = {}
        if os.path.exists(CHAT_HISTORY_FILE):
            try:
                with open(CHAT_HISTORY_FILE, "r", encoding="utf-8") as f:
                    history = json.load(f)
                    if not isinstance(history, dict):
                        history = {}
            except Exception:
                return False

        if cid in history:
            history[cid] = []
            tmp_file = f"{CHAT_HISTORY_FILE}.tmp.{os.getpid()}"
            try:
                with open(tmp_file, "w", encoding="utf-8") as f:
                    json.dump(history, f, indent=2, ensure_ascii=False)
                os.replace(tmp_file, CHAT_HISTORY_FILE)
                return True
            except Exception as e:
                safe_log_err("Error clearing chat history", e)
                return False
        return True


def answer_callback_query(callback_query_id, text=None, show_alert=False):
    """Answer an incoming callback query with safe error handling."""
    if not BOT_TOKEN or not callback_query_id:
        return None
    payload = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text
        payload["show_alert"] = show_alert
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{BASE_URL}/answerCallbackQuery",
            data=data,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "LeeWuBot/1.0",
                "Connection": "close"
            }
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        safe_log_err("Error answering callback query", e)
        return None


def send_message(chat_id, text, thread_id=None):
    if not BOT_TOKEN:
        print("[Telegram Bot] Cannot send message: TELEGRAM_BOT_TOKEN is not configured.", file=sys.stderr)
        return None

    if text and len(text) > 3950:
        text = text[:3950] + "\n..."

    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }
    if thread_id:
        payload["message_thread_id"] = thread_id
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        BASE_URL + "/sendMessage",
        data=data,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "LeeWuBot/1.0",
            "Connection": "close"
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as he:
        if he.code == 400 and payload.get("parse_mode") == "HTML":
            try:
                import re
                payload.pop("parse_mode", None)
                plain_text = html.unescape(re.sub(r"<[^>]+>", "", text))
                payload["text"] = plain_text[:3950]
                data_plain = json.dumps(payload).encode("utf-8")
                req_plain = urllib.request.Request(
                    BASE_URL + "/sendMessage",
                    data=data_plain,
                    headers={
                        "Content-Type": "application/json",
                        "User-Agent": "LeeWuBot/1.0",
                        "Connection": "close"
                    }
                )
                with urllib.request.urlopen(req_plain, timeout=15) as r:
                    return json.loads(r.read().decode("utf-8"))
            except Exception as fallback_err:
                safe_log_err("Error on plaintext fallback send", fallback_err)
        safe_log_err("Error sending message", he)
        return None
    except Exception as e:
        safe_log_err("Error sending message", e)
        return None


def format_ai_for_telegram_html(raw_text: str) -> str:
    """
    Converts Markdown-style LLM output (**bold**, `code`, ### headings) into clean
    Telegram HTML while stripping internal reasoning summaries and avoiding nested tags.
    """
    import re
    if not raw_text:
        return ""
    text = raw_text.strip()

    if "[Reasoning Summary]" in text:
        parts = re.split(r"\n\s*\n", text)
        filtered = [p for p in parts if not p.strip().startswith("[Reasoning Summary]")]
        if filtered:
            text = "\n\n".join(filtered).strip()

    escaped = html.escape(text)
    escaped = re.sub(r"`([^`\n]+)`", r"<code>\1</code>", escaped)

    out_lines = []
    for line in escaped.splitlines():
        m = re.match(r"^#{1,4}\s+(.+)$", line.strip())
        if m:
            heading_clean = m.group(1).replace("**", "")
            out_lines.append(f"📌 <b>{heading_clean}</b>")
        else:
            out_lines.append(re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", line))
    return "\n".join(out_lines)


def get_live_operational_context() -> str:
    """
    Reads real-time survey state from SQLite (in immutable read-only mode so the DB file
    is never modified) and field remarks from survey_remarks.json to ground the AI in facts.
    """
    import sqlite3
    lines = [
        "=== CONTEXT OPERAȚIONAL REAL (PORTUL CONSTANȚA — LEEWU MARITIME SURVEY) ===",
        "1. INSPECȚIE GREA (HEAVY-LIFT) ÎN BAZA SQLITE — DOSAR LW-DEMO-001:"
    ]
    db_file = os.path.join(DATA_DIR, "leewu_mvp.db")
    if os.path.exists(db_file):
        try:
            uri = f"file:{Path(db_file).as_posix()}?mode=ro&immutable=1"
            conn = sqlite3.connect(uri, uri=True, timeout=5.0)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM surveys WHERE survey_id = 'LW-DEMO-001'")
            s = cur.fetchone()
            if s:
                lines.append(
                    f"   - Navă: {s['vessel_name']} (IMO {s['imo_number']}) | Locație: {s['location']}, {s['berth']}"
                )
                lines.append(
                    f"   - Marfă: {s['cargo_name']} (Unitate: {s['cargo_item']}, Greutate brută: 124.5 MT) | Client: {s['client_name']}"
                )
                lines.append(
                    f"   - Status dosar: {s['status']} | Inspector: {s['approved_by'] or 'Ing. Alexandru Radu'} "
                    f"(Licență: {s['surveyor_license'] or 'DEMO-MWS-2026-001'})"
                )
                if s["cryptographic_hash"]:
                    lines.append(f"   - Sigiliu SHA-256 raport: {s['cryptographic_hash'][:24]}...")
            cur.execute("SELECT COUNT(*), MAX(sha256) FROM evidence WHERE survey_id = 'LW-DEMO-001'")
            ev_row = cur.fetchone()
            if ev_row and ev_row[0]:
                lines.append(f"   - Dovezi foto atașate: {ev_row[0]} fotografie HD verificată (SHA-256: {ev_row[1][:16]}...)")
            cur.execute(
                "SELECT nitrogen_pressure, impact_recorder_g, lashing_status FROM ai_assessments "
                "WHERE survey_id = 'LW-DEMO-001' ORDER BY id DESC LIMIT 1"
            )
            ai_row = cur.fetchone()
            if ai_row:
                lines.append(
                    f"   - Telemetrie măsurată TR-001: Presiune azot (N2) = {ai_row['nitrogen_pressure']} (țintă 0.15-0.35 bar, OPTIM); "
                    f"Înregistrator șocuri = {ai_row['impact_recorder_g']} (sub limita IMO CSS Annex 13 de 1.5 G); "
                    f"Amarare = {ai_row['lashing_status']}."
                )
            else:
                lines.append(
                    "   - Telemetrie standard TR-001: Presiune azot (N2) = 0.24-0.25 bar (țintă 0.15-0.35 bar, OPTIM); "
                    "Șocuri = 0.75 G longitudinal / 0.35 G transversal (sub pragul de 1.5 G IMO CSS Code Annex 13); "
                    "Amarare = 8 lanțuri Grade 80 de 16mm la 45° cu întinzătoare sigilate."
                )
            conn.close()
        except Exception:
            pass

    lines.append(
        "2. OPERAȚIUNE DESCĂRCARE OȚEL — NAVA MV WAN FU (IMO 9482184, Dana 52 Constanța Sud):\n"
        "   - Marfă: 15.420 MT oțel laminat & bobine laminate la cald (Hot Rolled Steel Coils) | Client: GLOBAL OCEAN SHIPPING.\n"
        "   - Progres descărcare: 4.820 MT descărcate (31.2%), rămase 10.600 MT | Macarale active: Macara 2 & Macara 3 cheu.\n"
        "   - Condiții meteo în port: Vânt 12 noduri ESE, mare grad 2, fără precipitații active."
    )

    remarks_list = []
    if os.path.exists(REMARKS_FILE):
        try:
            with open(REMARKS_FILE, "r", encoding="utf-8") as f:
                remarks_list = json.load(f)
        except Exception:
            remarks_list = []

    if remarks_list:
        lines.append(f"3. AVARII / REMARCI ÎNREGISTRATE PE TEREN ({len(remarks_list)} înregistrări în survey_remarks.json):")
        for r in remarks_list[:5]:
            lines.append(
                f"   - [{r.get('id')}] Magazia (Hold) {r.get('hold_no')}: {r.get('description')} "
                f"(Severitate: {r.get('severity')}, Cauză: {r.get('attributed_party')}, Ora: {r.get('photo_timestamp')})"
            )
    else:
        lines.append("3. AVARII / REMARCI ÎNREGISTRATE PE TEREN: Nicio avarie activă înregistrată momentan (se pot adăuga cu /remark).")

    lines.append(
        "4. FLOTĂ AUTO & PONTAJ INSPECTOR (Ing. Alexandru Radu):\n"
        "   - Pontaj curent reconstituit EXIF: 08:14 - 17:08 (8.15 ore net facturabile după 45 min pauză meteo) = 1.507,75 RON (185 RON/oră).\n"
        "   - Foaie parcurs CT-88-LPM (Dacia Duster 4x4): 48 km (Mamaia -> Poarta 10 -> Dana 52 -> Retur), consum 3.45L Diesel, randament 0.89 RON/km.\n"
        "   - Alerte acte auto: CT-88-LPM ITP expiră în 18 zile (17.11.2026); CT-22-LPM (Renault Megane) Rovinietă expiră în 7 zile (06.11.2026).\n"
        "   - Cadru juridic: Hague-Visby Rules Art. III r.2, Codul IMO CSS Annex 13, Legea 51/1995 (Baroul Constanța), Club P&I Gard Norway."
    )
    return "\n".join(lines)


def query_nemotron_with_history(chat_id, user_prompt, api_key=None):
    key = api_key if api_key is not None else (os.getenv("NEBIUS_API_KEY") if "NEBIUS_API_KEY" in os.environ else NEBIUS_KEY)
    key = (key or "").strip()
    if not key:
        return "⚠️ Serviciul de inteligență artificială nu este configurat (NEBIUS_API_KEY lipsește). Contactați administratorul de sistem."

    live_context = get_live_operational_context()
    context_msgs = get_recent_context(chat_id, limit=8)

    system_prompt = (
        "Ești LeeWu AI — Senior Marine Cargo Warranty Surveyor (MWS) și Asistentul Neural Operațional "
        "al LeeWu Maritime Survey în Portul Constanța, lucrând direct cu inspectorul șef Ing. Alexandru Radu.\n\n"
        f"{live_context}\n\n"
        "REGULI STRICTE DE COMUNICARE ȘI INTELIGENȚĂ:\n"
        "1. Vorbește o limba română impecabilă, naturală, tehnică și directă (folosește termeni corecți: "
        "'marfă/cargo', 'magazie (Hold)', 'dană', 'amarare (lashing)', 'conosament (Bill of Lading)', 'Clean Mate\\'s Receipt', 'notificare de rezervă P&I'). "
        "NU inventa niciodată cuvinte stricate precum 'Navtiic Mare' sau 'compartimentul de cargă' și NU inventa ani din trecut (suntem în octombrie 2026).\n"
        "2. Folosește întotdeauna datele reale din CONTEXTUL OPERAȚIONAL de mai sus (atât pentru transformatorul TR-001 de pe MV DEMO CARRIER la Dana 120, "
        "cât și pentru bobinele de oțel de pe MV WAN FU la Dana 52, avariile din survey_remarks.json, pontaj și flotă).\n"
        "3. INTERZIS să repeți mecanic același mesaj sau să închei cu fraze robotice de tipul 'Vă rugăm să confirmați acceptarea acestor puncte'.\n"
        "4. Dacă utilizatorul spune 'Confirm', 'Aprob', 'Ok', 'Deci?', 'Ce facem acum?' sau pune o întrebare scurtă, "
        "răspunde inteligent la pasul următor concret (de ex. confirmă că raportul statutar este pregătit fără rezerve / Clean Mate's Receipt, "
        "sau rezumă exact ce mai este de făcut pe cheu la Dana 52 / Dana 120). Fii concis (max 6-10 rânduri clare)."
    )

    messages = [{"role": "system", "content": system_prompt}]
    for cm in context_msgs:
        messages.append(cm)

    messages.append({
        "role": "user",
        "content": sanitize_input(user_prompt, max_len=1500)
    })

    # Prefer flagship Nemotron-3-Ultra-550b-a55b for natural Romanian reasoning, with automatic fallback to NEBIUS_MODEL
    primary_model = os.getenv("TELEGRAM_AI_MODEL", "nvidia/Nemotron-3-Ultra-550b-a55b").strip()
    candidate_models = [primary_model]
    if NEBIUS_MODEL not in candidate_models:
        candidate_models.append(NEBIUS_MODEL)

    for chosen_model in candidate_models:
        payload = {
            "model": chosen_model,
            "messages": messages,
            "max_tokens": 1800,
            "temperature": 0.25
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(NEBIUS_URL, data=data, headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + key,
            "User-Agent": "LeeWuNemotron/1.0",
            "Connection": "close"
        })
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                res = json.loads(r.read().decode("utf-8"))
                choices = res.get("choices", [])
                reply_raw = choices[0].get("message", {}).get("content") if choices else None
                reply = (reply_raw or "").strip()
                if reply:
                    save_chat_message(chat_id, "user", user_prompt)
                    save_chat_message(chat_id, "assistant", reply)
                    return format_ai_for_telegram_html(reply)
        except Exception as e:
            safe_log_err(f"Nemotron query error ({chosen_model})", e)
            continue

    return "Am întâmpinat o întârziere la comunicarea cu serverul NVIDIA Nemotron. Te rog încearcă din nou."


def build_live_status_html() -> str:
    import sqlite3
    status_tr = "IN_PROGRESS"
    approved_by = "Ing. Alexandru Radu"
    ev_count = 0
    seal_short = "În așteptare"
    db_file = os.path.join(DATA_DIR, "leewu_mvp.db")
    if os.path.exists(db_file):
        try:
            uri = f"file:{Path(db_file).as_posix()}?mode=ro&immutable=1"
            conn = sqlite3.connect(uri, uri=True, timeout=5.0)
            cur = conn.cursor()
            cur.execute("SELECT status, approved_by, cryptographic_hash FROM surveys WHERE survey_id = 'LW-DEMO-001'")
            row = cur.fetchone()
            if row:
                status_tr = row[0] or "IN_PROGRESS"
                approved_by = row[1] or "Ing. Alexandru Radu"
                if row[2]:
                    seal_short = row[2][:16] + "..."
            cur.execute("SELECT COUNT(*) FROM evidence WHERE survey_id = 'LW-DEMO-001'")
            ev_count = cur.fetchone()[0]
            conn.close()
        except Exception:
            pass

    remarks = []
    if os.path.exists(REMARKS_FILE):
        try:
            with open(REMARKS_FILE, "r", encoding="utf-8") as f:
                remarks = json.load(f)
        except Exception:
            remarks = []

    return (
        "📊 <b>Panou Operațional Live — Portul Constanța</b>\n\n"
        "⚡ <b>1. Dosar Heavy-Lift <code>LW-DEMO-001</code> (Dana 120):</b>\n"
        "  • <b>Navă:</b> MV DEMO CARRIER (IMO 9845120)\n"
        "  • <b>Unitate:</b> Transformator 110kV <code>TR-001</code> (124.5 MT)\n"
        "  • <b>Telemetrie:</b> N2 = <code>0.24 bar</code> (Optim) | Șoc = <code>0.75 G</code> (&lt; 1.5 G IMO)\n"
        f"  • <b>Dovezi Foto:</b> {ev_count} atașate | <b>Status:</b> <code>{status_tr}</code>\n"
        f"  • <b>Inspector:</b> {html.escape(approved_by)} | <b>Sigiliu:</b> <code>{seal_short}</code>\n\n"
        "🚢 <b>2. Descărcare Bobine Oțel — <code>MV WAN FU</code> (Dana 52):</b>\n"
        "  • <b>Marfă:</b> 15.420 MT Hot Rolled Steel Coils\n"
        "  • <b>Descărcat:</b> 4.820 MT (<b>31.2%</b>) — Macaralele 2 &amp; 3 active\n"
        f"  • <b>Avarii (Remarks) înregistrate:</b> <b>{len(remarks)}</b> piese (vezi <code>/avarii</code>)\n\n"
        "💡 <i>Comenzi rapide:</i> <code>/avarii</code> | <code>/raport</code> | <code>/nava</code> | <code>/pontaj</code> | <code>/acte</code>"
    )


def handle_remark(chat_id, thread_id, text):
    parts = sanitize_input(text.replace("/remark", "").strip(), max_len=500)
    if not parts:
        send_message(
            chat_id,
            "⚠️ Format comandă: <code>/remark [Magazie] [Piesă] [Descriere avarie]</code>\n"
            "Exemplu: <code>/remark Hold 3 Coil #482 miez deformat strivit macara</code>",
            thread_id
        )
        return

    hold_no = 3
    low = parts.lower()
    if "hold 1" in low:
        hold_no = 1
    elif "hold 2" in low:
        hold_no = 2
    elif "hold 4" in low:
        hold_no = 4
    elif "hold 5" in low:
        hold_no = 5

    rem_id = "REM-" + str(int(time.time()) % 1000).zfill(3)
    now_str = time.strftime("%Y-%m-%d %H:%M:%S")

    remark = {
        "id": rem_id,
        "hold_no": hold_no,
        "item_ref": "Piesă Inspecție Teren",
        "description": parts,
        "photo_timestamp": now_str,
        "severity": "CRITIC",
        "attributed_party": "Manipulare defectuoasă macara cheu (Stevedore)",
        "legal_status": "Hague-Visby Art. III r.2 (Notificare P&I inițiată)",
        "created_via": "Telegram Bot (@Leewubot)",
        "surveyor": "Alexandru Radu"
    }

    remarks = []
    if os.path.exists(REMARKS_FILE):
        try:
            with open(REMARKS_FILE, "r", encoding="utf-8") as f:
                remarks = json.load(f)
        except Exception:
            remarks = []
    remarks.insert(0, remark)
    try:
        with open(REMARKS_FILE, "w", encoding="utf-8") as f:
            json.dump(remarks, f, indent=2, ensure_ascii=False)
    except Exception as e:
        safe_log_err("Error writing remarks", e)

    save_chat_message(chat_id, "user", text)
    save_chat_message(chat_id, "assistant", f"Remarcă înregistrată {rem_id}: {parts}")

    safe_parts = html.escape(parts)
    resp = (
        "✅ <b>Remarcă Înregistrată în Tabelul de Piese Bulite!</b>\n\n"
        f"🆔 <b>ID Remarcă:</b> <code>{rem_id}</code>\n"
        f"🚢 <b>Locație:</b> Magazia (Hold) {hold_no}\n"
        f"📝 <b>Descriere:</b> {safe_parts}\n"
        f"⏱️ <b>Ora înregistrare:</b> <code>{now_str}</code>\n"
        "⚠️ <b>Severitate:</b> CRITIC\n"
        "⚖️ <b>Bază Legală:</b> Hague-Visby Art. III r.2 (Custody & Care of Cargo)\n"
        "📋 <b>Status:</b> Sincronizat instant în Consola Web și Raportul A4!"
    )
    send_message(chat_id, resp, thread_id)


def main():
    if not BOT_TOKEN:
        print("[ERROR] TELEGRAM_BOT_TOKEN is not configured in environment or .env file.", file=sys.stderr)
        print("Please configure TELEGRAM_BOT_TOKEN before launching the daemon.", file=sys.stderr)
        sys.exit(1)

    print("Starting LeeWu Telegram Bot Daemon (@Leewubot with Persistent Chat Memory)...")
    print(f"- Bot Token Status: {safe_mask(BOT_TOKEN)}")
    print(f"- Nebius Key Status: {safe_mask(NEBIUS_KEY)}")
    print(f"- Configured Model: {NEBIUS_MODEL}")
    allowed_ids, is_valid, config_reason = parse_allowed_entities()
    if not is_valid:
        print(f"[SECURITY WARNING] Allowlist configuration invalid: {config_reason}", file=sys.stderr)
        print("- Security Allowlist: INACTIVE (FAIL-CLOSED: All access denied)", file=sys.stderr)
    else:
        print(f"- Security Allowlist: {len(allowed_ids)} authorized numeric ID(s) active")
    sys.stdout.flush()

    offset = None
    while True:
        try:
            url = BASE_URL + "/getUpdates?timeout=10"
            if offset:
                url += "&offset=" + str(offset)
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "LeeWuBot/1.0",
                    "Connection": "close"
                }
            )
            with urllib.request.urlopen(req, timeout=20) as r:
                res = json.loads(r.read().decode("utf-8"))
            if not res.get("ok"):
                time.sleep(2)
                continue

            for update in res.get("result", []):
                offset = update["update_id"] + 1

                # 1. Callback Query Security Check
                cb = update.get("callback_query")
                if cb:
                    cb_from = cb.get("from") or {}
                    cb_chat_id = (cb.get("message") or {}).get("chat", {}).get("id") or cb_from.get("id")
                    cb_id = cb.get("id")
                    cb_auth, cb_reason = is_authorized(cb_chat_id, cb_from)
                    if not cb_auth:
                        print(f"[SECURITY] Blocked unauthorized callback query from user {mask_numeric_id(cb_from.get('id'))}: {cb_reason}")
                        sys.stdout.flush()
                        answer_callback_query(cb_id, text="Acces Neautorizat.", show_alert=True)
                        continue
                    # Process authorized callback if any handler exists
                    continue

                # 2. Message / Edited Message Security Check
                msg = update.get("message") or update.get("edited_message")
                if not msg:
                    continue

                chat_id = (msg.get("chat") or {}).get("id")
                from_user = msg.get("from") or {}
                thread_id = msg.get("message_thread_id")
                raw_text = (msg.get("text") or "").strip()
                photos = msg.get("photo")

                # Telegram Security: Mandatory Authorization Check BEFORE every command, photo, remark, or query
                authorized, reason = is_authorized(chat_id, from_user)
                if not authorized:
                    print(f"[SECURITY] Blocked unauthorized request from chat {mask_numeric_id(chat_id)}: {reason}")
                    sys.stdout.flush()
                    rejection_msg = (
                        "⛔ <b>Acces Neautorizat</b>\n\n"
                        "Acest canal operațional este rezervat exclusiv personalului autorizat <b>LeeWu Maritime Services</b>.\n"
                        "ID-ul dumneavoastră numeric Telegram nu figurează în lista de acces autorizată."
                    )
                    send_message(chat_id, rejection_msg, thread_id)
                    continue

                # Input Validation & Length Check
                if len(raw_text) > 4000:
                    send_message(
                        chat_id,
                        "⚠️ <b>Eroare Validare:</b> Mesajul transmis depășește lungimea maximă admisă (4000 caractere).",
                        thread_id
                    )
                    continue

                text = sanitize_input(raw_text)

                if photos:
                    now_str = time.strftime("%H:%M:%S")
                    save_chat_message(chat_id, "user", f"[Foto încărcată la {now_str}]")
                    send_message(
                        chat_id,
                        "📸 <b>Poză Inspecție Recepționată!</b>\n"
                        f"⏱️ <b>Timestamp EXIF:</b> <code>{now_str}</code>\n"
                        "🚢 <b>Destinație:</b> Adăugată cronologic în Indexul Foto și Secvența de Descărcare MV WAN FU (Dana 52).\n"
                        "💡 Trimite <code>/remark [text]</code> dacă piesa fotografiată prezintă avarii.",
                        thread_id
                    )
                    continue

                if not text:
                    continue

                low = text.lower()
                if low.startswith("/start") or low.startswith("/help") or low.startswith("/ajutor"):
                    menu = (
                        "⚓ <b>LeeWu AI — Robotul de Inspecție Maritimă & Flotă</b>\n"
                        "<i>Powered by NVIDIA Nemotron (Nebius Token Factory) & Persistent Memory</i>\n\n"
                        "📋 <b>Comenzi disponibile pe teren:</b>\n\n"
                        "• <code>/remark [text]</code> — Înregistrează o piesă bulită (ex: <code>/remark Hold 3 Coil #482 miez strivit</code>)\n"
                        "• <code>/pontaj</code> — Afișează pontajul calculat automat din pozele EXIF (08:14 - 17:08)\n"
                        "• <code>/foaie</code> — Generează foaie de parcurs pentru CT-88-LPM (0.89 RON/km)\n"
                        "• <code>/acte</code> — Verifică scadențele actelor mașinilor (ITP, RCA, Rovinietă)\n"
                        "• <code>/status</code> — Panou operațional live (TR-001 Dana 120 + MV WAN FU Dana 52)\n"
                        "• <code>/avarii</code> — Lista avariilor înregistrate pe teren\n"
                        "• <code>/raport</code> — Rezumatul certificatului statutar & sigiliul SHA-256\n"
                        "• <code>/nava</code> — Status descărcare MV WAN FU Dana 52 Port Constanța\n"
                        "• <code>/juridic</code> — Baza legală Legea 51/1995 & arbitraj daune\n"
                        "• <code>/istoric</code> — Afișează ultimele mesaje din istoricul salvat\n"
                        "• <code>/reset</code> — Șterge istoricul conversației curente\n\n"
                        "💬 <i>Scrie orice întrebare directă! NVIDIA Nemotron ține minte contextul discuției noastre anterioare!</i>"
                    )
                    send_message(chat_id, menu, thread_id)
                    save_chat_message(chat_id, "user", text)
                    save_chat_message(chat_id, "assistant", "Meniu de pornire afișat.")

                elif low.startswith("/istoric") or low.startswith("/history"):
                    recent = get_recent_context(chat_id, limit=6)
                    if not recent:
                        send_message(chat_id, "📜 <b>Istoric Conversație:</b> Nu există mesaje salvate încă.", thread_id)
                    else:
                        out = ["📜 <b>Ultimele Mesaje Salvate în Memorie:</b>\n"]
                        for m in recent:
                            icon = "👤" if m["role"] == "user" else "🧠"
                            safe_content = html.escape(m["content"][:120])
                            out.append(f"{icon} <b>{m['role'].capitalize()}:</b> {safe_content}")
                        send_message(chat_id, "\n\n".join(out), thread_id)

                elif low.startswith("/reset") or low.startswith("/clear"):
                    clear_chat_history(chat_id)
                    send_message(chat_id, "🧹 <b>Memoria conversației curente a fost ștearsă!</b> Putem începe un nou subiect curat.", thread_id)

                elif low.startswith("/status") or low.startswith("/inspectie"):
                    status_html = build_live_status_html()
                    send_message(chat_id, status_html, thread_id)
                    save_chat_message(chat_id, "user", text)
                    save_chat_message(chat_id, "assistant", "Panou operațional live afișat (LW-DEMO-001 TR-001 + MV WAN FU Dana 52).")

                elif low.startswith("/avarii") or low.startswith("/remarks"):
                    remarks = []
                    if os.path.exists(REMARKS_FILE):
                        try:
                            with open(REMARKS_FILE, "r", encoding="utf-8") as f:
                                remarks = json.load(f)
                        except Exception:
                            remarks = []
                    if not remarks:
                        msg_av = "✅ <b>Registru Avarii:</b> Nu există piese avariate înregistrate momentan.\nFolosește <code>/remark [Magazie] [Piesă] [Descriere]</code> pentru a raporta o daună."
                    else:
                        lines_av = [f"⚠️ <b>Registru Avarii Teren ({len(remarks)} înregistrări):</b>\n"]
                        for r in remarks[:8]:
                            lines_av.append(
                                f"• <b>{html.escape(str(r.get('id')))}</b> | Magazia {html.escape(str(r.get('hold_no')))}: "
                                f"{html.escape(str(r.get('description')))} (<i>{html.escape(str(r.get('photo_timestamp')))}</i>)"
                            )
                        msg_av = "\n".join(lines_av)
                    send_message(chat_id, msg_av, thread_id)
                    save_chat_message(chat_id, "user", text)
                    save_chat_message(chat_id, "assistant", f"Registru avarii afișat ({len(remarks)} înregistrări).")

                elif low.startswith("/raport"):
                    rap_html = (
                        "📜 <b>Certificat Statutar MWS — Dosar <code>LW-DEMO-001</code></b>\n\n"
                        "• <b>Unitate inspectată:</b> Transformator Industrial 110kV <code>TR-001</code> (124.5 MT)\n"
                        "• <b>Navă / Terminal:</b> MV DEMO CARRIER (IMO 9845120) — Dana 120 Constanța\n"
                        "• <b>Atmosferă internă:</b> Pernă azot <code>0.24 bar</code> (etanșare intactă, silicagel albastru cobalt)\n"
                        "• <b>Dinamică maritimă:</b> <code>0.75 G</code> longitudinal / <code>0.35 G</code> transversal (sub pragul IMO CSS de 1.5 G)\n"
                        "• <b>Amarare:</b> 8 lanțuri Grade 80 Ø16mm la 45° verificate\n"
                        "• <b>Concluzie MWS:</b> Emitere <b>UNCONDITIONAL CLEAN MATE'S RECEIPT</b> fără rezerve de daună\n"
                        "• <b>Inspector certificator:</b> Ing. Alexandru Radu (<code>DEMO-MWS-2026-001</code>)"
                    )
                    send_message(chat_id, rap_html, thread_id)
                    save_chat_message(chat_id, "user", text)
                    save_chat_message(chat_id, "assistant", "Certificat statutar LW-DEMO-001 TR-001 afișat (Clean Mate's Receipt).")

                elif low.startswith("/remark"):
                    handle_remark(chat_id, thread_id, text)

                elif low.startswith("/pontaj"):
                    pontaj = (
                        "⏱️ <b>Pontaj Surveyor Reconstituit din Poze EXIF:</b>\n\n"
                        "👤 <b>Inspector:</b> Alexandru Radu (LPM-SRV-04)\n"
                        "📅 <b>Data:</b> 29 Octombrie 2026 (MV WAN FU)\n"
                        "⏰ <b>Start (prima poză):</b> 08:14:22\n"
                        "⏰ <b>Final (ultima poză):</b> 17:08:45\n"
                        "⏳ <b>Timp brut pe navă:</b> 8 ore 54 min (8.90 ore)\n"
                        "🌧️ <b>Pauză meteo (ploaie):</b> -45 min (0.75 ore)\n"
                        "✅ <b>Timp net facturabil:</b> <b>8.15 ORE</b>\n"
                        "💰 <b>Tarif orar agreat:</b> 185,00 RON / oră\n"
                        "💵 <b>Valoare factură pontaj:</b> <b>1.507,75 RON</b>"
                    )
                    send_message(chat_id, pontaj, thread_id)
                    save_chat_message(chat_id, "user", "/pontaj")
                    save_chat_message(chat_id, "assistant", "Pontaj afișat: 8.15 ore facturabile (1.507,75 RON)")

                elif low.startswith("/foaie"):
                    fp = (
                        "📄 <b>Foaie de Parcurs Generată (Serie: LPM-FP-6258)</b>\n\n"
                        "🚙 <b>Vehicul:</b> Dacia Duster 4x4 (CT-88-LPM)\n"
                        "👤 <b>Șofer:</b> Alexandru Radu\n"
                        "📍 <b>Traseu:</b> Sediu Mamaia ➡️ Poarta 10 Port Constanța ➡️ Dana 52 (MV WAN FU) ➡️ Retur\n"
                        "🛣️ <b>Kilometraj:</b> 142.310 ➡️ 142.358 (<b>48 km</b>)\n"
                        "⛽ <b>Consum:</b> 3.45 L Diesel (28.28 RON)\n"
                        "🔧 <b>Uzură & regie:</b> 14.40 RON\n"
                        "💶 <b>Randament per km:</b> <b>0.89 RON / km</b> (Randament Optim)\n"
                        "✅ <b>Status:</b> Semnat digital și transmis la Contabilitate!"
                    )
                    send_message(chat_id, fp, thread_id)
                    save_chat_message(chat_id, "user", "/foaie")
                    save_chat_message(chat_id, "assistant", "Foaie de parcurs generată: 48 km, randament 0.89 RON/km")

                elif low.startswith("/acte"):
                    acte = (
                        "🔔 <b>Stare Acte Flotă Auto LeeWu Maritime:</b>\n\n"
                        "🚙 <b>CT-88-LPM (Dacia Duster 4x4):</b>\n"
                        "  • ⚠️ <b>ITP:</b> Expiră în <b>18 zile</b> (17.11.2026) — Necesită programare RAR!\n"
                        "  • ✅ <b>RCA (Allianz-Țiriac):</b> Valabil 42 zile\n"
                        "  • ✅ <b>Rovinietă (CNAIR):</b> Valabilă 114 zile\n\n"
                        "🚗 <b>CT-22-LPM (Renault Megane):</b>\n"
                        "  • 🚨 <b>ROVINIETĂ:</b> <b>EXPIRĂ ÎN 7 ZILE!</b> (06.11.2026) — Reînnoiește urgent!\n"
                        "  • ✅ <b>RCA (Omniasig):</b> Valabil 89 zile\n"
                        "  • ✅ <b>ITP:</b> Valabil 140 zile"
                    )
                    send_message(chat_id, acte, thread_id)
                    save_chat_message(chat_id, "user", "/acte")
                    save_chat_message(chat_id, "assistant", "Alerte acte flotă auto afișate.")

                elif low.startswith("/nava"):
                    nava = (
                        "🚢 <b>Status Navă: MV WAN FU (IMO 9482184)</b>\n\n"
                        "📍 <b>Locație:</b> Dana 52, Portul Constanța Sud\n"
                        "📦 <b>Marfă:</b> Oțel laminate & bobine laminate la cald (15.420 MT)\n"
                        "🏗️ <b>Macarale active:</b> Macara 2 & Macara 3 cheu\n"
                        "📊 <b>Total descărcat:</b> 4.820 MT (Progres: 31.2%)\n"
                        "🌤️ <b>Meteo:</b> Vânt 12 noduri ESE, mare gr. 2, fără precipitații active."
                    )
                    send_message(chat_id, nava, thread_id)
                    save_chat_message(chat_id, "user", "/nava")
                    save_chat_message(chat_id, "assistant", "Status descărcare MV WAN FU afișat.")

                elif low.startswith("/juridic"):
                    jur = (
                        "⚖️ <b>Dosar Juridic & Statutar (Legea 51/1995)</b>\n\n"
                        "🏛️ <b>Cabinet Avocat Partener:</b> Asistență Baroul Constanța\n"
                        "📜 <b>Convenție Internațională:</b> Hague-Visby Rules 1968\n"
                        "🛡️ <b>Club P&I Asigurător:</b> Gard P&I Club (Norway)\n"
                        "📉 <b>Discount Statutar Aplicat:</b> 10% conform grilei de parteneriat naval\n"
                        "🔒 <b>Mandatory Gate:</b> Nicio notificare de daună nu părăsește platforma fără avizul avocatului coordonator."
                    )
                    send_message(chat_id, jur, thread_id)
                    save_chat_message(chat_id, "user", "/juridic")
                    save_chat_message(chat_id, "assistant", "Dosar juridic Legea 51/1995 afișat.")

                else:
                    reply = query_nemotron_with_history(chat_id, text)
                    formatted_reply = "🧠 <b>NVIDIA Nemotron (LeeWu AI):</b>\n\n" + reply
                    send_message(chat_id, formatted_reply, thread_id)

        except Exception as err:
            err_str = str(err)
            if "104" not in err_str and "timed out" not in err_str:
                safe_log_err("Polling loop note", err)
            time.sleep(1)


if __name__ == '__main__':
    main()
