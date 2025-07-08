#!/usr/bin/env python3
"""
Script per aggiornare automaticamente i secrets di GitHub Actions
"""
import requests
import json
import os
import base64
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding
from dotenv import load_dotenv

def load_environment():
    """
    Carica le variabili d'ambiente dal file .env
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    env_file = os.path.join(script_dir, ".env")
    
    if not os.path.exists(env_file):
        print(f"❌ File .env non trovato: {env_file}")
        return None
    
    load_dotenv(env_file)
    github_token = os.getenv('GITHUB_TOKEN')
    
    if not github_token:
        print("❌ GITHUB_TOKEN non trovato nel file .env")
        return None
    
    return github_token

def get_repo_info():
    """
    Determina automaticamente owner e repository dal remote git
    """
    try:
        import subprocess
        result = subprocess.run(['git', 'remote', 'get-url', 'origin'], 
                              capture_output=True, text=True, check=True)
        remote_url = result.stdout.strip()
        
        # Parsing dell'URL GitHub
        if 'github.com' in remote_url:
            if remote_url.endswith('.git'):
                remote_url = remote_url[:-4]
            if remote_url.startswith('https://github.com/'):
                repo_path = remote_url.replace('https://github.com/', '')
            elif remote_url.startswith('git@github.com:'):
                repo_path = remote_url.replace('git@github.com:', '')
            else:
                raise ValueError("URL format non riconosciuto")
            
            owner, repo = repo_path.split('/')
            return owner, repo
        else:
            raise ValueError("Non è un repository GitHub")
            
    except Exception as e:
        print(f"❌ Errore nel determinare il repository: {e}")
        return None, None

def get_public_key(owner, repo, token):
    """
    Ottiene la chiave pubblica del repository per criptare i secrets
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/actions/secrets/public-key"
    headers = {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github.v3+json'
    }
    
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        return response.json()
    else:
        print(f"❌ Errore nell'ottenere la chiave pubblica: {response.status_code}")
        print(response.text)
        return None

def encrypt_secret(public_key, secret_value):
    """
    Cripta il secret usando la chiave pubblica del repository
    """
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.primitives import hashes
    
    public_key_bytes = base64.b64decode(public_key)
    public_key_obj = serialization.load_der_public_key(public_key_bytes)
    
    encrypted = public_key_obj.encrypt(
        secret_value.encode('utf-8'),
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
    
    return base64.b64encode(encrypted).decode('utf-8')

def update_secret(owner, repo, token, secret_name, secret_value, key_id, public_key):
    """
    Aggiorna un secret del repository
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/actions/secrets/{secret_name}"
    headers = {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github.v3+json'
    }
    
    encrypted_value = encrypt_secret(public_key, secret_value)
    
    data = {
        'encrypted_value': encrypted_value,
        'key_id': key_id
    }
    
    response = requests.put(url, headers=headers, json=data)
    
    if response.status_code in [201, 204]:
        print(f"✅ Secret {secret_name} aggiornato con successo!")
        return True
    else:
        print(f"❌ Errore nell'aggiornamento del secret {secret_name}: {response.status_code}")
        print(response.text)
        return False

def main():
    """
    Funzione principale
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Carica il token GitHub
    github_token = load_environment()
    if not github_token:
        return
    
    # Determina owner e repository
    owner, repo = get_repo_info()
    if not owner or not repo:
        print("❌ Impossibile determinare owner e repository")
        return
    
    print(f"📍 Repository: {owner}/{repo}")
    
    # Percorsi dei file
    config_file = os.path.join(script_dir, "deploy_config.json")
    pem_file = os.path.join(script_dir, "my-ec2-key.pem")
    
    # Verifica esistenza dei file
    if not os.path.exists(config_file):
        print(f"❌ File di configurazione non trovato: {config_file}")
        return
    
    if not os.path.exists(pem_file):
        print(f"❌ File PEM non trovato: {pem_file}")
        return
    
    # Leggi la configurazione
    with open(config_file, 'r') as f:
        config = json.load(f)
    
    # Leggi la chiave PEM
    with open(pem_file, 'r') as f:
        pem_content = f.read()
    
    # Ottieni la chiave pubblica del repository
    public_key_info = get_public_key(owner, repo, github_token)
    if not public_key_info:
        return
    
    # Aggiorna i secrets
    success = True
    
    # Aggiorna EC2_HOST
    print(f"🔄 Aggiornando EC2_HOST con: {config['server_public_ip']}")
    if not update_secret(owner, repo, github_token, "EC2_HOST", 
                        config['server_public_ip'], 
                        public_key_info['key_id'], 
                        public_key_info['key']):
        success = False
    
    # Aggiorna EC2_SSH_KEY
    print("🔄 Aggiornando EC2_SSH_KEY...")
    if not update_secret(owner, repo, github_token, "EC2_SSH_KEY", 
                        pem_content, 
                        public_key_info['key_id'], 
                        public_key_info['key']):
        success = False
    
    if success:
        print("🚀 Tutti i secrets sono stati aggiornati con successo!")
        print("Ora puoi procedere con il push per triggerare il deploy!")
    else:
        print("❌ Alcuni secrets non sono stati aggiornati correttamente.")

if __name__ == "__main__":
    main()
