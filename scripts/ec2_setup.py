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
import botocore.exceptions
import os # Importa il modulo os per la gestione dei percorsi

# --- 1. Impostazioni Iniziali ---
AWS_REGION = "us-east-1"
INSTANCE_TYPE = "t2.micro" # t2.micro è nel piano gratuito
KEY_PAIR_NAME = "Progetto" # Assicurati che questa Key Pair esista nella regione specificata!

# Controlla se è stato inserito un nome per la Key Pair
if not KEY_PAIR_NAME:
    print("ATTENZIONE: La variabile 'KEY_PAIR_NAME' è vuota.")
    print("Non potrai connetterti alle istanze via SSH senza una chiave.")
    print("Per favore, modifica lo script e inserisci il nome della tua Key Pair creata su AWS.")
    # Puoi decidere di uscire dallo script qui se la chiave è obbligatoria
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

# --- 2. Ricerca dell'AMI più recente per Amazon Linux 2023 ---
print("Ricerca dell'AMI Amazon Linux 2023 più recente (x86_64)...")
try:
    response = ec2_client.describe_images(
        Owners=['amazon'],
        Filters=[
            # Filtro per Amazon Linux 2023 (AL2023) per architettura x86_64
            {'Name': 'name', 'Values': ['al2023-ami-*-x86_64']},
            {'Name': 'virtualization-type', 'Values': ['hvm']},
            {'Name': 'architecture', 'Values': ['x86_64']}, # Aggiunto per specificare l'architettura
        ]
    )

    images = response['Images']
    
    # ORDINA le immagini per CreationDate in ordine decrescente (la più recente prima)
    images.sort(key=lambda x: x['CreationDate'], reverse=True)
    
    if not images:
        raise Exception("Nessuna AMI Amazon Linux 2023 (x86_64) trovata con i filtri specificati.")

    ami_id = images[0]['ImageId'] # Prendi la prima (la più recente)
    print(f"Trovata AMI: {ami_id}")
except Exception as e:
    print(f"Errore nella ricerca dell'AMI: {e}")
    exit()

# --- 3. Gestione del VPC e Creazione del Gruppo di Sicurezza ---
sg_name = 'app-server-client-sg-boto3'
print(f"Creazione/Verifica del Gruppo di Sicurezza '{sg_name}'...")

try:
    # Trova il VPC ID. Cerca prima un VPC predefinito.
    vpc_id = None
    try:
        response_vpcs = ec2_client.describe_vpcs(Filters=[{'Name': 'isDefault', 'Values': ['true']}])
        if response_vpcs['Vpcs']:
            vpc_id = response_vpcs['Vpcs'][0]['VpcId']
            print(f"Trovato VPC predefinito con ID: {vpc_id}")
        else:
            # Se non c'è un VPC predefinito, cerca qualsiasi VPC esistente
            response_vpcs = ec2_client.describe_vpcs()
            if response_vpcs['Vpcs']:
                vpc_id = response_vpcs['Vpcs'][0]['VpcId']
                print(f"Trovato VPC non predefinito esistente con ID: {vpc_id}")
            else:
                print("Nessun VPC trovato nell'account. Tentativo di creare un VPC predefinito...")
                # Tenta di creare un VPC predefinito tramite Boto3
                default_vpc_response = ec2_client.create_default_vpc()
                vpc_id = default_vpc_response['Vpc']['VpcId']
                print(f"Creato nuovo VPC predefinito con ID: {vpc_id}")
                # È buona norma attendere un attimo che il VPC sia completamente disponibile
                time.sleep(10) 
    except botocore.exceptions.ClientError as e:
        if "DefaultVpcAlreadyExists" in str(e):
            print("Un VPC predefinito esiste già ma non è stato trovato dalla prima query. Riprovo a cercarlo.")
            response_vpcs = ec2_client.describe_vpcs(Filters=[{'Name': 'isDefault', 'Values': ['true']}])
            if response_vpcs['Vpcs']:
                vpc_id = response_vpcs['Vpcs'][0]['VpcId']
                print(f"Trovato VPC predefinito esistente con ID: {vpc_id}")
            else:
                print(f"Errore durante la ricerca/creazione del VPC: {e}")
                print("Per favore, verifica che esista un VPC predefinito nella regione us-east-1 o creane uno manualmente dalla console AWS.")
                exit()
        else:
            print(f"Errore durante la ricerca/creazione del VPC: {e}")
            print("Per favore, verifica che esista un VPC predefinito nella regione us-east-1 o creane uno manualmente dalla console AWS.")
            exit()
    except Exception as e:
        print(f"Errore generico durante la ricerca/creazione del VPC: {e}")
        print("Per favore, verifica che esista un VPC predefinito nella regione us-east-1 o creane uno manualmente dalla console AWS.")
        exit()

    if not vpc_id:
        print("ERRORE CRITICO: Non è stato possibile ottenere un VPC ID. Impossibile procedere.")
        exit()

    # Controlla se il gruppo di sicurezza esiste già
    response = ec2_client.describe_security_groups(
        Filters=[dict(Name='group-name', Values=[sg_name]), dict(Name='vpc-id', Values=[vpc_id])]
    )
    if response['SecurityGroups']:
        security_group_id = response['SecurityGroups'][0]['GroupId']
        print("Il gruppo di sicurezza esiste già. Lo riutilizzo.")
        # Rimuovi eventuali regole esistenti prima di aggiungerne di nuove per evitare duplicati/errori
        # (Opzionale, ma utile per ri-esecuzioni dello script)
        # try:
        #     for ip_perm in response['SecurityGroups'][0]['IpPermissions']:
        #         ec2_client.revoke_security_group_ingress(GroupId=security_group_id, IpPermissions=[ip_perm])
        #     print("Regole di ingresso esistenti rimosse.")
        # except botocore.exceptions.ClientError as e:
        #     if "InvalidPermission.NotFound" not in str(e): # Ignora errori se la regola non esiste
        #         print(f"Avviso: Impossibile rimuovere alcune regole esistenti: {e}")
    else:
        # Se non esiste, lo crea
        sg_response = ec2_client.create_security_group(
            GroupName=sg_name,
            Description='Gruppo di sicurezza per app client-server creato con Boto3',
            VpcId=vpc_id # Usa il vpc_id trovato/creato
        )
        security_group_id = sg_response['GroupId']
        print(f"Gruppo di Sicurezza creato con ID: {security_group_id}")
        
    # Aggiunta delle regole di traffico (Ingress)
    # Si tenta di aggiungere le regole solo se il SG è stato appena creato o se si vuole ri-aggiungerle
    print("Aggiunta/Aggiornamento delle regole di sicurezza...")
    try:
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
                    'UserIdGroupPairs': [{'GroupId': security_group_id, 'Description': 'Accesso al DB dallo stesso Security Group'}]
                },
                {
                    'IpProtocol': '-1', # Tutto il traffico tra istanze nello stesso SG
                    'FromPort': -1,
                    'ToPort': -1,
                    'UserIdGroupPairs': [{'GroupId': security_group_id, 'Description': 'Comunicazione completa tra tutte le istanze dello stesso Security Group'}]
                }
            ]
        )
        print("Regole di accesso aggiunte/aggiornate con successo.")
    except botocore.exceptions.ClientError as e:
        if "InvalidPermission.Duplicate" in str(e):
            print("Le regole di sicurezza esistono già. Nessuna modifica necessaria.")
        else:
            print(f"Errore nell'aggiunta delle regole di sicurezza: {e}")
            exit()

except ec2_client.exceptions.ClientError as e:
    print(f"Errore nella gestione del gruppo di sicurezza: {e}")
    exit()
except Exception as e:
    print(f"Errore inatteso nella gestione del gruppo di sicurezza: {e}")
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
    
    # Ricarica gli attributi per assicurarsi di avere gli IP pubblici e privati
    server_instance.reload()
    for inst in client_instances:
        inst.reload()

    print("\nTutte le istanze sono attive!")
    print("-" * 40)
    print("INFORMAZIONI INFRASTRUTTURA:")
    print(f"    -> ID Istanza Server: {server_instance.id}")
    print(f"    -> IP Pubblico Server: {server_instance.public_ip_address}")
    print(f"    -> IP Privato Server: {server_instance.private_ip_address}")
    for i, inst in enumerate(client_instances):
        print(f"    -> ID Istanza Client {i+1}: {inst.id}")
        print(f"    -> IP Pubblico Client {i+1}: {inst.public_ip_address}")
        print(f"    -> IP Privato Client {i+1}: {inst.private_ip_address}")
    
    if KEY_PAIR_NAME:
        print(f"\nComando per connettersi (sostituisci <IP_PUBBLICO> e assicurati il percorso corretto per la tua chiave):")
        print(f"ssh -i /path/to/{KEY_PAIR_NAME}.pem ec2-user@<IP_PUBBLICO>")
    else:
        print("\nRicorda: non puoi connetterti via SSH perché non è stata specificata una Key Pair.")
    print("-" * 40)

    # --- 6. Generazione del file di riepilogo ---
    summary_filename = "infrastructure_summary.txt"
    with open(summary_filename, "w") as f:
        f.write("=========================================\n")
        f.write("RIEPILOGO INFRASTRUTTURA AWS CREATA\n")
        f.write("=========================================\n\n")
        f.write(f"Regione AWS: {AWS_REGION}\n")
        f.write(f"Tipo di Istanza: {INSTANCE_TYPE}\n")
        f.write(f"Key Pair Usata: {KEY_PAIR_NAME if KEY_PAIR_NAME else 'Nessuna Specificata'}\n")
        f.write(f"AMI Utilizzata (Amazon Linux 2023 x86_64): {ami_id}\n\n")
        f.write(f"IP Pubblico del tuo Computer (per SSH): {my_ip_cidr}\n\n")

        f.write("--- Dettagli VPC e Security Group ---\n")
        f.write(f"ID VPC: {vpc_id}\n")
        f.write(f"ID Security Group '{sg_name}': {security_group_id}\n\n")

        f.write("--- Regole di Comunicazione (basate sul Security Group) ---\n")
        f.write(f"1. Accesso SSH (Porta 22/TCP) al SG: Consentito dal tuo IP pubblico ({my_ip_cidr}).\n")
        f.write(f"2. Accesso HTTP (Porta 80/TCP) al SG: Consentito da qualsiasi IP (0.0.0.0/0).\n")
        f.write(f"3. Accesso DB (Porta 3306/TCP) al SG: Consentito SOLO dalle istanze all'interno di questo stesso Security Group.\n")
        f.write(f"4. Comunicazione Completa (Tutte le Porte/Protocolli) all'interno del SG: Consentita tra tutte le istanze all'interno di questo stesso Security Group.\n\n")
        f.write("Ciò significa che:\n")
        f.write(" - Le istanze Server e Client possono comunicare tra loro su tutte le porte.\n")
        f.write(" - Tu puoi accedere via SSH a tutte le istanze.\n")
        f.write(" - Chiunque può accedere via HTTP alle istanze (se un web server è in ascolto).\n")
        f.write(" - Solo le istanze nel gruppo possono accedere ai servizi sulla porta 3306 (ad esempio un DB sul server).\n\n")

        f.write("--- Dettagli Istanze EC2 ---\n")
        f.write(f"Server (EC2-Server-Boto3):\n")
        f.write(f"  ID: {server_instance.id}\n")
        f.write(f"  IP Pubblico: {server_instance.public_ip_address}\n")
        f.write(f"  IP Privato: {server_instance.private_ip_address}\n\n")

        for i, inst in enumerate(client_instances):
            f.write(f"Client {i+1} (EC2-Client-Boto3):\n")
            f.write(f"  ID: {inst.id}\n")
            f.write(f"  IP Pubblico: {inst.public_ip_address}\n")
            f.write(f"  IP Privato: {inst.private_ip_address}\n\n")
        
        f.write("=========================================\n")
        f.write("FINE RIEPILOGO\n")
        f.write("=========================================\n")

    print(f"\nRiepilogo dell'infrastruttura salvato in: {os.path.abspath(summary_filename)}")

except Exception as e:
    print(f"\nERRORE durante la creazione delle istanze: {e}")
    exit()
