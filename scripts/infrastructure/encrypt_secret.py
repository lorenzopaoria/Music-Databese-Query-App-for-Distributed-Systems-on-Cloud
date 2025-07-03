import os
import base64
import requests
from nacl import encoding, public
from dotenv import load_dotenv

# Carica variabili da .env
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO = os.getenv("REPO")
SECRET_NAME = os.getenv("SECRET_NAME")
NEW_IP = os.getenv("NEW_IP")

if not all([GITHUB_TOKEN, REPO, SECRET_NAME, NEW_IP]):
    print("Errore: variabili mancanti in .env")
    exit(1)

headers = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json"
}

# 1. Recupera la public key e key_id
resp = requests.get(
    f"https://api.github.com/repos/{REPO}/actions/secrets/public-key",
    headers=headers
)
if resp.status_code != 200:
    print("Errore nel recupero della public key:", resp.text)
    exit(1)

data = resp.json()
public_key = data["key"]
key_id = data["key_id"]

# 2. Cifra il nuovo IP
def encrypt(public_key: str, secret_value: str) -> str:
    public_key = public.PublicKey(public_key.encode("utf-8"), encoding.Base64Encoder())
    sealed_box = public.SealedBox(public_key)
    encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
    return base64.b64encode(encrypted).decode("utf-8")

encrypted_value = encrypt(public_key, NEW_IP)

# 3. Aggiorna il secret
payload = {
    "encrypted_value": encrypted_value,
    "key_id": key_id
}
resp = requests.put(
    f"https://api.github.com/repos/{REPO}/actions/secrets/{SECRET_NAME}",
    headers=headers,
    json=payload
)
if resp.status_code in (201, 204):
    print(f"Secret '{SECRET_NAME}' aggiornato con successo!")
else:
    print("Errore nell'aggiornamento del secret:", resp.text)