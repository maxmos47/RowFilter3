# Patient Dashboard (Row via URL, no selector)
- ลบตัวเลือกแถวบนหน้า (row selector) ออก
- แปลความหมาย URL `?row=1` ให้เท่ากับแถวที่ 2 ในชีต (header อยู่แถว 1) ⇒ sheet_row = display_row + 1

ตัวอย่างลิงก์:
- `?row=1&mode=edit1` → ใช้ข้อมูลที่แถว 2 ในชีต
- `?row=5&mode=edit2` → ใช้ข้อมูลที่แถว 6 ในชีต
