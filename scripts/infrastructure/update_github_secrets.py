import requests
import json
import os
import base64
import subprocess
from nacl import public
from dotenv import load_dotenv

# caricamento variabili da .env
def load_environment():

    # percorso al file .env
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(script_dir))
    env_file = os.path.join(project_root, ".env")
    
    # verifica dell'esistenza del file .env
    if not os.path.exists(env_file):
        print(f"[ERROR] File .env non trovato: {env_file}")
        return None
    
    # caricamento delle variabili d'ambiente dal file
    load_dotenv(env_file)
    github_token = os.getenv('GITHUB_TOKEN')
    
    # validazione del token GitHub
    if not github_token:
        print("[ERROR] Variabile GITHUB_TOKEN non trovata nel file .env")
        return None
    
    return github_token

# recupero delle informazioni del repository GitHub
def get_repo_info():

    try: 
        # esecuzione del comando git per ottenere l'URL del repository remoto
        result = subprocess.run(['git', 'remote', 'get-url', 'origin'], capture_output=True, text=True, check=True)
        remote_url = result.stdout.strip()

        # verifica che sia un repository GitHub
        if 'github.com' in remote_url:
            # rimozione dell'estensione .git se presente
            if remote_url.endswith('.git'):
                remote_url = remote_url[:-4]
            
            # gestione dei diversi formati di URL GitHub
            if remote_url.startswith('https://github.com/'):
                repo_path = remote_url.replace('https://github.com/', '')
            elif remote_url.startswith('git@github.com:'):
                repo_path = remote_url.replace('git@github.com:', '')
            else:
                raise ValueError("URL format non riconosciuto")
            
            # estrazione di owner e repository name
            owner, repo = repo_path.split('/')
            return owner, repo
        else:
            raise ValueError("Non è un repository GitHub")
            
    except Exception as e:
        print(f"[ERROR] Impossibile determinare il repository: {e}")
        return None, None

# recupero della chiave pubblica del repository
def get_public_key(owner, repo, token):

    # costruzione dell'URL per l'API GitHub
    url = f"https://api.github.com/repos/{owner}/{repo}/actions/secrets/public-key"
    headers = {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github.v3+json'
    }
    
    # richiesta alla API GitHub
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        return response.json()
    else:
        print(f"[ERROR] Impossibile ottenere la chiave pubblica dal repository - status {response.status_code}")
        print(response.text)
        return None

# crittografia del secret con la chiave pubblica
def encrypt_secret(public_key, secret_value):

    # decodifica della chiave pubblica da base64
    public_key_bytes = base64.b64decode(public_key)
    
    # creazione dell'oggetto chiave pubblica usando PyNaCl
    public_key_obj = public.PublicKey(public_key_bytes)
    
    # creazione di una SealedBox per la crittografia
    sealed_box = public.SealedBox(public_key_obj)
    
    # crittografia del secret
    encrypted = sealed_box.encrypt(secret_value.encode('utf-8'))
    
    # restituzione del valore crittografato in base64
    return base64.b64encode(encrypted).decode('utf-8')

# aggiornamento si un secret
def update_secret(owner, repo, token, secret_name, secret_value, key_id, public_key):

    # costruzione dell'URL per l'aggiornamento del secret
    url = f"https://api.github.com/repos/{owner}/{repo}/actions/secrets/{secret_name}"
    headers = {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github.v3+json'
    }
    
    # crittografia del valore del secret
    encrypted_value = encrypt_secret(public_key, secret_value)
    
    # preparazione dei dati per la richiesta
    data = {
        'encrypted_value': encrypted_value,
        'key_id': key_id
    }
    
    # invio della richiesta di aggiornamento
    response = requests.put(url, headers=headers, json=data)
    
    if response.status_code in [201, 204]:
        print(f"[SUCCESS] Secret '{secret_name}' aggiornato correttamente.")
        return True
    else:
        print(f"[ERROR] Aggiornamento del secret '{secret_name}' fallito - status {response.status_code}")
        print(response.text)
        return False

def main():

    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # STEP 1: caricamento del token GitHub dall'ambiente
    github_token = load_environment()
    if not github_token:
        return
    
    # STEP 2: recupero delle informazioni del repository Git
    owner, repo = get_repo_info()
    if not owner or not repo:
        print("[ERROR] Impossibile determinare owner e repository.")
        return
    
    print(f"[INFO] Repository selezionato: {owner}/{repo}")
    
    # STEP 3: verifica dell'esistenza dei file necessari
    config_file = os.path.join(script_dir, "deploy_config.json")
    pem_file = os.path.join(script_dir, "my-ec2-key.pem")
    
    if not os.path.exists(config_file):
        print(f"[ERROR] File di configurazione non trovato: {config_file}")
        return
    
    if not os.path.exists(pem_file):
        print(f"[ERROR] File PEM non trovato: {pem_file}")
        return
    
    # STEP 4: lettura delle configurazioni e della chiave privata
    with open(config_file, 'r') as f:
        config = json.load(f)
    
    with open(pem_file, 'r') as f:
        pem_content = f.read()
    
    # STEP 5: recupero della chiave pubblica del repository
    public_key_info = get_public_key(owner, repo, github_token)
    if not public_key_info:
        return
    
    success = True
    
    # STEP 6: aggiornamento del secret EC2_HOST
    print(f"[STEP] Aggiornamento del secret EC2_HOST con valore: {config['server_public_ip']}")
    if not update_secret(owner, repo, github_token, "EC2_HOST", 
                        config['server_public_ip'], 
                        public_key_info['key_id'], 
                        public_key_info['key']):
        success = False
    
    # STEP 7: aggiornamento del secret EC2_SSH_KEY
    print("[STEP] Aggiornamento del secret EC2_SSH_KEY in corso...")
    if not update_secret(owner, repo, github_token, "EC2_SSH_KEY", 
                        pem_content, 
                        public_key_info['key_id'], 
                        public_key_info['key']):
        success = False
    
    # STEP 8: verifica del risultato finale
    if success:
        print("[SUCCESS] Tutti i secrets sono stati aggiornati correttamente!")
        print("[INFO] Ora puoi procedere con il push per triggerare il deploy!")
    else:
        print("[ERROR] Alcuni secrets non sono stati aggiornati correttamente.")

if __name__ == "__main__":
    main()