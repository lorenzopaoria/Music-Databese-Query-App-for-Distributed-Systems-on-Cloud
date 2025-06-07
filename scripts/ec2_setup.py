"""
================================================================================
Script Boto3 per la Creazione di Istanze EC2 (Server e Client) v2
Descrizione: Questo script Python utilizza la libreria Boto3 per creare
un'infrastruttura di base su AWS, composta da:
1. Un gruppo di sicurezza (firewall virtuale) con regole specifiche.
2. Un'istanza EC2 che fungerà da server.
3. Due istanze EC2 che fungeranno da client.
================================================================================
"""
import boto3
import time
import urllib.request
import json

# --- 1. Impostazioni Iniziali ---
AWS_REGION = "us-east-1"  # Puoi cambiare questa regione (es. "eu-central-1")
INSTANCE_TYPE = "t2.micro" # Tipo di istanza (t2.micro è nel piano gratuito)
KEY_PAIR_NAME = "" # <-- INSERISCI QUI IL NOME DELLA TUA KEY PAIR AWS!

# Controlla se è stato inserito un nome per la Key Pair
if not KEY_PAIR_NAME:
    print("ATTENZIONE: La variabile 'KEY_PAIR_NAME' è vuota.")
    print("Non potrai connetterti alle istanze via SSH senza una chiave.")
    print("Per favore, modifica lo script e inserisci il nome della tua Key Pair creata su AWS.")
    # exit()

print(f"Avvio dello script di creazione infrastruttura in regione {AWS_REGION}...")

# --- Funzione per ottenere l'IP pubblico del computer attuale ---
def get_my_public_ip():
    """Recupera l'IP pubblico usando un servizio esterno."""
    try:
        ip = urllib.request.urlopen('https://checkip.amazonaws.com').read().decode('utf-8').strip()
        print(f"Trovato IP pubblico del computer locale: {ip}")
        return f"{ip}/32" # Formato CIDR per un singolo IP
    except Exception as e:
        print(f"ATTENZIONE: Impossibile recuperare l'IP pubblico locale: {e}")
        print("La regola SSH permetterà l'accesso da qualsiasi IP (0.0.0.0/0).")
        return "0.0.0.0/0"

my_ip_cidr = get_my_public_ip()

ec2_client = boto3.client('ec2', region_name=AWS_REGION)
ec2_resource = boto3.resource('ec2', region_name=AWS_REGION)


# --- 2. Ricerca dell'AMI più recente per Amazon Linux 2 ---
print("Ricerca dell'AMI Amazon Linux 2 più recente...")
try:
    response = ec2_client.describe_images(
        Owners=['amazon'],
        Filters=[
            {'Name': 'name', 'Values': ['amzn2-ami-hvm-*-x86_64-gp2']},
            {'Name': 'virtualization-type', 'Values': ['hvm']},
        ],
        SortBy='CreationDate',
        SortOrder='descending'
    )
    ami_id = response['Images'][0]['ImageId']
    print(f"Trovata AMI: {ami_id}")
except Exception as e:
    print(f"Errore nella ricerca dell'AMI: {e}")
    exit()


# --- 3. Creazione del Gruppo di Sicurezza ---
sg_name = 'app-server-client-sg-boto3'
print(f"Creazione/Verifica del Gruppo di Sicurezza '{sg_name}'...")
try:
    # Controlla se il gruppo di sicurezza esiste già
    response = ec2_client.describe_security_groups(
        Filters=[dict(Name='group-name', Values=[sg_name])]
    )
    if response['SecurityGroups']:
        security_group_id = response['SecurityGroups'][0]['GroupId']
        print("Il gruppo di sicurezza esiste già. Lo riutilizzo.")
    else:
        # Se non esiste, lo crea
        sg_response = ec2_client.create_security_group(
            GroupName=sg_name,
            Description='Gruppo di sicurezza per app client-server creato con Boto3',
            VpcId=ec2_client.describe_vpcs()['Vpcs'][0]['VpcId']
        )
        security_group_id = sg_response['GroupId']
        print(f"Gruppo di Sicurezza creato con ID: {security_group_id}")
        
        # Aggiunta delle regole di traffico (Ingress)
        print("Aggiunta delle nuove regole di sicurezza...")
        ec2_client.authorize_security_group_ingress(
            GroupId=security_group_id,
            IpPermissions=[
                {
                    'IpProtocol': 'tcp',
                    'FromPort': 22, # SSH
                    'ToPort': 22,
                    'IpRanges': [{'CidrIp': my_ip_cidr, 'Description': 'Accesso SSH dal mio computer'}]
                },
                {
                    'IpProtocol': 'tcp',
                    'FromPort': 80, # HTTP
                    'ToPort': 80,
                    'IpRanges': [{'CidrIp': '0.0.0.0/0', 'Description': 'Accesso HTTP da chiunque'}]
                },
                {
                    'IpProtocol': 'tcp',
                    'FromPort': 3306, # MySQL/Aurora DB
                    'ToPort': 3306,
                    'UserIdGroupPairs': [{'GroupId': security_group_id, 'Description': 'Accesso al DB dal server'}]
                },
                {
                    'IpProtocol': '-1', # Tutto il traffico
                    'FromPort': -1,
                    'ToPort': -1,
                    'UserIdGroupPairs': [{'GroupId': security_group_id, 'Description': 'Comunicazione tra tutte le istanze del gruppo'}]
                }
            ]
        )
        print("Regole di accesso aggiunte con successo.")

except ec2_client.exceptions.ClientError as e:
    print(f"Errore nella gestione del gruppo di sicurezza: {e}")
    exit()


# --- 4. Creazione delle Istanze EC2 ---
print("\nCreazione delle istanze EC2 in corso. Questa operazione richiederà qualche minuto...")

instance_params = {
    'ImageId': ami_id,
    'InstanceType': INSTANCE_TYPE,
    'SecurityGroupIds': [security_group_id]
}

if KEY_PAIR_NAME:
    instance_params['KeyName'] = KEY_PAIR_NAME

try:
    # Creazione Istanza Server
    server_instance = ec2_resource.create_instances(
        **instance_params,
        MinCount=1,
        MaxCount=1,
        TagSpecifications=[{
            'ResourceType': 'instance',
            'Tags': [{'Key': 'Name', 'Value': 'EC2-Server-Boto3'}, {'Key': 'Role', 'Value': 'Server'}]
        }]
    )[0]
    print(f"Istanza Server creata con ID: {server_instance.id}")

    # Creazione Istanze Client
    client_instances = ec2_resource.create_instances(
        **instance_params,
        MinCount=2,
        MaxCount=2,
        TagSpecifications=[{
            'ResourceType': 'instance',
            'Tags': [{'Key': 'Name', 'Value': 'EC2-Client-Boto3'}, {'Key': 'Role', 'Value': 'Client'}]
        }]
    )
    print(f"Istanze Client create con ID: {[inst.id for inst in client_instances]}")

    # --- 5. Attesa e Recupero Informazioni ---
    print("\nIn attesa che le istanze siano nello stato 'running'...")
    server_instance.wait_until_running()
    for inst in client_instances:
        inst.wait_until_running()
    
    server_instance.reload()
    for inst in client_instances:
        inst.reload()

    print("\nTutte le istanze sono attive!")
    print("-" * 40)
    print("INFORMAZIONI INFRASTRUTTURA:")
    print(f"  -> IP Pubblico Server: {server_instance.public_ip_address}")
    for i, inst in enumerate(client_instances):
        print(f"  -> IP Pubblico Client {i+1}: {inst.public_ip_address}")
    
    if KEY_PAIR_NAME:
        print(f"\nComando per connettersi (chiave e IP da sostituire se necessario):")
        print(f"ssh -i /percorso/tua/{KEY_PAIR_NAME}.pem ec2-user@<IP_PUBBLICO>")
    else:
        print("\nRicorda: non puoi connetterti via SSH perché non è stata specificata una Key Pair.")
    print("-" * 40)

except Exception as e:
    print(f"\nERRORE durante la creazione delle istanze: {e}")

