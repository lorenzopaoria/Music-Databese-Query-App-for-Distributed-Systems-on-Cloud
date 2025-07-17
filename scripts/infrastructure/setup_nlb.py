import boto3
import json
import time
import os
from botocore.exceptions import ClientError
from dotenv import load_dotenv

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, "..", ".."))
env_path = os.path.join(project_root, ".env")
load_dotenv(env_path)

# congifurazione da env
REGION = os.getenv('AWS_REGION', 'us-east-1')
NLB_NAME = os.getenv('NLB_NAME', 'musicapp-nlb')
TARGET_GROUP_NAME = os.getenv('TARGET_GROUP_NAME', 'musicapp-targets')
SERVER_PORT = int(os.getenv('SERVER_PORT', '8080'))
NLB_PORT = int(os.getenv('NLB_PORT', '8080'))

def print_section(title):

    print(f"\n[SECTION] {title}")
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

def read_deploy_config():

    config_path = os.path.join(os.path.dirname(__file__), 'deploy_config.json')
    if not os.path.exists(config_path):
        raise Exception(f"File di configurazione deploy non trovato: {config_path}")
    
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    required_keys = ['server_private_ip', 'server_public_ip']
    for key in required_keys:
        if key not in config:
            raise Exception(f"Chiave mancante nella configurazione di deploy: {key}")
    
    print_info(f"Configurazione di deploy letta correttamente da {config_path}")
    return config

def get_default_vpc_and_subnets(ec2_client):

    print_section("Recupero VPC e Subnet")
    
    vpcs = ec2_client.describe_vpcs(Filters=[{'Name': 'isDefault', 'Values': ['true']}])
    if not vpcs['Vpcs']:
        raise Exception("VPC di default non trovata")
    
    vpc_id = vpcs['Vpcs'][0]['VpcId']
    print_info(f"VPC di default: {vpc_id}")
    
    subnets = ec2_client.describe_subnets(
        Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}]
    )
    
    if len(subnets['Subnets']) < 2:
        raise Exception("Necessarie almeno 2 subnet per il Network Load Balancer")
    
    subnet_ids = [subnet['SubnetId'] for subnet in subnets['Subnets']]
    print_info(f"Subnet trovate: {subnet_ids}")
    
    return vpc_id, subnet_ids

def get_server_instance_id(ec2_client):

    print_section("Recupero Istanza Server")
    
    instances = ec2_client.describe_instances(
        Filters=[
            {'Name': 'tag:Name', 'Values': ['MusicAppServer']},
            {'Name': 'instance-state-name', 'Values': ['running']}
        ]
    )
    
    if not instances['Reservations']:
        raise Exception("Nessuna istanza MusicAppServer in esecuzione trovata")
    
    instance_id = instances['Reservations'][0]['Instances'][0]['InstanceId']
    print_info(f"Istanza MusicAppServer trovata: {instance_id}")
    
    return instance_id

def get_or_create_target_group(elbv2_client, vpc_id):

    print_section("Creazione Target Group")
    
    try:
        existing_tgs = elbv2_client.describe_target_groups(Names=[TARGET_GROUP_NAME])
        if existing_tgs['TargetGroups']:
            target_group_arn = existing_tgs['TargetGroups'][0]['TargetGroupArn']
            print_info(f"Target Group '{TARGET_GROUP_NAME}' già esistente: {target_group_arn}")
            return target_group_arn
    except ClientError as e:
        if "TargetGroupNotFound" not in str(e):
            raise
    
    response = elbv2_client.create_target_group(
        Name=TARGET_GROUP_NAME,
        Protocol='TCP',
        Port=SERVER_PORT,
        VpcId=vpc_id,
        TargetType='instance',
        HealthCheckProtocol='TCP',
        HealthCheckPort=str(SERVER_PORT),
        HealthCheckIntervalSeconds=30,
        HealthyThresholdCount=3,
        UnhealthyThresholdCount=3
    )
    
    target_group_arn = response['TargetGroups'][0]['TargetGroupArn']
    print_success(f"Target Group '{TARGET_GROUP_NAME}' creato: {target_group_arn}")
    
    return target_group_arn

def get_or_create_nlb(elbv2_client, subnet_ids):

    print_section("Creazione Network Load Balancer")
    
    try:
        existing_nlbs = elbv2_client.describe_load_balancers(Names=[NLB_NAME])
        if existing_nlbs['LoadBalancers']:
            nlb = existing_nlbs['LoadBalancers'][0]
            nlb_arn = nlb['LoadBalancerArn']
            nlb_dns = nlb['DNSName']
            print_info(f"Network Load Balancer '{NLB_NAME}' già esistente: {nlb_dns}")
            return nlb_arn, nlb_dns
    except ClientError as e:
        if "LoadBalancerNotFound" not in str(e):
            raise
    
    response = elbv2_client.create_load_balancer(
        Name=NLB_NAME,
        Subnets=subnet_ids[:2],
        Type='network',
        Scheme='internet-facing',
        Tags=[
            {'Key': 'Application', 'Value': 'MusicApp'},
            {'Key': 'Component', 'Value': 'LoadBalancer'}
        ]
    )
    
    nlb = response['LoadBalancers'][0]
    nlb_arn = nlb['LoadBalancerArn']
    nlb_dns = nlb['DNSName']
    
    print_success(f"Network Load Balancer '{NLB_NAME}' creato: {nlb_dns}")
    print_info(f"NLB ARN: {nlb_arn}")
    
    print_info("Attesa che il NLB diventi attivo...")
    waiter = elbv2_client.get_waiter('load_balancer_available')
    waiter.wait(LoadBalancerArns=[nlb_arn])
    print_success("Network Load Balancer è ora attivo")
    
    return nlb_arn, nlb_dns

def get_or_create_listener(elbv2_client, nlb_arn, target_group_arn):

    print_section("Creazione Listener NLB")
    
    try:
        existing_listeners = elbv2_client.describe_listeners(LoadBalancerArn=nlb_arn)
        for listener in existing_listeners['Listeners']:
            if listener['Port'] == NLB_PORT:
                listener_arn = listener['ListenerArn']
                print_info(f"Listener sulla porta {NLB_PORT} già esistente: {listener_arn}")
                return listener_arn
    except ClientError as e:
        if "LoadBalancerNotFound" not in str(e):
            raise
    
    response = elbv2_client.create_listener(
        LoadBalancerArn=nlb_arn,
        Protocol='TCP',
        Port=NLB_PORT,
        DefaultActions=[
            {
                'Type': 'forward',
                'TargetGroupArn': target_group_arn
            }
        ]
    )
    
    listener_arn = response['Listeners'][0]['ListenerArn']
    print_success(f"Listener creato sulla porta {NLB_PORT}: {listener_arn}")
    
    return listener_arn

def check_target_health(elbv2_client, target_group_arn, instance_id, max_attempts=20):

    print_info("Attesa che il target diventi healthy...")
    
    for attempt in range(max_attempts):
        try:
            response = elbv2_client.describe_target_health(TargetGroupArn=target_group_arn)
            for target in response['TargetHealthDescriptions']:
                if target['Target']['Id'] == instance_id:
                    if target['TargetHealth']['State'] == 'healthy':
                        print_success(f"Target {instance_id} è ora healthy")
                        return True
                    else:
                        print_info(f"Target {instance_id} stato: {target['TargetHealth']['State']}")
        except ClientError as e:
            print_warning(f"Errore nel controllo dello stato del target: {e}")
        
        if attempt < max_attempts - 1:
            time.sleep(30)
    
    print_warning(f"Target non è diventato healthy entro {max_attempts * 30} secondi")
    return False

def register_target(elbv2_client, target_group_arn, instance_id):

    print_section("Registrazione Target")
    
    try:
        response = elbv2_client.describe_target_health(TargetGroupArn=target_group_arn)
        for target in response['TargetHealthDescriptions']:
            if target['Target']['Id'] == instance_id:
                print_info(f"Istanza {instance_id} già registrata nel target group")
                print_info(f"Stato corrente: {target['TargetHealth']['State']}")
                check_target_health(elbv2_client, target_group_arn, instance_id)
                return
    except ClientError:
        pass

    elbv2_client.register_targets(
        TargetGroupArn=target_group_arn,
        Targets=[
            {
                'Id': instance_id,
                'Port': SERVER_PORT
            }
        ]
    )
    
    print_success(f"Istanza {instance_id} registrata nel target group")
    check_target_health(elbv2_client, target_group_arn, instance_id)

def update_deploy_config(nlb_dns, nlb_port):

    print_section("Aggiornamento Configurazione")
    
    config_path = os.path.join(os.path.dirname(__file__), 'deploy_config.json')
    
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    config['nlb_dns'] = nlb_dns
    config['nlb_port'] = nlb_port
    config['nlb_enabled'] = True
    
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=4)
    
    print_success(f"Configurazione aggiornata in {config_path}")
    print_info(f"NLB DNS: {nlb_dns}")
    print_info(f"NLB Port: {nlb_port}")

def delete_nlb_resources(elbv2_client):

    try:
        try:
            nlbs = elbv2_client.describe_load_balancers(Names=[NLB_NAME])
            if nlbs['LoadBalancers']:
                nlb_arn = nlbs['LoadBalancers'][0]['LoadBalancerArn']
                elbv2_client.delete_load_balancer(LoadBalancerArn=nlb_arn)
                print_info(f"Network Load Balancer '{NLB_NAME}' eliminato")
                
                # Wait for deletion
                print_info("Attesa della cancellazione del NLB...")
                waiter = elbv2_client.get_waiter('load_balancers_deleted')
                waiter.wait(LoadBalancerArns=[nlb_arn])
                print_success("Network Load Balancer eliminato completamente")
        except ClientError as e:
            handle_client_error(e, ["LoadBalancerNotFound"], f"Network Load Balancer '{NLB_NAME}' non trovato o già eliminato", "Errore nell'eliminazione del NLB")
        
        try:
            target_groups = elbv2_client.describe_target_groups(Names=[TARGET_GROUP_NAME])
            if target_groups['TargetGroups']:
                tg_arn = target_groups['TargetGroups'][0]['TargetGroupArn']
                elbv2_client.delete_target_group(TargetGroupArn=tg_arn)
                print_info(f"Target Group '{TARGET_GROUP_NAME}' eliminato")
        except ClientError as e:
            handle_client_error(e, ["TargetGroupNotFound"], f"Target Group '{TARGET_GROUP_NAME}' non trovato o già eliminato", "Errore nell'eliminazione del Target Group")
        
    except Exception as e:
        print_error(f"Durante l'eliminazione delle risorse NLB: {e}")
        raise

def remove_nlb_config():

    config_path = os.path.join(os.path.dirname(__file__), 'deploy_config.json')
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        config.pop('nlb_dns', None)
        config.pop('nlb_port', None)
        config.pop('nlb_enabled', None)
        
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=4)
        
        print_info(f"Configurazione NLB rimossa da {config_path}")

def cleanup_nlb_resources():

    print_section("Pulizia Risorse NLB")
    
    elbv2_client = boto3.client('elbv2', region_name=REGION)
    
    try:
        delete_nlb_resources(elbv2_client)
        remove_nlb_config()
        print_success("Pulizia risorse NLB completata")
        
    except Exception as e:
        print_error(f"Durante la pulizia delle risorse NLB: {e}")
        raise

def main():

    if "--clean" in sys.argv:
        cleanup_nlb_resources()
        return
    
    try:
        deploy_config = read_deploy_config()
        
        ec2_client = boto3.client('ec2', region_name=REGION)
        elbv2_client = boto3.client('elbv2', region_name=REGION)
        
        vpc_id, subnet_ids = get_default_vpc_and_subnets(ec2_client)
        
        server_instance_id = get_server_instance_id(ec2_client)
        
        target_group_arn = get_or_create_target_group(elbv2_client, vpc_id)
        
        nlb_arn, nlb_dns = get_or_create_nlb(elbv2_client, subnet_ids)
        
        listener_arn = get_or_create_listener(elbv2_client, nlb_arn, target_group_arn)
        
        register_target(elbv2_client, target_group_arn, server_instance_id)
        
        update_deploy_config(nlb_dns, NLB_PORT)
        
        print_success("Setup Network Load Balancer completato!")
        print("=" * 60)
        print_info(f"NLB DNS: {nlb_dns}")
        print_info(f"NLB Port: {NLB_PORT}")
        print_info("Il client ora può connettersi tramite il Network Load Balancer")
        print_info("Esegui 'python update_java_config_on_ec2.py' per aggiornare la configurazione Java")
        print("=" * 60)
        
    except Exception as e:
        print_error(f"Durante il setup del Network Load Balancer: {e}")
        raise

if __name__ == "__main__":
    import sys
    main()
