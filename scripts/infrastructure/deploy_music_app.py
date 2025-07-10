import boto3
import time
import os
import psycopg2
import json
import configparser
from botocore.exceptions import ClientError

# configurazione AWS
REGION = 'us-east-1'
KEY_PAIR_NAME = 'my-ec2-key'
AMI_ID = 'ami-09e6f87a47903347c'
INSTANCE_TYPE = 't2.micro'

# configurazione Database RDS
DB_INSTANCE_IDENTIFIER = 'music-db-app-rds'
DB_ENGINE = 'postgres'
DB_ENGINE_VERSION = '17.4'
DB_INSTANCE_CLASS = 'db.t3.micro'
DB_ALLOCATED_STORAGE = 20
DB_MASTER_USERNAME = 'dbadmin'
DB_MASTER_PASSWORD = '12345678'
DB_NAME = 'musicdb'

def read_aws_credentials():
    """Legge le credenziali AWS dal file ~/.aws/credentials locale"""
    credentials_path = os.path.expanduser('~/.aws/credentials')
    if not os.path.exists(credentials_path):
        raise Exception(f"File delle credenziali AWS non trovato: {credentials_path}")
    
    config = configparser.ConfigParser()
    config.read(credentials_path)
    
    if 'default' not in config:
        raise Exception("Sezione [default] non trovata nel file delle credenziali AWS")
    
    credentials = {
        'aws_access_key_id': config['default'].get('aws_access_key_id'),
        'aws_secret_access_key': config['default'].get('aws_secret_access_key'),
        'aws_session_token': config['default'].get('aws_session_token')  # Può essere None
    }
    
    if not credentials['aws_access_key_id'] or not credentials['aws_secret_access_key']:
        raise Exception("Credenziali AWS incomplete nel file ~/.aws/credentials")
    
    print("[INFO] Credenziali AWS lette correttamente dal file locale")
    return credentials

def update_user_data_with_credentials(user_data_script, credentials):
    """Sostituisce i placeholder nel user data script con le credenziali reali"""
    updated_script = user_data_script.replace(
        'AWS_ACCESS_KEY_ID_PLACEHOLDER', credentials['aws_access_key_id']
    ).replace(
        'AWS_SECRET_ACCESS_KEY_PLACEHOLDER', credentials['aws_secret_access_key']
    )
    
    # Gestisce il session token (può essere None per credenziali permanenti)
    if credentials['aws_session_token']:
        updated_script = updated_script.replace(
            'AWS_SESSION_TOKEN_PLACEHOLDER', credentials['aws_session_token']
        )
    else:
        # Rimuove la riga del session token se non presente
        lines = updated_script.split('\n')
        updated_lines = [line for line in lines if 'AWS_SESSION_TOKEN_PLACEHOLDER' not in line]
        updated_script = '\n'.join(updated_lines)
    
    return updated_script

def get_key_pair(ec2_client, key_name):

    print("\n[SECTION] Gestione Chiave EC2")
    print("-" * 50)
    try:
        response = ec2_client.describe_key_pairs(KeyNames=[key_name])
        print(f"[INFO] La chiave EC2 '{key_name}' è già presente nel tuo account AWS.")
        return response['KeyPairs'][0]['KeyName']
    except ClientError as e:
        if "InvalidKeyPair.NotFound" in str(e):
            print(f"[INFO] La chiave EC2 '{key_name}' non è stata trovata. Avvio della creazione...")
            key_pair = ec2_client.create_key_pair(KeyName=key_name)
            with open(f"{key_name}.pem", "w") as f:
                f.write(key_pair['KeyMaterial'])
            os.chmod(f"{key_name}.pem", 0o400)
            print(f"[SUCCESS] File '{key_name}.pem' creato e salvato localmente.")
            return key_pair['KeyName']
        else:
            raise

def create_vpc_and_security_groups(ec2_client, rds_client):

    print("\n[SECTION] VPC e Security Groups")
    print("-" * 50)
    # VPC di default
    vpcs = ec2_client.describe_vpcs(Filters=[{'Name': 'isDefault', 'Values':['true']}])
    vpc_id = vpcs['Vpcs'][0]['VpcId']
    print(f"[INFO] VPC di default individuata: {vpc_id}")

    # creazione Security Group per RDS
    try:
        rds_sg_response = ec2_client.create_security_group(
            GroupName='MusicAppRDSSecurityGroup',
            Description='Consenti accesso PostgreSQL per EC2 MusicApp e script locale',
            VpcId=vpc_id
        )
        rds_security_group_id = rds_sg_response['GroupId']
        print(f"[SUCCESS] Security Group per RDS creata con ID: {rds_security_group_id}")
    except ClientError as e:
        if 'InvalidGroup.Duplicate' in str(e):
            rds_security_group_id = ec2_client.describe_security_groups(
                GroupNames=['MusicAppRDSSecurityGroup'], Filters=[{'Name': 'vpc-id', 'Values':[vpc_id]}]
            )['SecurityGroups'][0]['GroupId']
            print(f"[INFO] Security Group per RDS già esistente: {rds_security_group_id}")
        else:
            raise

    # creazione Security Group per EC2
    try:
        ec2_sg_response = ec2_client.create_security_group(
            GroupName='MusicAppEC2SecurityGroup',
            Description='Consenti SSH e traffico applicativo alle istanze EC2 MusicApp',
            VpcId=vpc_id
        )
        ec2_security_group_id = ec2_sg_response['GroupId']
        print(f"[SUCCESS] Security Group per EC2 creata con ID: {ec2_security_group_id}")
    except ClientError as e:
        if 'InvalidGroup.Duplicate' in str(e):
            ec2_security_group_id = ec2_client.describe_security_groups(
                GroupNames=['MusicAppEC2SecurityGroup'], Filters=[{'Name': 'vpc-id', 'Values':[vpc_id]}]
            )['SecurityGroups'][0]['GroupId']
            print(f"[INFO] Security Group per EC2 già esistente: {ec2_security_group_id}")
        else:
            raise

    # autorizzazioni per SG RDS (da EC2 SG)
    try:
        ec2_client.authorize_security_group_ingress(
            GroupId=rds_security_group_id,
            IpPermissions=[
                {
                    'IpProtocol': 'tcp',
                    'FromPort': 5432, # Porta PostgreSQL
                    'ToPort': 5432,
                    'UserIdGroupPairs':[{'GroupId': ec2_security_group_id}]
                }
            ]
        )
        print("[SUCCESS] Regola di ingresso per RDS autorizzata dal Security Group EC2.")
    except ClientError as e:
        if 'InvalidPermission.Duplicate' in str(e):
            print("[INFO] Regola di ingresso per RDS già presente (EC2->RDS).")
        else:
            raise

    # autorizzazioni per SG RDS da macchina locale (solo per inizializzazione DB, sviluppo)
    try:
        ec2_client.authorize_security_group_ingress(
            GroupId=rds_security_group_id,
            IpPermissions=[
                {
                    'IpProtocol': 'tcp',
                    'FromPort': 5432, # Porta PostgreSQL
                    'ToPort': 5432,
                    'IpRanges':[{'CidrIp': '0.0.0.0/0', 'Description': 'Consenti accesso script locale per init DB (solo sviluppo)'}]
                }
            ]
        )
        print("[SUCCESS] Regola di ingresso per RDS autorizzata da 0.0.0.0/0 per inizializzazione locale.")
    except ClientError as e:
        if 'InvalidPermission.Duplicate' in str(e):
            print("[INFO] Regola di ingresso per RDS già presente (0.0.0.0/0->RDS).")
        else:
            raise
            
    # autorizzazioni per EC2 (SSH e porta app)
    try:
        ec2_client.authorize_security_group_ingress(
            GroupId=ec2_security_group_id,
            IpPermissions=[
                {
                    'IpProtocol': 'tcp',
                    'FromPort': 22, # SSH
                    'ToPort': 22,
                    'IpRanges':[{'CidrIp': '0.0.0.0/0'}]
                },
                {
                    'IpProtocol': 'tcp',
                    'FromPort': 8080, # porta app
                    'ToPort': 8080,
                    'IpRanges':[{'CidrIp': '0.0.0.0/0'}]
                }
            ]
        )
        print("[SUCCESS] Regole di ingresso per EC2 autorizzate per SSH e applicazione.")
    except ClientError as e:
        if 'InvalidPermission.Duplicate' in str(e):
            print("[INFO] Regole di ingresso per EC2 già presenti.")
        else:
            raise

    return vpc_id, rds_security_group_id, ec2_security_group_id

def delete_resources(ec2_client, rds_client, key_name, rds_id, rds_sg_name, ec2_sg_name):
    print("\n[SECTION] Pulizia Risorse AWS")
    print("-" * 50)

    # termino EC2
    print("[STEP] Terminazione delle istanze EC2 in corso...")
    instances = ec2_client.describe_instances(
        Filters=[{'Name': 'tag:Application', 'Values':['MusicApp']}]
    )
    instance_ids =[]
    for reservation in instances['Reservations']:
        for instance in reservation['Instances']:
            if instance['State']['Name'] != 'terminated':
                instance_ids.append(instance['InstanceId'])
    if instance_ids:
        ec2_client.terminate_instances(InstanceIds=instance_ids)
        print(f"[INFO] Istanze EC2 terminate: {instance_ids}. Attendo la conferma di terminazione...")
        waiter = ec2_client.get_waiter('instance_terminated')
        waiter.wait(InstanceIds=instance_ids)
        print("[SUCCESS] Tutte le istanze EC2 sono state terminate correttamente.")
    else:
        print("[INFO] Nessuna istanza EC2 'MusicApp' trovata da terminare.")

    # elimino RDS
    print(f"[STEP] Eliminazione dell'istanza RDS '{rds_id}' in corso...")
    try:
        rds_client.delete_db_instance(
            DBInstanceIdentifier=rds_id,
            SkipFinalSnapshot=True
        )
        print(f"[INFO] Istanza RDS '{rds_id}' eliminata. Attesa della cancellazione...")
        waiter = rds_client.get_waiter('db_instance_deleted')
        waiter.wait(DBInstanceIdentifier=rds_id)
        print(f"[SUCCESS] Istanza RDS '{rds_id}' eliminata.")
    except ClientError as e:
        if "DBInstanceNotFound" in str(e):
            print(f"[INFO] Istanza RDS '{rds_id}' non trovata o già eliminata.")
        else:
            print(f"[ERROR] durante l'eliminazione dell'istanza RDS: {e}")

    # elimino SG
    print("[STEP] Eliminazione dei Security Groups...")
    vpcs = ec2_client.describe_vpcs(Filters=[{'Name': 'isDefault', 'Values':['true']}])
    vpc_id = vpcs['Vpcs'][0]['VpcId']
    
    sg_to_delete =[]
    try:
        rds_sg_id = ec2_client.describe_security_groups(
            GroupNames=[rds_sg_name], Filters=[{'Name': 'vpc-id', 'Values':[vpc_id]}]
        )['SecurityGroups'][0]['GroupId']
        sg_to_delete.append(rds_sg_id)
    except ClientError as e:
        if "InvalidGroup.NotFound" not in str(e): print(f"[ERROR] {e}")
    
    try:
        ec2_sg_id = ec2_client.describe_security_groups(
            GroupNames=[ec2_sg_name], Filters=[{'Name': 'vpc-id', 'Values':[vpc_id]}]
        )['SecurityGroups'][0]['GroupId']
        sg_to_delete.append(ec2_sg_id)
    except ClientError as e:
        if "InvalidGroup.NotFound" not in str(e): print(f"[ERROR] {e}")

    for sg_id in sg_to_delete:
        try:
            sg_details = ec2_client.describe_security_groups(GroupIds=[sg_id])['SecurityGroups'][0]
            if 'IpPermissions' in sg_details and sg_details['IpPermissions']:
                ec2_client.revoke_security_group_ingress(
                    GroupId=sg_id,
                    IpPermissions=sg_details['IpPermissions']
                )
                print(f"[INFO] Regole di ingresso revocate per SG {sg_id}.")
        except ClientError as e:
            if 'InvalidPermission.NotFound' not in str(e):
                print(f"[WARNING] Impossibile revocare regole di ingresso per {sg_id}: {e}")

    for sg_name_current in[rds_sg_name, ec2_sg_name]:
        try:
            sg_id_current = ec2_client.describe_security_groups(
                GroupNames=[sg_name_current], Filters=[{'Name': 'vpc-id', 'Values':[vpc_id]}]
            )['SecurityGroups'][0]['GroupId']
            ec2_client.delete_security_group(GroupId=sg_id_current)
            print(f"[INFO] Security Group '{sg_name_current}' ({sg_id_current}) eliminato.")
        except ClientError as e:
            if "InvalidGroup.NotFound" in str(e):
                print(f"[INFO] Security Group '{sg_name_current}' non trovato o già eliminato.")
            elif "DependencyViolation" in str(e):
                print(f"[WARNING] Security Group '{sg_name_current}' ha ancora dipendenze. Riprova più tardi o elimina manualmente.")
            else:
                print(f"[ERROR] durante l'eliminazione del Security Group '{sg_name_current}': {e}")
    
    # elimino Key Pair
    print(f"[STEP] Eliminazione della Key Pair '{key_name}'...")
    try:
        ec2_client.delete_key_pair(KeyName=key_name)
        print(f"[INFO] Key Pair '{key_name}' eliminata da AWS.")
        if os.path.exists(f"{key_name}.pem"):
            try:
                os.remove(f"{key_name}.pem")
                print(f"[INFO] File locale '{key_name}.pem' eliminato.")
            except PermissionError:
                print(f"[WARNING] Impossibile eliminare il file locale '{key_name}.pem' per errore di permessi. Elimina manualmente.")
            except Exception as file_e:
                print(f"[WARNING] Errore nell'eliminazione del file locale '{key_name}.pem': {file_e}")
    except ClientError as e:
        if "InvalidKeyPair.NotFound" in str(e):
            print(f"[INFO] Key Pair '{key_name}' non trovata o già eliminata in AWS.")
            if os.path.exists(f"{key_name}.pem"):
                try:
                    os.remove(f"{key_name}.pem")
                    print(f"[INFO] File locale '{key_name}.pem' eliminato.")
                except PermissionError:
                    print(f"[WARNING] Impossibile eliminare il file locale '{key_name}.pem' per errore di permessi. Elimina manualmente.")
                except Exception as file_e:
                    print(f"[WARNING] Errore nell'eliminazione del file locale '{key_name}.pem': {file_e}")
        else:
            print(f"[ERROR] durante l'eliminazione della Key Pair in AWS: {e}")
            raise

    print("[SUCCESS] Pulizia delle risorse AWS completata.")


def initialize_database(rds_endpoint, db_username, db_password, db_name, schema_sql, data_sql):

    print("\n[SECTION] Inizializzazione Database RDS")
    print("-" * 50)
    print(f"[INFO] Inizializzazione del database '{db_name}' su {rds_endpoint}...")

    # connessione al database postgres
    conn_str_master = f"dbname=postgres user={db_username} password={db_password} host={rds_endpoint} port=5432"
    conn = None
    try:
        for i in range(5):
            try:
                conn = psycopg2.connect(conn_str_master)
                conn.autocommit = True
                print("[INFO] Connesso al database 'postgres' per la gestione.")
                break
            except psycopg2.OperationalError as e:
                print(f"[INFO] Tentativo {i+1} di connessione fallito: {e}. Attesa di 10 secondi...")
                time.sleep(10)
        if conn is None:
            raise Exception("Impossibile connettersi al database master PostgreSQL.")

        cur = conn.cursor()

        # 1. termina tutte le connessioni al database
        print(f"[STEP] Terminazione delle connessioni attive al database '{db_name}'...")
        try:
            cur.execute(f"""
                SELECT pg_terminate_backend(pg_stat_activity.pid)
                FROM pg_stat_activity
                WHERE pg_stat_activity.datname = '{db_name}'
                    AND pid <> pg_backend_pid();
            """)
            print(f"[INFO] Connessioni terminate per '{db_name}'.")
        except Exception as e:
            print(f"[WARNING] Errore nella terminazione delle connessioni: {e}")

        # 2. elimino il database esistente (se esiste)
        print(f"[STEP] Tentativo di eliminazione del database '{db_name}' se esiste...")
        try:
            cur.execute(f"DROP DATABASE IF EXISTS {db_name};")
            print(f"[INFO] Database '{db_name}' eliminato o non esisteva.")
        except Exception as e:
            print(f"[ERROR] Nell'eliminazione del database '{db_name}': {e}")
            raise

        # 3. creo il database
        print(f"[STEP] Creazione del database '{db_name}'...")
        cur.execute(f"CREATE DATABASE {db_name};")
        print(f"[SUCCESS] Database '{db_name}' creato.")

        cur.close()
        conn.close()

        # connetto al database per inizializzazione schema e dati
        conn_str_app = f"dbname={db_name} user={db_username} password={db_password} host={rds_endpoint} port=5432"
        conn_app = None
        for i in range(5):
            try:
                conn_app = psycopg2.connect(conn_str_app)
                print(f"[INFO] Connesso al database '{db_name}' per inizializzazione schema.")
                break
            except psycopg2.OperationalError as e:
                print(f"[INFO] Tentativo {i+1} di connessione al DB app fallito: {e}. Attesa di 5 secondi...")
                time.sleep(5)
        if conn_app is None:
            raise Exception("Impossibile connettersi al database applicativo.")

        conn_app.autocommit = True
        cur_app = conn_app.cursor()

        # schema.sql
        print("[STEP] Esecuzione di schema.sql...")
        try:
            cur_app.execute(schema_sql)
            print("[SUCCESS] schema.sql eseguito con successo.")
        except Exception as e:
            print(f"[ERROR] Nell'esecuzione dello schema SQL: {e}")
            raise

        # data.sql
        print("[STEP] Esecuzione di data.sql...")
        try:
            cur_app.execute(data_sql)
            print("[SUCCESS] data.sql eseguito con successo.")
        except Exception as e:
            print(f"[ERROR] Nell'esecuzione del comando SQL per i dati: {e}")
            raise

        cur_app.close()
        conn_app.close()
        print(f"[SUCCESS] Inizializzazione del database '{db_name}' completata con successo.")

    except psycopg2.Error as e:
        print(f"[ERROR] Durante l'inizializzazione del database: {e}")
        raise
    except Exception as e:
        print(f"[ERROR] Inatteso durante l'inizializzazione del database: {e}")
        raise
    finally:
        if conn:
            conn.close()
        if 'conn_app' in locals() and conn_app:
            conn_app.close()


def get_account_id():
    sts = boto3.client('sts')
    return sts.get_caller_identity()['Account']

def setup_sns_notification(region, topic_name, email_address):
    print("\n[SECTION] Notifiche SNS")
    print("-" * 50)

    sns_client = boto3.client('sns', region_name=region)
    topic_arn = None
    try:
        response = sns_client.create_topic(Name=topic_name)
        topic_arn = response['TopicArn']
        print(f"[SUCCESS] SNS topic creato: {topic_arn}")
    except Exception as e:
        print(f"[ERROR] Nella creazione del topic SNS: {e}")
        raise

    try:
        sns_client.subscribe(TopicArn=topic_arn, Protocol='email', Endpoint=email_address)
        print(f"[SUCCESS] Sottoscrizione email {email_address} al topic SNS completata.")
        print(f"[INFO] Conferma la sottoscrizione tramite il link che riceverai via email.")
    except Exception as e:
        print(f"[ERROR] Nella sottoscrizione email SNS: {e}")
        raise
    return topic_arn

def main():
    if "--clean" in os.sys.argv:
        print("\n[SECTION] Pulizia Risorse AWS")
        print("-" * 50)
        ec2 = boto3.client('ec2', region_name=REGION)
        rds = boto3.client('rds', region_name=REGION)
        if "--nords" in os.sys.argv:
            # elimino tutto tranne il database RDS
            print("[INFO] Opzione --nords attiva: elimino tutte le risorse tranne il database RDS.")
            def delete_resources_no_rds(ec2_client, key_name, rds_sg_name, ec2_sg_name):
                print("\n[SECTION] Pulizia Risorse AWS - No RDS")
                print("-" * 50)
                # Termina le istanze EC2
                print("[STEP] Terminazione delle istanze EC2 in corso...")
                instances = ec2_client.describe_instances(
                    Filters=[{'Name': 'tag:Application', 'Values':['MusicApp']}]
                )
                instance_ids =[]
                for reservation in instances['Reservations']:
                    for instance in reservation['Instances']:
                        if instance['State']['Name'] != 'terminated':
                            instance_ids.append(instance['InstanceId'])
                if instance_ids:
                    ec2_client.terminate_instances(InstanceIds=instance_ids)
                    print(f"[INFO] Istanze EC2 terminate: {instance_ids}. Attendo la conferma di terminazione...")
                    waiter = ec2_client.get_waiter('instance_terminated')
                    waiter.wait(InstanceIds=instance_ids)
                    print("[SUCCESS] Tutte le istanze EC2 sono state terminate correttamente.")
                else:
                    print("[INFO] Nessuna istanza EC2 'MusicApp' trovata da terminare.")

                print("[STEP] Eliminazione dei Security Groups...")
                vpcs = ec2_client.describe_vpcs(Filters=[{'Name': 'isDefault', 'Values':['true']}])
                vpc_id = vpcs['Vpcs'][0]['VpcId']
                sg_to_delete =[]
                try:
                    rds_sg_id = ec2_client.describe_security_groups(
                        GroupNames=[rds_sg_name], Filters=[{'Name': 'vpc-id', 'Values':[vpc_id]}]
                    )['SecurityGroups'][0]['GroupId']
                    sg_to_delete.append(rds_sg_id)
                except ClientError as e:
                    if "InvalidGroup.NotFound" not in str(e): print(f"[ERROR] {e}")
                try:
                    ec2_sg_id = ec2_client.describe_security_groups(
                        GroupNames=[ec2_sg_name], Filters=[{'Name': 'vpc-id', 'Values':[vpc_id]}]
                    )['SecurityGroups'][0]['GroupId']
                    sg_to_delete.append(ec2_sg_id)
                except ClientError as e:
                    if "InvalidGroup.NotFound" not in str(e): print(f"[ERROR] {e}")
                for sg_id in sg_to_delete:
                    try:
                        sg_details = ec2_client.describe_security_groups(GroupIds=[sg_id])['SecurityGroups'][0]
                        if 'IpPermissions' in sg_details and sg_details['IpPermissions']:
                            ec2_client.revoke_security_group_ingress(
                                GroupId=sg_id,
                                IpPermissions=sg_details['IpPermissions']
                            )
                            print(f"[INFO] Regole di ingresso revocate per SG {sg_id}.")
                    except ClientError as e:
                        if 'InvalidPermission.NotFound' not in str(e):
                            print(f"[WARNING] Impossibile revocare regole di ingresso per {sg_id}: {e}")
                for sg_name_current in[rds_sg_name, ec2_sg_name]:
                    try:
                        sg_id_current = ec2_client.describe_security_groups(
                            GroupNames=[sg_name_current], Filters=[{'Name': 'vpc-id', 'Values':[vpc_id]}]
                        )['SecurityGroups'][0]['GroupId']
                        ec2_client.delete_security_group(GroupId=sg_id_current)
                        print(f"[INFO] Security Group '{sg_name_current}' ({sg_id_current}) eliminato.")
                    except ClientError as e:
                        if "InvalidGroup.NotFound" in str(e):
                            print(f"[INFO] Security Group '{sg_name_current}' non trovato o già eliminato.")
                        elif "DependencyViolation" in str(e):
                            print(f"[WARNING] Security Group '{sg_name_current}' ha ancora dipendenze. Riprova più tardi o elimina manualmente.")
                        else:
                            print(f"[ERROR] durante l'eliminazione del Security Group '{sg_name_current}': {e}")

                print(f"[STEP] Eliminazione della Key Pair '{key_name}'...")
                try:
                    ec2_client.delete_key_pair(KeyName=key_name)
                    print(f"[INFO] Key Pair '{key_name}' eliminata da AWS.")
                    if os.path.exists(f"{key_name}.pem"):
                        try:
                            os.remove(f"{key_name}.pem")
                            print(f"[INFO] File locale '{key_name}.pem' eliminato.")
                        except PermissionError:
                            print(f"[WARNING] Impossibile eliminare il file locale '{key_name}.pem' per errore di permessi. Elimina manualmente.")
                        except Exception as file_e:
                            print(f"[WARNING] Errore nell'eliminazione del file locale '{key_name}.pem': {file_e}")
                except ClientError as e:
                    if "InvalidKeyPair.NotFound" in str(e):
                        print(f"[INFO] Key Pair '{key_name}' non trovata o già eliminata in AWS.")
                        if os.path.exists(f"{key_name}.pem"):
                            try:
                                os.remove(f"{key_name}.pem")
                                print(f"[INFO] File locale '{key_name}.pem' eliminato.")
                            except PermissionError:
                                print(f"[WARNING] Impossibile eliminare il file locale '{key_name}.pem' per errore di permessi. Elimina manualmente.")
                            except Exception as file_e:
                                print(f"[WARNING] Errore nell'eliminazione del file locale '{key_name}.pem': {file_e}")
                    else:
                        print(f"[ERROR] Durante l'eliminazione della Key Pair in AWS: {e}")
                        raise
                print("[SUCCESS] Pulizia delle risorse AWS completata - No RDS.")

            delete_resources_no_rds(ec2, KEY_PAIR_NAME, 'MusicAppRDSSecurityGroup', 'MusicAppEC2SecurityGroup')
        else:
            delete_resources(ec2, rds, KEY_PAIR_NAME, DB_INSTANCE_IDENTIFIER, 'MusicAppRDSSecurityGroup', 'MusicAppEC2SecurityGroup')
        return


    print("\n[SECTION] Deploy Risorse AWS")
    print("-" * 50)
    ec2_client = boto3.client('ec2', region_name=REGION)
    rds_client = boto3.client('rds', region_name=REGION)

    schema_sql_path = os.path.join(
        os.path.dirname(__file__),
        '..', '..', 'Database', 'postgreSQL', 'schema.sql'
    )
    dati_sql_path = os.path.join(
        os.path.dirname(__file__),
        '..', '..', 'Database', 'postgreSQL', 'dati.sql'
    )
    with open(os.path.abspath(schema_sql_path), 'r', encoding='utf-8') as f:
        schema_sql_content = f.read()
    with open(os.path.abspath(dati_sql_path), 'r', encoding='utf-8') as f:
        dati_sql_content = f.read()

    try:
        # 0. Legge le credenziali AWS dal file locale
        aws_credentials = read_aws_credentials()
        
        # 1. ottengo o creo la Key Pair
        key_pair_name_actual = get_key_pair(ec2_client, KEY_PAIR_NAME)

        # 2. creo VPC e SG
        vpc_id, rds_security_group_id, ec2_security_group_id = create_vpc_and_security_groups(ec2_client, rds_client)

        # 3. deploy istanza RDS
        print(f"\n[STEP] Tentativo di deploy dell'istanza RDS '{DB_INSTANCE_IDENTIFIER}'...")
        rds_endpoint = None
        try:
            response = rds_client.describe_db_instances(DBInstanceIdentifier=DB_INSTANCE_IDENTIFIER)
            instance_status = response['DBInstances'][0]['DBInstanceStatus']
            rds_endpoint = response['DBInstances'][0]['Endpoint']['Address']
            print(f"[INFO] Istanza RDS '{DB_INSTANCE_IDENTIFIER}' trovata con stato: {instance_status}.")
            if instance_status != 'available':
                print(f"[INFO] Attesa che l'istanza RDS '{DB_INSTANCE_IDENTIFIER}' diventi 'available'...")
                waiter = rds_client.get_waiter('db_instance_available')
                waiter.wait(DBInstanceIdentifier=DB_INSTANCE_IDENTIFIER)
                response = rds_client.describe_db_instances(DBInstanceIdentifier=DB_INSTANCE_IDENTIFIER)
                rds_endpoint = response['DBInstances'][0]['Endpoint']['Address']
                print(f"[SUCCESS] Istanza RDS '{DB_INSTANCE_IDENTIFIER}' ora è 'available'.")
        except ClientError as e:
            if "DBInstanceNotFound" in str(e):
                print(f"[INFO] Istanza RDS '{DB_INSTANCE_IDENTIFIER}' non trovata. Creazione in corso...")
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
                    PubliclyAccessible=True # Per debug e accesso locale, impostare a False per sicurezza in produzione
                )
                print(f"[INFO] Creazione dell'istanza RDS '{DB_INSTANCE_IDENTIFIER}' avviata. Attesa che diventi 'available'...")
                waiter = rds_client.get_waiter('db_instance_available')
                waiter.wait(DBInstanceIdentifier=DB_INSTANCE_IDENTIFIER)
                response = rds_client.describe_db_instances(DBInstanceIdentifier=DB_INSTANCE_IDENTIFIER)
                rds_endpoint = response['DBInstances'][0]['Endpoint']['Address']
                print(f"[SUCCESS] Istanza RDS '{DB_INSTANCE_IDENTIFIER}' ora è 'available'. Endpoint: {rds_endpoint}")
            else:
                raise

        if not rds_endpoint:
            raise Exception("Impossibile ottenere l'endpoint RDS.")

        # 4. inizializzo il db con schema e dati
        print("[STEP] Inizializzazione del database RDS con schema e dati...")
        initialize_database(
            rds_endpoint=rds_endpoint,
            db_username=DB_MASTER_USERNAME,
            db_password=DB_MASTER_PASSWORD,
            db_name=DB_NAME,
            schema_sql=schema_sql_content,
            data_sql=dati_sql_content
        )

        # 5. setup SNS notification e modifico user_data_script
        topic_name = 'musicapp-server-setup-complete'
        email_address = 'lorenzopaoria@icloud.com'
        topic_arn = setup_sns_notification(REGION, topic_name, email_address)
        
        script_dir = os.path.dirname(os.path.abspath(__file__))
        user_data_script_path = os.path.join(script_dir, 'user_data_script.sh')
        with open(user_data_script_path, 'r') as f:
            user_data_script = f.read()

        user_data_script = update_user_data_with_credentials(user_data_script, aws_credentials)

        # 6. deploy istanza EC2 MusicAppServer (o usa esistente)
        server_public_ip = None
        server_private_ip = None
        server_instances_found = ec2_client.describe_instances(
            Filters=[
                {'Name': 'tag:Name', 'Values':['MusicAppServer']},
                {'Name': 'instance-state-name', 'Values':['pending', 'running']}
            ]
        )['Reservations']

        if server_instances_found:
            server_instance_id = server_instances_found[0]['Instances'][0]['InstanceId']
            server_public_ip = server_instances_found[0]['Instances'][0].get('PublicIpAddress')
            server_private_ip = server_instances_found[0]['Instances'][0].get('PrivateIpAddress')
            print(f"\n[INFO] Istanza MusicAppServer esistente e in esecuzione: {server_instance_id}. Public IP: {server_public_ip}, Private IP: {server_private_ip}")
        else:
            print("\n[STEP] Deploy dell'istanza EC2 'MusicAppServer'...")
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
                        'Tags':[
                            {'Key': 'Name', 'Value': 'MusicAppServer'},
                            {'Key': 'Application', 'Value': 'MusicApp'}
                        ]
                    },
                ]
            )
            server_instance_id = server_instances['Instances'][0]['InstanceId']
            print(f"[INFO] Istanza MusicAppServer avviata: {server_instance_id}. Attesa che sia 'running'...")
            waiter = ec2_client.get_waiter('instance_running')
            waiter.wait(InstanceIds=[server_instance_id])
            server_instance_details = ec2_client.describe_instances(InstanceIds=[server_instance_id])
            server_public_ip = server_instance_details['Reservations'][0]['Instances'][0]['PublicIpAddress']
            server_private_ip = server_instance_details['Reservations'][0]['Instances'][0]['PrivateIpAddress']
            print(f"[SUCCESS] MusicAppServer è in esecuzione. Public IP: {server_public_ip}, Private IP: {server_private_ip}")

        # configurazione salvata in un file JSON
        config = {
            "server_public_ip": server_public_ip,
            "server_private_ip": server_private_ip,
            "rds_endpoint": rds_endpoint,
            "db_username": DB_MASTER_USERNAME,
            "db_password": DB_MASTER_PASSWORD,
            "db_name": DB_NAME,
            "key_pair_name": key_pair_name_actual
        }
        with open("deploy_config.json", "w") as f:
            json.dump(config, f, indent=4)
        print("\n[SUCCESS] Configurazione salvata in 'deploy_config.json'.")
        print("\n[GUIDE] Guida Rapida Deploy Applicazione")
        print("=" * 60)
        print("[1] Aggiorna i segreti GitHub")
        print("    python scripts/infrastructure/update_github_secrets.py")
        print("")
        print("[2] Aggiorna i file di configurazione Java locali")
        print("    python scripts/infrastructure/update_java_config_on_ec2.py")
        print("    Dopo il push, la GitHub Action parte da sola")
        print("")
        print("[3] Avvia il server via SSH su EC2")
        print(f"    ssh -i {key_pair_name_actual}.pem ec2-user@{server_public_ip}")
        print("")
        print("[4] Avvia il client Java in locale")
        print("    mvn clean install && mvn -Pclient exec:java")
        print("")
        print("[5] Log del container Docker del server:")
        print("    docker logs -f musicapp-server")
        print("=" * 60)

    except ClientError as e:
        print(f"[ERROR] AWS: {e}")
    except Exception as e:
        print(f"[ERROR] Inatteso: {e}")

if __name__ == "__main__":
    main()