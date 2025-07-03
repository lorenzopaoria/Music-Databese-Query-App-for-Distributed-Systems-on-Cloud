import os
import base64
import requests
from nacl import encoding, public
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"))

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN_API")
REPO = os.getenv("REPO")
SECRET_NAME = os.getenv("SECRET_NAME")
NEW_IP = os.getenv("NEW_IP")
PEM_PATH = os.getenv("PEM_PATH")

if not all([GITHUB_TOKEN, REPO, SECRET_NAME, NEW_IP]):
    print("Errore: variabili mancanti in .env")
    exit(1)

if not PEM_PATH or not os.path.exists(PEM_PATH):
    print("Errore: percorso PEM mancante o file non trovato.")
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

# 2. Cifra il contenuto di NEW_IP
def encrypt(public_key: str, secret_value: str) -> str:
    public_key = public.PublicKey(public_key.encode("utf-8"), encoding.Base64Encoder())
    sealed_box = public.SealedBox(public_key)
    encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
    return base64.b64encode(encrypted).decode("utf-8")

print("Valore del secret in chiaro (NEW_IP):", NEW_IP)

encrypted_value = encrypt(public_key, NEW_IP)

print("Valore cifrato che verrà inviato a GitHub:", encrypted_value)

# 3. Aggiorna il secret EC2_HOST
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

with open(PEM_PATH, "r") as f:
    pem_content = f.read()

# Cifra il contenuto della chiave PEM
encrypted_pem = encrypt(public_key, pem_content)

# Aggiorna il secret EC2_SSH_KEY (PEM)
payload_pem = {
    "encrypted_value": encrypted_pem,
    "key_id": key_id
}
resp_pem = requests.put(
    f"https://api.github.com/repos/{REPO}/actions/secrets/EC2_SSH_KEY",
    headers=headers,
    json=payload_pem
)
if resp_pem.status_code in (201, 204):
    print("Secret 'EC2_SSH_KEY' aggiornato con successo!")
else:
    print("Errore nell'aggiornamento del secret EC2_SSH_KEY:", resp_pem.text)