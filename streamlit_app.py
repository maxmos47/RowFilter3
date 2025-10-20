import json
from typing import Dict, List, Tuple

import pandas as pd
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Patient Dashboard", page_icon="🩺", layout="centered")

# =========================
# CONFIG: Google Sheets
# =========================
SPREADSHEET_ID = st.secrets.get("gsheets", {}).get("spreadsheet_id", "")
WORKSHEET_NAME = st.secrets.get("gsheets", {}).get("worksheet_name", "Secondary")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

def get_gs_client():
    if "gcp_service_account" not in st.secrets:
        st.error("Missing [gcp_service_account] in secrets.toml")
        st.stop()
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=SCOPES
    )
    return gspread.authorize(creds)

def open_ws():
    if not SPREADSHEET_ID:
        st.error("Missing [gsheets].spreadsheet_id in secrets.toml")
        st.stop()
    gc = get_gs_client()
    sh = gc.open_by_key(SPREADSHEET_ID)
    try:
        ws = sh.worksheet(WORKSHEET_NAME)
    except gspread.WorksheetNotFound:
        st.error(f"Worksheet '{WORKSHEET_NAME}' not found.")
        st.stop()
    return ws

ALLOWED_V = ["Priority 1", "Priority 2", "Priority 3"]
YN = ["Yes", "No"]

# Keep phase-2 payload after L–Q submit (avoid extra reload)
if "next_after_lq" not in st.session_state:
    st.session_state["next_after_lq"] = None

# =========================
# Helpers for query params
# =========================
def get_query_params() -> Dict[str, str]:
    try:
        q = st.query_params
        return {k: v for k, v in q.items()}
    except Exception:
        return {k: v[0] for k, v in st.experimental_get_query_params().items()}

def set_query_params(**kwargs):
    try:
        st.query_params.clear()
        st.query_params.update(kwargs)
    except Exception:
        st.experimental_set_query_params(**kwargs)

# =========================
# Utility: column helpers
# =========================
def col_letter_to_index(letter: str) -> int:
    """A -> 1, B -> 2, ..."""
    letter = letter.upper()
    result = 0
    for ch in letter:
        result = result * 26 + (ord(ch) - ord('A') + 1)
    return result

def index_to_col_letter(idx: int) -> str:
    """1 -> A, 2 -> B, ..."""
    letters = ""
    while idx > 0:
        idx, rem = divmod(idx - 1, 26)
        letters = chr(65 + rem) + letters
    return letters

# =========================
# Sheets data access layer
# =========================
def get_header_and_row(ws, row: int) -> Tuple[List[str], List[str]]:
    """Return (headers, values) where headers are row 1 and values are row N."""
    headers = ws.row_values(1)
    vals = ws.row_values(row)
    # pad vals to len(headers)
    if len(vals) < len(headers):
        vals = vals + [""] * (len(headers) - len(vals))
    return headers, vals

def slice_dict_by_cols(headers: List[str], vals: List[str], start_col: str, end_col: str) -> Dict[str, str]:
    s = col_letter_to_index(start_col) - 1  # 0-based
    e = col_letter_to_index(end_col) - 1
    out = {}
    for i in range(s, e + 1):
        if i < len(headers):
            out[headers[i]] = vals[i] if i < len(vals) else ""
    return out

def build_payloads_from_row(ws, row: int, mode: str) -> Dict:
    headers, vals = get_header_and_row(ws, row)

    # A–K
    AK = slice_dict_by_cols(headers, vals, "A", "K")
    # L–Q (6 flags)
    LQ_dict = slice_dict_by_cols(headers, vals, "L", "Q")
    headers_LQ = list(LQ_dict.keys())
    current_LQ = [LQ_dict[h] if LQ_dict[h] in YN else ("Yes" if str(LQ_dict[h]).strip().lower() == "yes" else "No") for h in headers_LQ]

    # R–U (post phase-1 view)
    RU = slice_dict_by_cols(headers, vals, "R", "U")
    # V (priority)
    Vcol_idx = col_letter_to_index("V") - 1
    current_V = vals[Vcol_idx] if Vcol_idx < len(vals) else ""

    # A–C + R–U (for edit2)
    AC = slice_dict_by_cols(headers, vals, "A", "C")
    A_C_R_U = {**AC, **RU}
    # A–C + R–V (for final)
    RV = slice_dict_by_cols(headers, vals, "R", "V")
    A_C_R_V = {**AC, **RV}

    data = {"status": "ok"}
    if mode == "edit1":
        data["A_K"] = AK
        data["headers_LQ"] = headers_LQ
        data["current_LQ"] = current_LQ
    elif mode == "edit2":
        data["A_C_R_U"] = A_C_R_U
        data["current_V"] = current_V
    elif mode == "view":
        data["A_C_R_V"] = A_C_R_V
    return data

def update_LQ(ws, row: int, lq_values: Dict[str, str]) -> Dict:
    # Find header row, map header -> col
    headers = ws.row_values(1)
    updates = []
    for h, v in lq_values.items():
        if h in headers:
            col_idx = headers.index(h) + 1  # 1-based
            a1 = f"{index_to_col_letter(col_idx)}{row}"
            updates.append({"range": a1, "values": [[v]]})
    if updates:
        ws.spreadsheet.values_batch_update(
            body={
                "valueInputOption": "RAW",
                "data": updates
            }
        )
    # Build "next" payload (same row after update)
    data_next = build_payloads_from_row(ws, row, mode="edit2")
    return {"status": "ok", "next": data_next}

def update_V(ws, row: int, v_value: str) -> Dict:
    # column V
    V_idx = col_letter_to_index("V")
    a1 = f"{index_to_col_letter(V_idx)}{row}"
    ws.update_acell(a1, v_value)
    # Build final payload
    headers, vals = get_header_and_row(ws, row)
    AC = slice_dict_by_cols(headers, vals, "A", "C")
    RV = slice_dict_by_cols(headers, vals, "R", "V")
    return {"status": "ok", "final": {"A_C_R_V": {**AC, **RV}}}

# =========================
# Card UI (mobile-friendly)
# =========================
st.markdown("""
<style>
.kv-card{border:1px solid #e5e7eb;padding:12px;border-radius:14px;margin-bottom:10px;box-shadow:0 1px 4px rgba(0,0,0,0.06);background:#fff;}
.kv-label{font-size:0.9rem;color:#6b7280;margin-bottom:2px;}
.kv-value{font-size:1.05rem;font-weight:600;word-break:break-word;}
@media (max-width: 640px){
  .kv-card{padding:12px;}
  .kv-value{font-size:1.06rem;}
}
</style>
""", unsafe_allow_html=True)

def _pairs_from_row(df_one_row: pd.DataFrame) -> List[tuple[str, str]]:
    s = df_one_row.iloc[0]
    pairs = []
    for col in df_one_row.columns:
        val = s[col]
        if pd.isna(val):
            val = ""
        pairs.append((str(col), str(val)))
    return pairs

def render_kv_grid(df_one_row: pd.DataFrame, title: str = "", cols: int = 2):
    if title:
        st.subheader(title)
    items = _pairs_from_row(df_one_row)
    n = len(items)
    for i in range(0, n, cols):
        row_items = items[i:i+cols]
        col_objs = st.columns(len(row_items))
        for c, (label, value) in zip(col_objs, row_items):
            with c:
                st.markdown(
                    f"""
                    <div class="kv-card">
                      <div class="kv-label">{label}</div>
                      <div class="kv-value">{value if value!='' else '-'}</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

# =========================
# Main UI
# =========================
st.markdown("### 🩺 Patient Information")

qp = get_query_params()
row_str = qp.get("row", "1")
mode = qp.get("mode", "edit1")  # edit1 -> L–Q; edit2 -> V; view -> final

try:
    row = int(row_str)
    if row < 1:
        row = 1
except ValueError:
    row = 1

ws = open_ws()
has_inline_phase2 = st.session_state["next_after_lq"] is not None

# Prepare dataframes by mode
if mode == "edit1" and not has_inline_phase2:
    try:
        data = build_payloads_from_row(ws, row=row, mode="edit1")
    except Exception as e:
        st.error(f"Failed to read sheet: {e}")
        st.stop()
    df_AK = pd.DataFrame([data.get("A_K", {})])
    headers_LQ = data.get("headers_LQ", ["L","M","N","O","P","Q"])
    current_LQ = data.get("current_LQ", [])
elif mode == "edit2" and not has_inline_phase2:
    try:
        data = build_payloads_from_row(ws, row=row, mode="edit2")
    except Exception as e:
        st.error(f"Failed to read sheet: {e}")
        st.stop()
    df_AC_RU = pd.DataFrame([data.get("A_C_R_U", {})])
    current_V = data.get("current_V", "")
elif mode == "view":
    try:
        data = build_payloads_from_row(ws, row=row, mode="view")
    except Exception as e:
        st.error(f"Failed to read sheet: {e}")
        st.stop()
    df_AC_RV = pd.DataFrame([data.get("A_C_R_V", {})])

# ============ Modes ============
if mode == "view":
    render_kv_grid(df_AC_RV, title="Patient", cols=2)
    st.success("Triage completed")
    if st.button("Triage again"):
        st.session_state["next_after_lq"] = None
        set_query_params(row=str(row), mode="edit1")
        st.rerun()

elif mode == "edit2" and not has_inline_phase2:
    render_kv_grid(df_AC_RU, title="Patient", cols=2)
    st.markdown("#### Secondary Triage")
    idx = ALLOWED_V.index(current_V) if current_V in ALLOWED_V else 0
    with st.form("form_v", border=True):
        v_value = st.selectbox("Select Triage priority", ALLOWED_V, index=idx)
        submitted = st.form_submit_button("Submit")
    if submitted:
        try:
            res = update_V(ws, row=row, v_value=v_value)
            if res.get("status") == "ok":
                final = res.get("final", {})
                df_final = pd.DataFrame([final.get("A_C_R_V", {})])
                render_kv_grid(df_final, title="Patient", cols=2)
                st.success("Saved. Final view (no form).")
                set_query_params(row=str(row), mode="view")
            else:
                st.error(f"Update V failed: {res}")
        except Exception as e:
            st.error(f"Failed to update V: {e}")

else:
    # Phase 1: A–K + L–Q form
    if not has_inline_phase2:
        render_kv_grid(df_AK, title="Patient", cols=2)
        st.markdown("#### Treatment")
        l_col, r_col = st.columns(2)
        selections = {}
        curr_vals = current_LQ if current_LQ and len(current_LQ) == 6 else ["No"] * 6

        with st.form("form_lq", border=True):
            with l_col:
                for i, label in enumerate(headers_LQ[:3]):
                    default = True if curr_vals[i] == "Yes" else False
                    chk = st.checkbox(f"{label}", value=default)
                    selections[label] = "Yes" if chk else "No"
            with r_col:
                for i, label in enumerate(headers_LQ[3:6], start=3):
                    default = True if curr_vals[i] == "Yes" else False
                    chk = st.checkbox(f"{label}", value=default)
                    selections[label] = "Yes" if chk else "No"

            submitted = st.form_submit_button("Submit")

        if submitted:
            try:
                res = update_LQ(ws, row=row, lq_values=selections)
                if res.get("status") == "ok":
                    st.session_state["next_after_lq"] = res.get("next", {})
                else:
                    st.error(f"Update L–Q failed: {res}")
            except Exception as e:
                st.error(f"Failed to update L–Q: {e}")

    # Inline phase 2 after L–Q submit
    nxt = st.session_state.get("next_after_lq")
    if nxt:
        df_ru = pd.DataFrame([nxt.get("A_C_R_U", {})])
        render_kv_grid(df_ru, title="Patient", cols=2)

        st.markdown("#### Secondary Triage")
        current_V2 = nxt.get("current_V", "")
        idx2 = ALLOWED_V.index(current_V2) if current_V2 in ALLOWED_V else 0
        with st.form("form_v_inline", border=True):
            v_value = st.selectbox("Select Triage priority", ALLOWED_V, index=idx2)
            v_submitted = st.form_submit_button("Submit")

        if v_submitted:
            try:
                res2 = update_V(ws, row=row, v_value=v_value)
                if res2.get("status") == "ok":
                    final = res2.get("final", {})
                    df_final = pd.DataFrame([final.get("A_C_R_V", {})])
                    render_kv_grid(df_final, title="Patient", cols=2)
                    st.success("Triage เรียบร้อย")
                    st.session_state["next_after_lq"] = None
                    set_query_params(row=str(row), mode="view")
                else:
                    st.error(f"Update V failed: {res2}")
            except Exception as e:
                st.error(f"Failed to update V: {e}")
