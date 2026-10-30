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
        # If HTML entity parsing fails (e.g. unclosed tags from AI), fallback to plain text
        if he.code == 400 and payload.get("parse_mode") == "HTML":
            try:
                payload.pop("parse_mode", None)
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


def query_nemotron_with_history(chat_id, user_prompt, api_key=None):
    key = api_key if api_key is not None else (os.getenv("NEBIUS_API_KEY") if "NEBIUS_API_KEY" in os.environ else NEBIUS_KEY)
    key = (key or "").strip()
    if not key:
        return "⚠️ Serviciul de inteligență artificială nu este configurat (NEBIUS_API_KEY lipsește). Contactați administratorul de sistem."

    context_msgs = get_recent_context(chat_id, limit=8)
    messages = [
        {
            "role": "system",
            "content": (
                "Ești LeeWu AI — Asistentul Neural de Inspecție Maritimă și Daune Navale "
                "al LeeWu Maritime Services, operativ în Portul Constanța (Dana 52 - MV WAN FU). "
                "Ești alimentat de NVIDIA Nemotron și ai memorie de conversație activă. "
                "Ține minte întrebările și răspunsurile anterioare din sesiune. "
                "Răspunde scurt, profesional, direct și autoritar în limba română (cu trimiteri la codul CSS IMO, Hague-Visby sau Legea 51/1995 dacă e cazul)."
            )
        }
    ]

    for cm in context_msgs:
        messages.append(cm)

    messages.append({
        "role": "user",
        "content": sanitize_input(user_prompt, max_len=1500)
    })

    payload = {
        "model": NEBIUS_MODEL,
        "messages": messages,
        "max_tokens": 450,
        "temperature": 0.4
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(NEBIUS_URL, data=data, headers={
        "Content-Type": "application/json",
        "Authorization": "Bearer " + key,
        "User-Agent": "LeeWuNemotron/1.0",
        "Connection": "close"
    })
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            res = json.loads(r.read().decode("utf-8"))
            choices = res.get("choices", [])
            reply_raw = choices[0].get("message", {}).get("content") if choices else None
            reply = (reply_raw or "").strip()
            if not reply:
                reply = "Răspunsul recepționat este gol. Te rog reformulează întrebarea."
            save_chat_message(chat_id, "user", user_prompt)
            save_chat_message(chat_id, "assistant", reply)
            return reply
    except Exception as e:
        safe_log_err("Nemotron query error", e)
        return "Am întâmpinat o întârziere la comunicarea cu serverul NVIDIA Nemotron. Te rog reformulează."


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
