import boto3
import time
import os
import psycopg2
import json
from botocore.exceptions import ClientError

# --- Configurazione AWS ---
REGION = 'us-east-1'
KEY_PAIR_NAME = 'my-ec2-key'
AMI_ID = 'ami-09e6f87a47903347c'
INSTANCE_TYPE = 't2.micro'
NUM_CLIENTS = 0  # Nessun client EC2, solo server EC2

# --- Configurazione Database RDS (PostgreSQL) ---
DB_INSTANCE_IDENTIFIER = 'music-db-app-rds'
DB_ENGINE = 'postgres'
DB_ENGINE_VERSION = '17.4' # Assicurati che questa versione sia supportata da RDS nella tua regione
DB_INSTANCE_CLASS = 'db.t3.micro' # Tipo di istanza RDS
DB_ALLOCATED_STORAGE = 20 # GB
DB_MASTER_USERNAME = 'dbadmin' # Aggiornato con il nome utente non riservato
DB_MASTER_PASSWORD = '12345678' # !!! CAMBIA QUESTA PASSWORD CON UNA ROBUSTA E UNICA !!!
DB_NAME = 'musicdb' # Nome del database all'interno di PostgreSQL

# --- Funzioni di supporto ---
def get_key_pair(ec2_client, key_name):
    try:
        response = ec2_client.describe_key_pairs(KeyNames=[key_name])
        print(f"La chiave EC2 '{key_name}' esiste già.")
        return response['KeyPairs'][0]['KeyName']
    except ClientError as e:
        if "InvalidKeyPair.NotFound" in str(e):
            print(f"La chiave EC2 '{key_name}' non trovata. Creazione in corso...")
            key_pair = ec2_client.create_key_pair(KeyName=key_name)
            with open(f"{key_name}.pem", "w") as f:
                f.write(key_pair['KeyMaterial'])
            os.chmod(f"{key_name}.pem", 0o400) # Imposta permessi restrittivi
            print(f"Chiave '{key_name}.pem' creata.")
            return key_pair['KeyName']
        else:
            raise

def create_vpc_and_security_groups(ec2_client, rds_client):
    print("Verifica o creazione di VPC e Security Groups...")
    # Get default VPC
    vpcs = ec2_client.describe_vpcs(Filters=[{'Name': 'isDefault', 'Values': ['true']}])
    vpc_id = vpcs['Vpcs'][0]['VpcId']
    print(f"VPC predefinito trovato: {vpc_id}")

    # Create Security Group for RDS
    try:
        rds_sg_response = ec2_client.create_security_group(
            GroupName='MusicAppRDSSecurityGroup',
            Description='Allow PostgreSQL access for MusicApp EC2 instances and local script',
            VpcId=vpc_id
        )
        rds_security_group_id = rds_sg_response['GroupId']
        print(f"Security Group RDS creato: {rds_security_group_id}")
    except ClientError as e:
        if 'InvalidGroup.Duplicate' in str(e):
            rds_security_group_id = ec2_client.describe_security_groups(
                GroupNames=['MusicAppRDSSecurityGroup'], Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}]
            )['SecurityGroups'][0]['GroupId']
            print(f"Security Group RDS esistente: {rds_security_group_id}")
        else:
            raise

    # Create Security Group for EC2
    try:
        ec2_sg_response = ec2_client.create_security_group(
            GroupName='MusicAppEC2SecurityGroup',
            Description='Allow SSH and application traffic to MusicApp EC2 instances',
            VpcId=vpc_id
        )
        ec2_security_group_id = ec2_sg_response['GroupId']
        print(f"Security Group EC2 creato: {ec2_security_group_id}")
    except ClientError as e:
        if 'InvalidGroup.Duplicate' in str(e):
            ec2_security_group_id = ec2_client.describe_security_groups(
                GroupNames=['MusicAppEC2SecurityGroup'], Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}]
            )['SecurityGroups'][0]['GroupId']
            print(f"Security Group EC2 esistente: {ec2_security_group_id}")
        else:
            raise

    # Authorize ingress for RDS SG (from EC2 SG)
    try:
        ec2_client.authorize_security_group_ingress(
            GroupId=rds_security_group_id,
            IpPermissions=[
                {
                    'IpProtocol': 'tcp',
                    'FromPort': 5432, # PostgreSQL port
                    'ToPort': 5432,
                    'UserIdGroupPairs': [{'GroupId': ec2_security_group_id}]
                }
            ]
        )
        print("Regola di ingresso RDS SG autorizzata per EC2 SG.")
    except ClientError as e:
        if 'InvalidPermission.Duplicate' in str(e):
            print("Regola di ingresso RDS SG già esistente (EC2->RDS).")
        else:
            raise

    # NEW: Authorize ingress for RDS SG (from local machine / 0.0.0.0/0 for script init)
    try:
        ec2_client.authorize_security_group_ingress(
            GroupId=rds_security_group_id,
            IpPermissions=[
                {
                    'IpProtocol': 'tcp',
                    'FromPort': 5432, # PostgreSQL port
                    'ToPort': 5432,
                    'IpRanges': [{'CidrIp': '0.0.0.0/0', 'Description': 'Allow local script access for DB init (dev only)'}]
                }
            ]
        )
        print("Regola di ingresso RDS SG autorizzata per 0.0.0.0/0 (necessaria per l'inizializzazione locale).")
    except ClientError as e:
        if 'InvalidPermission.Duplicate' in str(e):
            print("Regola di ingresso RDS SG già esistente (0.0.0.0/0->RDS).")
        else:
            raise
            
    # Authorize ingress for EC2 SG (SSH from anywhere, App from anywhere)
    try:
        ec2_client.authorize_security_group_ingress(
            GroupId=ec2_security_group_id,
            IpPermissions=[
                {
                    'IpProtocol': 'tcp',
                    'FromPort': 22, # SSH
                    'ToPort': 22,
                    'IpRanges': [{'CidrIp': '0.0.0.0/0'}]
                },
                {
                    'IpProtocol': 'tcp',
                    'FromPort': 8080, # Application port
                    'ToPort': 8080,
                    'IpRanges': [{'CidrIp': '0.0.0.0/0'}]
                }
            ]
        )
        print("Regole di ingresso EC2 SG autorizzate (SSH, App).")
    except ClientError as e:
        if 'InvalidPermission.Duplicate' in str(e):
            print("Regole di ingresso EC2 SG già esistenti.")
        else:
            raise

    return vpc_id, rds_security_group_id, ec2_security_group_id

def delete_resources(ec2_client, rds_client, key_name, rds_id, rds_sg_name, ec2_sg_name):
    print("Avvio pulizia risorse AWS...")

    # Terminate EC2 instances
    print("Terminazione istanze EC2...")
    instances = ec2_client.describe_instances(
        Filters=[{'Name': 'tag:Application', 'Values': ['MusicApp']}]
    )
    instance_ids = []
    for reservation in instances['Reservations']:
        for instance in reservation['Instances']:
            if instance['State']['Name'] != 'terminated':
                instance_ids.append(instance['InstanceId'])
    if instance_ids:
        ec2_client.terminate_instances(InstanceIds=instance_ids)
        print(f"Istanze EC2 terminate: {instance_ids}. Attesa terminazione...")
        waiter = ec2_client.get_waiter('instance_terminated')
        waiter.wait(InstanceIds=instance_ids)
        print("Istanze EC2 terminate con successo.")
    else:
        print("Nessuna istanza EC2 'MusicApp' trovata da terminare.")

    # Delete RDS instance
    print(f"Eliminazione istanza RDS '{rds_id}'...")
    try:
        rds_client.delete_db_instance(
            DBInstanceIdentifier=rds_id,
            SkipFinalSnapshot=True # Skip for quick cleanup
        )
        print(f"Istanza RDS '{rds_id}' eliminata. Attesa eliminazione...")
        waiter = rds_client.get_waiter('db_instance_deleted')
        waiter.wait(DBInstanceIdentifier=rds_id)
        print(f"Istanza RDS '{rds_id}' eliminata con successo.")
    except ClientError as e:
        if "DBInstanceNotFound" in str(e):
            print(f"Istanza RDS '{rds_id}' non trovata o già eliminata.")
        else:
            print(f"Errore durante l'eliminazione dell'istanza RDS: {e}")

    # Delete Security Groups
    print("Eliminazione Security Groups...")
    vpcs = ec2_client.describe_vpcs(Filters=[{'Name': 'isDefault', 'Values': ['true']}])
    vpc_id = vpcs['Vpcs'][0]['VpcId']
    
    # Tentativo di eliminare i SG in un ordine che riduca le violazioni di dipendenza
    sg_to_delete = []
    try:
        rds_sg_id = ec2_client.describe_security_groups(
            GroupNames=[rds_sg_name], Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}]
        )['SecurityGroups'][0]['GroupId']
        sg_to_delete.append(rds_sg_id)
    except ClientError as e:
        if "InvalidGroup.NotFound" not in str(e): print(f"Errore: {e}")
    
    try:
        ec2_sg_id = ec2_client.describe_security_groups(
            GroupNames=[ec2_sg_name], Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}]
        )['SecurityGroups'][0]['GroupId']
        sg_to_delete.append(ec2_sg_id)
    except ClientError as e:
        if "InvalidGroup.NotFound" not in str(e): print(f"Errore: {e}")

    # Tentativo di rimuovere prima le regole di ingresso inter-SG
    for sg_id in sg_to_delete:
        try:
            # Revoca tutte le regole di ingresso per il SG
            sg_details = ec2_client.describe_security_groups(GroupIds=[sg_id])['SecurityGroups'][0]
            if 'IpPermissions' in sg_details and sg_details['IpPermissions']:
                ec2_client.revoke_security_group_ingress(
                    GroupId=sg_id,
                    IpPermissions=sg_details['IpPermissions']
                )
                print(f"Revocate regole di ingresso per SG {sg_id}.")
        except ClientError as e:
            if 'InvalidPermission.NotFound' not in str(e):
                print(f"Avviso: Impossibile revocare regole di ingresso per {sg_id}: {e}")

    # Ora elimina i SG
    for sg_name_current in [rds_sg_name, ec2_sg_name]: # Ordine fisso per ridurre dipendenze
        try:
            sg_id_current = ec2_client.describe_security_groups(
                GroupNames=[sg_name_current], Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}]
            )['SecurityGroups'][0]['GroupId']
            ec2_client.delete_security_group(GroupId=sg_id_current)
            print(f"Security Group '{sg_name_current}' ({sg_id_current}) eliminato.")
        except ClientError as e:
            if "InvalidGroup.NotFound" in str(e):
                print(f"Security Group '{sg_name_current}' non trovato o già eliminato.")
            elif "DependencyViolation" in str(e):
                print(f"Errore: Il Security Group '{sg_name_current}' ha ancora dipendenze. Riprovare tra qualche istante o eliminare manualmente.")
            else:
                print(f"Errore durante l'eliminazione del Security Group '{sg_name_current}': {e}")
    
    # Delete Key Pair
    print(f"Eliminazione Key Pair '{key_name}'...")
    try:
        ec2_client.delete_key_pair(KeyName=key_name)
        print(f"Key Pair '{key_name}' eliminata da AWS.")
        if os.path.exists(f"{key_name}.pem"):
            try:
                os.remove(f"{key_name}.pem")
                print(f"File locale '{key_name}.pem' eliminato.")
            except PermissionError:
                print(f"AVVISO: Impossibile eliminare il file locale '{key_name}.pem' a causa di un errore di permessi (potrebbe essere in uso). Eliminalo manualmente.")
            except Exception as file_e:
                print(f"AVVISO: Errore durante l'eliminazione del file locale '{key_name}.pem': {file_e}")
    except ClientError as e:
        if "InvalidKeyPair.NotFound" in str(e):
            print(f"Key Pair '{key_name}' non trovata o già eliminata in AWS.")
            if os.path.exists(f"{key_name}.pem"):
                try:
                    os.remove(f"{key_name}.pem")
                    print(f"File locale '{key_name}.pem' eliminato.")
                except PermissionError:
                    print(f"AVVISO: Impossibile eliminare il file locale '{key_name}.pem' a causa di un errore di permessi (potrebbe essere in uso). Eliminalo manualmente.")
                except Exception as file_e:
                    print(f"AVVISO: Errore durante l'eliminazione del file locale '{key_name}.pem': {file_e}")
        else:
            print(f"Errore durante l'eliminazione della Key Pair in AWS: {e}")
            raise # Re-raise other ClientErrors

    print("Pulizia risorse AWS completata.")


def initialize_database(rds_endpoint, db_username, db_password, db_name, schema_sql, data_sql):
    print(f"\nInizializzazione del database '{db_name}' su {rds_endpoint}...")

    # Connessione al database "postgres" (il database predefinito) per drop/create
    conn_str_master = f"dbname=postgres user={db_username} password={db_password} host={rds_endpoint} port=5432"
    conn = None
    try:
        # Tentativo di connessione con retry per dare tempo all'RDS di avviarsi
        for i in range(5):
            try:
                conn = psycopg2.connect(conn_str_master)
                conn.autocommit = True # Permette DDL come DROP DATABASE
                print("Connesso al database 'postgres' per la gestione.")
                break
            except psycopg2.OperationalError as e:
                print(f"Tentativo {i+1} di connessione fallito: {e}. Attesa 10 secondi...")
                time.sleep(10)
        if conn is None:
            raise Exception("Impossibile connettersi al database master PostgreSQL.")

        cur = conn.cursor()

        # 1. Termina tutte le connessioni al database target
        print(f"Terminazione connessioni attive al database '{db_name}'...")
        try:
            cur.execute(f"""
                SELECT pg_terminate_backend(pg_stat_activity.pid)
                FROM pg_stat_activity
                WHERE pg_stat_activity.datname = '{db_name}'
                  AND pid <> pg_backend_pid();
            """)
            print(f"Connessioni terminate per '{db_name}'.")
        except Exception as e:
            print(f"Avviso: Errore durante la terminazione delle connessioni (potrebbe non esistere o non avere permessi): {e}")

        # 2. Drop del database esistente (se esiste)
        print(f"Tentativo di drop del database '{db_name}' (se esiste)...")
        try:
            cur.execute(f"DROP DATABASE IF EXISTS {db_name};")
            print(f"Database '{db_name}' eliminato (o non esisteva).")
        except Exception as e:
            print(f"Errore durante il drop del database '{db_name}': {e}")
            raise # Rilancia l'errore se non si riesce a eliminare il DB

        # 3. Creazione del database
        print(f"Creazione del database '{db_name}'...")
        cur.execute(f"CREATE DATABASE {db_name};")
        print(f"Database '{db_name}' creato.")

        cur.close()
        conn.close() # Chiudi la connessione al database master

        # Connessione al database appena creato per schema e dati
        conn_str_app = f"dbname={db_name} user={db_username} password={db_password} host={rds_endpoint} port=5432"
        conn_app = None
        for i in range(5):
            try:
                conn_app = psycopg2.connect(conn_str_app)
                print(f"Connesso al database '{db_name}' per l'inizializzazione dello schema.")
                break
            except psycopg2.OperationalError as e:
                print(f"Tentativo {i+1} di connessione al DB dell'app fallito: {e}. Attesa 5 secondi...")
                time.sleep(5)
        if conn_app is None:
            raise Exception("Impossibile connettersi al database dell'applicazione.")

        conn_app.autocommit = True # Per eseguire più statement DDL/DML senza commit esplicito
        cur_app = conn_app.cursor()

        # Esecuzione dello schema
        print("Esecuzione dello schema.sql...")
        try:
            cur_app.execute(schema_sql)
            print("Schema.sql eseguito con successo.")
        except Exception as e:
            print(f"Errore durante l'esecuzione dello schema SQL: {e}")
            raise

        # Esecuzione dei dati
        print("Esecuzione dei dati.sql...")
        try:
            cur_app.execute(data_sql)
            print("Dati.sql eseguiti con successo.")
        except Exception as e:
            print(f"Errore durante l'esecuzione del comando SQL per i dati: {e}")
            raise

        cur_app.close()
        conn_app.close()
        print(f"Inizializzazione del database '{db_name}' completata con successo.")

    except psycopg2.Error as e:
        print(f"Errore durante l'inizializzazione del database: {e}")
        raise # Rilancia l'errore per fermare lo script principale
    except Exception as e:
        print(f"Si è verificato un errore inaspettato durante l'inizializzazione del database: {e}")
        raise
    finally:
        if conn:
            conn.close()
        if 'conn_app' in locals() and conn_app:
            conn_app.close()


# --- Main deployment logic ---
def main():
    if "--clean" in os.sys.argv:
        ec2 = boto3.client('ec2', region_name=REGION)
        rds = boto3.client('rds', region_name=REGION)
        delete_resources(ec2, rds, KEY_PAIR_NAME, DB_INSTANCE_IDENTIFIER, 'MusicAppRDSSecurityGroup', 'MusicAppEC2SecurityGroup')
        return

    ec2_client = boto3.client('ec2', region_name=REGION)
    rds_client = boto3.client('rds', region_name=REGION)

    # --- LEGGI I FILE SQL ---
    schema_sql_path = os.path.join(
        os.path.dirname(__file__),
        '..', '..', 'Database', 'Sql', 'schema.sql'
    )
    dati_sql_path = os.path.join(
        os.path.dirname(__file__),
        '..', '..', 'Database', 'Sql', 'dati.sql'
    )
    with open(os.path.abspath(schema_sql_path), 'r', encoding='utf-8') as f:
        schema_sql_content = f.read()
    with open(os.path.abspath(dati_sql_path), 'r', encoding='utf-8') as f:
        dati_sql_content = f.read()

    try:
        # 1. Ottieni o crea la Key Pair
        key_pair_name_actual = get_key_pair(ec2_client, KEY_PAIR_NAME)

        # 2. Crea VPC e Security Groups
        vpc_id, rds_security_group_id, ec2_security_group_id = create_vpc_and_security_groups(ec2_client, rds_client)

        # 3. Deploy RDS Instance
        print(f"\nTentativo di deploy dell'istanza RDS '{DB_INSTANCE_IDENTIFIER}'...")
        rds_endpoint = None
        try:
            # Try to describe if it already exists and is available
            response = rds_client.describe_db_instances(DBInstanceIdentifier=DB_INSTANCE_IDENTIFIER)
            instance_status = response['DBInstances'][0]['DBInstanceStatus']
            rds_endpoint = response['DBInstances'][0]['Endpoint']['Address']
            print(f"Istanza RDS '{DB_INSTANCE_IDENTIFIER}' trovata con stato: {instance_status}.")
            if instance_status != 'available':
                print(f"Attesa che l'istanza RDS '{DB_INSTANCE_IDENTIFIER}' diventi 'available'...")
                waiter = rds_client.get_waiter('db_instance_available')
                waiter.wait(DBInstanceIdentifier=DB_INSTANCE_IDENTIFIER)
                response = rds_client.describe_db_instances(DBInstanceIdentifier=DB_INSTANCE_IDENTIFIER)
                rds_endpoint = response['DBInstances'][0]['Endpoint']['Address']
                print(f"Istanza RDS '{DB_INSTANCE_IDENTIFIER}' è ora 'available'.")
        except ClientError as e:
            if "DBInstanceNotFound" in str(e):
                print(f"Istanza RDS '{DB_INSTANCE_IDENTIFIER}' non trovata. Creazione in corso...")
                rds_client.create_db_instance(
                    DBInstanceIdentifier=DB_INSTANCE_IDENTIFIER,
                    DBInstanceClass=DB_INSTANCE_CLASS,
                    Engine=DB_ENGINE,
                    MasterUsername=DB_MASTER_USERNAME,
                    MasterUserPassword=DB_MASTER_PASSWORD,
                    AllocatedStorage=DB_ALLOCATED_STORAGE,
                    DBName=DB_NAME,
                    VpcSecurityGroupIds=[rds_security_group_id],
                    EngineVersion=DB_ENGINE_VERSION,
                    PubliclyAccessible=True # Per debug e accesso da locale, cambia a False per sicurezza in prod
                )
                print(f"Creazione dell'istanza RDS '{DB_INSTANCE_IDENTIFIER}' avviata. Attesa che diventi 'available'...")
                waiter = rds_client.get_waiter('db_instance_available')
                waiter.wait(DBInstanceIdentifier=DB_INSTANCE_IDENTIFIER)
                response = rds_client.describe_db_instances(DBInstanceIdentifier=DB_INSTANCE_IDENTIFIER)
                rds_endpoint = response['DBInstances'][0]['Endpoint']['Address']
                print(f"Istanza RDS '{DB_INSTANCE_IDENTIFIER}' è ora 'available'. Endpoint: {rds_endpoint}")
            else:
                raise

        if not rds_endpoint:
            raise Exception("Impossibile ottenere l'endpoint RDS.")

        # 4. Inizializza il database con lo schema e i dati
        print("Inizializzazione database RDS con schema e dati...")
        initialize_database(
            rds_endpoint=rds_endpoint,
            db_username=DB_MASTER_USERNAME,
            db_password=DB_MASTER_PASSWORD,
            db_name=DB_NAME,
            schema_sql=schema_sql_content,
            data_sql=dati_sql_content
        )

        # 5. Get User Data Script
        with open('user_data_script.sh', 'r') as f:
            user_data_script = f.read()

        # 6. Deploy MusicAppServer EC2 instance (or use existing)
        server_public_ip = None
        server_private_ip = None
        server_instances_found = ec2_client.describe_instances(
            Filters=[
                {'Name': 'tag:Name', 'Values': ['MusicAppServer']},
                {'Name': 'instance-state-name', 'Values': ['pending', 'running']}
            ]
        )['Reservations']

        if server_instances_found:
            server_instance_id = server_instances_found[0]['Instances'][0]['InstanceId']
            server_public_ip = server_instances_found[0]['Instances'][0].get('PublicIpAddress')
            server_private_ip = server_instances_found[0]['Instances'][0].get('PrivateIpAddress')
            print(f"\nIstanza MusicAppServer esistente e running: {server_instance_id}. IP Pubblico: {server_public_ip}, IP Privato: {server_private_ip}")
        else:
            print("\nDeploy dell'istanza EC2 'MusicAppServer'...")
            server_instances = ec2_client.run_instances(
                ImageId=AMI_ID,
                InstanceType=INSTANCE_TYPE,
                MinCount=1,
                MaxCount=1,
                KeyName=key_pair_name_actual,
                SecurityGroupIds=[ec2_security_group_id],
                UserData=user_data_script,
                TagSpecifications=[
                    {
                        'ResourceType': 'instance',
                        'Tags': [
                            {'Key': 'Name', 'Value': 'MusicAppServer'},
                            {'Key': 'Application', 'Value': 'MusicApp'}
                        ]
                    },
                ]
            )
            server_instance_id = server_instances['Instances'][0]['InstanceId']
            print(f"Istanza MusicAppServer avviata: {server_instance_id}. Attesa che sia 'running'...")
            waiter = ec2_client.get_waiter('instance_running')
            waiter.wait(InstanceIds=[server_instance_id])
            server_instance_details = ec2_client.describe_instances(InstanceIds=[server_instance_id])
            server_public_ip = server_instance_details['Reservations'][0]['Instances'][0]['PublicIpAddress']
            server_private_ip = server_instance_details['Reservations'][0]['Instances'][0]['PrivateIpAddress']
            print(f"MusicAppServer è running. IP Pubblico: {server_public_ip}, IP Privato: {server_private_ip}")

        # 7. Deploy MusicAppClient EC2 instances (or use existing)
        client_public_ips = []
        client_private_ips = []
        # Nessun deploy client EC2: client sarà in localhost
        print("\n--- Deploy Completato ---")
        print("Dettagli per la connessione:")
        print(f"Chiave SSH: {key_pair_name_actual}.pem")
        print(f"Endpoint RDS: {rds_endpoint}")
        print(f"Utente DB: {DB_MASTER_USERNAME}")
        print(f"Password DB: {DB_MASTER_PASSWORD}")
        print(f"Nome DB: {DB_NAME}")
        print(f"\nIP Pubblico Server EC2: {server_public_ip}")
        print(f"IP Privato Server EC2 (per client nella stessa VPC): {server_private_ip}")
        print(f"Client locale: usa l'IP pubblico del server EC2 per connettersi")

        # Salva la configurazione in un file JSON
        config = {
            "server_public_ip": server_public_ip,
            "server_private_ip": server_private_ip,
            "client_public_ips": [],  # Nessun client EC2
            "rds_endpoint": rds_endpoint,
            "db_username": DB_MASTER_USERNAME,
            "db_password": DB_MASTER_PASSWORD,
            "db_name": DB_NAME,
            "key_pair_name": key_pair_name_actual
        }
        with open("deploy_config.json", "w") as f:
            json.dump(config, f, indent=4)
        print("\nConfigurazione salvata in 'deploy_config.json'.")

        print("\n--- Prossimi Passi ---")
        print("1. Aggiorna la configurazione del client locale per puntare all'IP pubblico del server EC2.")
        print("2. Avvia il server su EC2 e il client in locale.")

    except ClientError as e:
        print(f"Si è verificato un errore AWS: {e}")
    except Exception as e:
        print(f"Si è verificato un errore inaspettato: {e}")

if __name__ == "__main__":
    main()