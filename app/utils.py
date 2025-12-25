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
BOT_LINK = os.getenv("BOT_LINK")
PAYMENT_TOKEN = os.getenv("PAYMENT_TOKEN")

# Используем один сервер
BASE_URL = os.getenv("BASE_URL")
SUB_URL = os.getenv("SUB_URL")
USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")
PASSPHRASE = os.getenv("PASSPHRASE")

SERVICE_ID = os.getenv("SERVICE_ID")

db = sqlite3.connect('users.db')
cursor = db.cursor()

cursor.execute("""CREATE TABLE IF NOT EXISTS trials (
               user_id BIGINT PRIMARY KEY,
               vpn_subscribe TEXT,
               start_date TEXT
)""")          # Решить со start_date

cursor.execute("""CREATE TABLE IF NOT EXISTS users (
               user_id BIGINT PRIMARY KEY,
               balance INTEGER DEFAULT 0,
               referrer_id BIGINT NULL,
               created_at TIMESTAMP
)""")          # Таблица для всех пользователей

cursor.execute("""CREATE TABLE IF NOT EXISTS refs (
               referrer_id BIGINT,
               invited_id BIGINT,
               bonus INTEGER,
               created_at TIMESTAMP
)""")          # Таблица для пользователей УЖЕ учавствующих в реферальной программе

db.commit()
db.close()

def user_has_referrer(user_id: int) -> bool:
    with sqlite3.connect("users.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM users WHERE user_id = ? AND referrer_id IS NOT NULL", (user_id,)) # Нужно как-то реализовать проверку вот здесь
        return cursor.fetchone() is not None
    
def user_has_invites(user_id: int) -> bool:
    with sqlite3.connect("users.db") as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM refs WHERE referrer_id = ? LIMIT 1",
            (user_id,)
        )
        return cursor.fetchone() is not None
    
def get_balance(user_id):
    with sqlite3.connect("users.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        if result is not None:
            balance = result[0]
        else:
            balance = 0
        return balance

    
def add_balance(user_id, balance):
    with sqlite3.connect("users.db") as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET balance = balance + ? WHERE user_id = ?",
            (balance, user_id)
        )

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
    # Авторизация
    login_data = {
        "username": USERNAME,
        "password": PASSWORD
    }

    session = requests.Session()
    session.verify = False
    requests.packages.urllib3.disable_warnings()

    r = session.post(f"{BASE_URL}/login", json=login_data)
    print("Login status:", r.status_code)

    # Создание клиента
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

    r = session.post(f"{BASE_URL}/panel/api/inbounds/addClient", json=payload)
    print(r.status_code)

    subscribe_link = f"{SUB_URL}/{PASSPHRASE}/sub/{subscription_generated}"
    return subscribe_link
