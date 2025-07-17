import paramiko
import time
import os
import subprocess
import re
import json

def run_remote_command(ssh_client, command, cwd=None):

    full_command = f"cd {cwd} && {command}" if cwd else command
    print(f"[STEP] Esecuzione comando remoto: {full_command}")
    stdin, stdout, stderr = ssh_client.exec_command(full_command)
    output = stdout.read().decode()
    error = stderr.read().decode()
    exit_status = stdout.channel.recv_exit_status()

    if "mvn clean install" in command:
        build_result = None
        for line in output.splitlines():
            if "BUILD SUCCESS" in line:
                build_result = "BUILD SUCCESS"
            elif "BUILD FAILURE" in line:
                build_result = "BUILD FAILURE"
        if build_result:
            print(f"[INFO] Risultato Maven: {build_result}")
        else:
            print("[INFO] Risultato Maven: Sconosciuto - nessun BUILD SUCCESS/FAILURE trovato")
    else:
        if output:
            print(f"[STDOUT]\n{output}")
        if error:
            print(f"[STDERR]\n{error}")

    if exit_status != 0:
        print(f"[ERROR] Comando fallito con stato di uscita {exit_status}")
        raise Exception(f"Comando '{full_command}' fallito sull'host remoto.")
    return output

def ssh_connect(ec2_public_ip, key_pair_path):

    key = paramiko.RSAKey.from_private_key_file(key_pair_path)
    ssh_client = paramiko.SSHClient()
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh_client.connect(hostname=ec2_public_ip, username='ec2-user', pkey=key, timeout=60)
    print(f"[SUCCESS] Connessione SSH stabilita verso {ec2_public_ip}.")
    return ssh_client

def git_commit_and_push():

    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(script_dir, "..", ".."))
    subprocess.run(["git", "add", "."], cwd=project_root, check=True)
    try:
        subprocess.run(["git", "commit", "-m", "update_java_cofig_on_ec2 commit, action in corso..."], cwd=project_root, check=True)
        subprocess.run(["git", "push"], cwd=project_root, check=True)
        print("[SUCCESS] Modifiche locali committate e pushate sul repository remoto.")
    except subprocess.CalledProcessError as e:
        if e.returncode == 1:
            print("[INFO] Nessuna modifica da committare. Continuo il processo di deploy.")
        else:
            raise

def update_local_java_config(
    server_ip, server_port, rds_endpoint, db_username, db_password,
    client_server_ip, client_server_port,
    server_config_path, server_db_properties_path, client_config_path
):

    # aggiorno DatabaseConfig.java
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

    # aggiorno database.properties
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

    # aggiorno DatabaseClient.java
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
    print("[SUCCESS] File di configurazione Java locali aggiornati.")

def main():#

    with open("deploy_config.json", "r") as f:
        config = json.load(f)

    SERVER_EC2_PUBLIC_IP = config["server_public_ip"]
    SERVER_EC2_PRIVATE_IP = config["server_private_ip"]
    SERVER_APPLICATION_PORT = "8080"
    RDS_ENDPOINT = config["rds_endpoint"]
    DB_USERNAME = config["db_username"]
    DB_PASSWORD = config["db_password"]
    
    # controllo se il NLB è disponibile
    nlb_enabled = config.get("nlb_enabled", False)
    if nlb_enabled and "nlb_dns" in config and "nlb_port" in config:
        CLIENT_TARGET_HOST = config["nlb_dns"]
        CLIENT_TARGET_PORT = str(config["nlb_port"])
        print(f"[INFO] Configurazione client per Network Load Balancer: {CLIENT_TARGET_HOST}:{CLIENT_TARGET_PORT}")
    else:
        CLIENT_TARGET_HOST = SERVER_EC2_PUBLIC_IP
        CLIENT_TARGET_PORT = SERVER_APPLICATION_PORT
        print(f"[INFO] Configurazione client per connessione diretta EC2: {CLIENT_TARGET_HOST}:{CLIENT_TARGET_PORT}")

    print("[STEP] Avvio del processo di aggiornamento della configurazione...")

    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(script_dir, "..", ".."))

    server_config_path = os.path.join(project_root, "mvnProject-Server", "src", "main", "java", "com", "example", "config", "DatabaseConfig.java")
    server_db_properties_path = os.path.join(project_root, "mvnProject-Server", "src", "main", "java", "com", "example", "config", "database.properties")
    client_config_path = os.path.join(project_root, "mvnProject-Client", "src", "main", "java", "com", "example", "DatabaseClient.java")

    update_local_java_config(
        server_ip=SERVER_EC2_PRIVATE_IP,
        server_port=SERVER_APPLICATION_PORT,
        rds_endpoint=RDS_ENDPOINT,
        db_username=DB_USERNAME,
        db_password=DB_PASSWORD,
        client_server_ip=CLIENT_TARGET_HOST,
        client_server_port=CLIENT_TARGET_PORT,
        server_config_path=server_config_path,
        server_db_properties_path=server_db_properties_path,
        client_config_path=client_config_path
    )

    git_commit_and_push()

if __name__ == "__main__":
    main()