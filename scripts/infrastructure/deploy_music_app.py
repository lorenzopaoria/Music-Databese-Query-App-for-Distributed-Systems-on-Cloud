import boto3
import time
import os
import psycopg2
import json
from botocore.exceptions import ClientError

# --- Configurazione AWS ---
REGION = 'us-east-1'
KEY_PAIR_NAME = 'my-ec2-key'
AMI_ID = 'ami-09e6f87a47903347c' # Ensure this AMI ID is valid for your region and architecture (e.g., Amazon Linux 2)
INSTANCE_TYPE = 't2.micro'
NUM_CLIENTS = 2 # Number of client instances
NUM_SERVERS = 1 # Number of server instances (can be scaled behind ALB)

# --- Configurazione Database RDS (PostgreSQL) ---
DB_INSTANCE_IDENTIFIER = 'music-db-app-rds'
DB_ENGINE = 'postgres'
DB_ENGINE_VERSION = '17.4' # Assicurati che questa versione sia supportata da RDS nella tua regione
DB_INSTANCE_CLASS = 'db.t3.micro' # Tipo di istanza RDS
DB_ALLOCATED_STORAGE = 20 # GB
DB_MASTER_USERNAME = 'dbadmin' # Aggiornato con il nome utente non riservato
DB_MASTER_PASSWORD = '12345678' # !!! CAMBIA QUESTA PASSWORD CON UNA ROBUSTA E UNICA !!!
DB_NAME = 'musicdb' # Nome del database all'interno di PostgreSQL


# --- SQL per Schema (Corretto per PostgreSQL con virgolette doppie e tabelle appropriate) ---
SCHEMA_SQL_CONTENT = """
-- Tabelle principali senza dipendenze immediate o che sono referenziate per prime
CREATE TABLE IF NOT EXISTS "Tipo_Utente" (
    "tipo" VARCHAR(50) PRIMARY KEY -- Assumendo 'premium'/'free' come chiave primaria stringa
);

CREATE TABLE IF NOT EXISTS utente (
    "email" VARCHAR(255) PRIMARY KEY,
    "nome" VARCHAR(255) NOT NULL,
    "cognome" VARCHAR(255) NOT NULL,
    "passw" VARCHAR(255) NOT NULL,
    "tipo" VARCHAR(50),
    "num_telefono" VARCHAR(20),
    "cf" VARCHAR(16) UNIQUE,
    FOREIGN KEY ("tipo") REFERENCES "Tipo_Utente"("tipo") ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS Artista ( -- Notare la maiuscola, manterrò per consistenza con i dati forniti
    "nomeArtista" VARCHAR(255) PRIMARY KEY
);

-- Correzione: La tabella Album che usa nomeArtista e titolo come PK
CREATE TABLE IF NOT EXISTS Album ( -- Notare la maiuscola, come nei tuoi INSERT
    "nomeArtista" VARCHAR(255),
    "titolo" VARCHAR(255),
    "data_pubblicazione" DATE,
    "num_tracce" INT,
    PRIMARY KEY ("nomeArtista", "titolo"), -- Chiave primaria composta
    FOREIGN KEY ("nomeArtista") REFERENCES Artista("nomeArtista") ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS contenuto (
    "idContenuto" SERIAL PRIMARY KEY,
    "nome" VARCHAR(255) NOT NULL,
    "duarata" INT, -- Assumo 'duarata' sia un refuso per 'durata'
    "riproduzione" INT,
    "tipo" INT -- Assumo che questo si riferisca a Tipo_Contenuto, ma non è una FK esplicita nei dati forniti
);

CREATE TABLE IF NOT EXISTS "Crea_Contenuto" (
    "idContenuto" INT,
    "nomeArtista" VARCHAR(255),
    PRIMARY KEY ("idContenuto", "nomeArtista"),
    FOREIGN KEY ("idContenuto") REFERENCES contenuto("idContenuto") ON DELETE CASCADE,
    FOREIGN KEY ("nomeArtista") REFERENCES Artista("nomeArtista") ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS "Tipo_Contenuto" (
    "idTipoContenuto" SERIAL PRIMARY KEY,
    "tipo" VARCHAR(50) NOT NULL
);

CREATE TABLE IF NOT EXISTS Genere (
    "idGenere" SERIAL PRIMARY KEY,
    "genere" VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS "Preferenza_Genere" (
    "email" VARCHAR(255),
    "idGenere" INT,
    PRIMARY KEY ("email", "idGenere"),
    FOREIGN KEY ("email") REFERENCES utente("email") ON DELETE CASCADE,
    FOREIGN KEY ("idGenere") REFERENCES Genere("idGenere") ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS "playlist_utente" (
    "email" VARCHAR(255),
    "nomePlaylist" VARCHAR(255),
    "num_tracce_P" INT,
    PRIMARY KEY ("email", "nomePlaylist"),
    FOREIGN KEY ("email") REFERENCES utente("email") ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS Abbonamento (
    "idAbbonamento" SERIAL PRIMARY KEY,
    "tipo" VARCHAR(50),
    "email" VARCHAR(255),
    FOREIGN KEY ("email") REFERENCES utente("email") ON DELETE CASCADE,
    FOREIGN KEY ("tipo") REFERENCES "Tipo_Utente"("tipo") ON DELETE SET NULL -- SET NULL perché "tipo" può non esistere per l'FK
);

CREATE TABLE IF NOT EXISTS "contenuti_playlist" (
    "idContenuto" INT,
    "nomePlaylist" VARCHAR(255),
    "email" VARCHAR(255),
    PRIMARY KEY ("idContenuto", "nomePlaylist", "email"),
    FOREIGN KEY ("idContenuto") REFERENCES contenuto("idContenuto") ON DELETE CASCADE,
    FOREIGN KEY ("email", "nomePlaylist") REFERENCES "playlist_utente"("email", "nomePlaylist") ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS "Metodo_Di_Pagamento" (
    "idMet_Pag" SERIAL PRIMARY KEY,
    "CVV" INT,
    "num_carta" BIGINT UNIQUE,
    "data_scadenza" DATE,
    "email" VARCHAR(255) UNIQUE,
    FOREIGN KEY ("email") REFERENCES utente("email") ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS pagamento (
    "idAbbonamento" INT,
    "data" DATE,
    "email" VARCHAR(255),
    PRIMARY KEY ("idAbbonamento", "email", "data"), -- Aggiunto 'data' per unicità se un utente paga più abbonamenti nel tempo
    FOREIGN KEY ("idAbbonamento") REFERENCES Abbonamento("idAbbonamento") ON DELETE CASCADE,
    FOREIGN KEY ("email") REFERENCES utente("email") ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS "Riproduzione_Contenuto" (
    "idContenuto" INT,
    "email" VARCHAR(255),
    "data" DATE,
    PRIMARY KEY ("idContenuto", "email", "data"),
    FOREIGN KEY ("idContenuto") REFERENCES contenuto("idContenuto") ON DELETE CASCADE,
    FOREIGN KEY ("email") REFERENCES utente("email") ON DELETE CASCADE
);
"""

DATI_SQL_CONTENT = """
-- Nota: L'ordine degli INSERT è cruciale. Le tabelle referenziate devono essere popolate per prime.

INSERT INTO "Tipo_Utente"("tipo")
VALUES
('premium'),
('free');

INSERT INTO utente("email", "nome", "cognome", "passw", "tipo", "num_telefono", "cf")
VALUES
('margheritaursino@gmail.com', 'margherita', 'ursino', 'marghe02', 'free', '3398423455', 'MRGURSN015H865R'),
('benedettostraquadanio@gmail.com', 'benedetto', 'straquadanio', 'bene03', 'premium', '3397534691', 'BNDT02S1412H534T'),
('mariorossi@gmail.com', 'mario', 'rossi', 'rossi04', 'free', '3317212117', 'MRRSSQ86SH152S'),
('annapistorio@gmail.com', 'anna', 'pistorio', 'anna04', 'premium', '3324621589', 'NPSTRQ99S54H563R'),
('robertarusso@gmail.com', 'roberta', 'russo', 'russo07', 'free', '3341256355', 'RBRTRS01F34H154S'),
('federicafirrito@gmail.com', 'federica', 'firrito', 'fede88', 'premium', '3362145711', 'FDRCFR02S10H163S');

INSERT INTO contenuto("nome", "duarata", "riproduzione", "tipo")
VALUES
('bello', 215, 0, 0),
('podcast tranquillo', 1024, 0, 1),
('another day', 305, 0, 0),
('francesco totti', 252, 0, 0),
('la storia dei DBS', 2052, 0, 1),
('katy', 310, 0, 0),
('rossana', 213, 0, 0),
('tonto', 330, 0, 0),
('muschio', 2215, 0, 1),
('risica', 206, 0, 0);

INSERT INTO Artista("nomeArtista")
VALUES
('joji'),
('baffo'),
('another love'),
('bello figo gu'),
('alaimo'),
('perry'),
('toto'),
('tha supreme'),
('selvaggio'),
('non rosica');

INSERT INTO "Crea_Contenuto"("idContenuto", "nomeArtista")
VALUES
(1,'joji'),
(2,'baffo'),
(3,'another love'),
(4,'bello figo gu'),
(5,'alaimo'),
(6,'perry'),
(7,'toto'),
(8,'tha supreme'),
(9,'selvaggio'),
(10,'non rosica');

INSERT INTO "Tipo_Contenuto"("idTipoContenuto", "tipo")
VALUES
(1,'brano'),
(2,'podcast'),
(3,'brano'),
(4,'brano'),
(5,'podcast'),
(6,'brano'),
(7,'brano'),
(8,'brano'),
(9,'podcast'),
(10,'brano');

INSERT INTO Genere("idGenere", "genere")
VALUES
(1,'classica'),
(2,'rock'),
(3,'trap'),
(4,'rap'),
(5,'disco'),
(6,'dance'),
(7,'punk'),
(8,'indie'),
(9,'folk'),
(10,'folklore');

INSERT INTO "Preferenza_Genere"("email", "idGenere")
VALUES
('margheritaursino@gmail.com', 1),
('benedettostraquadanio@gmail.com', 1),
('mariorossi@gmail.com', 3),
('annapistorio@gmail.com', 2),
('robertarusso@gmail.com', 7),
('federicafirrito@gmail.com', 5);

INSERT INTO "playlist_utente"("email", "nomePlaylist", "num_tracce_P")
VALUES
('benedettostraquadanio@gmail.com', 'tempo libero', 5),
('annapistorio@gmail.com', 'passatempo', 3),
('federicafirrito@gmail.com', 'macchina', 5),
('benedettostraquadanio@gmail.com', 'sonno', 8),
('annapistorio@gmail.com', 'studio', 7),
('federicafirrito@gmail.com', 'lavoro', 5),
('benedettostraquadanio@gmail.com', 'classica', 8),
('annapistorio@gmail.com', 'amici', 2),
('federicafirrito@gmail.com', 'giocare', 8),
('annapistorio@gmail.com', 'lettura', 6),
('federicafirrito@gmail.com', 'relazionefinita', 9);

INSERT INTO Abbonamento("idAbbonamento", "tipo", "email")
VALUES
(1,'premium','benedettostraquadanio@gmail.com'),
(2,'premium','federicafirrito@gmail.com'),
(3,'premium','annapistorio@gmail.com');

INSERT INTO Album("nomeArtista", "titolo","data_pubblicazione","num_tracce")
VALUES
('alaimo','DBS', '2006/11/15','15'),
('another love','love','2015/05/22','7'),
('baffo','baffissimo','2001/04/12','15'),
('bello figo gu','erroma','2009/11/15','17'),
('joji','depressione','2008/02/07','4'),
('non rosica','ride bene','2007/01/11','10'),
('perry','horse','2019/12/01','21'),
('perry','dark','2015/05/12','6'),
('toto','pinuccio','1999/06/07','5'),
('tha supreme','3s72r0','2020/10/10','17'),
('joji','nulla','1995/12/12','12'),
('non rosica','chi ride ultimo','2003/06/12','23'),
('joji','per niente','2015/05/17','7'),
('perry','consolation','2009/05/05','6'),
('baffo','pelle','2000/02/02','6'),
('another love','distorsione','2022/12/22','7');

INSERT INTO "contenuti_playlist"("idContenuto", "nomePlaylist", "email")
VALUES
(1, 'tempo libero','benedettostraquadanio@gmail.com'),
(1, 'passatempo','annapistorio@gmail.com'),
(3, 'macchina', 'federicafirrito@gmail.com'),
(6, 'sonno','benedettostraquadanio@gmail.com'),
(9, 'studio', 'annapistorio@gmail.com'),
(7, 'lavoro','federicafirrito@gmail.com'),
(1, 'classica', 'benedettostraquadanio@gmail.com'),
(9, 'amici','annapistorio@gmail.com'),
(8, 'giocare', 'federicafirrito@gmail.com'),
(10, 'lettura', 'annapistorio@gmail.com'),
(6, 'relazionefinita', 'federicafirrito@gmail.com'),
(7, 'tempo libero','benedettostraquadanio@gmail.com'),
(6, 'tempo libero','benedettostraquadanio@gmail.com'),
(4, 'tempo libero','benedettostraquadanio@gmail.com'),
(3, 'tempo libero','benedettostraquadanio@gmail.com'),
(6, 'passatempo','annapistorio@gmail.com'),
(7, 'passatempo','annapistorio@gmail.com'),
(8, 'macchina', 'federicafirrito@gmail.com'),
(1, 'macchina', 'federicafirrito@gmail.com'),
(4, 'macchina', 'federicafirrito@gmail.com'),
(7, 'macchina', 'federicafirrito@gmail.com'),
(7, 'sonno','benedettostraquadanio@gmail.com'),
(2, 'sonno','benedettostraquadanio@gmail.com'),
(1, 'sonno','benedettostraquadanio@gmail.com'),
(5, 'sonno','benedettostraquadanio@gmail.com'),
(9, 'sonno','benedettostraquadanio@gmail.com'),
(10, 'sonno','benedettostraquadanio@gmail.com'),
(3, 'sonno','benedettostraquadanio@gmail.com'),
(10, 'studio', 'annapistorio@gmail.com'),
(6, 'studio', 'annapistorio@gmail.com'),
(3, 'studio', 'annapistorio@gmail.com'),
(1, 'studio', 'annapistorio@gmail.com'),
(2, 'studio', 'annapistorio@gmail.com'),
(4, 'studio', 'annapistorio@gmail.com'),
(1, 'lavoro','federicafirrito@gmail.com'),
(4, 'lavoro','federicafirrito@gmail.com'),
(8, 'lavoro','federicafirrito@gmail.com'),
(10, 'lavoro','federicafirrito@gmail.com'),
(3, 'classica', 'benedettostraquadanio@gmail.com'),
(8, 'classica', 'benedettostraquadanio@gmail.com'),
(9, 'classica', 'benedettostraquadanio@gmail.com'),
(7, 'classica', 'benedettostraquadanio@gmail.com'),
(4, 'classica', 'benedettostraquadanio@gmail.com'),
(10, 'classica', 'benedettostraquadanio@gmail.com'),
(6, 'classica', 'benedettostraquadanio@gmail.com'),
(10, 'amici','annapistorio@gmail.com'),
(1, 'giocare', 'federicafirrito@gmail.com'),
(6, 'giocare', 'federicafirrito@gmail.com'),
(5, 'giocare', 'federicafirrito@gmail.com'),
(4, 'giocare', 'federicafirrito@gmail.com'),
(9, 'giocare', 'federicafirrito@gmail.com'),
(10, 'giocare', 'federicafirrito@gmail.com'),
(7, 'giocare', 'federicafirrito@gmail.com'),
(1, 'lettura', 'annapistorio@gmail.com'),
(2, 'lettura', 'annapistorio@gmail.com'),
(4, 'lettura', 'annapistorio@gmail.com'),
(8, 'lettura', 'annapistorio@gmail.com'),
(9, 'lettura', 'annapistorio@gmail.com'),
(4, 'relazionefinita', 'federicafirrito@gmail.com'),
(7, 'relazionefinita', 'federicafirrito@gmail.com'),
(8, 'relazionefinita', 'federicafirrito@gmail.com'),
(9, 'relazionefinita', 'federicafirrito@gmail.com'),
(3, 'relazionefinita', 'federicafirrito@gmail.com'),
(2, 'relazionefinita', 'federicafirrito@gmail.com'),
(1, 'relazionefinita', 'federicafirrito@gmail.com'),
(10, 'relazionefinita', 'federicafirrito@gmail.com');

INSERT INTO "Metodo_Di_Pagamento"("idMet_Pag", "CVV", "num_carta", "data_scadenza", "email")
VALUES
(1,123,123145874125,'2024/12/05','annapistorio@gmail.com'),
(2,456,156423451539,'2023/11/11','benedettostraquadanio@gmail.com'),
(3,789,752315249854,'2026/05/15','federicafirrito@gmail.com');

INSERT INTO pagamento("idAbbonamento", "data", "email")
VALUES
(1,'2023/02/15','benedettostraquadanio@gmail.com'),
(2,'2023/02/02','annapistorio@gmail.com'),
(3,'2023/02/11','federicafirrito@gmail.com');

INSERT INTO "Riproduzione_Contenuto"("idContenuto", "email", "data")
VALUES
(1,'benedettostraquadanio@gmail.com','2023/02/22'),
(4,'annapistorio@gmail.com','2023/02/04'),
(1,'federicafirrito@gmail.com','2023/02/20'),
(1,'mariorossi@gmail.com','2023/02/06'),
(5,'benedettostraquadanio@gmail.com','2023/02/22');
"""

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

def get_public_and_private_subnets(ec2_client, vpc_id):
    print(f"Ricerca subnet pubbliche e private nel VPC: {vpc_id}...")
    subnets_response = ec2_client.describe_subnets(Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}])
    all_subnets = subnets_response['Subnets']

    public_subnets = []
    private_subnets = []

    # Get Internet Gateway for the VPC
    igw_response = ec2_client.describe_internet_gateways(Filters=[{'Name': 'attachment.vpc-id', 'Values': [vpc_id]}])
    internet_gateway_ids = [igw['InternetGatewayId'] for igw in igw_response['InternetGateways']]

    for subnet in all_subnets:
        subnet_id = subnet['SubnetId']
        # Check if subnet has a route to an Internet Gateway
        route_tables_response = ec2_client.describe_route_tables(
            Filters=[
                {'Name': 'association.subnet-id', 'Values': [subnet_id]}
            ]
        )
        # If no explicit association, it's implicitly associated with the main route table
        if not route_tables_response['RouteTables']:
            route_tables_response = ec2_client.describe_route_tables(
                Filters=[
                    {'Name': 'vpc-id', 'Values': [vpc_id]},
                    {'Name': 'association.main', 'Values': ['true']}
                ]
            )

        is_public = False
        for rt in route_tables_response['RouteTables']:
            for route in rt['Routes']:
                if route.get('GatewayId') in internet_gateway_ids and route.get('DestinationCidrBlock') == '0.0.0.0/0':
                    is_public = True
                    break
            if is_public:
                break
        
        if is_public:
            public_subnets.append(subnet_id)
        else:
            private_subnets.append(subnet_id)

    if not public_subnets:
        raise Exception(f"Nessuna subnet pubblica trovata nel VPC {vpc_id}. Assicurati che le tue subnet abbiano una route all'Internet Gateway.")
    if not private_subnets:
        print(f"AVVISO: Nessuna subnet privata trovata nel VPC {vpc_id}. Le istanze private saranno lanciate in subnet pubbliche. Questo non è raccomandato per la produzione.")
        # Fallback to public subnets if no private ones are found, with a warning
        private_subnets = public_subnets 

    print(f"Subnet Pubbliche: {public_subnets}")
    print(f"Subnet Private: {private_subnets}")
    return public_subnets, private_subnets


def create_security_groups(ec2_client, vpc_id):
    print("Verifica o creazione di Security Groups...")

    # Security Group for RDS (accessible from private subnets where servers are)
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

    # Security Group for Bastion Host (SSH from anywhere)
    try:
        bastion_sg_response = ec2_client.create_security_group(
            GroupName='MusicAppBastionSecurityGroup',
            Description='Allow SSH access to Bastion Host from anywhere',
            VpcId=vpc_id
        )
        bastion_security_group_id = bastion_sg_response['GroupId']
        print(f"Security Group Bastion creato: {bastion_security_group_id}")
    except ClientError as e:
        if 'InvalidGroup.Duplicate' in str(e):
            bastion_security_group_id = ec2_client.describe_security_groups(
                GroupNames=['MusicAppBastionSecurityGroup'], Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}]
            )['SecurityGroups'][0]['GroupId']
            print(f"Security Group Bastion esistente: {bastion_security_group_id}")
        else:
            raise

    # Security Group for Server EC2 instances (SSH from Bastion, App from ALB SG)
    try:
        server_sg_response = ec2_client.create_security_group(
            GroupName='MusicAppServerSecurityGroup',
            Description='Allow SSH from Bastion, App traffic from ALB',
            VpcId=vpc_id
        )
        server_security_group_id = server_sg_response['GroupId']
        print(f"Security Group Server creato: {server_security_group_id}")
    except ClientError as e:
        if 'InvalidGroup.Duplicate' in str(e):
            server_security_group_id = ec2_client.describe_security_groups(
                GroupNames=['MusicAppServerSecurityGroup'], Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}]
            )['SecurityGroups'][0]['GroupId']
            print(f"Security Group Server esistente: {server_security_group_id}")
        else:
            raise

    # Security Group for Client EC2 instances (SSH from Bastion)
    try:
        client_sg_response = ec2_client.create_security_group(
            GroupName='MusicAppClientSecurityGroup',
            Description='Allow SSH from Bastion',
            VpcId=vpc_id
        )
        client_security_group_id = client_sg_response['GroupId']
        print(f"Security Group Client creato: {client_security_group_id}")
    except ClientError as e:
        if 'InvalidGroup.Duplicate' in str(e):
            client_security_group_id = ec2_client.describe_security_groups(
                GroupNames=['MusicAppClientSecurityGroup'], Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}]
            )['SecurityGroups'][0]['GroupId']
            print(f"Security Group Client esistente: {client_security_group_id}")
        else:
            raise

    # Security Group for ALB (HTTP/S from anywhere, forward to Server SG)
    try:
        alb_sg_response = ec2_client.create_security_group(
            GroupName='MusicAppALBSecurityGroup',
            Description='Allow HTTP/S traffic to ALB',
            VpcId=vpc_id
        )
        alb_security_group_id = alb_sg_response['GroupId']
        print(f"Security Group ALB creato: {alb_security_group_id}")
    except ClientError as e:
        if 'InvalidGroup.Duplicate' in str(e):
            alb_security_group_id = ec2_client.describe_security_groups(
                GroupNames=['MusicAppALBSecurityGroup'], Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}]
            )['SecurityGroups'][0]['GroupId']
            print(f"Security Group ALB esistente: {alb_security_group_id}")
        else:
            raise

    # Authorize ingress rules
    # RDS SG: from Server SG and local script (0.0.0.0/0 for setup, should be restricted later)
    try:
        ec2_client.authorize_security_group_ingress(
            GroupId=rds_security_group_id,
            IpPermissions=[
                {
                    'IpProtocol': 'tcp',
                    'FromPort': 5432, # PostgreSQL port
                    'ToPort': 5432,
                    'UserIdGroupPairs': [{'GroupId': server_security_group_id}], # From Server instances
                },
                {
                    'IpProtocol': 'tcp',
                    'FromPort': 5432,
                    'ToPort': 5432,
                    'IpRanges': [{'CidrIp': '0.0.0.0/0', 'Description': 'Allow local script access for DB init (dev only)'}]
                }
            ]
        )
        print("Regole di ingresso RDS SG autorizzate.")
    except ClientError as e:
        if 'InvalidPermission.Duplicate' in str(e):
            print("Regole di ingresso RDS SG già esistenti.")
        else:
            raise
    
    # Bastion SG: SSH from anywhere
    try:
        ec2_client.authorize_security_group_ingress(
            GroupId=bastion_security_group_id,
            IpPermissions=[
                {
                    'IpProtocol': 'tcp',
                    'FromPort': 22, # SSH
                    'ToPort': 22,
                    'IpRanges': [{'CidrIp': '0.0.0.0/0'}] # Be careful with this in production! Restrict to your IP.
                }
            ]
        )
        print("Regole di ingresso Bastion SG autorizzate.")
    except ClientError as e:
        if 'InvalidPermission.Duplicate' in str(e):
            print("Regole di ingresso Bastion SG già esistenti.")
        else:
            raise

    # Server SG: SSH from Bastion SG, App from ALB SG, HTTP from ALB SG
    try:
        ec2_client.authorize_security_group_ingress(
            GroupId=server_security_group_id,
            IpPermissions=[
                {
                    'IpProtocol': 'tcp',
                    'FromPort': 22, # SSH
                    'ToPort': 22,
                    'UserIdGroupPairs': [{'GroupId': bastion_security_group_id}]
                },
                {
                    'IpProtocol': 'tcp',
                    'FromPort': 8080, # Application port
                    'ToPort': 8080,
                    'UserIdGroupPairs': [{'GroupId': alb_security_group_id}]
                }
            ]
        )
        print("Regole di ingresso Server SG autorizzate.")
    except ClientError as e:
        if 'InvalidPermission.Duplicate' in str(e):
            print("Regole di ingresso Server SG già esistenti.")
        else:
            raise

    # Client SG: SSH from Bastion SG
    try:
        ec2_client.authorize_security_group_ingress(
            GroupId=client_security_group_id,
            IpPermissions=[
                {
                    'IpProtocol': 'tcp',
                    'FromPort': 22, # SSH
                    'ToPort': 22,
                    'UserIdGroupPairs': [{'GroupId': bastion_security_group_id}]
                }
            ]
        )
        print("Regole di ingresso Client SG autorizzate.")
    except ClientError as e:
        if 'InvalidPermission.Duplicate' in str(e):
            print("Regole di ingresso Client SG già esistenti.")
        else:
            raise

    # ALB SG: HTTP from anywhere
    try:
        ec2_client.authorize_security_group_ingress(
            GroupId=alb_security_group_id,
            IpPermissions=[
                {
                    'IpProtocol': 'tcp',
                    'FromPort': 80, # HTTP
                    'ToPort': 80,
                    'IpRanges': [{'CidrIp': '0.0.0.0/0'}]
                }
            ]
        )
        print("Regole di ingresso ALB SG autorizzate.")
    except ClientError as e:
        if 'InvalidPermission.Duplicate' in str(e):
            print("Regole di ingresso ALB SG già esistenti.")
        else:
            raise

    return rds_security_group_id, bastion_security_group_id, server_security_group_id, client_security_group_id, alb_security_group_id

def create_load_balancer(elbv2_client, ec2_client, vpc_id, public_subnet_ids, server_security_group_id, alb_security_group_id):
    print("\nCreazione o verifica dell'Application Load Balancer...")
    alb_arn = None
    alb_dns_name = None

    try:
        # Check if ALB already exists
        response = elbv2_client.describe_load_balancers(Names=['MusicAppALB'])
        if response['LoadBalancers']:
            alb = response['LoadBalancers'][0]
            alb_arn = alb['LoadBalancerArn']
            alb_dns_name = alb['DNSName']
            print(f"ALB 'MusicAppALB' esistente: {alb_dns_name}")
        else:
            raise ClientError({'Error': {'Code': 'LoadBalancerNotFound'}}, 'DescribeLoadBalancers')
    except ClientError as e:
        if e.response['Error']['Code'] == 'LoadBalancerNotFound':
            print("ALB 'MusicAppALB' non trovato. Creazione in corso...")
            alb_response = elbv2_client.create_load_balancer(
                Name='MusicAppALB',
                Subnets=public_subnet_ids,
                SecurityGroups=[alb_security_group_id],
                Scheme='internet-facing',
                Type='application'
            )
            alb_arn = alb_response['LoadBalancers'][0]['LoadBalancerArn']
            print(f"ALB 'MusicAppALB' creato. Attesa che diventi 'active'...")
            waiter = elbv2_client.get_waiter('load_balancer_available')
            waiter.wait(LoadBalancerArns=[alb_arn])
            
            # Get DNS name after it's active
            alb_details = elbv2_client.describe_load_balancers(LoadBalancerArns=[alb_arn])
            alb_dns_name = alb_details['LoadBalancers'][0]['DNSName']
            print(f"ALB 'MusicAppALB' è ora 'active'. DNS: {alb_dns_name}")
        else:
            raise

    # Create or retrieve Target Group
    target_group_arn = None
    try:
        tg_response = elbv2_client.describe_target_groups(Names=['MusicAppTargetGroup'])
        if tg_response['TargetGroups']:
            target_group_arn = tg_response['TargetGroups'][0]['TargetGroupArn']
            print(f"Target Group 'MusicAppTargetGroup' esistente: {target_group_arn}")
        else:
            raise ClientError({'Error': {'Code': 'TargetGroupNotFound'}}, 'DescribeTargetGroups')
    except ClientError as e:
        if e.response['Error']['Code'] == 'TargetGroupNotFound':
            print("Target Group 'MusicAppTargetGroup' non trovato. Creazione in corso...")
            tg_response = elbv2_client.create_target_group(
                Name='MusicAppTargetGroup',
                Protocol='HTTP',
                Port=8080, # Application port on EC2 instances
                VpcId=vpc_id,
                HealthCheckProtocol='HTTP',
                HealthCheckPort='8080',
                HealthCheckPath='/', # Basic health check, adjust if your app has a specific health endpoint
                HealthCheckIntervalSeconds=30,
                HealthCheckTimeoutSeconds=5,
                HealthyThresholdCount=2,
                UnhealthyThresholdCount=2,
                Matcher={'HttpCode': '200'}
            )
            target_group_arn = tg_response['TargetGroups'][0]['TargetGroupArn']
            print(f"Target Group 'MusicAppTargetGroup' creato: {target_group_arn}")
        else:
            raise
    
    # Create or retrieve Listener for the ALB
    listener_arn = None
    try:
        listener_response = elbv2_client.describe_listeners(LoadBalancerArn=alb_arn)
        found_listener = False
        for listener in listener_response['Listeners']:
            if listener['Port'] == 80 and listener['Protocol'] == 'HTTP':
                listener_arn = listener['ListenerArn']
                print(f"Listener HTTP:80 per ALB '{alb_arn}' esistente: {listener_arn}")
                found_listener = True
                break
        if not found_listener:
            raise ClientError({'Error': {'Code': 'ListenerNotFound'}}, 'DescribeListeners')
    except ClientError as e:
        if e.response['Error']['Code'] == 'ListenerNotFound':
            print(f"Listener HTTP:80 per ALB '{alb_arn}' non trovato. Creazione in corso...")
            listener_response = elbv2_client.create_listener(
                LoadBalancerArn=alb_arn,
                Protocol='HTTP',
                Port=80,
                DefaultActions=[
                    {
                        'Type': 'forward',
                        'TargetGroupArn': target_group_arn
                    }
                ]
            )
            listener_arn = listener_response['Listeners'][0]['ListenerArn']
            print(f"Listener HTTP:80 creato per ALB '{alb_arn}': {listener_arn}")
        else:
            raise

    return alb_arn, alb_dns_name, target_group_arn

def register_instances_with_target_group(elbv2_client, target_group_arn, instance_ids):
    print(f"Registrazione istanze {instance_ids} con Target Group {target_group_arn}...")
    try:
        # Check already registered instances
        current_registrations = elbv2_client.describe_target_health(TargetGroupArn=target_group_arn)
        registered_instance_ids = [t['Target']['Id'] for t in current_registrations['TargetHealth']]

        to_register = []
        for instance_id in instance_ids:
            if instance_id not in registered_instance_ids:
                to_register.append({'Id': instance_id, 'Port': 8080})
        
        if to_register:
            elbv2_client.register_targets(
                TargetGroupArn=target_group_arn,
                Targets=to_register
            )
            print(f"Istanze {instance_ids} registrate con successo. Attesa che diventino healthy...")
            # Polling for health check (basic, can be improved)
            max_attempts = 10
            for attempt in range(max_attempts):
                time.sleep(30) # Wait for health checks
                health_status = elbv2_client.describe_target_health(TargetGroupArn=target_group_arn)
                all_healthy = True
                for target_health in health_status['TargetHealth']:
                    if target_health['Target']['Id'] in instance_ids and target_health['TargetHealth']['State'] != 'healthy':
                        all_healthy = False
                        print(f"Istanza {target_health['Target']['Id']} stato: {target_health['TargetHealth']['State']}")
                        break
                if all_healthy:
                    print("Tutte le istanze sono ora healthy nel Target Group.")
                    break
                elif attempt == max_attempts - 1:
                    print("Avviso: Non tutte le istanze sono diventate healthy nel tempo previsto.")
        else:
            print("Tutte le istanze sono già registrate con il Target Group.")
    except ClientError as e:
        print(f"Errore durante la registrazione delle istanze al Target Group: {e}")
        raise

def delete_resources(ec2_client, rds_client, elbv2_client, key_name, rds_id, rds_sg_name, bastion_sg_name, server_sg_name, client_sg_name, alb_sg_name, alb_name, tg_name):
    print("Avvio pulizia risorse AWS...")

    # Deregister instances from Target Groups and delete Target Groups/ALB
    print("Eliminazione Load Balancer e Target Groups...")
    try:
        response = elbv2_client.describe_target_groups(Names=[tg_name])
        if response['TargetGroups']:
            tg_arn = response['TargetGroups'][0]['TargetGroupArn']
            # Deregister any instances first
            target_health = elbv2_client.describe_target_health(TargetGroupArn=tg_arn)
            if target_health['TargetHealth']:
                targets_to_deregister = [{'Id': t['Target']['Id']} for t in target_health['TargetHealth']]
                elbv2_client.deregister_targets(TargetGroupArn=tg_arn, Targets=targets_to_deregister)
                print(f"Deregistrazione istanze dal Target Group '{tg_name}'.")
                time.sleep(5) # Give it a moment to process
            elbv2_client.delete_target_group(TargetGroupArn=tg_arn)
            print(f"Target Group '{tg_name}' eliminato.")
        else:
            print(f"Target Group '{tg_name}' non trovato o già eliminato.")
    except ClientError as e:
        if "TargetGroupNotFoundException" not in str(e):
            print(f"Errore durante l'eliminazione del Target Group '{tg_name}': {e}")
        else:
            print(f"Target Group '{tg_name}' non trovato o già eliminato.")

    try:
        response = elbv2_client.describe_load_balancers(Names=[alb_name])
        if response['LoadBalancers']:
            alb_arn = response['LoadBalancers'][0]['LoadBalancerArn']
            # Delete listeners first
            listeners_response = elbv2_client.describe_listeners(LoadBalancerArn=alb_arn)
            for listener in listeners_response['Listeners']:
                elbv2_client.delete_listener(ListenerArn=listener['ListenerArn'])
                print(f"Listener {listener['ListenerArn']} eliminato.")
            
            elbv2_client.delete_load_balancer(LoadBalancerArn=alb_arn)
            print(f"Load Balancer '{alb_name}' eliminato. Attesa eliminazione...")
            waiter = elbv2_client.get_waiter('load_balancer_not_exists')
            waiter.wait(LoadBalancerArns=[alb_arn])
            print(f"Load Balancer '{alb_name}' eliminato con successo.")
        else:
            print(f"Load Balancer '{alb_name}' non trovato o già eliminato.")
    except ClientError as e:
        if "LoadBalancerNotFoundException" not in str(e):
            print(f"Errore durante l'eliminazione del Load Balancer '{alb_name}': {e}")
        else:
            print(f"Load Balancer '{alb_name}' non trovato o già eliminato.")

    # Terminate EC2 instances
    print("Terminazione istanze EC2 (Bastion, Server, Client)...")
    instances_to_terminate_tags = [
        {'Name': 'tag:Name', 'Values': ['MusicAppBastion']},
        {'Name': 'tag:Name', 'Values': ['MusicAppServer']},
        {'Name': 'tag:Name', 'Values': ['MusicAppClient']}
    ]
    
    instance_ids_to_terminate = []
    for tag_filter in instances_to_terminate_tags:
        instances = ec2_client.describe_instances(Filters=[tag_filter])
        for reservation in instances['Reservations']:
            for instance in reservation['Instances']:
                if instance['State']['Name'] not in ['shutting-down', 'terminated']:
                    instance_ids_to_terminate.append(instance['InstanceId'])
    
    if instance_ids_to_terminate:
        ec2_client.terminate_instances(InstanceIds=instance_ids_to_terminate)
        print(f"Istanze EC2 terminate: {instance_ids_to_terminate}. Attesa terminazione...")
        waiter = ec2_client.get_waiter('instance_terminated')
        waiter.wait(InstanceIds=instance_ids_to_terminate)
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
    
    sg_names_to_delete = [
        alb_sg_name, # ALB SG must be deleted before its dependencies are gone
        bastion_sg_name,
        server_sg_name,
        client_sg_name,
        rds_sg_name
    ]

    for sg_name_current in sg_names_to_delete:
        try:
            sg_id_current = ec2_client.describe_security_groups(
                GroupNames=[sg_name_current], Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}]
            )['SecurityGroups'][0]['GroupId']
            
            # Revoke all ingress rules first to avoid DependencyViolation
            try:
                sg_details = ec2_client.describe_security_groups(GroupIds=[sg_id_current])['SecurityGroups'][0]
                if 'IpPermissions' in sg_details and sg_details['IpPermissions']:
                    ec2_client.revoke_security_group_ingress(
                        GroupId=sg_id_current,
                        IpPermissions=sg_details['IpPermissions']
                    )
                    print(f"Revocate regole di ingresso per SG {sg_name_current} ({sg_id_current}).")
            except ClientError as e:
                if 'InvalidPermission.NotFound' not in str(e):
                    print(f"Avviso: Impossibile revocare regole di ingresso per {sg_name_current}: {e}")

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
    ec2_client = boto3.client('ec2', region_name=REGION)
    rds_client = boto3.client('rds', region_name=REGION)
    elbv2_client = boto3.client('elbv2', region_name=REGION)

    if "--clean" in os.sys.argv:
        delete_resources(
            ec2_client, rds_client, elbv2_client, KEY_PAIR_NAME, DB_INSTANCE_IDENTIFIER, 
            'MusicAppRDSSecurityGroup', 'MusicAppBastionSecurityGroup', 
            'MusicAppServerSecurityGroup', 'MusicAppClientSecurityGroup', 
            'MusicAppALBSecurityGroup', 'MusicAppALB', 'MusicAppTargetGroup'
        )
        return

    try:
        # 1. Ottieni o crea la Key Pair
        key_pair_name_actual = get_key_pair(ec2_client, KEY_PAIR_NAME)

        # Get default VPC and subnets
        vpcs = ec2_client.describe_vpcs(Filters=[{'Name': 'isDefault', 'Values': ['true']}])
        vpc_id = vpcs['Vpcs'][0]['VpcId']
        print(f"VPC predefinito trovato: {vpc_id}")
        
        public_subnets, private_subnets = get_public_and_private_subnets(ec2_client, vpc_id)
        if not private_subnets:
            raise Exception("Impossibile procedere senza subnet private disponibili per le istanze dell'applicazione.")

        # 2. Crea Security Groups
        rds_security_group_id, bastion_security_group_id, server_security_group_id, client_security_group_id, alb_security_group_id = \
            create_security_groups(ec2_client, vpc_id)

        # 3. Deploy RDS Instance
        print(f"\nTentativo di deploy dell'istanza RDS '{DB_INSTANCE_IDENTIFIER}'...")
        rds_endpoint = None
        try:
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
                    PubliclyAccessible=True # Set to False in production for RDS. True for local script init
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
            schema_sql=SCHEMA_SQL_CONTENT,
            data_sql=DATI_SQL_CONTENT
        )

        # 5. Deploy Bastion Host
        bastion_public_ip = None
        bastion_instance_id = None
        bastion_instances_found = ec2_client.describe_instances(
            Filters=[
                {'Name': 'tag:Name', 'Values': ['MusicAppBastion']},
                {'Name': 'instance-state-name', 'Values': ['pending', 'running']}
            ]
        )['Reservations']

        if bastion_instances_found:
            bastion_instance_id = bastion_instances_found[0]['Instances'][0]['InstanceId']
            bastion_public_ip = bastion_instances_found[0]['Instances'][0].get('PublicIpAddress')
            print(f"\nIstanza MusicAppBastion esistente e running: {bastion_instance_id}. IP Pubblico: {bastion_public_ip}")
        else:
            print("\nDeploy dell'istanza EC2 'MusicAppBastion'...")
            # Bastion needs a public IP, so it must be in a public subnet
            bastion_instances = ec2_client.run_instances(
                ImageId=AMI_ID,
                InstanceType=INSTANCE_TYPE,
                MinCount=1,
                MaxCount=1,
                KeyName=key_pair_name_actual,
                NetworkInterfaces=[{
                    'DeviceIndex': 0,
                    'AssociatePublicIpAddress': True,
                    'Groups': [bastion_security_group_id],
                    'SubnetId': public_subnets[0] # Use the first public subnet
                }],
                TagSpecifications=[
                    {
                        'ResourceType': 'instance',
                        'Tags': [
                            {'Key': 'Name', 'Value': 'MusicAppBastion'},
                            {'Key': 'Application', 'Value': 'MusicApp'}
                        ]
                    },
                ]
            )
            bastion_instance_id = bastion_instances['Instances'][0]['InstanceId']
            print(f"Istanza MusicAppBastion avviata: {bastion_instance_id}. Attesa che sia 'running'...")
            waiter = ec2_client.get_waiter('instance_running')
            waiter.wait(InstanceIds=[bastion_instance_id])
            bastion_instance_details = ec2_client.describe_instances(InstanceIds=[bastion_instance_id])
            bastion_public_ip = bastion_instance_details['Reservations'][0]['Instances'][0]['PublicIpAddress']
            print(f"MusicAppBastion è running. IP Pubblico: {bastion_public_ip}")

        # 6. Deploy ALB
        alb_arn, alb_dns_name, target_group_arn = create_load_balancer(elbv2_client, ec2_client, vpc_id, public_subnets, server_security_group_id, alb_security_group_id)

        # 7. Get User Data Script (for server and client)
        with open('user_data_script.sh', 'r') as f:
            user_data_script = f.read()

        # 8. Deploy MusicAppServer EC2 instance(s)
        server_instance_ids = []
        server_private_ips = []
        server_instances_found = ec2_client.describe_instances(
            Filters=[
                {'Name': 'tag:Name', 'Values': ['MusicAppServer']},
                {'Name': 'instance-state-name', 'Values': ['pending', 'running']}
            ]
        )['Reservations']

        for reservation in server_instances_found:
            for instance in reservation['Instances']:
                server_instance_ids.append(instance['InstanceId'])
                server_private_ips.append(instance.get('PrivateIpAddress'))
        
        num_existing_servers = len(server_instance_ids)
        num_servers_to_create = NUM_SERVERS - num_existing_servers

        if num_existing_servers > 0:
            print(f"\n{num_existing_servers} istanze MusicAppServer esistenti e running: {server_instance_ids}. IP Privati: {server_private_ips}")
        
        if num_servers_to_create > 0:
            print(f"\nDeploy di {num_servers_to_create} nuove istanze EC2 'MusicAppServer' in subnet private...")
            server_instances_response = ec2_client.run_instances(
                ImageId=AMI_ID,
                InstanceType=INSTANCE_TYPE,
                MinCount=num_servers_to_create,
                MaxCount=num_servers_to_create,
                KeyName=key_pair_name_actual,
                NetworkInterfaces=[{
                    'DeviceIndex': 0,
                    'AssociatePublicIpAddress': False, # Servers are in private subnet, no public IP
                    'Groups': [server_security_group_id],
                    'SubnetId': private_subnets[0] # Use the first private subnet
                }],
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
            new_server_instance_ids = [i['InstanceId'] for i in server_instances_response['Instances']]
            server_instance_ids.extend(new_server_instance_ids) # Add new IDs to the list
            print(f"Nuove istanze MusicAppServer avviate: {new_server_instance_ids}. Attesa che siano 'running'...")
            waiter = ec2_client.get_waiter('instance_running')
            waiter.wait(InstanceIds=new_server_instance_ids)
            
            for instance_id in new_server_instance_ids:
                details = ec2_client.describe_instances(InstanceIds=[instance_id])
                server_private_ips.append(details['Reservations'][0]['Instances'][0]['PrivateIpAddress'])
            print(f"Nuovi MusicAppServers sono running. IP Privati aggiunti: {server_private_ips[num_existing_servers:]}")
        else:
            print(f"\nNumero di istanze MusicAppServer desiderate ({NUM_SERVERS}) già raggiunto o superato. Nessuna nuova istanza server avviata.")

        # Register server instances with Target Group
        register_instances_with_target_group(elbv2_client, target_group_arn, server_instance_ids)

        # 9. Deploy MusicAppClient EC2 instances
        client_instance_ids = []
        client_private_ips = []
        
        client_instances_found = ec2_client.describe_instances(
            Filters=[
                {'Name': 'tag:Name', 'Values': ['MusicAppClient']},
                {'Name': 'instance-state-name', 'Values': ['pending', 'running']}
            ]
        )['Reservations']
        
        for reservation in client_instances_found:
            for instance in reservation['Instances']:
                client_instance_ids.append(instance['InstanceId'])
                client_private_ips.append(instance.get('PrivateIpAddress'))

        num_existing_clients = len(client_instance_ids)
        num_clients_to_create = NUM_CLIENTS - num_existing_clients

        if num_existing_clients > 0:
            print(f"\n{num_existing_clients} istanze MusicAppClient esistenti e running: {client_instance_ids}. IP Privati: {client_private_ips}")
        
        if num_clients_to_create > 0:
            print(f"\nDeploy di {num_clients_to_create} nuove istanze EC2 'MusicAppClient' in subnet private...")
            client_instances_response = ec2_client.run_instances(
                ImageId=AMI_ID,
                InstanceType=INSTANCE_TYPE,
                MinCount=num_clients_to_create,
                MaxCount=num_clients_to_create,
                KeyName=key_pair_name_actual,
                NetworkInterfaces=[{
                    'DeviceIndex': 0,
                    'AssociatePublicIpAddress': False, # Clients are in private subnet, no public IP
                    'Groups': [client_security_group_id],
                    'SubnetId': private_subnets[0] # Use the first private subnet
                }],
                UserData=user_data_script,
                TagSpecifications=[
                    {
                        'ResourceType': 'instance',
                        'Tags': [
                            {'Key': 'Name', 'Value': 'MusicAppClient'},
                            {'Key': 'Application', 'Value': 'MusicApp'}
                        ]
                    },
                ]
            )
            new_client_instance_ids = [i['InstanceId'] for i in client_instances_response['Instances']]
            client_instance_ids.extend(new_client_instance_ids)
            print(f"Nuove istanze MusicAppClient avviate: {new_client_instance_ids}. Attesa che siano 'running'...")
            waiter.wait(InstanceIds=new_client_instance_ids)
            for instance_id in new_client_instance_ids:
                details = ec2_client.describe_instances(InstanceIds=[instance_id])
                client_private_ips.append(details['Reservations'][0]['Instances'][0]['PrivateIpAddress'])
            print(f"Nuovi MusicAppClients sono running. IP Privati aggiunti: {client_private_ips[num_existing_clients:]}")
        else:
            print(f"\nNumero di istanze MusicAppClient desiderate ({NUM_CLIENTS}) già raggiunto o superato. Nessuna nuova istanza client avviata.")

        print("\n--- Deploy Completato ---")
        print("Dettagli per la connessione:")
        print(f"Chiave SSH: {key_pair_name_actual}.pem")
        print(f"Endpoint RDS: {rds_endpoint}")
        print(f"Utente DB: {DB_MASTER_USERNAME}")
        print(f"Password DB: {DB_MASTER_PASSWORD}")
        print(f"Nome DB: {DB_NAME}")
        print(f"\nIP Pubblico Bastion Host: {bastion_public_ip}")
        print(f"IP Privato Server EC2 (dietro ALB): {server_private_ips}")
        print(f"IP Privati Client EC2: {client_private_ips}")
        print(f"DNS Name ALB (per Client): {alb_dns_name}")

        # Salva la configurazione in un file JSON
        config = {
            "bastion_public_ip": bastion_public_ip,
            "server_private_ips": server_private_ips, # List of private IPs
            "client_private_ips": client_private_ips, # List of private IPs
            "alb_dns_name": alb_dns_name,
            "rds_endpoint": rds_endpoint,
            "db_username": DB_MASTER_USERNAME,
            "db_password": DB_MASTER_PASSWORD,
            "db_name": DB_NAME,
            "key_pair_name": key_pair_name_actual,
            "server_application_port": 8080 # Add application port for clarity
        }
        with open("deploy_config.json", "w") as f:
            json.dump(config, f, indent=4)
        print("\nConfigurazione salvata in 'deploy_config.json'.")

        print("\n--- Prossimi Passi (Manuali o Automation Tool) ---")
        print("Aggiornare il file config di ssh per connettersi tramite Bastion Host (o usare paramiko ProxyCommand).")
        print("Eseguire update_java_config_on_ec2.py per aggiornare la configurazione Java e clonare su EC2.")

    except ClientError as e:
        print(f"Si è verificato un errore AWS: {e}")
    except Exception as e:
        print(f"Si è verificato un errore inaspettato: {e}")

if __name__ == "__main__":
    main()