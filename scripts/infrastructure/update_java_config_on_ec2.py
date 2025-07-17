import paramiko
import time
import os
import subprocess
import re
import json
from dotenv import load_dotenv

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, "..", ".."))
env_path = os.path.join(project_root, ".env")
load_dotenv(env_path)

# configurazione da env
DEPLOY_CONFIG_FILE = os.getenv('DEPLOY_CONFIG_FILE', 'deploy_config.json')
APPLICATION_PORT = os.getenv('APPLICATION_PORT', '8080')
SERVER_CONFIG_RELATIVE_PATH = os.getenv('SERVER_CONFIG_RELATIVE_PATH', 'mvnProject-Server/src/main/java/com/example/config/DatabaseConfig.java')
SERVER_DB_PROPERTIES_RELATIVE_PATH = os.getenv('SERVER_DB_PROPERTIES_RELATIVE_PATH', 'mvnProject-Server/src/main/java/com/example/config/database.properties')
CLIENT_CONFIG_RELATIVE_PATH = os.getenv('CLIENT_CONFIG_RELATIVE_PATH', 'mvnProject-Client/src/main/java/com/example/DatabaseClient.java')

def print_info(message):

    print(f"[INFO] {message}")

def print_success(message):

    print(f"[SUCCESS] {message}")

def print_error(message):

    print(f"[ERROR] {message}")

def print_step(message):

    print(f"[STEP] {message}")

def print_stdout(output):

    print(f"[STDOUT]\n{output}")

def print_stderr(error):

    print(f"[STDERR]\n{error}")

def analyze_maven_output(output):

    build_result = None
    for line in output.splitlines():
        if "BUILD SUCCESS" in line:
            build_result = "BUILD SUCCESS"
        elif "BUILD FAILURE" in line:
            build_result = "BUILD FAILURE"
    
    if build_result:
        print_info(f"Risultato Maven: {build_result}")
    else:
        print_info("Risultato Maven: Sconosciuto - nessun BUILD SUCCESS/FAILURE trovato")

def run_remote_command(ssh_client, command, cwd=None):

    full_command = f"cd {cwd} && {command}" if cwd else command
    print_step(f"Esecuzione comando remoto: {full_command}")
    
    stdin, stdout, stderr = ssh_client.exec_command(full_command)
    output = stdout.read().decode()
    error = stderr.read().decode()
    exit_status = stdout.channel.recv_exit_status()

    if "mvn clean install" in command:
        analyze_maven_output(output)
    else:
        if output:
            print_stdout(output)
        if error:
            print_stderr(error)

    if exit_status != 0:
        print_error(f"Comando fallito con stato di uscita {exit_status}")
        raise Exception(f"Comando '{full_command}' fallito sull'host remoto.")
    return output

def ssh_connect(ec2_public_ip, key_pair_path):

    key = paramiko.RSAKey.from_private_key_file(key_pair_path)
    ssh_client = paramiko.SSHClient()
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh_client.connect(hostname=ec2_public_ip, username='ec2-user', pkey=key, timeout=60)
    print_success(f"Connessione SSH stabilita verso {ec2_public_ip}.")
    return ssh_client

def handle_git_operations():

    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(script_dir, "..", ".."))
    
    try:
        subprocess.run(["git", "add", "."], cwd=project_root, check=True)
        subprocess.run(["git", "commit", "-m", "update_java_cofig_on_ec2 commit, action in corso..."], cwd=project_root, check=True)
        subprocess.run(["git", "push"], cwd=project_root, check=True)
        print_success("Modifiche locali committate e pushate sul repository remoto.")
    except subprocess.CalledProcessError as e:
        if e.returncode == 1:
            print_info("Nessuna modifica da committare. Continuo il processo di deploy.")
        else:
            raise

def update_file_content(file_path, patterns_replacements):

    with open(file_path, "r") as f:
        content = f.read()
    
    for pattern, replacement in patterns_replacements:
        content = re.sub(pattern, replacement, content)
    
    with open(file_path, "w") as f:
        f.write(content)

def update_properties_file(file_path, property_updates):

    with open(file_path, "r") as f:
        lines = f.readlines()
    
    with open(file_path, "w") as f:
        for line in lines:
            updated = False
            for prop_key, new_value in property_updates.items():
                if line.startswith(f"{prop_key}="):
                    f.write(f"{prop_key}={new_value}\n")
                    updated = True
                    break
            if not updated:
                f.write(line)

def update_local_java_config(
    server_ip, server_port, rds_endpoint, db_username, db_password,
    client_server_ip, client_server_port,
    server_config_path, server_db_properties_path, client_config_path
):
    
    # Update DatabaseConfig.java
    server_config_patterns = [
        (r'properties\.setProperty\("server\.host",\s*".*?"\);', 
         f'properties.setProperty("server.host", "{server_ip}");'),
        (r'properties\.setProperty\("server\.port",\s*".*?"\);', 
         f'properties.setProperty("server.port", "{server_port}");'),
        (r'properties\.setProperty\("database\.url",\s*".*?"\);', 
         f'properties.setProperty("database.url", "jdbc:postgresql://{rds_endpoint}:5432/musicdb");'),
        (r'properties\.setProperty\("database\.user",\s*".*?"\);', 
         f'properties.setProperty("database.user", "{db_username}");'),
        (r'properties\.setProperty\("database\.password",\s*".*?"\);', 
         f'properties.setProperty("database.password", "{db_password}");')
    ]
    update_file_content(server_config_path, server_config_patterns)

    # Update database.properties
    db_properties_updates = {
        "server.host": server_ip,
        "server.port": server_port,
        "database.url": f"jdbc:postgresql://{rds_endpoint}:5432/musicdb",
        "database.user": db_username,
        "database.password": db_password
    }
    update_properties_file(server_db_properties_path, db_properties_updates)

    # Update DatabaseClient.java
    client_config_patterns = [
        (r'private static final String SERVER_HOST = ".*?";', 
         f'private static final String SERVER_HOST = "{client_server_ip}";'),
        (r'private static final int SERVER_PORT = \d+;', 
         f'private static final int SERVER_PORT = {client_server_port};')
    ]
    update_file_content(client_config_path, client_config_patterns)
    
    print_success("File di configurazione Java locali aggiornati.")

def get_configuration_paths():

    server_config_path = os.path.join(project_root, SERVER_CONFIG_RELATIVE_PATH)
    server_db_properties_path = os.path.join(project_root, SERVER_DB_PROPERTIES_RELATIVE_PATH)
    client_config_path = os.path.join(project_root, CLIENT_CONFIG_RELATIVE_PATH)
    
    return server_config_path, server_db_properties_path, client_config_path

def determine_client_target(config):

    nlb_enabled = config.get("nlb_enabled", False)
    if nlb_enabled and "nlb_dns" in config and "nlb_port" in config:
        client_target_host = config["nlb_dns"]
        client_target_port = str(config["nlb_port"])
        print_info(f"Configurazione client per Network Load Balancer: {client_target_host}:{client_target_port}")
    else:
        client_target_host = config["server_public_ip"]
        client_target_port = APPLICATION_PORT
        print_info(f"Configurazione client per connessione diretta EC2: {client_target_host}:{client_target_port}")
    
    return client_target_host, client_target_port

def main():

    with open(DEPLOY_CONFIG_FILE, "r") as f:
        config = json.load(f)

    SERVER_EC2_PUBLIC_IP = config["server_public_ip"]
    SERVER_EC2_PRIVATE_IP = config["server_private_ip"]
    SERVER_APPLICATION_PORT = APPLICATION_PORT
    RDS_ENDPOINT = config["rds_endpoint"]
    DB_USERNAME = config["db_username"]
    DB_PASSWORD = config["db_password"]
    
    CLIENT_TARGET_HOST, CLIENT_TARGET_PORT = determine_client_target(config)

    print_step("Avvio del processo di aggiornamento della configurazione...")

    server_config_path, server_db_properties_path, client_config_path = get_configuration_paths()

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

    handle_git_operations()

if __name__ == "__main__":
    main()