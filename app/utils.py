import requests
import sqlite3
import base64
import uuid
import json
import os
import random
import string
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
PAYMENT_TOKEN = os.getenv("PAYMENT_TOKEN")

SUB_PORT = 3196

db = sqlite3.connect('users.db')
cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS server_state (
    id INTEGER PRIMARY KEY,
    last_server INTEGER
)
""")
cursor.execute("INSERT OR IGNORE INTO server_state (id, last_server) VALUES (1, 1)")

cursor.execute("""CREATE TABLE IF NOT EXISTS trials (
               user_id  PRIMARY KEY,
               vpn_subscribe TEXT,
               start_date TEXT
)""")

db.commit()
db.close()

def get_next_server():
    with sqlite3.connect("users.db") as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT last_server FROM server_state WHERE id = 1")
        last_server = cursor.fetchone()[0]

        # переключаем между 1 и 2
        next_server = 2 if last_server == 1 else 1

        cursor.execute("UPDATE server_state SET last_server = ? WHERE id = 1", (next_server,))
        conn.commit()

        return next_server
    
def check_users_gift(user_id):
    with sqlite3.connect("users.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM trials WHERE user_id = ?", (user_id,))
        return cursor.fetchone() is not None
    
def random_email(length=10):
    chars = string.ascii_lowercase + string.digits
    name = ''.join(random.choice(chars) for _ in range(length))
    return f"{name}"
    
def create_a_subscribe_link(expiryTime):
    server = get_next_server()

    if server == 1:
        BASE_URL_USE = os.getenv("BASE_URL_1")
        BASE_IP_USE = os.getenv("BASE_IP_1")
        USERNAME_USE = os.getenv("USERNAME_1")
        PASSWORD_USE = os.getenv("PASSWORD_1")
        PASSPHRASE_USE = os.getenv("PASSPHRASE_1")
    else:
        BASE_URL_USE = os.getenv("BASE_URL_2")
        BASE_IP_USE = os.getenv("BASE_IP_2")
        USERNAME_USE = os.getenv("USERNAME_2")
        PASSWORD_USE = os.getenv("PASSWORD_2")
        PASSPHRASE_USE = os.getenv("PASSPHRASE_2")
            
    print("Client assigned to server:", server)

    # Creating and getting a client
    login_data = {
        "username": USERNAME_USE,
        "password": PASSWORD_USE
    }

    session = requests.Session()
    session.verify = False
    requests.packages.urllib3.disable_warnings()

    r = session.post(f"{BASE_URL_USE}/login", json=login_data)
    print("Login status:", r.status_code)

    new_uuid = str(uuid.uuid4())
    email_generated = random_email()
    subscription_generated = base64.b32encode(os.urandom(10)).decode().lower()[:16]

    client = {
        "enable": True,
        "email": email_generated,
        "id": new_uuid,
        "subId": subscription_generated,
        "flow": "xtls-rprx-vision",
        "limitIp": 0,
        "totalGB": 0,
        "expiryTime": expiryTime
    }

    settings_str = json.dumps({"clients": [client]})

    payload = {
        "id": 1,
        "settings": settings_str
    }

    r = session.post(f"{BASE_URL_USE}/panel/api/inbounds/addClient", json=payload)

    subscribe_link = f"{BASE_IP_USE}:{SUB_PORT}/{PASSPHRASE_USE}/sub/{subscription_generated}"
    return subscribe_link