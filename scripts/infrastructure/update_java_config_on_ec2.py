import paramiko
import time
import os
import subprocess
import re
import json
import socket

# ------------------- SSH UTILS -------------------

def create_bastion_proxy(bastion_public_ip, key_pair_path):
    """Crea e restituisce un'istanza di ProxyCommand per la connessione via Bastion."""
    return paramiko.ProxyCommand(f"ssh -i {key_pair_path} -W %h:%p ec2-user@{bastion_public_ip}")

def ssh_connect(target_ip, key_pair_path, proxy_command=None):
    """Crea e restituisce una connessione SSH pronta all'uso, con opzionale ProxyCommand."""
    key = paramiko.RSAKey.from_private_key_file(key_pair_path)
    ssh_client = paramiko.SSHClient()
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    # Retry logic for SSH connection
    max_retries = 10
    for i in range(max_retries):
        try:
            if proxy_command:
                sock = proxy_command.connect(target_ip, 22)
                ssh_client.connect(hostname=target_ip, username='ec2-user', pkey=key, sock=sock, timeout=60)
            else:
                ssh_client.connect(hostname=target_ip, username='ec2-user', pkey=key, timeout=60)
            print(f"SSH connection established to {target_ip} (via bastion if proxy used).")
            return ssh_client
        except (paramiko.AuthenticationException, paramiko.SSHException, socket.error) as e:
            print(f"Tentativo {i+1} di connessione a {target_ip} fallito: {e}. Attesa 10 secondi...")
            time.sleep(10)
    raise Exception(f"Impossibile stabilire una connessione SSH a {target_ip} dopo {max_retries} tentativi.")


def run_remote_command(ssh_client, command, cwd=None):
    """Esegue un comando remoto su EC2, opzionalmente in una directory specifica.
    Se il comando è 'mvn clean install', mostra solo BUILD SUCCESS o BUILD FAILURE."""
    full_command = f"cd {cwd} && {command}" if cwd else command
    print(f"Executing: {full_command}")
    stdin, stdout, stderr = ssh_client.exec_command(full_command)
    output = stdout.read().decode()
    error = stderr.read().decode()
    exit_status = stdout.channel.recv_exit_status()

    # Filtra l'output per Maven build
    if "mvn clean install" in command:
        build_result = None
        for line in output.splitlines():
            if "BUILD SUCCESS" in line:
                build_result = "BUILD SUCCESS"
            elif "BUILD FAILURE" in line:
                build_result = "BUILD FAILURE"
        if build_result:
            print(f"Maven result: {build_result}")
        else:
            print("Maven result: Unknown (no BUILD SUCCESS/FAILURE found)")
    else:
        if output:
            print(f"Stdout:\n{output}")
        if error:
            print(f"Stderr:\n{error}")

    if exit_status != 0:
        print(f"Error: Command failed with exit status {exit_status}")
        raise Exception(f"Command '{full_command}' failed on remote host.")
    return output

# ------------------- GIT UTILS -------------------

def git_commit_and_push():
    """Esegue git add, commit e push nella root della repo locale.
    Se non ci sono cambiamenti da committare, continua senza errore."""
    # Calcola la root del progetto (due livelli sopra questo script)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(script_dir, "..", ".."))
    # Esegui i comandi git nella root del progetto
    subprocess.run(["git", "add", "."], cwd=project_root, check=True)
    try:
        subprocess.run(["git", "commit", "-m", "Automatic config update"], cwd=project_root, check=True)
        subprocess.run(["git", "push"], cwd=project_root, check=True)
        print("Local changes committed and pushed to remote repository.")
    except subprocess.CalledProcessError as e:
        if e.returncode == 1:
            print("No changes to commit. Continuing deployment process.")
        else:
            raise

def git_pull_on_ec2(ec2_private_ip, key_pair_path, repo_url, repo_dir, proxy_command):
    """Effettua git pull (o clone se necessario) sulla EC2 indicata."""
    ssh_client = None
    try:
        ssh_client = ssh_connect(ec2_private_ip, key_pair_path, proxy_command)
        check_dir_cmd = f"if [ -d {repo_dir} ]; then echo 'exists'; else echo 'not_exists'; fi"
        result = run_remote_command(ssh_client, check_dir_cmd).strip()
        if result == "exists":
            print(f"Repo directory {repo_dir} exists on {ec2_private_ip}, running git pull...")
            run_remote_command(ssh_client, "git pull", cwd=repo_dir)
        else:
            print(f"Repo directory {repo_dir} does not exist on {ec2_private_ip}, running git clone...")
            run_remote_command(ssh_client, f"git clone {repo_url} {repo_dir}", cwd="/home/ec2-user")
    finally:
        if ssh_client:
            ssh_client.close()
            print(f"SSH connection to {ec2_private_ip} closed.")

# ------------------- BUILD UTILS -------------------

def build_java_project_on_ec2(ec2_private_ip, key_pair_path, is_server_instance, proxy_command):
    """Esegue la build Maven del modulo server o client sulla EC2 indicata."""
    ssh_client = None
    try:
        ssh_client = ssh_connect(ec2_private_ip, key_pair_path, proxy_command)
        app_repo_root = "/home/ec2-user/Music-Databese-Query-App-for-Distributed-Systems-on-Cloud"
        module_path = f"{app_repo_root}/mvnProject-Server" if is_server_instance else f"{app_repo_root}/mvnProject-Client"
        print(f"Building {'server' if is_server_instance else 'client'} application on {ec2_private_ip}...")
        run_remote_command(ssh_client, "mvn clean install", cwd=module_path)
        print(f"Build completed for {'server' if is_server_instance else 'client'} on {ec2_private_ip}.")
    finally:
        if ssh_client:
            ssh_client.close()
            print(f"SSH connection to {ec2_private_ip} closed.")

# ------------------- CONFIG FILE UTILS -------------------

def update_local_java_config(
    server_ip_for_server_config, server_port, rds_endpoint, db_username, db_password,
    client_server_hostname, client_server_port,
    server_config_path, server_db_properties_path, client_config_path
):
    """Aggiorna i file di configurazione Java e properties localmente."""

    # Aggiorna DatabaseConfig.java (Server)
    with open(server_config_path, "r") as f:
        content = f.read()
    content = re.sub(
        r'properties\.setProperty\("server\.host",\s*".*?"\);',
        f'properties.setProperty("server.host", "{server_ip_for_server_config}");',
        content
    )
    content = re.sub(
        r'properties\.setProperty\("server\.port",\s*".*?"\);',
        f'properties.setProperty("server.port", "{server_port}");',
        content
    )
    content = re.sub(
        r'properties\.setProperty\("database\.url",\s*".*?"\);',
        f'properties.setProperty("database.url", "jdbc:postgresql://{rds_endpoint}:5432/musicdb");',
        content
    )
    content = re.sub(
        r'properties\.setProperty\("database\.user",\s*".*?"\);',
        f'properties.setProperty("database.user", "{db_username}");',
        content
    )
    content = re.sub(
        r'properties\.setProperty\("database\.password",\s*".*?"\);',
        f'properties.setProperty("database.password", "{db_password}");',
        content
    )
    with open(server_config_path, "w") as f:
        f.write(content)

    # Aggiorna database.properties (Server)
    with open(server_db_properties_path, "r") as f:
        lines = f.readlines()
    with open(server_db_properties_path, "w") as f:
        for line in lines:
            if line.startswith("server.host="):
                f.write(f"server.host={server_ip_for_server_config}\n")
            elif line.startswith("server.port="):
                f.write(f"server.port={server_port}\n")
            elif line.startswith("database.url="):
                f.write(f"database.url=jdbc:postgresql://{rds_endpoint}:5432/musicdb\n")
            elif line.startswith("database.user="):
                f.write(f"database.user={db_username}\n")
            elif line.startswith("database.password="):
                f.write(f"database.password={db_password}\n")
            else:
                f.write(line)

    # Aggiorna DatabaseClient.java (Client)
    with open(client_config_path, "r") as f:
        content = f.read()
    content = re.sub(
        r'private static final String SERVER_HOST = ".*?";',
        f'private static final String SERVER_HOST = "{client_server_hostname}";', # This will be the ALB DNS name
        content
    )
    content = re.sub(
        r'private static final int SERVER_PORT = \d+;',
        f'private static final int SERVER_PORT = {client_server_port};', # This will be the ALB listener port (80)
        content
    )
    with open(client_config_path, "w") as f:
        f.write(content)

    print("Local Java config files updated.")

# ------------------- MAIN DEPLOYMENT LOGIC -------------------

def main():
    # Carica la configurazione dal file JSON
    with open("deploy_config.json", "r") as f:
        config = json.load(f)

    BASTION_PUBLIC_IP = config["bastion_public_ip"]
    SERVER_EC2_PRIVATE_IPS = config["server_private_ips"] # Now a list
    CLIENT_EC2_PRIVATE_IPS = config["client_private_ips"] # Now a list
    ALB_DNS_NAME = config["alb_dns_name"]
    KEY_PAIR_PATH = config["key_pair_name"] + ".pem"
    SERVER_APPLICATION_PORT = str(config["server_application_port"]) # Ensure it's a string for regex
    RDS_ENDPOINT = config["rds_endpoint"]
    DB_USERNAME = config["db_username"]
    DB_PASSWORD = config["db_password"]

    print("Starting configuration and deployment process...")

    # Calculate project root
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(script_dir, "..", ".."))

    # Path to local configuration files
    server_config_path = os.path.join(project_root, "mvnProject-Server", "src", "main", "java", "com", "example", "config", "DatabaseConfig.java")
    server_db_properties_path = os.path.join(project_root, "mvnProject-Server", "src", "main", "java", "com", "example", "config", "database.properties")
    client_config_path = os.path.join(project_root, "mvnProject-Client", "src", "main", "java", "com", "example", "DatabaseClient.java")

    # 1. Update local configuration files
    # Server config points to its own private IP (if it needs to bind to a specific interface) or 0.0.0.0
    # For simplicity, we'll configure server to listen on 0.0.0.0, so the 'server_ip' in its config
    # can actually be its private IP for internal reference if required, or simply "0.0.0.0"
    # Here, I'm setting it to the first server's private IP, assuming all servers will have similar config needs.
    # If the Java app binds to "0.0.0.0", this specific IP in the config might be less critical.
    # The crucial part for the server is the DB endpoint.
    update_local_java_config(
        server_ip_for_server_config=SERVER_EC2_PRIVATE_IPS[0], # Using the first server's private IP for server config
        server_port=SERVER_APPLICATION_PORT,
        rds_endpoint=RDS_ENDPOINT,
        db_username=DB_USERNAME,
        db_password=DB_PASSWORD,
        client_server_hostname=ALB_DNS_NAME, # Client connects to ALB
        client_server_port="80", # ALB listens on port 80 and forwards to 8080
        server_config_path=server_config_path,
        server_db_properties_path=server_db_properties_path,
        client_config_path=client_config_path
    )

    # 2. Commit and push to git
    git_commit_and_push()

    # 3. Create Bastion Proxy Command
    bastion_proxy = create_bastion_proxy(BASTION_PUBLIC_IP, KEY_PAIR_PATH)

    # 4. Update/clone the repo on EC2 instances via Bastion
    repo_url = "git@github.com:lorenzopaoria/Music-Databese-Query-App-for-Distributed-Systems-on-Cloud.git"
    repo_dir = "/home/ec2-user/Music-Databese-Query-App-for-Distributed-Systems-on-Cloud"
    
    print("\nPulling/cloning repo on server instances...")
    for server_ip in SERVER_EC2_PRIVATE_IPS:
        git_pull_on_ec2(server_ip, KEY_PAIR_PATH, repo_url, repo_dir, bastion_proxy)

    print("\nPulling/cloning repo on client instances...")
    for client_ip in CLIENT_EC2_PRIVATE_IPS:
        git_pull_on_ec2(client_ip, KEY_PAIR_PATH, repo_url, repo_dir, bastion_proxy)

    # 5. Build on EC2 instances via Bastion
    print("\nBuilding server application on server instances...")
    for server_ip in SERVER_EC2_PRIVATE_IPS:
        build_java_project_on_ec2(server_ip, KEY_PAIR_PATH, is_server_instance=True, proxy_command=bastion_proxy)

    print("\nBuilding client application on client instances...")
    for client_ip in CLIENT_EC2_PRIVATE_IPS:
        build_java_project_on_ec2(client_ip, KEY_PAIR_PATH, is_server_instance=False, proxy_command=bastion_proxy)

    print("Deployment process completed.")

    print("\nRemember to start the server application on server EC2 instances using:")
    print(f"  ssh -i {KEY_PAIR_PATH} -o ProxyCommand='ssh -W %h:%p ec2-user@{BASTION_PUBLIC_IP}' ec2-user@{SERVER_EC2_PRIVATE_IPS[0]} 'cd {repo_dir}/mvnProject-Server && nohup mvn -Pserver exec:java > server.log 2>&1 &'")
    print("\nAnd the client application on client EC2 instances using:")
    print(f"  ssh -i {KEY_PAIR_PATH} -o ProxyCommand='ssh -W %h:%p ec2-user@{BASTION_PUBLIC_IP}' ec2-user@{CLIENT_EC2_PRIVATE_IPS[0]} 'cd {repo_dir}/mvnProject-Client && nohup mvn -Pclient exec:java > client.log 2>&1 &'")
    print("\nAccess the application via the ALB DNS Name: http://{ALB_DNS_NAME}")

if __name__ == "__main__":
    main()