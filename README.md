# Patient Dashboard (Google Sheets - Secondary)

ดึง/เขียนข้อมูลจาก Google Sheet โดยตรง (ชีต: **Secondary**). โฟลว์:
1) โหมด `edit1` : แสดง A–K + ฟอร์มเช็คบ็อกซ์ L–Q (Yes/No)
2) โหมด `edit2` : แสดง A–C + R–U และเลือก Priority (V)
3) โหมด `view`  : แสดง A–C + R–V

## การตั้งค่า

1. สร้าง Service Account ใน Google Cloud และดาวน์โหลดไฟล์ JSON
2. แชร์สเปรดชีตให้ service account (สิทธิ์ Editor)
3. ตั้งค่า `.streamlit/secrets.toml`

ตัวอย่าง:
```
[gcp_service_account]
# คัดลอกค่าจากไฟล์ JSON ของ Service Account

[gsheets]
spreadsheet_id = "1oaQZ6OwxJUti4AIf620Hp_bCjmKwu8AF9jYTv4vs7Hc"
worksheet_name = "Secondary"
```

## รันแอป
```
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## การเปิดด้วย query params
- `?row=1&mode=edit1` (ค่าเริ่มต้น)
- `?row=1&mode=edit2`
- `?row=1&mode=view`
