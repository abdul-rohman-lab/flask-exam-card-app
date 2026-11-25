import requests
import re
from flask import current_app

def send_wa(target_phone, message):
    token = current_app.config.get('FONNTE_TOKEN')
    
    if not token or token == '': 
        print("Token Fonnte belum diset di .env")
        return False
    if not target_phone:
        print("Nomor HP kosong.")
        return False
        
    # Bersihkan nomor HP (hapus spasi, strip, dll)
    phone = re.sub(r'\D', '', target_phone)
    if phone.startswith('0'):
        phone = '62' + phone[1:]
    elif phone.startswith('8'):
        phone = '62' + phone

    url = "https://api.fonnte.com/send"
    headers = {"Authorization": token}
    data = {
        "target": phone,
        "message": message
    }
    
    try:
        response = requests.post(url, headers=headers, data=data)
        res_data = response.json()
        if res_data.get('status') == True:
            return True
        else:
            print(f"Fonnte Error: {res_data}")
            return False
    except Exception as e:
        print(f"Gagal kirim WA: {e}")
        return False