import requests
import json
import os
import base64
from nacl import encoding, public
from dotenv import load_dotenv

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, "..", ".."))
env_path = os.path.join(project_root, ".env")
load_dotenv(env_path)

# connfigurazione da env
DEPLOY_CONFIG_FILE = os.getenv('DEPLOY_CONFIG_FILE', 'deploy_config.json')

def print_info(message):

    print(f"[INFO] {message}")

def print_success(message):

    print(f"[SUCCESS] {message}")

def print_error(message):

    print(f"[ERROR] {message}")

def print_step(message):

    print(f"[STEP] {message}")

def load_environment():

    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(script_dir))
    env_file = os.path.join(project_root, ".env")
    
    if not os.path.exists(env_file):
        print_error(f"File .env non trovato: {env_file}")
        return None
    
    load_dotenv(env_file)
    github_token = os.getenv('GITHUB_TOKEN')
    
    if not github_token:
        print_error("Variabile GITHUB_TOKEN non trovata nel file .env")
        return None
    
    return github_token

def get_repo_info():

    try:
        import subprocess
        result = subprocess.run(['git', 'remote', 'get-url', 'origin'], capture_output=True, text=True, check=True)
        remote_url = result.stdout.strip()

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
        print_error(f"Impossibile determinare il repository: {e}")
        return None, None

def make_github_request(url, headers, method='GET', json_data=None):

    if method == 'GET':
        response = requests.get(url, headers=headers)
    elif method == 'PUT':
        response = requests.put(url, headers=headers, json=json_data)
    else:
        raise ValueError(f"Metodo HTTP non supportato: {method}")
    
    if response.status_code in [200, 201, 204]:
        return response
    else:
        print_error(f"Richiesta GitHub API fallita - status {response.status_code}")
        print(response.text)
        return None

def get_public_key(owner, repo, token):

    url = f"https://api.github.com/repos/{owner}/{repo}/actions/secrets/public-key"
    headers = {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github.v3+json'
    }
    
    response = make_github_request(url, headers)
    return response.json() if response else None

def encrypt_secret(public_key, secret_value):

    public_key_bytes = base64.b64decode(public_key)
    public_key_obj = public.PublicKey(public_key_bytes)
    sealed_box = public.SealedBox(public_key_obj)
    encrypted = sealed_box.encrypt(secret_value.encode('utf-8'))

    return base64.b64encode(encrypted).decode('utf-8')

def update_secret(owner, repo, token, secret_name, secret_value, key_id, public_key):

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
    
    response = make_github_request(url, headers, method='PUT', json_data=data)
    
    if response:
        print_success(f"Secret '{secret_name}' aggiornato correttamente.")
        return True
    else:
        print_error(f"Aggiornamento del secret '{secret_name}' fallito")
        return False

def read_config_files():

    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_file = os.path.join(script_dir, "deploy_config.json")
    pem_file = os.path.join(script_dir, "my-ec2-key.pem")
    
    if not os.path.exists(config_file):
        print_error(f"File di configurazione non trovato: {config_file}")
        return None, None
    
    if not os.path.exists(pem_file):
        print_error(f"File PEM non trovato: {pem_file}")
        return None, None
    
    with open(config_file, 'r') as f:
        config = json.load(f)
    
    with open(pem_file, 'r') as f:
        pem_content = f.read()
    
    return config, pem_content

def update_github_secrets(owner, repo, token, config, pem_content):

    public_key_info = get_public_key(owner, repo, token)
    if not public_key_info:
        return False
    
    success = True
    
    # Update EC2_HOST
    print_step(f"Aggiornamento del secret EC2_HOST con valore: {config['server_public_ip']}")
    if not update_secret(owner, repo, token, "EC2_HOST", 
                        config['server_public_ip'], 
                        public_key_info['key_id'], 
                        public_key_info['key']):
        success = False
    
    # Update EC2_SSH_KEY
    print_step("Aggiornamento del secret EC2_SSH_KEY in corso...")
    if not update_secret(owner, repo, token, "EC2_SSH_KEY", 
                        pem_content, 
                        public_key_info['key_id'], 
                        public_key_info['key']):
        success = False
    
    return success

def main():

    github_token = load_environment()
    if not github_token:
        return
    
    owner, repo = get_repo_info()
    if not owner or not repo:
        print_error("Impossibile determinare owner e repository.")
        return
    
    print_info(f"Repository selezionato: {owner}/{repo}")
    
    config, pem_content = read_config_files()
    if not config or not pem_content:
        return
    
    success = update_github_secrets(owner, repo, github_token, config, pem_content)
    
    if success:
        print_success("Tutti i secrets sono stati aggiornati correttamente!")
        print_info("Ora puoi procedere con il push per triggerare il deploy!")
    else:
        print_error("Alcuni secrets non sono stati aggiornati correttamente.")

if __name__ == "__main__":
    main()
