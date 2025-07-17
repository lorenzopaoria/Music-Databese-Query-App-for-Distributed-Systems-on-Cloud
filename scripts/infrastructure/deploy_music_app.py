import boto3
import time
import os
import psycopg2
import json
import configparser
from botocore.exceptions import ClientError
from dotenv import load_dotenv

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, "..", ".."))
env_path = os.path.join(project_root, ".env")
load_dotenv(env_path)

# configurazione da env
REGION = os.getenv('AWS_REGION', 'us-east-1')
KEY_PAIR_NAME = os.getenv('AWS_KEY_PAIR_NAME', 'my-ec2-key')
AMI_ID = os.getenv('AWS_AMI_ID', 'ami-09e6f87a47903347c')
INSTANCE_TYPE = os.getenv('AWS_INSTANCE_TYPE', 't2.micro')

DB_INSTANCE_IDENTIFIER = os.getenv('DB_INSTANCE_IDENTIFIER', 'music-db-app-rds')
DB_ENGINE = os.getenv('DB_ENGINE', 'postgres')
DB_ENGINE_VERSION = os.getenv('DB_ENGINE_VERSION', '17.4')
DB_INSTANCE_CLASS = os.getenv('DB_INSTANCE_CLASS', 'db.t3.micro')
DB_ALLOCATED_STORAGE = int(os.getenv('DB_ALLOCATED_STORAGE', '20'))
DB_MASTER_USERNAME = os.getenv('DB_MASTER_USERNAME', 'dbadmin')
DB_MASTER_PASSWORD = os.getenv('DB_MASTER_PASSWORD', '12345678')
DB_NAME = os.getenv('DB_NAME', 'musicdb')

def print_section(title, skip_suffix=""):

    print(f"\n[SECTION] {title}")
    if skip_suffix:
        print("-" * 50 + skip_suffix)
    else:
        print("-" * 50)

def print_step(message):

    print(f"[STEP] {message}")

def print_info(message):

    print(f"[INFO] {message}")

def print_success(message):

    print(f"[SUCCESS] {message}")

def print_warning(message):

    print(f"[WARNING] {message}")

def print_error(message):

    print(f"[ERROR] {message}")

def handle_client_error(e, not_found_keywords, not_found_message, action_description):

    error_str = str(e)
    for keyword in not_found_keywords:
        if keyword in error_str:
            print_info(not_found_message)
            return True
    print_error(f"{action_description}: {e}")
    raise e

def get_default_vpc(ec2_client):

    vpcs = ec2_client.describe_vpcs(Filters=[{'Name': 'isDefault', 'Values': ['true']}])
    if not vpcs['Vpcs']:
        raise Exception("VPC di default non trovata")
    vpc_id = vpcs['Vpcs'][0]['VpcId']
    print_info(f"VPC di default individuata: {vpc_id}")
    return vpc_id

def create_security_group_if_not_exists(ec2_client, group_name, description, vpc_id):

    try:
        response = ec2_client.create_security_group(
            GroupName=group_name,
            Description=description,
            VpcId=vpc_id
        )
        group_id = response['GroupId']
        print_success(f"Security Group '{group_name}' creata con ID: {group_id}")
        return group_id
    except ClientError as e:
        if 'InvalidGroup.Duplicate' in str(e):
            group_id = ec2_client.describe_security_groups(
                GroupNames=[group_name], 
                Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}]
            )['SecurityGroups'][0]['GroupId']
            print_info(f"Security Group '{group_name}' già esistente: {group_id}")
            return group_id
        else:
            raise

def authorize_security_group_rule(ec2_client, group_id, ip_permissions, rule_description):

    try:
        ec2_client.authorize_security_group_ingress(
            GroupId=group_id,
            IpPermissions=ip_permissions
        )
        print_success(f"Regola di ingresso autorizzata: {rule_description}")
    except ClientError as e:
        if 'InvalidPermission.Duplicate' in str(e):
            print_info(f"Regola di ingresso già presente: {rule_description}")
        else:
            raise

def wait_for_resource_state(waiter, resource_ids, resource_type, target_state):

    print_info(f"Attesa che {resource_type} raggiunga lo stato '{target_state}'...")
    waiter.wait(**{resource_ids[0]: resource_ids[1]})
    print_success(f"{resource_type} ha raggiunto lo stato '{target_state}'")

def connect_to_database(conn_str, db_name, max_retries=5, retry_delay=10):

    for i in range(max_retries):
        try:
            conn = psycopg2.connect(conn_str)
            print_info(f"Connesso al database '{db_name}'")
            return conn
        except psycopg2.OperationalError as e:
            print_info(f"Tentativo {i+1} di connessione fallito: {e}. Attesa di {retry_delay} secondi...")
            if i < max_retries - 1:
                time.sleep(retry_delay)
    raise Exception(f"Impossibile connettersi al database '{db_name}' dopo {max_retries} tentativi")

def read_aws_credentials():

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

    updated_script = user_data_script.replace(
        'AWS_ACCESS_KEY_ID_PLACEHOLDER', credentials['aws_access_key_id']
    ).replace(
        'AWS_SECRET_ACCESS_KEY_PLACEHOLDER', credentials['aws_secret_access_key']
    )
    
    if credentials['aws_session_token']:
        updated_script = updated_script.replace(
            'AWS_SESSION_TOKEN_PLACEHOLDER', credentials['aws_session_token']
        )
    else:
        lines = updated_script.split('\n')
        updated_lines = [line for line in lines if 'AWS_SESSION_TOKEN_PLACEHOLDER' not in line]
        updated_script = '\n'.join(updated_lines)
    
    return updated_script

def get_key_pair(ec2_client, key_name):

    print_section("Gestione Chiave EC2")
    try:
        response = ec2_client.describe_key_pairs(KeyNames=[key_name])
        print_info(f"La chiave EC2 '{key_name}' è già presente nel tuo account AWS.")
        return response['KeyPairs'][0]['KeyName']
    except ClientError as e:
        if handle_client_error(e, ["InvalidKeyPair.NotFound"], f"La chiave EC2 '{key_name}' non è stata trovata. Avvio della creazione", "Errore nella verifica della key pair"):
            key_pair = ec2_client.create_key_pair(KeyName=key_name)
            with open(f"{key_name}.pem", "w") as f:
                f.write(key_pair['KeyMaterial'])
            os.chmod(f"{key_name}.pem", 0o400)
            print_success(f"File '{key_name}.pem' creato e salvato localmente.")
            return key_pair['KeyName']

def create_vpc_and_security_groups(ec2_client, rds_client):

    print_section("VPC e Security Groups")
    
    vpc_id = get_default_vpc(ec2_client)

    rds_security_group_id = create_security_group_if_not_exists(
        ec2_client, 'MusicAppRDSSecurityGroup',
        'Consenti accesso PostgreSQL per EC2 MusicApp e script locale', vpc_id
    )
    
    ec2_security_group_id = create_security_group_if_not_exists(
        ec2_client, 'MusicAppEC2SecurityGroup',
        'Consenti SSH e traffico applicativo alle istanze EC2 MusicApp', vpc_id
    )

    setup_rds_security_rules(ec2_client, rds_security_group_id, ec2_security_group_id)
    setup_ec2_security_rules(ec2_client, ec2_security_group_id)

    return vpc_id, rds_security_group_id, ec2_security_group_id

def setup_rds_security_rules(ec2_client, rds_sg_id, ec2_sg_id):

    rds_from_ec2_rule = [{
        'IpProtocol': 'tcp',
        'FromPort': 5432,
        'ToPort': 5432,
        'UserIdGroupPairs': [{'GroupId': ec2_sg_id}]
    }]
    authorize_security_group_rule(ec2_client, rds_sg_id, rds_from_ec2_rule, "RDS autorizzata dal Security Group EC2")

    rds_from_local_rule = [{
        'IpProtocol': 'tcp',
        'FromPort': 5432,
        'ToPort': 5432,
        'IpRanges': [{'CidrIp': '0.0.0.0/0', 'Description': 'Consenti accesso script locale per init DB (solo sviluppo)'}]
    }]
    authorize_security_group_rule(ec2_client, rds_sg_id, rds_from_local_rule,
                                "RDS autorizzata da 0.0.0.0/0 per inizializzazione locale")

def setup_ec2_security_rules(ec2_client, ec2_sg_id):

    ec2_rules = [
        {
            'IpProtocol': 'tcp',
            'FromPort': 22,
            'ToPort': 22,
            'IpRanges': [{'CidrIp': '0.0.0.0/0'}]
        },
        {
            'IpProtocol': 'tcp',
            'FromPort': 8080,
            'ToPort': 8080,
            'IpRanges': [{'CidrIp': '0.0.0.0/0'}]
        }
    ]
    authorize_security_group_rule(ec2_client, ec2_sg_id, ec2_rules, "EC2 autorizzate per SSH e applicazione")

def terminate_ec2_instances(ec2_client, tag_filter):

    print_step("Terminazione delle istanze EC2 in corso...")
    instances = ec2_client.describe_instances(Filters=tag_filter)
    instance_ids = []
    for reservation in instances['Reservations']:
        for instance in reservation['Instances']:
            if instance['State']['Name'] != 'terminated':
                instance_ids.append(instance['InstanceId'])
    
    if instance_ids:
        ec2_client.terminate_instances(InstanceIds=instance_ids)
        print_info(f"Istanze EC2 terminate: {instance_ids}. Attendo la conferma di terminazione...")
        waiter = ec2_client.get_waiter('instance_terminated')
        waiter.wait(InstanceIds=instance_ids)
        print_success("Tutte le istanze EC2 sono state terminate correttamente.")
    else:
        print_info("Nessuna istanza EC2 'MusicApp' trovata da terminare.")

def delete_rds_instance(rds_client, rds_id):

    print_step(f"Eliminazione dell'istanza RDS '{rds_id}' in corso...")
    try:
        rds_client.delete_db_instance(
            DBInstanceIdentifier=rds_id,
            SkipFinalSnapshot=True
        )
        print_info(f"Istanza RDS '{rds_id}' eliminata. Attesa della cancellazione...")
        waiter = rds_client.get_waiter('db_instance_deleted')
        waiter.wait(DBInstanceIdentifier=rds_id)
        print_success(f"Istanza RDS '{rds_id}' eliminata.")
    except ClientError as e:
        handle_client_error(e, ["DBInstanceNotFound"], f"Istanza RDS '{rds_id}' non trovata o già eliminata.", "Errore durante l'eliminazione dell'istanza RDS")

def cleanup_security_groups(ec2_client, sg_names, vpc_id):

    print_step("Eliminazione dei Security Groups...")
    sg_to_delete = []
    for sg_name in sg_names:
        try:
            sg_id = ec2_client.describe_security_groups(
                GroupNames=[sg_name], 
                Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}]
            )['SecurityGroups'][0]['GroupId']
            sg_to_delete.append(sg_id)
        except ClientError as e:
            if "InvalidGroup.NotFound" not in str(e):
                print_error(f"Errore nel recupero SG {sg_name}: {e}")

    for sg_id in sg_to_delete:
        revoke_security_group_rules(ec2_client, sg_id)

    for sg_name in sg_names:
        delete_security_group_by_name(ec2_client, sg_name, vpc_id)

def revoke_security_group_rules(ec2_client, sg_id):

    try:
        sg_details = ec2_client.describe_security_groups(GroupIds=[sg_id])['SecurityGroups'][0]
        if 'IpPermissions' in sg_details and sg_details['IpPermissions']:
            ec2_client.revoke_security_group_ingress(
                GroupId=sg_id,
                IpPermissions=sg_details['IpPermissions']
            )
            print_info(f"Regole di ingresso revocate per SG {sg_id}.")
    except ClientError as e:
        if 'InvalidPermission.NotFound' not in str(e):
            print_warning(f"Impossibile revocare regole di ingresso per {sg_id}: {e}")

def delete_security_group_by_name(ec2_client, sg_name, vpc_id):

    try:
        sg_id = ec2_client.describe_security_groups(GroupNames=[sg_name], Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}])['SecurityGroups'][0]['GroupId']
        ec2_client.delete_security_group(GroupId=sg_id)
        print_info(f"Security Group '{sg_name}' ({sg_id}) eliminato.")
    except ClientError as e:
        if "InvalidGroup.NotFound" in str(e):
            print_info(f"Security Group '{sg_name}' non trovato o già eliminato.")
        elif "DependencyViolation" in str(e):
            print_warning(f"Security Group '{sg_name}' ha ancora dipendenze. Riprova più tardi o elimina manualmente.")
        else:
            print_error(f"Errore durante l'eliminazione del Security Group '{sg_name}': {e}")

def delete_key_pair_and_file(ec2_client, key_name):

    print_step(f"Eliminazione della Key Pair '{key_name}'...")
    try:
        ec2_client.delete_key_pair(KeyName=key_name)
        print_info(f"Key Pair '{key_name}' eliminata da AWS.")
        delete_local_pem_file(key_name)
    except ClientError as e:
        if handle_client_error(e, ["InvalidKeyPair.NotFound"], f"Key Pair '{key_name}' non trovata o già eliminata in AWS.", "Errore durante l'eliminazione della Key Pair in AWS"):
            delete_local_pem_file(key_name)

def delete_local_pem_file(key_name):

    pem_file = f"{key_name}.pem"
    if os.path.exists(pem_file):
        try:
            os.remove(pem_file)
            print_info(f"File locale '{pem_file}' eliminato.")
        except PermissionError:
            print_warning(f"Impossibile eliminare il file locale '{pem_file}' per errore di permessi. Elimina manualmente.")
        except Exception as file_e:
            print_warning(f"Errore nell'eliminazione del file locale '{pem_file}': {file_e}")

def cleanup_sns_sqs_resources():

    print_step("Eliminazione risorse SNS e SQS...")
    try:
        sns_client = boto3.client('sns', region_name=REGION)
        sqs_client = boto3.client('sqs', region_name=REGION)
        
        delete_sqs_queue(sqs_client, 'musicapp-sns-logging-queue')
        delete_sns_topic(sns_client, 'musicapp-server-setup-complete')
            
    except Exception as e:
        print_warning(f"Errore durante la pulizia di SNS/SQS: {e}")

def delete_sqs_queue(sqs_client, queue_name):

    try:
        queue_url = sqs_client.get_queue_url(QueueName=queue_name)['QueueUrl']
        sqs_client.delete_queue(QueueUrl=queue_url)
        print_info(f"Coda SQS '{queue_name}' eliminata.")
    except ClientError as e:
        if 'AWS.SimpleQueueService.NonExistentQueue' in str(e):
            print_info(f"Coda SQS '{queue_name}' non trovata o già eliminata.")
        else:
            print_warning(f"Errore nell'eliminazione della coda SQS: {e}")

def delete_sns_topic(sns_client, topic_name):

    try:
        topics = sns_client.list_topics()
        for topic in topics.get('Topics', []):
            if topic_name in topic['TopicArn']:
                sns_client.delete_topic(TopicArn=topic['TopicArn'])
                print_info(f"Topic SNS '{topic_name}' eliminato.")
                return
        print_info(f"Topic SNS '{topic_name}' non trovato o già eliminato.")
    except Exception as e:
        print_warning(f"Errore nell'eliminazione del topic SNS: {e}")

def delete_resources(ec2_client, rds_client, key_name, rds_id, rds_sg_name, ec2_sg_name, skip_rds=False):

    print_section("Pulizia Risorse AWS", " (Skip RDS)" if skip_rds else "")
    if skip_rds:
        print_info("Opzione skip RDS attiva: elimino tutte le risorse tranne il database RDS.")

    terminate_ec2_instances(ec2_client, [{'Name': 'tag:Application', 'Values': ['MusicApp']}])

    if not skip_rds:
        delete_rds_instance(rds_client, rds_id)
    else:
        print_info(f"Eliminazione del database RDS '{rds_id}' saltata come richiesto.")

    vpc_id = get_default_vpc(ec2_client)

    cleanup_security_groups(ec2_client, [rds_sg_name, ec2_sg_name], vpc_id) 
    delete_key_pair_and_file(ec2_client, key_name)
    cleanup_sns_sqs_resources()

    print_success("Pulizia delle risorse AWS completata.")


def execute_sql_with_connection(conn, sql_content, description):

    print_step(f"Esecuzione di {description}...")
    try:
        cur = conn.cursor()
        cur.execute(sql_content)
        cur.close()
        print_success(f"{description} eseguito con successo.")
    except Exception as e:
        print_error(f"Nell'esecuzione di {description}: {e}")
        raise

def setup_database_connection(rds_endpoint, db_username, db_password, db_name):

    conn_str_master = f"dbname=postgres user={db_username} password={db_password} host={rds_endpoint} port=5432"
    conn = connect_to_database(conn_str_master, 'postgres')
    conn.autocommit = True
    
    try:
        cur = conn.cursor()
        
        print_step(f"Terminazione delle connessioni attive al database '{db_name}'...")
        try:
            cur.execute(f"""
                SELECT pg_terminate_backend(pg_stat_activity.pid)
                FROM pg_stat_activity
                WHERE pg_stat_activity.datname = '{db_name}'
                    AND pid <> pg_backend_pid();
            """)
            print_info(f"Connessioni terminate per '{db_name}'.")
        except Exception as e:
            print_warning(f"Errore nella terminazione delle connessioni: {e}")

        print_step(f"Tentativo di eliminazione del database '{db_name}' se esiste...")
        cur.execute(f"DROP DATABASE IF EXISTS {db_name};")
        print_info(f"Database '{db_name}' eliminato o non esisteva.")

        print_step(f"Creazione del database '{db_name}'...")
        cur.execute(f"CREATE DATABASE {db_name};")
        print_success(f"Database '{db_name}' creato.")
        
        cur.close()
        return conn
        
    except Exception as e:
        print_error(f"Nell'inizializzazione del database '{db_name}': {e}")
        if conn:
            conn.close()
        raise

def initialize_database(rds_endpoint, db_username, db_password, db_name, schema_sql, data_sql):

    print_section("Inizializzazione Database RDS")
    print_info(f"Inizializzazione del database '{db_name}' su {rds_endpoint}...")

    master_conn = None
    app_conn = None
    
    try:
        master_conn = setup_database_connection(rds_endpoint, db_username, db_password, db_name)
        master_conn.close()

        conn_str_app = f"dbname={db_name} user={db_username} password={db_password} host={rds_endpoint} port=5432"
        app_conn = connect_to_database(conn_str_app, db_name, retry_delay=5)
        app_conn.autocommit = True

        execute_sql_with_connection(app_conn, schema_sql, "schema.sql")
        execute_sql_with_connection(app_conn, data_sql, "data.sql")

        print_success(f"Inizializzazione del database '{db_name}' completata con successo.")

    except psycopg2.Error as e:
        print_error(f"Durante l'inizializzazione del database: {e}")
        raise
    except Exception as e:
        print_error(f"Inatteso durante l'inizializzazione del database: {e}")
        raise
    finally:
        if master_conn:
            master_conn.close()
        if app_conn:
            app_conn.close()


def get_account_id():

    sts = boto3.client('sts')
    return sts.get_caller_identity()['Account']

def setup_sns_notification(region, topic_name, email_address):

    print_section("Notifiche SNS")

    sns_client = boto3.client('sns', region_name=region)
    try:
        response = sns_client.create_topic(Name=topic_name)
        topic_arn = response['TopicArn']
        print_success(f"SNS topic creato: {topic_arn}")
        
        sns_client.subscribe(TopicArn=topic_arn, Protocol='email', Endpoint=email_address)
        print_success(f"Sottoscrizione email {email_address} al topic SNS completata.")
        print_info("Conferma la sottoscrizione tramite il link che riceverai via email.")
        
        return topic_arn
    except Exception as e:
        print_error(f"Nella configurazione SNS: {e}")
        raise

def create_sqs_queue(sqs_client, queue_name):

    queue_response = sqs_client.create_queue(
        QueueName=queue_name,
        Attributes={
            'MessageRetentionPeriod': '1209600',
            'VisibilityTimeout': '300',
            'ReceiveMessageWaitTimeSeconds': '20'
        }
    )
    queue_url = queue_response['QueueUrl']
    
    queue_attributes = sqs_client.get_queue_attributes(
        QueueUrl=queue_url,
        AttributeNames=['QueueArn']
    )
    queue_arn = queue_attributes['Attributes']['QueueArn']
    
    print_success(f"Coda SQS creata: {queue_url}")
    print_info(f"ARN della coda: {queue_arn}")
    
    return queue_url, queue_arn

def setup_sqs_policy_and_subscription(sqs_client, sns_client, queue_url, queue_arn, topic_arn):

    queue_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "sns.amazonaws.com"},
                "Action": "sqs:SendMessage",
                "Resource": queue_arn,
                "Condition": {
                    "ArnEquals": {
                        "aws:SourceArn": topic_arn
                    }
                }
            }
        ]
    }
    
    sqs_client.set_queue_attributes(
        QueueUrl=queue_url,
        Attributes={'Policy': json.dumps(queue_policy)}
    )
    print_success("Policy di accesso configurata per la coda SQS")
    
    subscription_response = sns_client.subscribe(
        TopicArn=topic_arn,
        Protocol='sqs',
        Endpoint=queue_arn
    )
    print_success("Coda SQS sottoscritta al topic SNS per logging")
    print_info(f"Subscription ARN: {subscription_response['SubscriptionArn']}")

def handle_existing_sqs_queue(sqs_client, sns_client, queue_name, topic_arn):

    queue_url = sqs_client.get_queue_url(QueueName=queue_name)['QueueUrl']
    queue_attributes = sqs_client.get_queue_attributes(
        QueueUrl=queue_url,
        AttributeNames=['QueueArn']
    )
    queue_arn = queue_attributes['Attributes']['QueueArn']
    print_info(f"Coda SQS già esistente: {queue_url}")
    
    subscriptions = sns_client.list_subscriptions_by_topic(TopicArn=topic_arn)
    already_subscribed = any(
        sub['Endpoint'] == queue_arn and sub['Protocol'] == 'sqs'
        for sub in subscriptions['Subscriptions']
    )
    
    if not already_subscribed:
        subscription_response = sns_client.subscribe(
            TopicArn=topic_arn,
            Protocol='sqs',
            Endpoint=queue_arn
        )
        print_success("Coda SQS sottoscritta al topic SNS per logging")
    else:
        print_info("Coda SQS già sottoscritta al topic SNS")
    
    return queue_url, queue_arn

def setup_sqs_logging_queue(region, queue_name, topic_arn):

    print_section("Coda SQS per Logging SNS")

    sqs_client = boto3.client('sqs', region_name=region)
    sns_client = boto3.client('sns', region_name=region)
    
    try:
        queue_url, queue_arn = create_sqs_queue(sqs_client, queue_name)
        setup_sqs_policy_and_subscription(sqs_client, sns_client, queue_url, queue_arn, topic_arn)
        return queue_url, queue_arn
        
    except ClientError as e:
        if 'QueueAlreadyExists' in str(e):
            return handle_existing_sqs_queue(sqs_client, sns_client, queue_name, topic_arn)
        else:
            print_error(f"Nella creazione della coda SQS: {e}")
            raise
    except Exception as e:
        print_error(f"Setup coda SQS logging: {e}")
        raise

def parse_sns_message(message):

    try:
        sns_message = json.loads(message['Body'])
        log_entry = {
            'timestamp': sns_message.get('Timestamp'),
            'message_id': sns_message.get('MessageId'),
            'subject': sns_message.get('Subject'),
            'message': sns_message.get('Message'),
            'topic_arn': sns_message.get('TopicArn'),
            'receipt_handle': message['ReceiptHandle']
        }
        
        print(f"[LOG] {log_entry['timestamp']} - {log_entry['subject']}")
        print(f"      Message: {log_entry['message'][:100]}...")
        print(f"      Topic: {log_entry['topic_arn']}")
        print("-" * 30)
        
        return log_entry
    except json.JSONDecodeError:
        print_warning(f"Messaggio non JSON: {message['Body'][:100]}...")
        return None

def read_sns_logs_from_sqs(region, queue_url, max_messages=10):

    print_section("Lettura Log SNS da SQS")

    sqs_client = boto3.client('sqs', region_name=region)
    
    try:
        response = sqs_client.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=max_messages,
            WaitTimeSeconds=1,
            AttributeNames=['All'],
            MessageAttributeNames=['All']
        )
        
        messages = response.get('Messages', [])
        if not messages:
            print_info("Nessun messaggio presente nella coda di logging")
            return []
        
        log_entries = []
        for message in messages:
            log_entry = parse_sns_message(message)
            if log_entry:
                log_entries.append(log_entry)
        
        print_info(f"Trovati {len(log_entries)} messaggi di log")
        return log_entries
        
    except Exception as e:
        print_error(f"Lettura log SQS: {e}")
        raise

def cleanup_sqs_messages(region, queue_url, receipt_handles):

    if not receipt_handles:
        return
    
    sqs_client = boto3.client('sqs', region_name=region)
    
    try:
        for receipt_handle in receipt_handles:
            sqs_client.delete_message(
                QueueUrl=queue_url,
                ReceiptHandle=receipt_handle
            )
        print_success(f"Eliminati {len(receipt_handles)} messaggi processati dalla coda")
    except Exception as e:
        print_error(f"Pulizia messaggi SQS: {e}")

def load_sql_files():

    script_dir = os.path.dirname(__file__)
    schema_sql_path = os.path.join(script_dir, '..', '..', 'Database', 'postgreSQL', 'schema.sql')
    dati_sql_path = os.path.join(script_dir, '..', '..', 'Database', 'postgreSQL', 'dati.sql')
    
    with open(os.path.abspath(schema_sql_path), 'r', encoding='utf-8') as f:
        schema_sql_content = f.read()
    with open(os.path.abspath(dati_sql_path), 'r', encoding='utf-8') as f:
        dati_sql_content = f.read()
    
    return schema_sql_content, dati_sql_content

def get_or_create_rds_instance(rds_client, rds_security_group_id):

    print_step(f"Tentativo di deploy dell'istanza RDS '{DB_INSTANCE_IDENTIFIER}'...")
    
    try:
        response = rds_client.describe_db_instances(DBInstanceIdentifier=DB_INSTANCE_IDENTIFIER)
        instance_status = response['DBInstances'][0]['DBInstanceStatus']
        rds_endpoint = response['DBInstances'][0]['Endpoint']['Address']
        print_info(f"Istanza RDS '{DB_INSTANCE_IDENTIFIER}' trovata con stato: {instance_status}.")
        
        if instance_status != 'available':
            print_info(f"Attesa che l'istanza RDS '{DB_INSTANCE_IDENTIFIER}' diventi 'available'...")
            waiter = rds_client.get_waiter('db_instance_available')
            waiter.wait(DBInstanceIdentifier=DB_INSTANCE_IDENTIFIER)
            response = rds_client.describe_db_instances(DBInstanceIdentifier=DB_INSTANCE_IDENTIFIER)
            rds_endpoint = response['DBInstances'][0]['Endpoint']['Address']
            print_success(f"Istanza RDS '{DB_INSTANCE_IDENTIFIER}' ora è 'available'.")
        
        return rds_endpoint
        
    except ClientError as e:
        if "DBInstanceNotFound" in str(e):
            return create_new_rds_instance(rds_client, rds_security_group_id)
        else:
            raise

def create_new_rds_instance(rds_client, rds_security_group_id):

    print_info(f"Istanza RDS '{DB_INSTANCE_IDENTIFIER}' non trovata. Creazione in corso...")
    
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
        PubliclyAccessible=True  # For debug and local access, set to False for production security
    )
    
    print_info(f"Creazione dell'istanza RDS '{DB_INSTANCE_IDENTIFIER}' avviata. Attesa che diventi 'available'...")
    waiter = rds_client.get_waiter('db_instance_available')
    waiter.wait(DBInstanceIdentifier=DB_INSTANCE_IDENTIFIER)
    
    response = rds_client.describe_db_instances(DBInstanceIdentifier=DB_INSTANCE_IDENTIFIER)
    rds_endpoint = response['DBInstances'][0]['Endpoint']['Address']
    print_success(f"Istanza RDS '{DB_INSTANCE_IDENTIFIER}' ora è 'available'. Endpoint: {rds_endpoint}")
    
    return rds_endpoint

def get_or_create_ec2_server(ec2_client, ec2_security_group_id, key_pair_name_actual, user_data_script):

    server_instances_found = ec2_client.describe_instances(
        Filters=[
            {'Name': 'tag:Name', 'Values': ['MusicAppServer']},
            {'Name': 'instance-state-name', 'Values': ['pending', 'running']}
        ]
    )['Reservations']

    if server_instances_found:
        instance = server_instances_found[0]['Instances'][0]
        server_instance_id = instance['InstanceId']
        server_public_ip = instance.get('PublicIpAddress')
        server_private_ip = instance.get('PrivateIpAddress')
        print_info(f"Istanza MusicAppServer esistente e in esecuzione: {server_instance_id}. Public IP: {server_public_ip}, Private IP: {server_private_ip}")
        return server_public_ip, server_private_ip
    else:
        return create_new_ec2_server(ec2_client, ec2_security_group_id, key_pair_name_actual, user_data_script)

def create_new_ec2_server(ec2_client, ec2_security_group_id, key_pair_name_actual, user_data_script):

    print_section("Deploy Istanza EC2 MusicAppServer")
    
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
    print_info(f"Istanza MusicAppServer avviata: {server_instance_id}. Attesa che sia 'running'...")
    
    waiter = ec2_client.get_waiter('instance_running')
    waiter.wait(InstanceIds=[server_instance_id])
    
    server_instance_details = ec2_client.describe_instances(InstanceIds=[server_instance_id])
    instance = server_instance_details['Reservations'][0]['Instances'][0]
    server_public_ip = instance['PublicIpAddress']
    server_private_ip = instance['PrivateIpAddress']
    
    print_success(f"MusicAppServer è in esecuzione. Public IP: {server_public_ip}, Private IP: {server_private_ip}")
    return server_public_ip, server_private_ip

def save_deployment_config(server_public_ip, server_private_ip, rds_endpoint, key_pair_name_actual):

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
    print_success("Configurazione salvata in 'deploy_config.json'.")

def print_deployment_guide(key_pair_name_actual, server_public_ip):

    print_info("Guida Rapida Deploy Applicazione")
    print("=" * 60)
    print("[1] Aggiorna i segreti GitHub")
    print("    python scripts/infrastructure/update_github_secrets.py")
    print("")
    print("[2] (Opzionale) Configura Network Load Balancer")
    print("    python scripts/infrastructure/setup_nlb.py")
    print("")
    print("[3] Aggiorna i file di configurazione Java locali")
    print("    python scripts/infrastructure/update_java_config_on_ec2.py")
    print("    Dopo il push, la GitHub Action parte da sola")
    print("")
    print("[4] Avvia il server via SSH su EC2")
    print(f"    ssh -i {key_pair_name_actual}.pem ec2-user@{server_public_ip}")
    print("")
    print("[5] Avvia il client Java in locale")
    print("    mvn clean install && mvn -Pclient exec:java")
    print("")
    print("[6] Log del container Docker del server:")
    print("    docker logs -f musicapp-server")
    print("")
    print("[7] Monitoraggio live SQS:")
    print("    python scripts/infrastructure/monitor_sqs.py")
    print("")
    print("[NOTA] Se hai configurato il NLB, il client si connetterà automaticamente")
    print("       tramite il Load Balancer invece che direttamente all'EC2")
    print("")
    print("=" * 60)

def main():

    if "--clean" in os.sys.argv:
        print_section("Pulizia Risorse AWS")
        ec2 = boto3.client('ec2', region_name=REGION)
        rds = boto3.client('rds', region_name=REGION)
        
        # Check if --nords flag is present
        skip_rds = "--nords" in os.sys.argv
        delete_resources(ec2, rds, KEY_PAIR_NAME, DB_INSTANCE_IDENTIFIER, 
                        'MusicAppRDSSecurityGroup', 'MusicAppEC2SecurityGroup', skip_rds)
        return

    print_section("Deploy Risorse AWS")
    ec2_client = boto3.client('ec2', region_name=REGION)
    rds_client = boto3.client('rds', region_name=REGION)

    try:
        # Load SQL files
        schema_sql_content, dati_sql_content = load_sql_files()

        # Read AWS credentials from local file
        aws_credentials = read_aws_credentials()
        
        # Get or create key pair
        key_pair_name_actual = get_key_pair(ec2_client, KEY_PAIR_NAME)

        # Create VPC and security groups
        vpc_id, rds_security_group_id, ec2_security_group_id = create_vpc_and_security_groups(ec2_client, rds_client)

        # Deploy RDS instance
        rds_endpoint = get_or_create_rds_instance(rds_client, rds_security_group_id)
        
        if not rds_endpoint:
            raise Exception("Impossibile ottenere l'endpoint RDS.")

        # Initialize database with schema and data
        print_step("Inizializzazione del database RDS con schema e dati...")
        initialize_database(
            rds_endpoint=rds_endpoint,
            db_username=DB_MASTER_USERNAME,
            db_password=DB_MASTER_PASSWORD,
            db_name=DB_NAME,
            schema_sql=schema_sql_content,
            data_sql=dati_sql_content
        )

        # Setup SNS notification
        topic_name = 'musicapp-server-setup-complete'
        email_address = 'lorenzopaoria@icloud.com'
        topic_arn = setup_sns_notification(REGION, topic_name, email_address)
        
        # Setup SQS logging queue for all SNS messages
        queue_name = 'musicapp-sns-logging-queue'
        queue_url, queue_arn = setup_sqs_logging_queue(REGION, queue_name, topic_arn)
        
        # Prepare user data script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        user_data_script_path = os.path.join(script_dir, 'user_data_script.sh')
        with open(user_data_script_path, 'r') as f:
            user_data_script = f.read()

        user_data_script = update_user_data_with_credentials(user_data_script, aws_credentials)

        # Deploy EC2 MusicAppServer (or use existing)
        server_public_ip, server_private_ip = get_or_create_ec2_server(
            ec2_client, ec2_security_group_id, key_pair_name_actual, user_data_script
        )

        # Save configuration
        save_deployment_config(server_public_ip, server_private_ip, rds_endpoint, key_pair_name_actual)
        
        # Print deployment guide
        print_deployment_guide(key_pair_name_actual, server_public_ip)

    except ClientError as e:
        print_error(f"AWS: {e}")
    except Exception as e:
        print_error(f"Inatteso: {e}")

if __name__ == "__main__":
    main()