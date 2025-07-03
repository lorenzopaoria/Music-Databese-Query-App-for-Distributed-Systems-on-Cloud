import paramiko
import time
import os
import subprocess
import re
import json

# ------------------- SSH UTILS -------------------

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

def ssh_connect(ec2_public_ip, key_pair_path):
    """Crea e restituisce una connessione SSH pronta all'uso."""
    key = paramiko.RSAKey.from_private_key_file(key_pair_path)
    ssh_client = paramiko.SSHClient()
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh_client.connect(hostname=ec2_public_ip, username='ec2-user', pkey=key, timeout=60)
    print(f"SSH connection established to {ec2_public_ip}.")
    return ssh_client

# ------------------- GIT UTILS -------------------

def git_commit_and_push():
    """Esegue git add, commit e push nella root della repo locale.
    Se non ci sono cambiamenti da committare, continua senza errore."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(script_dir, "..", ".."))
    subprocess.run(["git", "add", "."], cwd=project_root, check=True)
    try:
        subprocess.run(["git", "commit", "-m", "update_java_cofig_on_ec2 commit"], cwd=project_root, check=True)
        subprocess.run(["git", "push"], cwd=project_root, check=True)
        print("Local changes committed and pushed to remote repository.")
    except subprocess.CalledProcessError as e:
        if e.returncode == 1:
            print("No changes to commit. Continuing deployment process.")
        else:
            raise

# ------------------- CONFIG FILE UTILS -------------------

def update_local_java_config(
    server_ip, server_port, rds_endpoint, db_username, db_password,
    client_server_ip, client_server_port,
    server_config_path, server_db_properties_path, client_config_path
):
    """Aggiorna i file di configurazione Java e properties localmente."""

    # Aggiorna DatabaseConfig.java (solo i valori di default nel blocco catch)
    with open(server_config_path, "r") as f:
        content = f.read()
    content = re.sub(
        r'properties\.setProperty\("server\.host",\s*".*?"\);',
        f'properties.setProperty("server.host", "{server_ip}");',
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

    # Aggiorna database.properties
    with open(server_db_properties_path, "r") as f:
        lines = f.readlines()
    with open(server_db_properties_path, "w") as f:
        for line in lines:
            if line.startswith("server.host="):
                f.write(f"server.host={server_ip}\n")
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

    # Aggiorna DatabaseClient.java
    with open(client_config_path, "r") as f:
        content = f.read()
    content = re.sub(
        r'private static final String SERVER_HOST = ".*?";',
        f'private static final String SERVER_HOST = "{client_server_ip}";',
        content
    )
    content = re.sub(
        r'private static final int SERVER_PORT = \d+;',
        f'private static final int SERVER_PORT = {client_server_port};',
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

    SERVER_EC2_PUBLIC_IP = config["server_public_ip"]
    SERVER_EC2_PRIVATE_IP = config["server_private_ip"]
    SERVER_APPLICATION_PORT = "8080"
    RDS_ENDPOINT = config["rds_endpoint"]
    DB_USERNAME = config["db_username"]
    DB_PASSWORD = config["db_password"]

    print("Starting configuration update process...")

    # Calcola la root del progetto (due livelli sopra lo script)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(script_dir, "..", ".."))

    # Path ai file di configurazione locali
    server_config_path = os.path.join(project_root, "mvnProject-Server", "src", "main", "java", "com", "example", "config", "DatabaseConfig.java")
    server_db_properties_path = os.path.join(project_root, "mvnProject-Server", "src", "main", "java", "com", "example", "config", "database.properties")
    client_config_path = os.path.join(project_root, "mvnProject-Client", "src", "main", "java", "com", "example", "DatabaseClient.java")

    # 1. Aggiorna i file di configurazione localmente
    update_local_java_config(
        server_ip=SERVER_EC2_PRIVATE_IP,
        server_port=SERVER_APPLICATION_PORT,
        rds_endpoint=RDS_ENDPOINT,
        db_username=DB_USERNAME,
        db_password=DB_PASSWORD,
        client_server_ip=SERVER_EC2_PUBLIC_IP,  # Il client locale si collega all'IP pubblico del server EC2
        client_server_port=SERVER_APPLICATION_PORT,
        server_config_path=server_config_path,
        server_db_properties_path=server_db_properties_path,
        client_config_path=client_config_path
    )

    # 2. Commit e push su git
    git_commit_and_push()

    print("Config update process completed. La build e il deploy su EC2 saranno gestiti da GitHub Actions.")

if __name__ == "__main__":
    main()