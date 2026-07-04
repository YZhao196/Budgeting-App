"""Live bank sync via an open-banking aggregator (Basiq — Australia).

WHY THIS SHAPE
--------------
Live ANZ / ANZ Plus data is ONLY available through the Consumer Data Right
(CDR / open banking).  To pull CDR data you must be an Accredited Data Recipient,
which a personal desktop app cannot be.  Licensed aggregators (Basiq, Frollo,
Adatree, …) hold that accreditation and expose an API.  Basiq is the common
Australian choice and supports ANZ and ANZ Plus.

THE SAFETY BOUNDARY (important):
The bank login happens on **ANZ's own official page** during the CDR consent
flow.  Your ANZ password is NEVER entered into this app.  The only credential
this app stores is *your own Basiq developer API key* (not a bank credential).

WHAT YOU MUST DO TO ACTIVATE IT
-------------------------------
1. Create a free developer account at https://dashboard.basiq.io
2. Create an Application and copy its **API key**.
3. Paste the API key in  Settings → Live bank sync.
4. Click "Connect ANZ" → a consent link opens; you authenticate on ANZ's site
   and pick the accounts to share.  Basiq returns a user id (store it).
5. Click "Sync now" — transactions flow through the same import + auto-categorise
   pipeline as the CSV importer.

CAVEAT: the live HTTP calls below are written to Basiq's documented API shape but
were NOT run against a real account in development.  Verify the first end-to-end
sync, and adjust field names if Basiq's API has changed.  Endpoints: au-api.basiq.io.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://au-api.basiq.io"
VERSION = "3.0"


class BankSyncError(Exception):
    pass


def _http(method: str, url: str, headers: dict, body: bytes | None = None) -> dict:
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8") or "{}"
            return json.loads(raw)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        raise BankSyncError(f"HTTP {e.code} {e.reason}: {detail}")
    except urllib.error.URLError as e:
        raise BankSyncError(f"Network error: {e.reason}")
    except json.JSONDecodeError:
        raise BankSyncError("Unexpected (non-JSON) response from the aggregator.")


def server_token(api_key: str) -> str:
    """Exchange the Basiq API key for a short-lived server access token.
    POST /token  (Authorization: Basic <api_key>, scope=SERVER_ACCESS)."""
    if not api_key:
        raise BankSyncError("No Basiq API key configured.")
    headers = {
        "Authorization": f"Basic {api_key}",
        "Content-Type": "application/x-www-form-urlencoded",
        "basiq-version": VERSION,
    }
    body = urllib.parse.urlencode({"scope": "SERVER_ACCESS"}).encode()
    data = _http("POST", f"{BASE}/token", headers, body)
    tok = data.get("access_token")
    if not tok:
        raise BankSyncError("No access_token in token response.")
    return tok


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Accept": "application/json",
            "Content-Type": "application/json", "basiq-version": VERSION}


def create_user(token: str, email: str = "", mobile: str = "") -> str:
    """POST /users → returns the new user's id."""
    payload = {k: v for k, v in (("email", email), ("mobile", mobile)) if v}
    data = _http("POST", f"{BASE}/users", _auth_headers(token),
                 json.dumps(payload or {"email": "user@example.com"}).encode())
    uid = data.get("id")
    if not uid:
        raise BankSyncError("No user id returned.")
    return uid


def consent_url(token: str, user_id: str) -> str:
    """Create a CDR consent / connect link the user opens to authenticate ON ANZ.
    POST /users/{id}/auth_link → returns the hosted consent URL."""
    data = _http("POST", f"{BASE}/users/{user_id}/auth_link",
                 _auth_headers(token), b"{}")
    url = (data.get("links", {}) or {}).get("public") or data.get("url")
    if not url:
        raise BankSyncError("No consent URL returned.")
    return url


def fetch_transactions(token: str, user_id: str, limit: int = 500) -> list:
    """GET /users/{id}/transactions → list of Basiq transaction objects."""
    url = f"{BASE}/users/{user_id}/transactions?limit={limit}"
    data = _http("GET", url, _auth_headers(token))
    return data.get("data", [])


def fetch_accounts(token: str, user_id: str) -> list:
    """GET /users/{id}/accounts → account objects (balances)."""
    data = _http("GET", f"{BASE}/users/{user_id}/accounts", _auth_headers(token))
    return data.get("data", [])


def to_app_transactions(basiq_txns: list) -> list:
    """Map Basiq transactions into the app's {date, amount, description} shape
    (negative = money out — same convention as the CSV importer)."""
    out = []
    for t in basiq_txns:
        d = (t.get("postDate") or t.get("transactionDate") or "")[:10]
        if not d:
            continue
        try:
            amt = float(t.get("amount", 0))
        except (TypeError, ValueError):
            continue
        out.append({"date": d, "amount": amt,
                    "description": t.get("description", "") or "(no description)"})
    return out


def sync(store, api_key: str, user_id: str, account: str = "ANZ (live)") -> dict:
    """Pull transactions for a connected user and import them via the store's
    existing dedup + auto-categorise pipeline.  Returns the import summary."""
    if not user_id:
        raise BankSyncError("Not connected yet — use “Connect ANZ” first.")
    token = server_token(api_key)
    raw = fetch_transactions(token, user_id)
    txns = to_app_transactions(raw)
    return store.import_transactions(txns, account=account)
