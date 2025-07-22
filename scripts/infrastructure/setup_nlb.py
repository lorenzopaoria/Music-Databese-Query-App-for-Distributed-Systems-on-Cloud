import boto3
import json
import time
import os
from botocore.exceptions import ClientError

# configurazione NLB
REGION = 'us-east-1'
NLB_NAME = 'musicapp-nlb'
TARGET_GROUP_NAME = 'musicapp-targets'
SERVER_PORT = 8080
NLB_PORT = 8080

# lettura della configurazione di deploy
def read_deploy_config():

    config_path = os.path.join(os.path.dirname(__file__), 'deploy_config.json')
    
    # verifica dell'esistenza del file di configurazione
    if not os.path.exists(config_path):
        raise Exception(f"File di configurazione deploy non trovato: {config_path}")
    
    # lettura e parsing del file JSON
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    # validazione delle chiavi necessarie
    required_keys = ['server_private_ip', 'server_public_ip']
    for key in required_keys:
        if key not in config:
            raise Exception(f"Chiave mancante nella configurazione di deploy: {key}")
    
    print(f"[INFO] Configurazione di deploy letta correttamente da {config_path}")
    return config

# recupero della VPC di default e delle subnet disponibili
def get_default_vpc_and_subnets(ec2_client):

    print("\n[SECTION] Recupero VPC e Subnet")
    print("-" * 50)
    
    # ottengo VPC di default
    vpcs = ec2_client.describe_vpcs(Filters=[{'Name': 'isDefault', 'Values': ['true']}])
    if not vpcs['Vpcs']:
        raise Exception("VPC di default non trovata")
    
    vpc_id = vpcs['Vpcs'][0]['VpcId']
    print(f"[INFO] VPC di default: {vpc_id}")
    
    # ottengo Subnet della VPC di default
    subnets = ec2_client.describe_subnets(
        Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}]
    )
    
    # verifica che ci siano almeno 2 subnet per alta disponibilità
    if len(subnets['Subnets']) < 2:
        raise Exception("Necessarie almeno 2 subnet per il Network Load Balancer")
    
    subnet_ids = [subnet['SubnetId'] for subnet in subnets['Subnets']]
    print(f"[INFO] Subnet trovate: {subnet_ids}")
    
    return vpc_id, subnet_ids

# recupero dell'istanza EC2 del server
def get_server_instance_id(ec2_client):

    print("\n[SECTION] Recupero Istanza Server")
    print("-" * 50)
    
    # ricerca dell'istanza con tag Name=MusicAppServer in stato running
    instances = ec2_client.describe_instances(
        Filters=[
            {'Name': 'tag:Name', 'Values': ['MusicAppServer']},
            {'Name': 'instance-state-name', 'Values': ['running']}
        ]
    )
    
    # verifica che l'istanza esista
    if not instances['Reservations']:
        raise Exception("Nessuna istanza MusicAppServer in esecuzione trovata")
    
    instance_id = instances['Reservations'][0]['Instances'][0]['InstanceId']
    print(f"[INFO] Istanza MusicAppServer trovata: {instance_id}")
    
    return instance_id

# creazione del target group per il load balancer
def create_target_group(elbv2_client, vpc_id):

    print("\n[SECTION] Creazione Target Group")
    print("-" * 50)
    
    try:
        # verifico se il target group esiste già
        existing_tgs = elbv2_client.describe_target_groups(Names=[TARGET_GROUP_NAME])
        if existing_tgs['TargetGroups']:
            target_group_arn = existing_tgs['TargetGroups'][0]['TargetGroupArn']
            print(f"[INFO] Target Group '{TARGET_GROUP_NAME}' già esistente: {target_group_arn}")
            return target_group_arn
    except ClientError as e:
        # se il target group non esiste, procedo con la creazione
        if "TargetGroupNotFound" not in str(e):
            raise
    
    # creazione del nuovo target group con configurazione health check
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
    
    # estrazione dell'ARN del target group creato
    target_group_arn = response['TargetGroups'][0]['TargetGroupArn']
    print(f"[SUCCESS] Target Group '{TARGET_GROUP_NAME}' creato: {target_group_arn}")
    
    return target_group_arn

# creazione NLB
def create_nlb(elbv2_client, subnet_ids):

    print("\n[SECTION] Creazione Network Load Balancer")
    print("-" * 50)
    
    try:
        # verifico se il NLB esiste già
        existing_nlbs = elbv2_client.describe_load_balancers(Names=[NLB_NAME])
        if existing_nlbs['LoadBalancers']:
            nlb = existing_nlbs['LoadBalancers'][0]
            nlb_arn = nlb['LoadBalancerArn']
            nlb_dns = nlb['DNSName']
            print(f"[INFO] Network Load Balancer '{NLB_NAME}' già esistente: {nlb_dns}")
            return nlb_arn, nlb_dns
    except ClientError as e:
        # se il NLB non esiste, procedo con la creazione
        if "LoadBalancerNotFound" not in str(e):
            raise
    
    # creazione del nuovo Network Load Balancer con tutte le subnet disponibili
    response = elbv2_client.create_load_balancer(
        Name=NLB_NAME,
        Subnets=subnet_ids,  # usa tutte le subnet disponibili (questa cosa non mi ha fatto dormire la notte, io gli passavo solo le prime 2)
        Type='network',
        Scheme='internet-facing',
        Tags=[
            {'Key': 'Application', 'Value': 'MusicApp'},
            {'Key': 'Component', 'Value': 'LoadBalancer'}
        ]
    )
    
    # estrazione dei parametri del NLB creato
    nlb = response['LoadBalancers'][0]
    nlb_arn = nlb['LoadBalancerArn']
    nlb_dns = nlb['DNSName']
    
    print(f"[SUCCESS] Network Load Balancer '{NLB_NAME}' creato: {nlb_dns}")
    print(f"[INFO] NLB ARN: {nlb_arn}")
    
    # attesa che il NLB diventi attivo prima di procedere
    print("[INFO] Attesa che il NLB diventi attivo...")
    waiter = elbv2_client.get_waiter('load_balancer_available')
    waiter.wait(LoadBalancerArns=[nlb_arn])
    print("[SUCCESS] Network Load Balancer è ora attivo")
    
    return nlb_arn, nlb_dns

# creazione del listener per il NLB
def create_listener(elbv2_client, nlb_arn, target_group_arn):

    print("\n[SECTION] Creazione Listener NLB")
    print("-" * 50)
    
    try:
        # verifico se il listener esiste già
        existing_listeners = elbv2_client.describe_listeners(LoadBalancerArn=nlb_arn)
        for listener in existing_listeners['Listeners']:
            if listener['Port'] == NLB_PORT:
                listener_arn = listener['ListenerArn']
                print(f"[INFO] Listener sulla porta {NLB_PORT} già esistente: {listener_arn}")
                return listener_arn
    except ClientError as e:
        # se non ci sono listener, procedo con la creazione
        if "LoadBalancerNotFound" not in str(e):
            raise
    
    # creazione del nuovo listener con instradamento al target group
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
    
    # estrazione dell'ARN del listener creato
    listener_arn = response['Listeners'][0]['ListenerArn']
    print(f"[SUCCESS] Listener creato sulla porta {NLB_PORT}: {listener_arn}")
    
    return listener_arn

# registrazione dell'istanza nel target group
def register_target(elbv2_client, target_group_arn, instance_id):

    print("\n[SECTION] Registrazione Target")
    print("-" * 50)
    
    # verifico se il target è già registrato
    try:
        response = elbv2_client.describe_target_health(TargetGroupArn=target_group_arn)
        for target in response['TargetHealthDescriptions']:
            if target['Target']['Id'] == instance_id:
                print(f"[INFO] Istanza {instance_id} già registrata nel target group")
                print(f"[INFO] Stato corrente: {target['TargetHealth']['State']}")
                return
    except ClientError:
        pass
    
    # registrazione del target nel target group
    elbv2_client.register_targets(
        TargetGroupArn=target_group_arn,
        Targets=[
            {
                'Id': instance_id,
                'Port': SERVER_PORT
            }
        ]
    )
    
    print(f"[SUCCESS] Istanza {instance_id} registrata nel target group")
    
    # attesa che il target diventi healthy per confermare il corretto funzionamento
    print("[INFO] Attesa che il target diventi healthy...")
    max_attempts = 20
    for attempt in range(max_attempts):
        try:
            response = elbv2_client.describe_target_health(TargetGroupArn=target_group_arn)
            for target in response['TargetHealthDescriptions']:
                if target['Target']['Id'] == instance_id:
                    state = target['TargetHealth']['State']
                    if state == 'healthy':
                        print(f"[SUCCESS] Target {instance_id} è ora healthy")
                        return
                    elif state == 'unhealthy':
                        reason = target['TargetHealth'].get('Reason', 'Unknown')
                        description = target['TargetHealth'].get('Description', '')
                        print(f"[WARNING] Target unhealthy - Reason: {reason}, Description: {description}")
                    else:
                        print(f"[INFO] Stato target: {state}")
        except ClientError as e:
            print(f"[WARNING] Errore nel controllo dello stato del target: {e}")
        
        # pausa tra i controlli dello stato
        if attempt < max_attempts - 1:
            time.sleep(30)
    
    print(f"[WARNING] Target non è diventato healthy entro {max_attempts * 30} secondi")

# aggiornamento del file di configurazione di deploy
def update_deploy_config(nlb_dns, nlb_port):

    print("\n[SECTION] Aggiornamento Configurazione")
    print("-" * 50)
    
    config_path = os.path.join(os.path.dirname(__file__), 'deploy_config.json')
    
    # lettura della configurazione esistente
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    # aggiunta delle informazioni del NLB al deploy_config.json
    config['nlb_dns'] = nlb_dns
    config['nlb_port'] = nlb_port
    config['nlb_enabled'] = True
    
    # salvataggio della configurazione aggiornata
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=4)
    
    print(f"[SUCCESS] Configurazione aggiornata in {config_path}")
    print(f"[INFO] NLB DNS: {nlb_dns}")
    print(f"[INFO] NLB Port: {nlb_port}")

# pulizia delle risorse create relative al NLB
def cleanup_nlb_resources():

    print("\n[SECTION] Pulizia Risorse NLB")
    print("-" * 50)
    
    # inizializzazione del client ELBv2 bestpratics per deleting
    elbv2_client = boto3.client('elbv2', region_name=REGION)
    
    try:
        # eliminazione del Load Balancer
        try:
            nlbs = elbv2_client.describe_load_balancers(Names=[NLB_NAME])
            if nlbs['LoadBalancers']:
                nlb_arn = nlbs['LoadBalancers'][0]['LoadBalancerArn']
                elbv2_client.delete_load_balancer(LoadBalancerArn=nlb_arn)
                print(f"[INFO] Network Load Balancer '{NLB_NAME}' eliminato")
                
                # attesa che l'eliminazione del NLB sia completata
                print("[INFO] Attesa eliminazione del NLB...")
                waiter = elbv2_client.get_waiter('load_balancers_deleted')
                waiter.wait(LoadBalancerArns=[nlb_arn])
                print("[SUCCESS] Network Load Balancer eliminato completamente")
        except ClientError as e:
            if "LoadBalancerNotFound" in str(e):
                print(f"[INFO] Network Load Balancer '{NLB_NAME}' non trovato")
            else:
                raise
        
        # eliminazione del Target Group
        try:
            target_groups = elbv2_client.describe_target_groups(Names=[TARGET_GROUP_NAME])
            if target_groups['TargetGroups']:
                tg_arn = target_groups['TargetGroups'][0]['TargetGroupArn']
                elbv2_client.delete_target_group(TargetGroupArn=tg_arn)
                print(f"[INFO] Target Group '{TARGET_GROUP_NAME}' eliminato")
        except ClientError as e:
            if "TargetGroupNotFound" in str(e):
                print(f"[INFO] Target Group '{TARGET_GROUP_NAME}' non trovato")
            else:
                raise
        
        # rimozione delle informazioni del NLB dal deploy_config.json
        config_path = os.path.join(os.path.dirname(__file__), 'deploy_config.json')
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            # rimozione delle chiavi relative al NLB
            config.pop('nlb_dns', None)
            config.pop('nlb_port', None)
            config.pop('nlb_enabled', None)
            
            # salvataggio della configurazione pulita
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=4)
            
            print(f"[INFO] Configurazione NLB rimossa da {config_path}")
        
        print("[SUCCESS] Pulizia risorse NLB completata")
        
    except Exception as e:
        print(f"[ERROR] Durante la pulizia delle risorse NLB: {e}")
        raise

def main():

    # controllo se è stata richiesta la pulizia delle risorse
    if "--clean" in os.sys.argv:
        cleanup_nlb_resources()
        return
    
    try:
        # lettura della configurazione di deploy esistente
        deploy_config = read_deploy_config()
        
        # inizializzazione dei client AWS
        ec2_client = boto3.client('ec2', region_name=REGION)
        elbv2_client = boto3.client('elbv2', region_name=REGION)
        
        # STEP 1: recupero delle informazioni di rete
        vpc_id, subnet_ids = get_default_vpc_and_subnets(ec2_client)
        
        # STEP 2: identificazione dell'istanza server
        server_instance_id = get_server_instance_id(ec2_client)
        
        # STEP 3: creazione del target group
        target_group_arn = create_target_group(elbv2_client, vpc_id)
        
        # STEP 4: creazione del Network Load Balancer
        nlb_arn, nlb_dns = create_nlb(elbv2_client, subnet_ids)
        
        # STEP 5: configurazione del listener
        listener_arn = create_listener(elbv2_client, nlb_arn, target_group_arn)
        
        # STEP 6: registrazione dell'istanza nel target group
        register_target(elbv2_client, target_group_arn, server_instance_id)
        
        # STEP 7: aggiornamento della configurazione di deploy
        update_deploy_config(nlb_dns, NLB_PORT)
        
        # riepilogo finale del setup completato
        print("\n[SUCCESS] Setup Network Load Balancer completato!")
        print("=" * 60)
        print(f"[INFO] NLB DNS: {nlb_dns}")
        print(f"[INFO] NLB Port: {NLB_PORT}")
        print("[INFO] Il client ora può connettersi tramite il Network Load Balancer")
        print("[INFO] Esegui 'python update_java_config_on_ec2.py' per aggiornare la configurazione Java e usare NLB")
        print("=" * 60)
        
    except Exception as e:
        print(f"[ERROR] Durante il setup del Network Load Balancer: {e}")
        raise

if __name__ == "__main__":
    main()