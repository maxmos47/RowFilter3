
import json
from typing import Dict, List

import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="Patient Dashboard", page_icon="🩺", layout="centered")

# =========================
# CONFIG (.streamlit/secrets.toml)
# =========================
# [gas]
# webapp_url = "https://script.google.com/macros/s/AKfycb.../exec"
# token = "MY_SHARED_SECRET"     # (optional, only if you set TOKEN in GAS)
GAS_WEBAPP_URL = st.secrets.get("gas", {}).get("webapp_url", "")
TOKEN = st.secrets.get("gas", {}).get("token", "")  # optional shared secret

ALLOWED_V = ["Priority 1", "Priority 2", "Priority 3"]
YN = ["Yes", "No"]

# Keep phase-2 payload after L–Q submit (avoid nested forms + extra GET)
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
# HTTP helpers
# =========================
def _parse_json_or_show(r: requests.Response, context: str):
    try:
        return r.json()
    except json.JSONDecodeError:
        body = r.text[:800]
        st.error(f"{context} returned non-JSON (status={r.status_code}, "
                 f"content-type={r.headers.get('content-type')}). "
                 f"Body preview:\\n\\n{body}")
        raise

@st.cache_data(ttl=10, show_spinner=False)
def cached_get_row(url: str, row: int, mode: str, token: str|None=None) -> dict:
    params = {"action": "get", "row": str(row), "mode": mode}
    if token:
        params["token"] = token
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    return _parse_json_or_show(r, "GET /exec")

def gas_get_row(row: int, mode: str) -> dict:
    return cached_get_row(GAS_WEBAPP_URL, row, mode, TOKEN if TOKEN else None)

def gas_update_lq(row: int, lq_values: Dict[str, str]) -> dict:
    payload = {"action": "update_lq", "row": str(row), "lq": pd.Series(lq_values).to_json()}
    if TOKEN:
        payload["token"] = TOKEN
    r = requests.post(GAS_WEBAPP_URL, data=payload, timeout=25)
    r.raise_for_status()
    return _parse_json_or_show(r, "POST update_lq")

def gas_update_v(row: int, v_value: str) -> dict:
    payload = {"action": "update_v", "row": str(row), "value": v_value}
    if TOKEN:
        payload["token"] = TOKEN
    r = requests.post(GAS_WEBAPP_URL, data=payload, timeout=25)
    r.raise_for_status()
    return _parse_json_or_show(r, "POST update_v")

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

if not GAS_WEBAPP_URL:
    st.error("Missing GAS web app URL. Add to secrets:\\n\\n[gas]\\nwebapp_url = \"https://script.google.com/macros/s/XXX/exec\"")
    st.stop()

qp = get_query_params()
row_str = qp.get("row", "1")
mode = qp.get("mode", "edit1")  # edit1 -> L–Q; edit2 -> V; view -> final

try:
    row = int(row_str)
    if row < 1:
        row = 1
except ValueError:
    row = 1

# If user just submitted L–Q, we have "next" payload in session → no extra GET/rerun
has_inline_phase2 = st.session_state["next_after_lq"] is not None

# Initial GET only if no "next" payload
if not has_inline_phase2:
    try:
        data = gas_get_row(row=row, mode=mode)
    except Exception as e:
        st.error(f"Failed to fetch row via GAS: {e}")
        st.stop()
    if data.get("status") != "ok":
        st.error(f"GAS error: {data}")
        st.stop()
else:
    data = {"status": "ok"}  # placeholder

# Prepare dataframes by mode
if mode == "edit1" and not has_inline_phase2:
    df_AK = pd.DataFrame([data.get("A_K", {})])
    headers_LQ = data.get("headers_LQ", ["L","M","N","O","P","Q"])
    current_LQ = data.get("current_LQ", [])
elif mode == "edit2" and not has_inline_phase2:
    df_AC_RU = pd.DataFrame([data.get("A_C_R_U", {})])
    current_V = data.get("current_V", "")
elif mode == "view":
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
            res = gas_update_v(row=row, v_value=v_value)
            if res.get("status") == "ok":
                final = res.get("final", {})
                df_final = pd.DataFrame([final.get("A_C_R_V", {})])
                render_kv_grid(df_final, title="Patient", cols=2)
                st.success("Saved. Final view (no form).")
                set_query_params(row=str(row), mode="view")
            else:
                st.error(f"Update V failed: {res}")
        except Exception as e:
            st.error(f"Failed to update V via GAS: {e}")

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
                res = gas_update_lq(row=row, lq_values=selections)
                if res.get("status") == "ok":
                    # Render next phase inline (no GET, no rerun)
                    st.session_state["next_after_lq"] = res.get("next", {})
                else:
                    st.error(f"Update L–Q failed: {res}")
            except Exception as e:
                st.error(f"Failed to update L–Q via GAS: {e}")

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
                res2 = gas_update_v(row=row, v_value=v_value)
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
                st.error(f"Failed to update V via GAS: {e}")
