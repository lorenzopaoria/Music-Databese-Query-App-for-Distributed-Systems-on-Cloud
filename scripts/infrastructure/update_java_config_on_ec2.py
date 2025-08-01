import paramiko
import time
import os
import subprocess
import re
import json

# commit e push delle modifiche da locale
def git_commit_and_push():

    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(script_dir, "..", ".."))
    
    # aggiunta di tutti i file modificati
    subprocess.run(["git", "add", "."], cwd=project_root, check=True)
    
    try:
        # commit delle modifiche
        subprocess.run(["git", "commit", "-m", "update_java_cofig_on_ec2 commit, action in corso..."], cwd=project_root, check=True)
        
        # push al repository remoto
        subprocess.run(["git", "push"], cwd=project_root, check=True)
        print("[SUCCESS] Modifiche locali committate e pushate sul repository remoto.")
    except subprocess.CalledProcessError as e:
        if e.returncode == 1:
            print("[INFO] Nessuna modifica da committare. Continuo il processo di deploy.")
        else:
            raise

# aggiornamento dei file di configurazione Java locali
def update_local_java_config(
    server_ip, server_port, rds_endpoint, db_username, db_password,
    client_server_ip, client_server_port,
    server_config_path, server_db_properties_path, client_config_path
):
    
    # STEP 1: aggiornamento di DatabaseConfig.java (server)
    with open(server_config_path, "r") as f:
        content = f.read()
    
    # sostituzione delle proprietà del server
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
    
    # sostituzione delle proprietà del database
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
    
    # salvataggio del file aggiornato
    with open(server_config_path, "w") as f:
        f.write(content)

    # STEP 2: aggiornamento di database.properties (server)
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

    # STEP 3: aggiornamento di DatabaseClient.java (client)
    with open(client_config_path, "r") as f:
        content = f.read()
    
    # sostituzione delle proprietà di connessione del client
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
    
    # salvataggio del file client aggiornato
    with open(client_config_path, "w") as f:
        f.write(content)
    
    print("[SUCCESS] File di configurazione Java locali aggiornati.")

def main():

    # lettura della configurazione di deploy
    with open("deploy_config.json", "r") as f:
        config = json.load(f)

    # estrazione dei parametri di configurazione
    SERVER_EC2_PUBLIC_IP = config["server_public_ip"]
    SERVER_EC2_PRIVATE_IP = config["server_private_ip"]
    SERVER_APPLICATION_PORT = "8080"
    RDS_ENDPOINT = config["rds_endpoint"]
    DB_USERNAME = config["db_username"]
    DB_PASSWORD = config["db_password"]
    
    # STEP 1: determinazione della configurazione client (NLB/EC2)
    nlb_enabled = config.get("nlb_enabled", False)
    if nlb_enabled and "nlb_dns" in config and "nlb_port" in config:
        # configurazione NLB
        CLIENT_TARGET_HOST = config["nlb_dns"]
        CLIENT_TARGET_PORT = str(config["nlb_port"])
        print(f"[INFO] Configurazione client per Network Load Balancer: {CLIENT_TARGET_HOST}:{CLIENT_TARGET_PORT}")
    else:
        # configurazione EC2
        CLIENT_TARGET_HOST = SERVER_EC2_PUBLIC_IP
        CLIENT_TARGET_PORT = SERVER_APPLICATION_PORT
        print(f"[INFO] Configurazione client per connessione diretta EC2: {CLIENT_TARGET_HOST}:{CLIENT_TARGET_PORT}")

    print("[STEP] Avvio del processo di aggiornamento della configurazione...")

    # STEP 2: costruzione dei percorsi ai file di configurazione
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(script_dir, "..", ".."))

    server_config_path = os.path.join(project_root, "mvnProject-Server", "src", "main", "java", "com", "example", "config", "DatabaseConfig.java")
    server_db_properties_path = os.path.join(project_root, "mvnProject-Server", "src", "main", "java", "com", "example", "config", "database.properties")
    client_config_path = os.path.join(project_root, "mvnProject-Client", "src", "main", "java", "com", "example", "DatabaseClient.java")

    # STEP 3: aggiornamento dei file di configurazione Java
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

    # STEP 4: commit e push delle modifiche per triggerare GitHub Actions
    git_commit_and_push()

if __name__ == "__main__":
    main()