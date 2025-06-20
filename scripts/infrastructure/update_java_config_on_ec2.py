import paramiko
import time
import os
import subprocess
import re
import json

def run_remote_command(ssh_client, command, cwd=None):
    """Executes a command on the remote EC2 instance with an optional working directory."""
    full_command = f"cd {cwd} && {command}" if cwd else command
    print(f"Executing: {full_command}") # For debugging
    stdin, stdout, stderr = ssh_client.exec_command(full_command)
    output = stdout.read().decode()
    error = stderr.read().decode()
    exit_status = stdout.channel.recv_exit_status()

    if output:
        print(f"Stdout:\n{output}")
    if error:
        print(f"Stderr:\n{error}")

    if exit_status != 0:
        print(f"Error: Command failed with exit status {exit_status}")
        raise Exception(f"Command '{full_command}' failed on remote host.")
    return output

def update_java_config_on_ec2(
    ec2_public_ip,
    ec2_private_ip, # Used for server binding, if applicable
    key_pair_path,
    rds_endpoint=None, # Only needed for server EC2
    db_username=None, # Only needed for server EC2
    db_password=None, # Only needed for server EC2
    server_app_port="8080", # Default server application port
    is_server_instance=False # Flag to distinguish server from client
):
    print(f"\n--- Connecting to EC2 instance: {ec2_public_ip} ---")
    try:
        key = paramiko.RSAKey.from_private_key_file(key_pair_path)
        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        # Changed username from 'ubuntu' to 'ec2-user'
        ssh_client.connect(hostname=ec2_public_ip, username='ec2-user', pkey=key, timeout=60)
        print("SSH connection established.")

        # Updated app_repo_root path to match user_data_script.sh
        app_repo_root = "/home/ec2-user/Music-Databese-Query-App-for-Distributed-Systems-on-Cloud"
        server_module_path = f"{app_repo_root}/mvnProject-Server"
        client_module_path = f"{app_repo_root}/mvnProject-Client"

        # Ensure the directories exist
        run_remote_command(ssh_client, f"mkdir -p {server_module_path}", cwd='/')
        run_remote_command(ssh_client, f"mkdir -p {client_module_path}", cwd='/')
        
        if is_server_instance:
            print("Configuring Server EC2 instance...")
            # Paths to configuration files on the server
            server_config_path = f"{server_module_path}/src/main/java/com/example/config/DatabaseConfig.java"
            server_db_properties_path = f"{server_module_path}/src/main/java/com/example/config/database.properties"

            # 1. Update Config.java (Server IP, DB URL, DB Credentials)
            print(f"Updating {server_config_path} on server...")
            # Use private IP for server binding
            run_remote_command(ssh_client, 
                f"sudo sed -i 's|public static final String SERVER_IP = \".*\";|public static final String SERVER_IP = \"{ec2_private_ip}\";|g' {server_config_path}")
            run_remote_command(ssh_client, 
                f"sudo sed -i 's|public static final int SERVER_PORT = .*;|public static final int SERVER_PORT = {server_app_port};|g' {server_config_path}")
            # Corrected for PostgreSQL URL and port
            run_remote_command(ssh_client, 
                f"sudo sed -i 's|public static final String DATABASE_URL = \".*\";|public static final String DATABASE_URL = \"jdbc:postgresql://{rds_endpoint}:5432/musicdb\";|g' {server_config_path}") # Assuming 'musicdb' as DB_NAME
            run_remote_command(ssh_client, 
                f"sudo sed -i 's|public static final String DB_USERNAME = \".*\";|public static final String DB_USERNAME = \"{db_username}\";|g' {server_config_path}")
            run_remote_command(ssh_client, 
                f"sudo sed -i 's|public static final String DB_PASSWORD = \".*\";|public static final String DB_PASSWORD = \"{db_password}\";|g' {server_config_path}")
            
            # 2. Update database.properties (DB URL, DB Credentials)
            print(f"Updating {server_db_properties_path} on server...")
            # Corrected for PostgreSQL URL and port
            run_remote_command(ssh_client, 
                f"sudo sed -i 's|^url=.*|url=jdbc:postgresql://{rds_endpoint}:5432/musicdb|g' {server_db_properties_path}") # Assuming 'musicdb' as DB_NAME
            run_remote_command(ssh_client, 
                f"sudo sed -i 's|^username=.*|username={db_username}|g' {server_db_properties_path}")
            run_remote_command(ssh_client, 
                f"sudo sed -i 's|^password=.*|password={db_password}|g' {server_db_properties_path}")

            # 3. Build and Start Server Application
            print("Building server application...")
            run_remote_command(ssh_client, "mvn clean install", cwd=server_module_path) # Build the entire project
            
            print("For starting server application go to therminal and run --mvn -Pserver exec:java-- in mvnProject-Server directory")

        else: # Client instance
            print("Configuring Client EC2 instance...")
            # Path to configuration file on the client
            client_config_path = f"{client_module_path}/src/main/java/com/example/DatabaseClient.java"

            # Update Config.java (Server IP)
            print(f"Updating {client_config_path} on client...")
            # Client connects to the public IP of the server
            run_remote_command(ssh_client, 
                f"sudo sed -i 's|public static final String SERVER_HOST = \".*\";|public static final String SERVER_HOST = \"{server_app_port}\";|g' {client_config_path}")
            run_remote_command(ssh_client, 
                f"sudo sed -i 's|public static final int SERVER_PORT = .*;|public static final int SERVER_PORT = {server_app_port};|g' {client_config_path}")
            
            # 3. Build and Start Client Application
            print("Building client application...")
            run_remote_command(ssh_client, "mvn clean install", cwd=client_module_path) # Build the entire project

            print("For starting client application go to therminal and run --mvn -Pclient exec:java-- in mvnProject-Client directory")

    except paramiko.AuthenticationException:
        print(f"Authentication failed, please check your {key_pair_path} and EC2 instance user.")
        raise
    except paramiko.SSHException as e:
        print(f"Could not establish SSH connection: {e}")
        raise
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        raise
    finally:
        if 'ssh_client' in locals() and ssh_client:
            print(f"--- SSH connection to {ec2_public_ip} closed. ---")
            ssh_client.close()

def update_local_java_config(
    server_ip, server_port, rds_endpoint, db_username, db_password,
    client_server_ip, client_server_port,
    server_config_path, server_db_properties_path, client_config_path
):
    # Aggiorna DatabaseConfig.java
    with open(server_config_path, "r") as f:
        content = f.read()
    content = re.sub(r'public static final String SERVER_IP = ".*";',
                     f'public static final String SERVER_IP = "{server_ip}";', content)
    content = re.sub(r'public static final int SERVER_PORT = .*;',
                     f'public static final int SERVER_PORT = {server_port};', content)
    content = re.sub(r'public static final String DATABASE_URL = ".*";',
                     f'public static final String DATABASE_URL = "jdbc:postgresql://{rds_endpoint}:5432/musicdb";', content)
    content = re.sub(r'public static final String DB_USERNAME = ".*";',
                     f'public static final String DB_USERNAME = "{db_username}";', content)
    content = re.sub(r'public static final String DB_PASSWORD = ".*";',
                     f'public static final String DB_PASSWORD = "{db_password}";', content)
    with open(server_config_path, "w") as f:
        f.write(content)

    # Aggiorna database.properties
    with open(server_db_properties_path, "r") as f:
        lines = f.readlines()
    with open(server_db_properties_path, "w") as f:
        for line in lines:
            if line.startswith("url="):
                f.write(f"url=jdbc:postgresql://{rds_endpoint}:5432/musicdb\n")
            elif line.startswith("username="):
                f.write(f"username={db_username}\n")
            elif line.startswith("password="):
                f.write(f"password={db_password}\n")
            else:
                f.write(line)

    # Aggiorna DatabaseClient.java
    with open(client_config_path, "r") as f:
        content = f.read()
    content = re.sub(r'public static final String SERVER_HOST = ".*";',
                     f'public static final String SERVER_HOST = "{client_server_ip}";', content)
    content = re.sub(r'public static final int SERVER_PORT = .*;',
                     f'public static final int SERVER_PORT = {client_server_port};', content)
    with open(client_config_path, "w") as f:
        f.write(content)

def git_commit_and_push():
    subprocess.run(["git", "add", "."], check=True)
    subprocess.run(["git", "commit", "-m", "AutomaticTest"], check=True)
    subprocess.run(["git", "push"], check=True)

if __name__ == "__main__":
    # Carica la configurazione dal file JSON
    with open("deploy_config.json", "r") as f:
        config = json.load(f)

    SERVER_EC2_PUBLIC_IP = config["server_public_ip"]
    SERVER_EC2_PRIVATE_IP = config["server_private_ip"]
    CLIENT_EC2_PUBLIC_IP = config["client_public_ips"][0] # o scegli quello che vuoi
    KEY_PAIR_PATH = config["key_pair_name"] + ".pem"
    SERVER_APPLICATION_PORT = "8080"
    RDS_ENDPOINT = config["rds_endpoint"]
    DB_USERNAME = config["db_username"]
    DB_PASSWORD = config["db_password"]

    print("Starting configuration and deployment process...")

    # Calcola la root del progetto (due livelli sopra lo script)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(script_dir, "..", ".."))

    # Path ai file di configurazione locali
    server_config_path = os.path.join(project_root, "mvnProject-Server", "src", "main", "java", "com", "example", "config", "DatabaseConfig.java")
    server_db_properties_path = os.path.join(project_root, "mvnProject-Server", "src", "main", "java", "com", "example", "config", "database.properties")
    client_config_path = os.path.join(project_root, "mvnProject-Client", "src", "main", "java", "com", "example", "DatabaseClient.java")

    # 1. Configure and Deploy the Server Instance
    print("\nAttempting to configure and deploy the Server EC2 instance...")
    try:
        update_java_config_on_ec2(
            ec2_public_ip=SERVER_EC2_PUBLIC_IP,
            ec2_private_ip=SERVER_EC2_PRIVATE_IP,
            key_pair_path=KEY_PAIR_PATH,
            rds_endpoint=RDS_ENDPOINT,
            db_username=DB_USERNAME,
            db_password=DB_PASSWORD,
            server_app_port=SERVER_APPLICATION_PORT,
            is_server_instance=True
        )
        print("\nServer deployment initiated. Waiting 15 seconds for server to start before deploying client...")
        time.sleep(15) # Give the server app time to fully start up

        # 2. Configure and Deploy the Client Instance
        print("\nAttempting to configure and deploy the Client EC2 instance...")
        update_java_config_on_ec2(
            ec2_public_ip=CLIENT_EC2_PUBLIC_IP,
            # For the client, ec2_private_ip, rds_endpoint, db_username, db_password are not applicable
            # to its own configuration, but the server's public IP is passed in ec2_public_ip.
            ec2_private_ip=SERVER_EC2_PUBLIC_IP, # Client connects to server's public IP
            key_pair_path=KEY_PAIR_PATH,
            server_app_port=SERVER_APPLICATION_PORT, # Pass server port for client config
            is_server_instance=False
        )
        print("\nClient deployment completed.")
        
    except Exception as e:
        print(f"An error occurred during the main deployment process: {e}")

    # 1. Aggiorna i file localmente
    update_local_java_config(
        server_ip=SERVER_EC2_PRIVATE_IP,
        server_port=SERVER_APPLICATION_PORT,
        rds_endpoint=RDS_ENDPOINT,
        db_username=DB_USERNAME,
        db_password=DB_PASSWORD,
        client_server_ip=SERVER_EC2_PUBLIC_IP,
        client_server_port=SERVER_APPLICATION_PORT,
        server_config_path=server_config_path,
        server_db_properties_path=server_db_properties_path,
        client_config_path=client_config_path
    )

    # 2. Commit e push su git
    git_commit_and_push()

    # 3. Connetti via SSH e clona la repo sulle EC2 (usa git clone o git pull)
    # ...qui puoi riadattare la funzione update_java_config_on_ec2 per fare solo git clone/pull e build...