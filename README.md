
# Patient Dashboard — FAST (GAS + Streamlit)

## What you get
- **GAS (Code.gs)**: mode-aware (`edit1|edit2|view`), returns `next/final` on POST, header cache 120s
- **Streamlit app**: no nested forms, renders next step inline after submit, GET caching (ttl=10s)

## Deploy GAS
1. Go to https://script.google.com/ → New project
2. Paste `Code.gs`
3. Set `SHEET_ID` (already set to your sheet ID in this template)
4. (Optional) set `TOKEN` and pass it from Streamlit
5. Deploy → Web app → Execute as: **Me**; Who has access: **Anyone with the link** (or your domain)

## Streamlit secrets
```
[gas]
webapp_url = "https://script.google.com/macros/s/AKfycbYOUR_WEBAPP_ID/exec"
# token = "MY_SHARED_SECRET"
```

## Run
```
pip install -r requirements.txt
streamlit run app.py
```

## URL usage
- Start: `?row=1&mode=edit1` → A–K + L–Q (Yes/No)
- Submit L–Q → inline A–C, R–U + V (Priority 1/2/3)
- Submit V → final A–C, R–V (no form)
