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

# configurazione Load Balancer
NLB_NAME = 'musicapp-nlb'
TARGET_GROUP_NAME = 'musicapp-tg'

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
        return response['KeyPairs'][0]['KeyName']
    except ClientError as e:
        if "InvalidKeyPair.NotFound" in str(e):
            key_pair = ec2_client.create_key_pair(KeyName=key_name)
            with open(f"{key_name}.pem", "w") as f:
                f.write(key_pair['KeyMaterial'])
            os.chmod(f"{key_name}.pem", 0o400)
            print(f"[SUCCESS] Chiave '{key_name}.pem' creata.")
            return key_pair['KeyName']
        else:
            raise

def create_network_load_balancer_and_target_group(ec2_client, elbv2_client, vpc_id, ec2_security_group_id):
    print("\n[SECTION] Network Load Balancer Setup")
    print("-" * 50)
    
    subnets_response = ec2_client.describe_subnets(
        Filters=[
            {'Name': 'vpc-id', 'Values': [vpc_id]},
            {'Name': 'map-public-ip-on-launch', 'Values': ['true']}
        ]
    )
    subnet_ids = [subnet['SubnetId'] for subnet in subnets_response['Subnets']]
    
    if len(subnet_ids) < 2:
        subnets_response = ec2_client.describe_subnets(
            Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}]
        )
        subnet_ids = [subnet['SubnetId'] for subnet in subnets_response['Subnets']]
    
    nlb_subnet_ids = subnet_ids[:2]

    try:
        ec2_client.authorize_security_group_ingress(
            GroupId=ec2_security_group_id,
            IpPermissions=[
                {
                    'IpProtocol': 'tcp',
                    'FromPort': 8080,
                    'ToPort': 8080,
                    'IpRanges': [{'CidrIp': '0.0.0.0/0', 'Description': 'Traffic from NLB'}]
                }
            ]
        )
    except ClientError as e:
        if 'InvalidPermission.Duplicate' not in str(e):
            raise

    target_group_arn = None
    try:
        target_group_response = elbv2_client.create_target_group(
            Name=TARGET_GROUP_NAME,
            Protocol='TCP',
            Port=8080,
            VpcId=vpc_id,
            TargetType='instance',
            HealthCheckProtocol='TCP',
            HealthCheckPort='8080',
            HealthCheckIntervalSeconds=60,# ogni 60 secondi si connettere alla ec2server per controllare
            HealthCheckTimeoutSeconds=10,
            HealthyThresholdCount=3,
            UnhealthyThresholdCount=3,
            Tags=[
                {'Key': 'Name', 'Value': TARGET_GROUP_NAME},
                {'Key': 'Application', 'Value': 'MusicApp'}
            ]
        )
        target_group_arn = target_group_response['TargetGroups'][0]['TargetGroupArn']
        print(f"[SUCCESS] Target Group creato: {TARGET_GROUP_NAME}")
    except ClientError as e:
        if 'DuplicateTargetGroupName' in str(e):
            target_groups = elbv2_client.describe_target_groups(Names=[TARGET_GROUP_NAME])
            existing_tg = target_groups['TargetGroups'][0]
            target_group_arn = existing_tg['TargetGroupArn']
            print(f"[INFO] Target Group esistente: {TARGET_GROUP_NAME}")
            
            if existing_tg['Protocol'] != 'TCP':
                elbv2_client.delete_target_group(TargetGroupArn=target_group_arn)
                target_group_response = elbv2_client.create_target_group(
                    Name=TARGET_GROUP_NAME,
                    Protocol='TCP',
                    Port=8080,
                    VpcId=vpc_id,
                    TargetType='instance',
                    HealthCheckProtocol='TCP',
                    HealthCheckPort='8080',
                    HealthCheckIntervalSeconds=60,
                    HealthCheckTimeoutSeconds=10,
                    HealthyThresholdCount=3,
                    UnhealthyThresholdCount=3,
                    Tags=[
                        {'Key': 'Name', 'Value': TARGET_GROUP_NAME},
                        {'Key': 'Application', 'Value': 'MusicApp'}
                    ]
                )
                target_group_arn = target_group_response['TargetGroups'][0]['TargetGroupArn']
                print(f"[SUCCESS] Target Group ricreato: {TARGET_GROUP_NAME}")
        else:
            raise

    try:
        nlb_response = elbv2_client.create_load_balancer(
            Name=NLB_NAME,
            Subnets=nlb_subnet_ids,
            Scheme='internet-facing',
            Type='network',
            IpAddressType='ipv4',
            Tags=[
                {'Key': 'Name', 'Value': NLB_NAME},
                {'Key': 'Application', 'Value': 'MusicApp'}
            ]
        )
        nlb_arn = nlb_response['LoadBalancers'][0]['LoadBalancerArn']
        nlb_dns_name = nlb_response['LoadBalancers'][0]['DNSName']
        print(f"[SUCCESS] Network Load Balancer creato: {nlb_dns_name}")
    except ClientError as e:
        if 'DuplicateLoadBalancerName' in str(e):
            nlbs = elbv2_client.describe_load_balancers(Names=[NLB_NAME])
            nlb_arn = nlbs['LoadBalancers'][0]['LoadBalancerArn']
            nlb_dns_name = nlbs['LoadBalancers'][0]['DNSName']
            print(f"[INFO] Network Load Balancer esistente: {nlb_dns_name}")
        else:
            raise

    waiter = elbv2_client.get_waiter('load_balancer_available')
    waiter.wait(LoadBalancerArns=[nlb_arn])

    try:
        listener_response = elbv2_client.create_listener(
            LoadBalancerArn=nlb_arn,
            Protocol='TCP',
            Port=8080,
            DefaultActions=[
                {
                    'Type': 'forward',
                    'TargetGroupArn': target_group_arn
                }
            ]
        )
        listener_arn = listener_response['Listeners'][0]['ListenerArn']
        print(f"[SUCCESS] Listener creato sulla porta 8080")
    except ClientError as e:
        if 'DuplicateListener' in str(e):
            listeners = elbv2_client.describe_listeners(LoadBalancerArn=nlb_arn)
            if listeners['Listeners']:
                existing_listener = listeners['Listeners'][0]
                listener_arn = existing_listener['ListenerArn']
                current_target_group = existing_listener['DefaultActions'][0].get('TargetGroupArn')
                if current_target_group != target_group_arn:
                    elbv2_client.modify_listener(
                        ListenerArn=listener_arn,
                        DefaultActions=[
                            {
                                'Type': 'forward',
                                'TargetGroupArn': target_group_arn
                            }
                        ]
                    )
                    print(f"[SUCCESS] Listener aggiornato")
                else:
                    print(f"[INFO] Listener esistente sulla porta 8080")
        else:
            raise

    return nlb_arn, nlb_dns_name, target_group_arn

def register_ec2_with_target_group(elbv2_client, target_group_arn, instance_id, wait_for_health=True):
    elbv2_client.register_targets(
        TargetGroupArn=target_group_arn,
        Targets=[{'Id': instance_id, 'Port': 8080}]
    )
    print(f"[SUCCESS] EC2 {instance_id} registrata nel Target Group")
    
    if wait_for_health:
        print(f"[INFO] Attendendo che il target diventi healthy...")
        waiter = elbv2_client.get_waiter('target_in_service')
        waiter.wait(
            TargetGroupArn=target_group_arn,
            Targets=[{'Id': instance_id, 'Port': 8080}]
        )
        print(f"[SUCCESS] Target healthy nel Load Balancer")
    else:
        print(f"[INFO] Target registrato - health check sarà completato dopo il deployment dell'applicazione")

def create_vpc_and_security_groups(ec2_client, rds_client):
    print("\n[SECTION] VPC e Security Groups")
    print("-" * 50)
    
    vpcs = ec2_client.describe_vpcs(Filters=[{'Name': 'isDefault', 'Values':['true']}])
    vpc_id = vpcs['Vpcs'][0]['VpcId']
    print(f"[INFO] VPC di default: {vpc_id}")

    try:
        rds_sg_response = ec2_client.create_security_group(
            GroupName='MusicAppRDSSecurityGroup',
            Description='Consenti accesso PostgreSQL per EC2 MusicApp e script locale',
            VpcId=vpc_id
        )
        rds_security_group_id = rds_sg_response['GroupId']
        print(f"[SUCCESS] Security Group RDS creato: {rds_security_group_id}")
    except ClientError as e:
        if 'InvalidGroup.Duplicate' in str(e):
            rds_security_group_id = ec2_client.describe_security_groups(
                GroupNames=['MusicAppRDSSecurityGroup'], Filters=[{'Name': 'vpc-id', 'Values':[vpc_id]}]
            )['SecurityGroups'][0]['GroupId']
            print(f"[INFO] Security Group RDS esistente: {rds_security_group_id}")

    try:
        ec2_sg_response = ec2_client.create_security_group(
            GroupName='MusicAppEC2SecurityGroup',
            Description='Consenti SSH e traffico applicativo alle istanze EC2 MusicApp',
            VpcId=vpc_id
        )
        ec2_security_group_id = ec2_sg_response['GroupId']
        print(f"[SUCCESS] Security Group EC2 creato: {ec2_security_group_id}")
    except ClientError as e:
        if 'InvalidGroup.Duplicate' in str(e):
            ec2_security_group_id = ec2_client.describe_security_groups(
                GroupNames=['MusicAppEC2SecurityGroup'], Filters=[{'Name': 'vpc-id', 'Values':[vpc_id]}]
            )['SecurityGroups'][0]['GroupId']
            print(f"[INFO] Security Group EC2 esistente: {ec2_security_group_id}")

    permissions = [
        (rds_security_group_id, [
            {'IpProtocol': 'tcp', 'FromPort': 5432, 'ToPort': 5432, 'UserIdGroupPairs':[{'GroupId': ec2_security_group_id}]},
            {'IpProtocol': 'tcp', 'FromPort': 5432, 'ToPort': 5432, 'IpRanges':[{'CidrIp': '0.0.0.0/0'}]}
        ]),
        (ec2_security_group_id, [
            {'IpProtocol': 'tcp', 'FromPort': 22, 'ToPort': 22, 'IpRanges':[{'CidrIp': '0.0.0.0/0'}]},
            {'IpProtocol': 'tcp', 'FromPort': 8080, 'ToPort': 8080, 'IpRanges':[{'CidrIp': '0.0.0.0/0'}]}
        ])
    ]
    
    for sg_id, perms in permissions:
        try:
            ec2_client.authorize_security_group_ingress(GroupId=sg_id, IpPermissions=perms)
        except ClientError as e:
            if 'InvalidPermission.Duplicate' not in str(e):
                raise

    return vpc_id, rds_security_group_id, ec2_security_group_id

def delete_resources(ec2_client, rds_client, elbv2_client, key_name, rds_id, rds_sg_name, ec2_sg_name, skip_rds=False):
    print("\n[SECTION] Pulizia Risorse AWS")
    print("-" * 50)

    try:
        nlbs = elbv2_client.describe_load_balancers(Names=[NLB_NAME])
        if nlbs['LoadBalancers']:
            elbv2_client.delete_load_balancer(LoadBalancerArns=[nlbs['LoadBalancers'][0]['LoadBalancerArn']])
            waiter = elbv2_client.get_waiter('load_balancers_deleted')
            waiter.wait(LoadBalancerArns=[nlbs['LoadBalancers'][0]['LoadBalancerArn']])
    except ClientError as e:
        if "LoadBalancerNotFound" not in str(e):
            print(f"[ERROR] NLB: {e}")

    try:
        target_groups = elbv2_client.describe_target_groups(Names=[TARGET_GROUP_NAME])
        if target_groups['TargetGroups']:
            elbv2_client.delete_target_group(TargetGroupArn=target_groups['TargetGroups'][0]['TargetGroupArn'])
    except ClientError as e:
        if "TargetGroupNotFound" not in str(e):
            print(f"[ERROR] Target Group: {e}")

    instances = ec2_client.describe_instances(
        Filters=[{'Name': 'tag:Application', 'Values':['MusicApp']}]
    )
    instance_ids = []
    for reservation in instances['Reservations']:
        for instance in reservation['Instances']:
            if instance['State']['Name'] != 'terminated':
                instance_ids.append(instance['InstanceId'])
    if instance_ids:
        ec2_client.terminate_instances(InstanceIds=instance_ids)
        waiter = ec2_client.get_waiter('instance_terminated')
        waiter.wait(InstanceIds=instance_ids)

    if not skip_rds:
        try:
            rds_client.delete_db_instance(DBInstanceIdentifier=rds_id, SkipFinalSnapshot=True)
            waiter = rds_client.get_waiter('db_instance_deleted')
            waiter.wait(DBInstanceIdentifier=rds_id)
        except ClientError as e:
            if "DBInstanceNotFound" not in str(e):
                print(f"[ERROR] RDS: {e}")

    vpcs = ec2_client.describe_vpcs(Filters=[{'Name': 'isDefault', 'Values':['true']}])
    vpc_id = vpcs['Vpcs'][0]['VpcId']
    
    for sg_name in [rds_sg_name, ec2_sg_name]:
        try:
            sg_id = ec2_client.describe_security_groups(
                GroupNames=[sg_name], Filters=[{'Name': 'vpc-id', 'Values':[vpc_id]}]
            )['SecurityGroups'][0]['GroupId']
            
            sg_details = ec2_client.describe_security_groups(GroupIds=[sg_id])['SecurityGroups'][0]
            if 'IpPermissions' in sg_details and sg_details['IpPermissions']:
                ec2_client.revoke_security_group_ingress(GroupId=sg_id, IpPermissions=sg_details['IpPermissions'])
            
            ec2_client.delete_security_group(GroupId=sg_id)
        except ClientError as e:
            if "InvalidGroup.NotFound" not in str(e) and "DependencyViolation" not in str(e):
                print(f"[ERROR] SG {sg_name}: {e}")

    try:
        ec2_client.delete_key_pair(KeyName=key_name)
        if os.path.exists(f"{key_name}.pem"):
            os.remove(f"{key_name}.pem")
    except (ClientError, PermissionError):
        pass

    print("[SUCCESS] Pulizia completata.")


def initialize_database(rds_endpoint, db_username, db_password, db_name, schema_sql, data_sql):
    print("\n[SECTION] Inizializzazione Database RDS")
    print("-" * 50)

    conn_str = f"dbname=postgres user={db_username} password={db_password} host={rds_endpoint} port=5432"
    
    for i in range(3):
        try:
            conn = psycopg2.connect(conn_str)
            conn.autocommit = True
            break
        except psycopg2.OperationalError:
            if i < 2:
                time.sleep(10)
            else:
                raise Exception("Impossibile connettersi al database PostgreSQL")

    cur = conn.cursor()
    cur.execute(f"DROP DATABASE IF EXISTS {db_name};")
    cur.execute(f"CREATE DATABASE {db_name};")
    cur.close()
    conn.close()

    conn_str_app = f"dbname={db_name} user={db_username} password={db_password} host={rds_endpoint} port=5432"
    conn_app = psycopg2.connect(conn_str_app)
    conn_app.autocommit = True
    cur_app = conn_app.cursor()
    
    cur_app.execute(schema_sql)
    cur_app.execute(data_sql)
    
    cur_app.close()
    conn_app.close()
    print(f"[SUCCESS] Database '{db_name}' inizializzato.")


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

def check_target_health(elbv2_client, target_group_arn, instance_id):
    """Controlla lo stato dell'health check per il target specificato"""
    try:
        response = elbv2_client.describe_target_health(
            TargetGroupArn=target_group_arn,
            Targets=[{'Id': instance_id, 'Port': 8080}]
        )
        
        if response['TargetHealthDescriptions']:
            health_status = response['TargetHealthDescriptions'][0]['TargetHealth']['State']
            description = response['TargetHealthDescriptions'][0]['TargetHealth'].get('Description', '')
            print(f"[INFO] Stato health check del target {instance_id}: {health_status}")
            if description:
                print(f"[INFO] Descrizione: {description}")
            return health_status
        else:
            print(f"[WARNING] Nessuna informazione di health check trovata per {instance_id}")
            return "unknown"
    except Exception as e:
        print(f"[ERROR] Errore nel controllo health check: {e}")
        return "error"

def main():
    if "--clean" in os.sys.argv:
        ec2 = boto3.client('ec2', region_name=REGION)
        rds = boto3.client('rds', region_name=REGION)
        elbv2 = boto3.client('elbv2', region_name=REGION)
        skip_rds = "--nords" in os.sys.argv
        delete_resources(ec2, rds, elbv2, KEY_PAIR_NAME, DB_INSTANCE_IDENTIFIER, 'MusicAppRDSSecurityGroup', 'MusicAppEC2SecurityGroup', skip_rds)
        return


    print("\n[SECTION] Deploy Risorse AWS")
    print("-" * 50)
    ec2_client = boto3.client('ec2', region_name=REGION)
    rds_client = boto3.client('rds', region_name=REGION)
    elbv2_client = boto3.client('elbv2', region_name=REGION)

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

        print(f"\n[STEP] Deploy RDS '{DB_INSTANCE_IDENTIFIER}'...")
        rds_endpoint = None
        try:
            response = rds_client.describe_db_instances(DBInstanceIdentifier=DB_INSTANCE_IDENTIFIER)
            instance_status = response['DBInstances'][0]['DBInstanceStatus']
            rds_endpoint = response['DBInstances'][0]['Endpoint']['Address']
            if instance_status != 'available':
                waiter = rds_client.get_waiter('db_instance_available')
                waiter.wait(DBInstanceIdentifier=DB_INSTANCE_IDENTIFIER)
                response = rds_client.describe_db_instances(DBInstanceIdentifier=DB_INSTANCE_IDENTIFIER)
                rds_endpoint = response['DBInstances'][0]['Endpoint']['Address']
        except ClientError as e:
            if "DBInstanceNotFound" in str(e):
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
                    PubliclyAccessible=True
                )
                waiter = rds_client.get_waiter('db_instance_available')
                waiter.wait(DBInstanceIdentifier=DB_INSTANCE_IDENTIFIER)
                response = rds_client.describe_db_instances(DBInstanceIdentifier=DB_INSTANCE_IDENTIFIER)
                rds_endpoint = response['DBInstances'][0]['Endpoint']['Address']
                print(f"[SUCCESS] RDS creato: {rds_endpoint}")
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

        # 5. creo Network Load Balancer e Target Group
        nlb_arn, nlb_dns_name, target_group_arn = create_network_load_balancer_and_target_group(
            ec2_client, elbv2_client, vpc_id, ec2_security_group_id
        )

        # 6. setup SNS notification e modifico user_data_script
        topic_name = 'musicapp-server-setup-complete'
        email_address = 'lorenzopaoria@icloud.com'
        topic_arn = setup_sns_notification(REGION, topic_name, email_address)
        
        script_dir = os.path.dirname(os.path.abspath(__file__))
        user_data_script_path = os.path.join(script_dir, 'user_data_script.sh')
        with open(user_data_script_path, 'r') as f:
            user_data_script = f.read()

        user_data_script = update_user_data_with_credentials(user_data_script, aws_credentials)

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
        else:
            print("\n[STEP] Deploy EC2 MusicAppServer...")
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
            waiter = ec2_client.get_waiter('instance_running')
            waiter.wait(InstanceIds=[server_instance_id])
            server_instance_details = ec2_client.describe_instances(InstanceIds=[server_instance_id])
            server_public_ip = server_instance_details['Reservations'][0]['Instances'][0]['PublicIpAddress']
            server_private_ip = server_instance_details['Reservations'][0]['Instances'][0]['PrivateIpAddress']
            print(f"[SUCCESS] EC2 attivo: {server_public_ip}")

        if server_instances_found:
            server_instance_id = server_instances_found[0]['Instances'][0]['InstanceId']
        register_ec2_with_target_group(elbv2_client, target_group_arn, server_instance_id, wait_for_health=False)

        config = {
            "server_public_ip": server_public_ip,
            "server_private_ip": server_private_ip,
            "rds_endpoint": rds_endpoint,
            "db_username": DB_MASTER_USERNAME,
            "db_password": DB_MASTER_PASSWORD,
            "db_name": DB_NAME,
            "key_pair_name": key_pair_name_actual,
            "nlb_dns_name": nlb_dns_name,
            "nlb_port": "8080"
        }

        with open("deploy_config.json", "w") as f:
            json.dump(config, f, indent=4)

        print("\n[SUCCESS] Configurazione salvata in 'deploy_config.json'.")
        
        # Controllo lo stato dell'health check
        print(f"\n[INFO] Controllo stato health check...")
        health_status = check_target_health(elbv2_client, target_group_arn, server_instance_id)
        
        if health_status == "unhealthy":
            print(f"[WARNING] Il target è ancora unhealthy - questo è normale se l'applicazione non è stata ancora deployata")
            print(f"[INFO] L'health check diventerà healthy dopo il deployment dell'applicazione Java")

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
        print("[4] Configura e avvia il client Java in locale")
        print("    - Il client si connetterà al NLB automaticamente")
        print(f"    - Endpoint: {nlb_dns_name}:8080")
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