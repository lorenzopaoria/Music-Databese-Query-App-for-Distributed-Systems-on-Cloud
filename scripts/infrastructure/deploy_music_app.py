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

# --- Configurazione Database RDS ---
DB_INSTANCE_IDENTIFIER = 'music-db-app-rds'
DB_ENGINE = 'postgres'
DB_ENGINE_VERSION = '17.4'
DB_INSTANCE_CLASS = 'db.t3.micro'
DB_ALLOCATED_STORAGE = 20
DB_MASTER_USERNAME = 'dbadmin'
DB_MASTER_PASSWORD = '12345678'
DB_NAME = 'musicdb'

# --- Funzioni di supporto ---
def get_key_pair(ec2_client, key_name):
    """
    Controlla se la key pair EC2 esiste,se non esiste la crea e salva il file .pem localmente.
    """
    try:
        response = ec2_client.describe_key_pairs(KeyNames=[key_name])
        print(f"EC2 key '{key_name}' già esistente.")
        return response['KeyPairs'][0]['KeyName']
    except ClientError as e:
        if "InvalidKeyPair.NotFound" in str(e):
            print(f"EC2 key '{key_name}' non trovata. Creazione in corso...")
            key_pair = ec2_client.create_key_pair(KeyName=key_name)
            with open(f"{key_name}.pem", "w") as f:
                f.write(key_pair['KeyMaterial'])
            os.chmod(f"{key_name}.pem", 0o400)
            print(f"Key '{key_name}.pem' creata.")
            return key_pair['KeyName']
        else:
            raise

def create_vpc_and_security_groups(ec2_client, rds_client):
    """
    Verifica che la VPC di default esista e crea o recupera i Security Group necessari per EC2 e RDS.
    Imposta anche le regole di ingresso per PostgreSQL, SSH e traffico applicativo.
    """
    print("Controllo o creazione di VPC e Security Groups...")
    # Ottieni la VPC di default
    vpcs = ec2_client.describe_vpcs(Filters=[{'Name': 'isDefault', 'Values': ['true']}])
    vpc_id = vpcs['Vpcs'][0]['VpcId']
    print(f"VPC di default trovata: {vpc_id}")

    # Crea Security Group per RDS
    try:
        rds_sg_response = ec2_client.create_security_group(
            GroupName='MusicAppRDSSecurityGroup',
            Description='Consenti accesso PostgreSQL per EC2 MusicApp e script locale',
            VpcId=vpc_id
        )
        rds_security_group_id = rds_sg_response['GroupId']
        print(f"Security Group RDS creata: {rds_security_group_id}")
    except ClientError as e:
        if 'InvalidGroup.Duplicate' in str(e):
            rds_security_group_id = ec2_client.describe_security_groups(
                GroupNames=['MusicAppRDSSecurityGroup'], Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}]
            )['SecurityGroups'][0]['GroupId']
            print(f"Security Group RDS già esistente: {rds_security_group_id}")
        else:
            raise

    # Crea Security Group per EC2
    try:
        ec2_sg_response = ec2_client.create_security_group(
            GroupName='MusicAppEC2SecurityGroup',
            Description='Consenti SSH e traffico applicativo alle istanze EC2 MusicApp',
            VpcId=vpc_id
        )
        ec2_security_group_id = ec2_sg_response['GroupId']
        print(f"Security Group EC2 creata: {ec2_security_group_id}")
    except ClientError as e:
        if 'InvalidGroup.Duplicate' in str(e):
            ec2_security_group_id = ec2_client.describe_security_groups(
                GroupNames=['MusicAppEC2SecurityGroup'], Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}]
            )['SecurityGroups'][0]['GroupId']
            print(f"Security Group EC2 già esistente: {ec2_security_group_id}")
        else:
            raise

    # Autorizza ingresso per SG RDS (da EC2 SG)
    try:
        ec2_client.authorize_security_group_ingress(
            GroupId=rds_security_group_id,
            IpPermissions=[
                {
                    'IpProtocol': 'tcp',
                    'FromPort': 5432, # Porta PostgreSQL
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

    # Autorizza ingresso per SG RDS da macchina locale (solo per inizializzazione DB, sviluppo)
    try:
        ec2_client.authorize_security_group_ingress(
            GroupId=rds_security_group_id,
            IpPermissions=[
                {
                    'IpProtocol': 'tcp',
                    'FromPort': 5432, # Porta PostgreSQL
                    'ToPort': 5432,
                    'IpRanges': [{'CidrIp': '0.0.0.0/0', 'Description': 'Consenti accesso script locale per init DB (solo sviluppo)'}]
                }
            ]
        )
        print("Regola di ingresso RDS SG autorizzata per 0.0.0.0/0 (per inizializzazione locale).")
    except ClientError as e:
        if 'InvalidPermission.Duplicate' in str(e):
            print("Regola di ingresso RDS SG già esistente (0.0.0.0/0->RDS).")
        else:
            raise
            
    # Autorizza ingresso per EC2 (SSH e porta app)
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
                    'FromPort': 8080, # Porta applicazione
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
    """
    Elimina tutte le risorse AWS create da questo deployment: istanze EC2, istanza RDS, Security Groups e Key Pair.
    """
    print("Avvio della pulizia delle risorse AWS...")

    # Termina le istanze EC2
    print("Terminazione delle istanze EC2...")
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
        print(f"Istanze EC2 terminate: {instance_ids}. Attesa della terminazione...")
        waiter = ec2_client.get_waiter('instance_terminated')
        waiter.wait(InstanceIds=instance_ids)
        print("Istanze EC2 terminate con successo.")
    else:
        print("Nessuna istanza EC2 'MusicApp' trovata da terminare.")

    # Elimina istanza RDS
    print(f"Eliminazione dell'istanza RDS '{rds_id}'...")
    try:
        rds_client.delete_db_instance(
            DBInstanceIdentifier=rds_id,
            SkipFinalSnapshot=True
        )
        print(f"Istanza RDS '{rds_id}' eliminata. Attesa della cancellazione...")
        waiter = rds_client.get_waiter('db_instance_deleted')
        waiter.wait(DBInstanceIdentifier=rds_id)
        print(f"Istanza RDS '{rds_id}' eliminata con successo.")
    except ClientError as e:
        if "DBInstanceNotFound" in str(e):
            print(f"Istanza RDS '{rds_id}' non trovata o già eliminata.")
        else:
            print(f"Errore durante l'eliminazione dell'istanza RDS: {e}")

    # Elimina Security Groups
    print("Eliminazione dei Security Groups...")
    vpcs = ec2_client.describe_vpcs(Filters=[{'Name': 'isDefault', 'Values': ['true']}])
    vpc_id = vpcs['Vpcs'][0]['VpcId']
    
    # Prova a eliminare i SG in un ordine che riduca le dipendenze
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

    # Prova a revocare tutte le regole di ingresso prima di eliminare i SG
    for sg_id in sg_to_delete:
        try:
            sg_details = ec2_client.describe_security_groups(GroupIds=[sg_id])['SecurityGroups'][0]
            if 'IpPermissions' in sg_details and sg_details['IpPermissions']:
                ec2_client.revoke_security_group_ingress(
                    GroupId=sg_id,
                    IpPermissions=sg_details['IpPermissions']
                )
                print(f"Regole di ingresso revocate per SG {sg_id}.")
        except ClientError as e:
            if 'InvalidPermission.NotFound' not in str(e):
                print(f"Attenzione: impossibile revocare regole di ingresso per {sg_id}: {e}")

    # Ora elimina i SG
    for sg_name_current in [rds_sg_name, ec2_sg_name]:
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
                print(f"Errore: Security Group '{sg_name_current}' ha ancora dipendenze. Riprova più tardi o elimina manualmente.")
            else:
                print(f"Errore durante l'eliminazione del Security Group '{sg_name_current}': {e}")
    
    # Elimina Key Pair
    print(f"Eliminazione della Key Pair '{key_name}'...")
    try:
        ec2_client.delete_key_pair(KeyName=key_name)
        print(f"Key Pair '{key_name}' eliminata da AWS.")
        if os.path.exists(f"{key_name}.pem"):
            try:
                os.remove(f"{key_name}.pem")
                print(f"File locale '{key_name}.pem' eliminato.")
            except PermissionError:
                print(f"ATTENZIONE: impossibile eliminare il file locale '{key_name}.pem' per errore di permessi (potrebbe essere in uso). Elimina manualmente.")
            except Exception as file_e:
                print(f"ATTENZIONE: errore nell'eliminazione del file locale '{key_name}.pem': {file_e}")
    except ClientError as e:
        if "InvalidKeyPair.NotFound" in str(e):
            print(f"Key Pair '{key_name}' non trovata o già eliminata in AWS.")
            if os.path.exists(f"{key_name}.pem"):
                try:
                    os.remove(f"{key_name}.pem")
                    print(f"File locale '{key_name}.pem' eliminato.")
                except PermissionError:
                    print(f"ATTENZIONE: impossibile eliminare il file locale '{key_name}.pem' per errore di permessi (potrebbe essere in uso). Elimina manualmente.")
                except Exception as file_e:
                    print(f"ATTENZIONE: errore nell'eliminazione del file locale '{key_name}.pem': {file_e}")
        else:
            print(f"Errore durante l'eliminazione della Key Pair in AWS: {e}")
            raise

    print("Pulizia delle risorse AWS completata.")


def initialize_database(rds_endpoint, db_username, db_password, db_name, schema_sql, data_sql):
    print(f"\nInizializzazione del database '{db_name}' su {rds_endpoint}...")

    # Connessione al database "postgres" (database di default) per operazioni di drop/create
    conn_str_master = f"dbname=postgres user={db_username} password={db_password} host={rds_endpoint} port=5432"
    conn = None
    try:
        # Prova a connetterti con tentativi multipli per dare tempo all'RDS di avviarsi
        for i in range(5):
            try:
                conn = psycopg2.connect(conn_str_master)
                conn.autocommit = True # Permette DDL come DROP DATABASE
                print("Connesso al database 'postgres' per la gestione.")
                break
            except psycopg2.OperationalError as e:
                print(f"Tentativo {i+1} di connessione fallito: {e}. Attesa di 10 secondi...")
                time.sleep(10)
        if conn is None:
            raise Exception("Impossibile connettersi al database master PostgreSQL.")

        cur = conn.cursor()

        # 1. Termina tutte le connessioni al database target
        print(f"Terminazione delle connessioni attive al database '{db_name}'...")
        try:
            cur.execute(f"""
                SELECT pg_terminate_backend(pg_stat_activity.pid)
                FROM pg_stat_activity
                WHERE pg_stat_activity.datname = '{db_name}'
                    AND pid <> pg_backend_pid();
            """)
            print(f"Connessioni terminate per '{db_name}'.")
        except Exception as e:
            print(f"Attenzione: errore nella terminazione delle connessioni (potrebbe non esistere o mancare permessi): {e}")

        # 2. Elimina il database esistente (se esiste)
        print(f"Tentativo di eliminazione del database '{db_name}' (se esiste)...")
        try:
            cur.execute(f"DROP DATABASE IF EXISTS {db_name};")
            print(f"Database '{db_name}' eliminato (o non esisteva).")
        except Exception as e:
            print(f"Errore nell'eliminazione del database '{db_name}': {e}")
            raise # Rilancia errore se impossibile eliminare DB

        # 3. Crea il database
        print(f"Creazione del database '{db_name}'...")
        cur.execute(f"CREATE DATABASE {db_name};")
        print(f"Database '{db_name}' creato.")

        cur.close()
        conn.close() # Chiudi connessione al database master

        # Connettiti al nuovo database per inizializzazione schema e dati
        conn_str_app = f"dbname={db_name} user={db_username} password={db_password} host={rds_endpoint} port=5432"
        conn_app = None
        for i in range(5):
            try:
                conn_app = psycopg2.connect(conn_str_app)
                print(f"Connesso al database '{db_name}' per inizializzazione schema.")
                break
            except psycopg2.OperationalError as e:
                print(f"Tentativo {i+1} di connessione al DB app fallito: {e}. Attesa di 5 secondi...")
                time.sleep(5)
        if conn_app is None:
            raise Exception("Impossibile connettersi al database applicativo.")

        conn_app.autocommit = True # Per eseguire più statement DDL/DML senza commit esplicito
        cur_app = conn_app.cursor()

        # Esegui schema.sql
        print("Esecuzione di schema.sql...")
        try:
            cur_app.execute(schema_sql)
            print("schema.sql eseguito con successo.")
        except Exception as e:
            print(f"Errore nell'esecuzione dello schema SQL: {e}")
            raise

        # Esegui data.sql
        print("Esecuzione di data.sql...")
        try:
            cur_app.execute(data_sql)
            print("data.sql eseguito con successo.")
        except Exception as e:
            print(f"Errore nell'esecuzione del comando SQL per i dati: {e}")
            raise

        cur_app.close()
        conn_app.close()
        print(f"Inizializzazione del database '{db_name}' completata con successo.")

    except psycopg2.Error as e:
        print(f"Errore durante l'inizializzazione del database: {e}")
        raise # Rilancia errore per fermare lo script principale
    except Exception as e:
        print(f"Si è verificato un errore inatteso durante l'inizializzazione del database: {e}")
        raise
    finally:
        if conn:
            conn.close()
        if 'conn_app' in locals() and conn_app:
            conn_app.close()


def get_account_id():
    sts = boto3.client('sts')
    return sts.get_caller_identity()['Account']

def create_ec2_codedeploy_role(iam_client):
    role_name = "MusicAppEC2CodeDeployRole"
    assume_role_policy = {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"Service": "ec2.amazonaws.com"},
            "Action": "sts:AssumeRole"
        }]
    }
    try:
        role = iam_client.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(assume_role_policy),
            Description="Ruolo per EC2 per lavorare con CodeDeploy"
        )
        print(f"Ruolo IAM '{role_name}' creato.")
    except ClientError as e:
        if "EntityAlreadyExists" in str(e):
            print(f"Ruolo IAM '{role_name}' già esistente.")
            role = iam_client.get_role(RoleName=role_name)
        else:
            raise

    # Associa la policy gestita per CodeDeploy
    policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonEC2RoleforAWSCodeDeploy"
    try:
        iam_client.attach_role_policy(RoleName=role_name, PolicyArn=policy_arn)
        print(f"Policy '{policy_arn}' associata a '{role_name}'.")
    except ClientError as e:
        if "EntityAlreadyExists" in str(e):
            print(f"Policy già associata.")
        else:
            raise

    return role['Role']['Arn']

def create_codepipeline(pipeline_name, repo_owner, repo_name, branch, buildspec_path, appspec_path, region):
    codepipeline = boto3.client('codepipeline', region_name=region)
    codebuild = boto3.client('codebuild', region_name=region)
    codedeploy = boto3.client('codedeploy', region_name=region)
    s3 = boto3.client('s3', region_name=region)
    account_id = get_account_id()
    artifact_bucket = f"musicapp-codepipeline-artifacts-{account_id}"

    # Crea bucket S3 se non esiste
    try:
        s3.head_bucket(Bucket=artifact_bucket)
        print(f"Bucket S3 '{artifact_bucket}' già esistente.")
    except ClientError:
        if region == "us-east-1":
            s3.create_bucket(Bucket=artifact_bucket)
        else:
            s3.create_bucket(
                Bucket=artifact_bucket,
                CreateBucketConfiguration={'LocationConstraint': region}
            )
        print(f"Bucket S3 '{artifact_bucket}' creato.")

    # Crea progetto CodeBuild se non esiste
    build_project_name = f"{pipeline_name}-build"
    try:
        codebuild.batch_get_projects(names=[build_project_name])['projects'][0]
        print(f"Progetto CodeBuild '{build_project_name}' già esistente.")
    except (IndexError, ClientError):
        codebuild.create_project(
            name=build_project_name,
            source={
                'type': 'GITHUB',
                'location': f"https://github.com/{repo_owner}/{repo_name}.git",
                'buildspec': buildspec_path
            },
            artifacts={'type': 'S3', 'location': artifact_bucket},
            environment={
                'type': 'LINUX_CONTAINER',
                'image': 'aws/codebuild/standard:7.0',
                'computeType': 'BUILD_GENERAL1_SMALL'
            },
            serviceRole=f"arn:aws:iam::{account_id}:role/service-role/AWSCodeBuildServiceRole"
        )
        print(f"Progetto CodeBuild '{build_project_name}' creato.")

    # Crea applicazione CodeDeploy se non esiste
    codedeploy_app_name = f"{pipeline_name}-codedeploy"
    try:
        codedeploy.get_application(applicationName=codedeploy_app_name)
        print(f"Applicazione CodeDeploy '{codedeploy_app_name}' già esistente.")
    except ClientError:
        codedeploy.create_application(applicationName=codedeploy_app_name, computePlatform='Server')
        print(f"Applicazione CodeDeploy '{codedeploy_app_name}' creata.")

    # Crea pipeline CodePipeline
    try:
        codepipeline.get_pipeline(name=pipeline_name)
        print(f"Pipeline '{pipeline_name}' già esistente.")
    except ClientError:
        pipeline = {
            'pipeline': {
                'name': pipeline_name,
                'roleArn': f"arn:aws:iam::{account_id}:role/AWSCodePipelineServiceRole",
                'artifactStore': {
                    'type': 'S3',
                    'location': artifact_bucket
                },
                'stages': [
                    {
                        'name': 'Source',
                        'actions': [{
                            'name': 'Source',
                            'actionTypeId': {
                                'category': 'Source',
                                'owner': 'ThirdParty',
                                'provider': 'GitHub',
                                'version': '1'
                            },
                            'outputArtifacts': [{'name': 'SourceArtifact'}],
                            'configuration': {
                                'Owner': repo_owner,
                                'Repo': repo_name,
                                'Branch': branch,
                                'OAuthToken': os.environ.get('GITHUB_TOKEN', 'INSERISCI_TOKEN_GITHUB')
                            },
                            'runOrder': 1
                        }]
                    },
                    {
                        'name': 'Build',
                        'actions': [{
                            'name': 'Build',
                            'actionTypeId': {
                                'category': 'Build',
                                'owner': 'AWS',
                                'provider': 'CodeBuild',
                                'version': '1'
                            },
                            'inputArtifacts': [{'name': 'SourceArtifact'}],
                            'outputArtifacts': [{'name': 'BuildArtifact'}],
                            'configuration': {
                                'ProjectName': build_project_name
                            },
                            'runOrder': 1
                        }]
                    },
                    {
                        'name': 'Deploy',
                        'actions': [{
                            'name': 'Deploy',
                            'actionTypeId': {
                                'category': 'Deploy',
                                'owner': 'AWS',
                                'provider': 'CodeDeploy',
                                'version': '1'
                            },
                            'inputArtifacts': [{'name': 'BuildArtifact'}],
                            'configuration': {
                                'ApplicationName': codedeploy_app_name,
                                'DeploymentGroupName': 'MusicAppDeploymentGroup'
                            },
                            'runOrder': 1
                        }]
                    }
                ],
                'version': 1
            }
        }
        codepipeline.create_pipeline(**pipeline)
        print(f"Pipeline '{pipeline_name}' creata.")

# --- Logica principale di deploy ---
def main():
    if "--clean" in os.sys.argv:
        ec2 = boto3.client('ec2', region_name=REGION)
        rds = boto3.client('rds', region_name=REGION)
        delete_resources(ec2, rds, KEY_PAIR_NAME, DB_INSTANCE_IDENTIFIER, 'MusicAppRDSSecurityGroup', 'MusicAppEC2SecurityGroup')
        return

    ec2_client = boto3.client('ec2', region_name=REGION)
    rds_client = boto3.client('rds', region_name=REGION)

    # --- LETTURA FILE SQL ---
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

        # 3. Deploy istanza RDS
        print(f"\nTentativo di deploy dell'istanza RDS '{DB_INSTANCE_IDENTIFIER}'...")
        rds_endpoint = None
        try:
            # Prova a descrivere se già esiste ed è disponibile
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
                print(f"Istanza RDS '{DB_INSTANCE_IDENTIFIER}' ora è 'available'.")
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
                    PubliclyAccessible=True # Per debug e accesso locale, impostare a False per sicurezza in produzione
                )
                print(f"Creazione dell'istanza RDS '{DB_INSTANCE_IDENTIFIER}' avviata. Attesa che diventi 'available'...")
                waiter = rds_client.get_waiter('db_instance_available')
                waiter.wait(DBInstanceIdentifier=DB_INSTANCE_IDENTIFIER)
                response = rds_client.describe_db_instances(DBInstanceIdentifier=DB_INSTANCE_IDENTIFIER)
                rds_endpoint = response['DBInstances'][0]['Endpoint']['Address']
                print(f"Istanza RDS '{DB_INSTANCE_IDENTIFIER}' ora è 'available'. Endpoint: {rds_endpoint}")
            else:
                raise

        if not rds_endpoint:
            raise Exception("Impossibile ottenere l'endpoint RDS.")

        # 4. Inizializza il database con schema e dati
        print("Inizializzazione del database RDS con schema e dati...")
        initialize_database(
            rds_endpoint=rds_endpoint,
            db_username=DB_MASTER_USERNAME,
            db_password=DB_MASTER_PASSWORD,
            db_name=DB_NAME,
            schema_sql=schema_sql_content,
            data_sql=dati_sql_content
        )

        # 5. Ottieni User Data Script
        with open('user_data_script.sh', 'r') as f:
            user_data_script = f.read()

        # 6. Deploy istanza EC2 MusicAppServer (o usa esistente)
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
            print(f"\nIstanza MusicAppServer esistente e in esecuzione: {server_instance_id}. Public IP: {server_public_ip}, Private IP: {server_private_ip}")
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
            print(f"MusicAppServer è in esecuzione. Public IP: {server_public_ip}, Private IP: {server_private_ip}")

        # 7. Deploy istanze EC2 MusicAppClient (o usa esistenti)
        client_public_ips = []
        client_private_ips = []
        # Nessun deploy client EC2: il client verrà eseguito in locale
        print("\n--- Deploy completato ---")
        print("Dettagli di connessione:")
        print(f"SSH Key: {key_pair_name_actual}.pem")
        print(f"RDS Endpoint: {rds_endpoint}")
        print(f"DB User: {DB_MASTER_USERNAME}")
        print(f"DB Password: {DB_MASTER_PASSWORD}")
        print(f"DB Name: {DB_NAME}")
        print(f"\nServer EC2 Public IP: {server_public_ip}")
        print(f"Server EC2 Private IP (per client nella stessa VPC): {server_private_ip}")
        print(f"Client locale: usa il public IP del server EC2 per connetterti")

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
        print("\n==============================")
        print("   GUIDA STEP-BY-STEP DEPLOY  ")
        print("==============================")
        print("1. Aggiorna i file di configurazione Java locali:")
        print("   python scripts/infrastructure/update_java_config_on_ec2.py")
        print("2. Effettua commit e push delle modifiche (lo script sopra lo fa automaticamente).")
        print("==============================\n")

    except ClientError as e:
        print(f"Si è verificato un errore AWS: {e}")
    except Exception as e:
        print(f"Si è verificato un errore inatteso: {e}")

if __name__ == "__main__":
    main()