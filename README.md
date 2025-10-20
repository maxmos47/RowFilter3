# Patient Dashboard (Google Sheets - Secondary) — Fixed
- แก้การเขียน L–Q ด้วย batch update ที่ใส่ชื่อชีต (ws.title!A1)
- เพิ่ม Row picker บน UI

## Setup
1) สร้าง Service Account และแชร์สเปรดชีตให้ client_email เป็น Editor
2) วาง `.streamlit/secrets.toml` ตามตัวอย่างด้านล่าง
3) `pip install -r requirements.txt` แล้ว `streamlit run streamlit_app.py`

### .streamlit/secrets.toml (ตัวอย่าง)
[gcp_service_account]
# คัดลอกค่าจากไฟล์ JSON ของ Service Account

[gsheets]
spreadsheet_id = "YOUR_SPREADSHEET_ID"
worksheet_name = "Secondary"
