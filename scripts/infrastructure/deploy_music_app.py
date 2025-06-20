import boto3
import time
import os
import psycopg2
from botocore.exceptions import ClientError

# --- Configurazione AWS ---
REGION = 'us-east-1'
KEY_PAIR_NAME = 'my-ec2-key'
AMI_ID = 'ami-09e6f87a47903347c'
INSTANCE_TYPE = 't2.micro'
NUM_CLIENTS = 2

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
            schema_sql=SCHEMA_SQL_CONTENT,
            data_sql=DATI_SQL_CONTENT
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
        
        client_instances_found = ec2_client.describe_instances(
            Filters=[
                {'Name': 'tag:Name', 'Values': ['MusicAppClient']},
                {'Name': 'instance-state-name', 'Values': ['pending', 'running']}
            ]
        )['Reservations']
        
        existing_client_ids = []
        for reservation in client_instances_found:
            for instance in reservation['Instances']:
                existing_client_ids.append(instance['InstanceId'])
                client_public_ips.append(instance.get('PublicIpAddress'))
                client_private_ips.append(instance.get('PrivateIpAddress'))

        num_existing_clients = len(existing_client_ids)
        num_clients_to_create = NUM_CLIENTS - num_existing_clients

        if num_existing_clients > 0:
            print(f"\n{num_existing_clients} istanze MusicAppClient esistenti e running: {existing_client_ids}. IP Pubblici: {client_public_ips[:num_existing_clients]}, IP Privati: {client_private_ips[:num_existing_clients]}")
        
        if num_clients_to_create > 0:
            print(f"\nDeploy di {num_clients_to_create} nuove istanze EC2 'MusicAppClient'...")
            client_instances_response = ec2_client.run_instances(
                ImageId=AMI_ID,
                InstanceType=INSTANCE_TYPE,
                MinCount=num_clients_to_create,
                MaxCount=num_clients_to_create,
                KeyName=key_pair_name_actual,
                SecurityGroupIds=[ec2_security_group_id],
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
            print(f"Nuove istanze MusicAppClient avviate: {new_client_instance_ids}. Attesa che siano 'running'...")
            waiter.wait(InstanceIds=new_client_instance_ids)
            for instance_id in new_client_instance_ids:
                details = ec2_client.describe_instances(InstanceIds=[instance_id])
                client_public_ips.append(details['Reservations'][0]['Instances'][0]['PublicIpAddress'])
                client_private_ips.append(details['Reservations'][0]['Instances'][0]['PrivateIpAddress'])
            print(f"Nuove MusicAppClients sono running. IP Pubblici aggiunti: {client_public_ips[num_existing_clients:]}, IP Privati aggiunti: {client_private_ips[num_existing_clients:]}")
        else:
            print(f"\nNumero di istanze MusicAppClient desiderate ({NUM_CLIENTS}) già raggiunto o superato. Nessuna nuova istanza client avviata.")

        print("\n--- Deploy Completato ---")
        print("Dettagli per la connessione:")
        print(f"Chiave SSH: {key_pair_name_actual}.pem")
        print(f"Endpoint RDS: {rds_endpoint}")
        print(f"Utente DB: {DB_MASTER_USERNAME}")
        print(f"Password DB: {DB_MASTER_PASSWORD}")
        print(f"Nome DB: {DB_NAME}")
        print(f"\nIP Pubblico Server EC2: {server_public_ip}")
        print(f"IP Privato Server EC2 (per client nella stessa VPC): {server_private_ip}")
        print(f"IP Pubblici Client EC2: {client_public_ips}")

        print("\n--- Prossimi Passi (Manuali o Automation Tool) ---")
        print("1. Connettiti all'istanza 'MusicAppServer' via SSH:")
        print(f"   `ssh -i {key_pair_name_actual}.pem ec2-user@{server_public_ip}`")
        print("2. Connettiti alle istanze 'MusicAppClient' via SSH:")
        for ip in client_public_ips:
            print(f"   `ssh -i {key_pair_name_actual}.pem ec2-user@{ip}`")
        print("\n3. **Aggiorna il file `Config.java`** nel repository clonato su ogni istanza EC2:")
        print("   Dovrai inserire l'endpoint del database RDS e le credenziali, e l'IP privato del server per la comunicazione interna tra EC2 se sono nella stessa VPC.")
        print(f"     Esempio per il server: `String DB_URL = \"jdbc:postgresql://{rds_endpoint}:5432/{DB_NAME}\";`")
        print(f"     Esempio per il server (per bind): `String SERVER_IP = \"0.0.0.0\";` (o l'IP privato del server per bind specifico)")
        print(f"     Esempio per il client: `String SERVER_IP = \"{server_private_ip}\";`") # Client si connette al server
        print(f"     `String DB_USERNAME = \"{DB_MASTER_USERNAME}\";`")
        print(f"     `String DB_PASSWORD = \"{DB_MASTER_PASSWORD}\";`")
        print("4. **Ricompila l'applicazione Java** dopo le modifiche (se necessario, altrimenti ignora):")
        print("   `mvn clean install` (questo è già stato fatto dallo UserData, ma potrebbe servire dopo modifiche a `Config.java`)")
        print("5. **Avvia il server Java** (sull'istanza 'MusicAppServer'):")
        print("   `java -jar /home/ec2-user/Music-Databese-Query-App-for-Distributed-Systems-on-Cloud/server/target/music-database-query-app-server.jar` (verifica il percorso esatto del JAR)")
        print("6. **Avvia i client Java** (sulle istanze 'MusicAppClient-*'):")
        print("   `java -jar /home/ec2-user/Music-Databese-Query-App-for-Distributed-Systems-on-Cloud/client/target/music-database-query-app-client.jar` (verifica il percorso esatto del JAR)")
        print("\nRicorda di pulire le risorse AWS quando hai finito per evitare costi!")
        print(f"Per pulire: python {os.path.basename(__file__)} --clean")

    except ClientError as e:
        print(f"Si è verificato un errore AWS: {e}")
    except Exception as e:
        print(f"Si è verificato un errore inaspettato: {e}")

if __name__ == "__main__":
    main()