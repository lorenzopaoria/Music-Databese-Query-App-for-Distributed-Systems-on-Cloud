import boto3
import time
import os
import psycopg2
from botocore.exceptions import ClientError

# --- Configurazione AWS ---
REGION = 'us-east-1'  # Sostituisci con la tua regione AWS preferita (es. 'eu-west-1' per Irlanda)
KEY_PAIR_NAME = 'my-ec2-key' # Sostituisci con il nome della tua chiave EC2. Se non esiste, verrà creata.
AMI_ID = 'ami-053b0a701833e7264' # AMI di Ubuntu Server 22.04 LTS (HVM), SSD Volume Type. Verifica l'AMI più recente per la tua regione!
INSTANCE_TYPE = 't2.micro' # Tipo di istanza EC2
NUM_CLIENTS = 2

# --- Configurazione Database RDS (PostgreSQL) ---
DB_INSTANCE_IDENTIFIER = 'music-db-app-rds'
DB_ENGINE = 'postgres'
DB_ENGINE_VERSION = '17.4' # Aggiornato con l'ultima versione che hai indicato
DB_INSTANCE_CLASS = 'db.t3.micro' # Tipo di istanza RDS
DB_ALLOCATED_STORAGE = 20 # GB
DB_MASTER_USERNAME = 'dbadmin' # Aggiornato con il nome utente non riservato
DB_MASTER_PASSWORD = '12345678' # !!! CAMBIA QUESTA PASSWORD CON UNA ROBUSTA E UNICA !!!
DB_NAME = 'musicdb' # Nome del database all'interno di PostgreSQL
DB_PORT = 5432 # Porta standard di PostgreSQL

# --- Repository GitHub ---
GITHUB_REPO_URL = 'https://github.com/lorenzopaoria/Music-Databese-Query-App-for-Distributed-Systems-on-Cloud.git'
REPO_ROOT_DIR = 'Music-Databese-Query-App-for-Distributed-Systems-on-Cloud' # Nome della directory dopo il clone
SERVER_PROJECT_DIR = 'mvnProject-Server'
CLIENT_PROJECT_DIR = 'mvnProject-Client'

# --- Contenuto di schema.sql (Recuperato dal repository) ---
SCHEMA_SQL_CONTENT = """
CREATE TABLE IF NOT EXISTS album (
    albumId SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    releaseDate DATE,
    genre VARCHAR(50),
    label VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS artist (
    artistId SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    country VARCHAR(100),
    birthDate DATE
);

CREATE TABLE IF NOT EXISTS song (
    songId SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    duration INT, -- Duration in seconds
    albumId INT,
    artistId INT,
    FOREIGN KEY (albumId) REFERENCES album(albumId) ON DELETE SET NULL,
    FOREIGN KEY (artistId) REFERENCES artist(artistId) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS playlist (
    playlistId SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    creationDate DATE
);

CREATE TABLE IF NOT EXISTS playlist_song (
    playlistId INT,
    songId INT,
    PRIMARY KEY (playlistId, songId),
    FOREIGN KEY (playlistId) REFERENCES playlist(playlistId) ON DELETE CASCADE,
    FOREIGN KEY (songId) REFERENCES song(songId) ON DELETE CASCADE
);

-- Inserimento di dati di esempio
INSERT INTO album (title, releaseDate, genre, label) VALUES
('The Dark Side of the Moon', '1973-03-01', 'Progressive Rock', 'Harvest'),
('Thriller', '1982-11-30', 'Pop', 'Epic'),
('Back in Black', '1980-07-25', 'Hard Rock', 'Atlantic'),
('Nevermind', '1991-09-24', 'Grunge', 'DGC');

INSERT INTO artist (name, country, birthDate) VALUES
('Pink Floyd', 'United Kingdom', NULL),
('Michael Jackson', 'USA', '1958-08-29'),
('AC/DC', 'Australia', NULL),
('Nirvana', 'USA', NULL);

INSERT INTO song (title, duration, albumId, artistId) VALUES
('Speak to Me', 180, 1, 1),
('Breathe', 163, 1, 1),
('Billie Jean', 294, 2, 2),
('Beat It', 258, 2, 2),
('Hells Bells', 309, 3, 3),
('Shoot to Thrill', 317, 3, 3),
('Smells Like Teen Spirit', 301, 4, 4),
('Come As You Are', 218, 4, 4);

INSERT INTO playlist (name, creationDate) VALUES
('My Rock Favorites', '2023-01-15'),
('80s Pop Hits', '2023-02-20');

INSERT INTO playlist_song (playlistId, songId) VALUES
(1, 1), (1, 2), (1, 5), (1, 6), (1, 7), (1, 8),
(2, 3), (2, 4);
"""

# --- Contenuto di dati.sql (Fornito dall'utente) ---
DATI_SQL_CONTENT = """
INSERT INTO utente(`email`, `nome`, `cognome`, `passw`, `tipo`, `num_telefono`, `cf`)
VALUES
('margheritaursino@gmail.com', 'margherita', 'ursino', 'marghe02', 0, '3398423455', 'MRGURSN015H865R'),
('benedettostraquadanio@gmail.com', 'benedetto', 'straquadanio', 'bene03', 1, '3397534691', 'BNDT02S1412H534T'),
('mariorossi@gmail.com', 'mario', 'rossi', 'rossi04', 0, '3317212117', 'MRRSSQ86SH152S'),
('annapistorio@gmail.com', 'anna', 'pistorio', 'anna04', 1, '3324621589', 'NPSTRQ99S54H563R'),
('robertarusso@gmail.com', 'roberta', 'russo', 'russo07', 0, '3341256355', 'RBRTRS01F34H154S'),
('federicafirrito@gmail.com', 'federica', 'firrito', 'fede88', 1, '3362145711', 'FDRCFR02S10H163S');

INSERT INTO Tipo_Utente(`tipo`)
VALUES
('premium'),
('premium'),
('premium'),
('free'),
('free'),
('free');

INSERT INTO contenuto(`nome`, `duarata`, `riproduzione`, `tipo`)
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

INSERT INTO Crea_Contenuto(`idContenuto`,`nomeArtista`)
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

INSERT INTO Tipo_Contenuto(`idTipoContenuto`,`tipo`)
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

INSERT INTO Preferenza_Genere(`email`, `idGenere`)
VALUES
('margheritaursino@gmail.com',  1),
('benedettostraquadanio@gmail.com', 1),
('mariorossi@gmail.com', 3),
('annapistorio@gmail.com', 2),
('robertarusso@gmail.com', 7),
('federicafirrito@gmail.com', 5);

INSERT INTO Genere(`idGenere`, `genere`)
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

INSERT INTO playlist(`email`, `nomePlaylist`,`num_tracce_P`)
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

INSERT INTO Artista(`nomeArtista`)
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

INSERT INTO Appartiene_Genere(`idGenere`, `idContenuto`)
VALUES
(3,1),
(1,2),
(5,3),
(6,4),
(3,5),
(9,6),
(7,9),
(2,7),
(6,8),
(9,10);

INSERT INTO Abbonamento(`idAbbonamento`, `tipo`,`email`)
VALUES
(1,'premium','benedettostraquadanio@gmail.com'),
(2,'premium','federicafirrito@gmail.com'),
(3,'premium','annapistorio@gmail.com'),
(4,'premium','benedettostraquadanio@gmail.com'),
(5,'premium','federicafirrito@gmail.com'),
(6,'premium','benedettostraquadanio@gmail.com'),
(7,'premium','federicafirrito@gmail.com'),
(8,'premium','annapistorio@gmail.com'),
(9,'premium','annapistorio@gmail.com'),
(10,'premium','federicafirrito@gmail.com');

INSERT INTO Album(`nomeArtista`, `titolo`,`data_pubblicazione`,`num_tracce`)
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

INSERT INTO contenuti_playlist(`idContenuto`, `nomePlaylist`, `email`)
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

INSERT INTO Metodo_Di_Pagamento(`idMet_Pag`, `CVV`, `num_carta`,`data_scadenza`, `email`)
VALUES
(1,123,123145874125,'2024/12/05','annapistorio@gmail.com'),
(2,456,156423451539,'2023/11/11','benedettostraquadanio@gmail.com'),
(3,789,752315249854,'2026/05/15','federicafirrito@gmail.com');

INSERT INTO pagamento(`idAbbonamento`, `data`, `email`)
VALUES
(1,'2023/02/15','benedettostraquadanio@gmail.com'),
(2,'2023/02/02','annapistorio@gmail.com'),
(3,'2023/02/11','federicafirrito@gmail.com');

INSERT INTO Riproduzione_Contenuto(`idContenuto`, `email`, `data`)
VALUES
(1,'benedettostraquadanio@gmail.com','2023/02/22'),
(4,'annapistorio@gmail.com','2023/02/04'),
(1,'federicafirrito@gmail.com','2023/02/20'),
(1,'mariorossi@gmail.com','2023/02/06'),
(5,'benedettostraquadanio@gmail.com','2023/02/22');
"""

# --- Inizializza i client Boto3 ---
ec2 = boto3.client('ec2', region_name=REGION)
rds = boto3.client('rds', region_name=REGION)

def create_ec2_key_pair(key_name):
    """Crea una nuova key pair EC2 e la salva localmente."""
    key_file_path = f"{key_name}.pem"
    if os.path.exists(key_file_path):
        print(f"La key pair '{key_name}.pem' esiste già localmente.")
        try:
            # Verifica se la key pair esiste anche in AWS
            ec2.describe_key_pairs(KeyNames=[key_name])
            print(f"La key pair '{key_name}' esiste anche in AWS.")
            return key_name
        except ClientError as e:
            if 'InvalidKeyPair.NotFound' in str(e):
                print(f"ATTENZIONE: La key pair '{key_name}' non esiste in AWS, ma il file .pem locale sì.")
                print(f"Elimina il file '{key_file_path}' localmente o scegli un nome diverso per KEY_PAIR_NAME.")
                raise e # Forzare l'utente a risolvere il conflitto
            else:
                raise e

    print(f"Creazione nuova key pair EC2: '{key_name}'...")
    try:
        key_pair = ec2.create_key_pair(KeyName=key_name)
        with open(key_file_path, 'w') as f:
            f.write(key_pair['KeyMaterial'])
        os.chmod(key_file_path, 0o400) # Imposta permessi restrittivi per la chiave
        print(f"Key pair '{key_name}.pem' creata e salvata in {key_file_path}")
        return key_name
    except ClientError as e:
        if 'KeyPairAlreadyExists' in str(e):
            print(f"La key pair '{key_name}' esiste già in AWS. Assicurati di avere il file '{key_name}.pem' localmente.")
            return key_name
        else:
            print(f"Errore durante la creazione della key pair: {e}")
            raise e

def create_security_groups():
    """Crea i Security Group per EC2 e RDS, gestendo le regole duplicate."""
    print("Creazione Security Groups...")
    
    ec2_sg_id = None
    rds_sg_id = None
    vpc_id = ec2.describe_vpcs(Filters=[{'Name': 'isDefault', 'Values': ['true']}])['Vpcs'][0]['VpcId']

    # --- Security Group per EC2 ---
    try:
        ec2_sg_id = ec2.describe_security_groups(GroupNames=['MusicAppEC2SG'])['SecurityGroups'][0]['GroupId']
        print("EC2 Security Group 'MusicAppEC2SG' esiste già. Recupero l'ID.")
    except ClientError as e:
        if 'InvalidGroup.NotFound' in str(e):
            ec2_sg_response = ec2.create_security_group(
                GroupName='MusicAppEC2SG',
                Description='Security group for Music App EC2 instances (Server and Clients)',
                VpcId=vpc_id
            )
            ec2_sg_id = ec2_sg_response['GroupId']
            print(f"Creato EC2 Security Group: {ec2_sg_id}")

            # Regole per EC2 Security Group: SSH, traffico app (es. porta 8080)
            try:
                ec2.authorize_security_group_ingress(
                    GroupId=ec2_sg_id,
                    IpPermissions=[
                        {'IpProtocol': 'tcp', 'FromPort': 22, 'ToPort': 22, 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]}, # SSH
                        {'IpProtocol': 'tcp', 'FromPort': 8080, 'ToPort': 8080, 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]}, # Porta app Java
                    ]
                )
                print("Regole ingresso aggiunte al Security Group EC2.")
            except ClientError as e_ingress:
                if 'InvalidPermission.Duplicate' in str(e_ingress):
                    print("Regola di ingresso SSH/App per EC2 già esistente. Ignoro.")
                else:
                    raise e_ingress # Rilancia altri errori

            # Regola outbound all
            try:
                ec2.authorize_security_group_egress(
                    GroupId=ec2_sg_id,
                    IpPermissions=[{'IpProtocol': '-1', 'FromPort': 0, 'ToPort': 65535, 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]}]
                )
                print("Regola uscita (all traffic) aggiunta al Security Group EC2.")
            except ClientError as e_egress:
                if 'InvalidPermission.Duplicate' in str(e_egress):
                    print("Regola di uscita per EC2 già esistente. Ignoro.")
                else:
                    raise e_egress # Rilancia altri errori
        else:
            raise e

    # --- Security Group per RDS ---
    try:
        rds_sg_id = ec2.describe_security_groups(GroupNames=['MusicAppRDSSG'])['SecurityGroups'][0]['GroupId']
        print("RDS Security Group 'MusicAppRDSSG' esiste già. Recupero l'ID.")
    except ClientError as e:
        if 'InvalidGroup.NotFound' in str(e):
            rds_sg_response = ec2.create_security_group(
                GroupName='MusicAppRDSSG',
                Description='Security group for Music App RDS database',
                VpcId=vpc_id
            )
            rds_sg_id = rds_sg_response['GroupId']
            print(f"Creato RDS Security Group: {rds_sg_id}")

            # Regola per RDS Security Group: Permetti ingresso da EC2 Security Group E DA OVUNQUE (0.0.0.0/0)
            try:
                ec2.authorize_security_group_ingress(
                    GroupId=rds_sg_id,
                    IpPermissions=[
                        # Permetti connessioni dall'EC2 Security Group
                        {'IpProtocol': 'tcp', 'FromPort': DB_PORT, 'ToPort': DB_PORT, 'UserIdGroupPairs': [{'GroupId': ec2_sg_id}]},
                        # Permetti connessioni da qualsiasi IP pubblico (0.0.0.0/0) - ATTENZIONE: SICUREZZA!
                        {'IpProtocol': 'tcp', 'FromPort': DB_PORT, 'ToPort': DB_PORT, 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]}
                    ]
                )
                print("Regole ingresso aggiunte al Security Group RDS (dal SG EC2 e da 0.0.0.0/0).")
            except ClientError as e_rds_ingress:
                if 'InvalidPermission.Duplicate' in str(e_rds_ingress):
                    print("Regola/e di ingresso per RDS già esistente. Ignoro.")
                else:
                    raise e_rds_ingress # Rilancia altri errori
        else:
            raise e
            
    return ec2_sg_id, rds_sg_id

def create_rds_instance(rds_sg_id):
    """Crea un'istanza RDS PostgreSQL."""
    print(f"Avvio creazione istanza RDS PostgreSQL: {DB_INSTANCE_IDENTIFIER}...")
    
    try:
        response = rds.create_db_instance(
            DBInstanceIdentifier=DB_INSTANCE_IDENTIFIER,
            DBName=DB_NAME,
            Engine=DB_ENGINE,
            EngineVersion=DB_ENGINE_VERSION,
            DBInstanceClass=DB_INSTANCE_CLASS,
            AllocatedStorage=DB_ALLOCATED_STORAGE,
            MasterUsername=DB_MASTER_USERNAME,
            MasterUserPassword=DB_MASTER_PASSWORD,
            VpcSecurityGroupIds=[rds_sg_id],
            Port=DB_PORT,
            PubliclyAccessible=True,
            Tags=[{'Key': 'Name', 'Value': DB_INSTANCE_IDENTIFIER}]
        )
        print(f"Richiesta creazione RDS inviata. Attendere che l'istanza sia 'available'...")

        waiter = rds.get_waiter('db_instance_available')
        waiter.wait(DBInstanceIdentifier=DB_INSTANCE_IDENTIFIER)
        print("Istanza RDS è 'available'.")

        db_instance = rds.describe_db_instances(DBInstanceIdentifier=DB_INSTANCE_IDENTIFIER)['DBInstances'][0]
        db_endpoint = db_instance['Endpoint']['Address']
        print(f"Endpoint RDS: {db_endpoint}")
        return db_endpoint

    except ClientError as e:
        if 'DBInstanceAlreadyExists' in str(e):
            print(f"L'istanza RDS '{DB_INSTANCE_IDENTIFIER}' esiste già. Recupero l'endpoint.")
            db_instance = rds.describe_db_instances(DBInstanceIdentifier=DB_INSTANCE_IDENTIFIER)['DBInstances'][0]
            if db_instance['DBInstanceStatus'] != 'available':
                print(f"L'istanza RDS è in stato '{db_instance['DBInstanceStatus']}', attendere che sia 'available'...")
                waiter = rds.get_waiter('db_instance_available')
                waiter.wait(DBInstanceIdentifier=DB_INSTANCE_IDENTIFIER)
                print("Istanza RDS è ora 'available'.")
            db_endpoint = db_instance['Endpoint']['Address']
            print(f"Endpoint RDS esistente: {db_endpoint}")
            return db_endpoint
        else:
            raise e

def initialize_database(db_endpoint):
    """Si connette al database RDS e crea lo schema e popola i dati."""
    print("Inizializzazione database RDS con schema.sql...")
    conn = None
    try:
        conn = psycopg2.connect(
            host=db_endpoint,
            database=DB_NAME,
            user=DB_MASTER_USERNAME,
            password=DB_MASTER_PASSWORD,
            port=DB_PORT
        )
        cur = conn.cursor()
        
        # Esegui lo schema
        cur.execute(SCHEMA_SQL_CONTENT)
        conn.commit()
        cur.close()
        print("Schema database creato con successo.")

        # Esegui i dati forniti
        print("Popolamento database con dati.sql...")
        cur = conn.cursor()
        sql_commands = [cmd.strip() for cmd in DATI_SQL_CONTENT.split(';') if cmd.strip()]
        for command in sql_commands:
            try:
                cur.execute(command)
                conn.commit()
            except psycopg2.Error as e:
                print(f"Errore durante l'esecuzione del comando SQL: {command[:100]}... Errore: {e}")
                conn.rollback()
                raise e

        cur.close()
        print("Dati inseriti con successo.")

    except Exception as e:
        print(f"Errore durante l'inizializzazione del database: {e}")
        print("Assicurati che l'istanza RDS sia completamente disponibile e che le credenziali siano corrette.")
        print("Potrebbe essere necessario un breve ritardo dopo che l'istanza RDS diventa 'available' prima di potersi connettere.")
        raise
    finally:
        if conn:
            conn.close()

def create_ec2_instances(ec2_sg_id, key_pair_name):
    """Crea le istanze EC2 (server e client)."""
    print("Avvio creazione istanze EC2 (Server e Client)...")

    # User Data script per l'istanza Server
    server_user_data_script = f"""#!/bin/bash
sudo apt update -y
sudo apt install -y openjdk-17-jdk git maven -y
git clone {GITHUB_REPO_URL}
cd {REPO_ROOT_DIR}/{SERVER_PROJECT_DIR}
mvn clean install
echo "Setup server completato. JARs compilati in target/."
"""
    
    # User Data script per le istanze Client
    client_user_data_script = f"""#!/bin/bash
sudo apt update -y
sudo apt install -y openjdk-17-jdk git maven -y
git clone {GITHUB_REPO_URL}
cd {REPO_ROOT_DIR}/{CLIENT_PROJECT_DIR}
mvn clean install
echo "Setup client completato. JARs compilati in target/."
"""
    
    instance_ids = []
    public_ips = {}

    # Crea istanza Server
    try:
        server_instance = ec2.run_instances(
            ImageId=AMI_ID,
            MinCount=1,
            MaxCount=1,
            InstanceType=INSTANCE_TYPE,
            KeyName=key_pair_name, # Usa il nome della key pair
            SecurityGroupIds=[ec2_sg_id],
            UserData=server_user_data_script,
            TagSpecifications=[
                {
                    'ResourceType': 'instance',
                    'Tags': [{'Key': 'Name', 'Value': 'MusicAppServer'}]
                }
            ]
        )
        server_id = server_instance['Instances'][0]['InstanceId']
        instance_ids.append(server_id)
        print(f"Istanza Server creata: {server_id}")

        # Crea istanze Client
        client_instances = ec2.run_instances(
            ImageId=AMI_ID,
            MinCount=NUM_CLIENTS,
            MaxCount=NUM_CLIENTS,
            InstanceType=INSTANCE_TYPE,
            KeyName=key_pair_name, # Usa il nome della key pair
            SecurityGroupIds=[ec2_sg_id],
            UserData=client_user_data_script,
            TagSpecifications=[
                {
                    'ResourceType': 'instance',
                    'Tags': [{'Key': 'Name', 'Value': f'MusicAppClient-{i+1}'}]
                } for i in range(NUM_CLIENTS)
            ]
        )
        for client_instance in client_instances['Instances']:
            instance_ids.append(client_instance['InstanceId'])
            print(f"Istanza Client creata: {client_instance['InstanceId']}")

        print("Attesa che le istanze EC2 siano 'running'...")
        waiter = ec2.get_waiter('instance_running')
        waiter.wait(InstanceIds=instance_ids)
        print("Tutte le istanze EC2 sono 'running'.")

        # Recupera gli IP pubblici e privati
        reservations = ec2.describe_instances(InstanceIds=instance_ids)['Reservations']
        for res in reservations:
            for instance in res['Instances']:
                instance_name = [tag['Value'] for tag in instance['Tags'] if tag['Key'] == 'Name'][0]
                public_ip = instance.get('PublicIpAddress', 'N/A')
                private_ip = instance.get('PrivateIpAddress', 'N/A')
                public_ips[instance_name] = {'PublicIp': public_ip, 'PrivateIp': private_ip, 'InstanceId': instance['InstanceId']}
        
        return public_ips

    except ClientError as e:
        print(f"Errore durante la creazione delle istanze EC2: {e}")
        raise

def clean_up(sg_ids, db_identifier, ec2_ids, key_name):
    """Funzione per la pulizia delle risorse create."""
    print("\nInizio processo di pulizia...")

    # Termina istanze EC2
    if ec2_ids:
        print(f"Terminazione istanze EC2: {ec2_ids}...")
        try:
            ec2.terminate_instances(InstanceIds=ec2_ids)
            waiter = ec2.get_waiter('instance_terminated')
            waiter.wait(InstanceIds=ec2_ids)
            print("Istanze EC2 terminate.")
        except ClientError as e:
            if 'InvalidInstanceID.NotFound' in str(e):
                print("Alcune istanze EC2 non trovate, probabilmente già terminate.")
            else:
                print(f"Errore durante la terminazione delle istanze EC2: {e}")

    # Elimina istanza RDS
    if db_identifier:
        print(f"Eliminazione istanza RDS: {db_identifier}...")
        try:
            rds.delete_db_instance(
                DBInstanceIdentifier=db_identifier,
                SkipFinalSnapshot=True, # Non creare snapshot finale per eliminazione rapida
                DeleteAutomatedBackups=True
            )
            waiter = rds.get_waiter('db_instance_deleted')
            waiter.wait(DBInstanceIdentifier=db_identifier)
            print("Istanza RDS eliminata.")
        except ClientError as e:
            if 'DBInstanceNotFoundFault' in str(e):
                print(f"Istanza RDS '{db_identifier}' non trovata, probabilmente già eliminata.")
            else:
                print(f"Errore durante l'eliminazione dell'istanza RDS: {e}")

    # Elimina Security Groups
    for sg_id in sg_ids[::-1]: # Elimina in ordine inverso di creazione per risolvere dipendenze
        print(f"Eliminazione Security Group: {sg_id}...")
        try:
            # Rimuovi eventuali regole di ingresso e uscita che potrebbero causare dipendenze residue
            # (Questo è un workaround, a volte necessario se ci sono dipendenze implicite)
            existing_sg_info = ec2.describe_security_groups(GroupIds=[sg_id])['SecurityGroups'][0]
            
            existing_ingress = existing_sg_info.get('IpPermissions', [])
            if existing_ingress:
                ec2.revoke_security_group_ingress(GroupId=sg_id, IpPermissions=existing_ingress)
            
            existing_egress = existing_sg_info.get('IpPermissionsEgress', [])
            if existing_egress:
                # Per le regole di egress predefinite, bisogna specificare CidrIp come '0.0.0.0/0' e IpProtocol come '-1'
                # Boto3 a volte richiede di essere molto specifico per revocare le regole di default.
                default_egress_rule = {'IpProtocol': '-1', 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]}
                if default_egress_rule in existing_egress:
                    ec2.revoke_security_group_egress(GroupId=sg_id, IpPermissions=[default_egress_rule])
                # Rimuovi altre regole di egress se presenti
                other_egress_rules = [rule for rule in existing_egress if rule != default_egress_rule]
                if other_egress_rules:
                    ec2.revoke_security_group_egress(GroupId=sg_id, IpPermissions=other_egress_rules)

            ec2.delete_security_group(GroupId=sg_id)
            print(f"Security Group {sg_id} eliminato.")
        except ClientError as e:
            if 'DependencyViolation' in str(e):
                print(f"Impossibile eliminare SG {sg_id}: dipendenze esistenti. Riprova dopo un po'.")
            elif 'InvalidGroup.NotFound' in str(e):
                print(f"Security Group {sg_id} non trovato, probabilmente già eliminato.")
            else:
                print(f"Errore durante l'eliminazione del Security Group {sg_id}: {e}")
    
    # Elimina la Key Pair EC2
    if key_name:
        print(f"Eliminazione Key Pair EC2: {key_name}...")
        try:
            ec2.delete_key_pair(KeyName=key_name)
            key_file_path = f"{key_name}.pem"
            if os.path.exists(key_file_path):
                os.remove(key_file_path)
                print(f"File locale '{key_file_path}' eliminato.")
            print(f"Key Pair '{key_name}' eliminata da AWS.")
        except ClientError as e:
            if 'InvalidKeyPair.NotFound' in str(e):
                print(f"Key Pair '{key_name}' non trovata in AWS, probabilmente già eliminata.")
            else:
                print(f"Errore durante l'eliminazione della Key Pair: {e}")


# --- Main execution ---
if __name__ == "__main__":
    ec2_sg_id = None
    rds_sg_id = None
    db_endpoint = None
    instance_info = {}
    all_instance_ids = []
    sg_to_clean = []
    key_pair_created = False # Flag per tracciare se la key pair è stata creata

    try:
        # Crea o verifica l'esistenza della key pair
        create_ec2_key_pair(KEY_PAIR_NAME)
        key_pair_created = True

        ec2_sg_id, rds_sg_id = create_security_groups()
        sg_to_clean = [ec2_sg_id, rds_sg_id]

        db_endpoint = create_rds_instance(rds_sg_id)
        
        # Attendere un po' per assicurarsi che RDS sia pronto per le connessioni
        print("Attendere 120 secondi per stabilizzazione connessione RDS...") # Aumento il tempo di attesa
        time.sleep(120) 

        initialize_database(db_endpoint)

        instance_info = create_ec2_instances(ec2_sg_id, KEY_PAIR_NAME)
        all_instance_ids = [info['InstanceId'] for info in instance_info.values()]

        print("\n--- Infrastruttura AWS creata con successo! ---")
        print("Dettagli del Database RDS:")
        print(f"  Endpoint: {db_endpoint}:{DB_PORT}")
        print(f"  Nome DB: {DB_NAME}")
        print(f"  Utente: {DB_MASTER_USERNAME}")
        print(f"  Password: {DB_MASTER_PASSWORD}")
        print(f"  Key Pair EC2 usata: {KEY_PAIR_NAME}.pem (salvata localmente)")
        print("\nDettagli delle istanze EC2:")
        for name, info in instance_info.items():
            print(f"  {name}:")
            print(f"    ID Istanza: {info['InstanceId']}")
            print(f"    IP Pubblico: {info['PublicIp']}")
            print(f"    IP Privato: {info['PrivateIp']}")
            print(f"    Comando SSH: ssh -i {KEY_PAIR_NAME}.pem ubuntu@{info['PublicIp']}")

        print("\n--- Passaggi successivi (MANUALI o con script separato) ---")
        print("1. **Connettiti via SSH** a ciascuna istanza EC2 usando i comandi forniti sopra.")
        print(f"2. **Naviga nella directory del progetto:** `cd {REPO_ROOT_DIR}/{SERVER_PROJECT_DIR}` (per il server) o `cd {REPO_ROOT_DIR}/{CLIENT_PROJECT_DIR}` (per i client)")
        print("3. **Modifica i file di configurazione Java** (`src/main/java/music/database/query/app/core/Config.java` o simili):")
        print("   - **Per l'istanza server:** Aggiorna l'endpoint del database RDS (`DB_URL`), l'utente (`DB_USER`) e la password (`DB_PASSWORD`).")
        print("   - **Per le istanze client:** Aggiorna l'indirizzo IP del server EC2 (`SERVER_IP`). Utilizza l'**IP Privato** del server per la comunicazione interna tra EC2 se sono nella stessa VPC.")
        print("     Esempio per il server: `String DB_URL = \"jdbc:postgresql://{db_endpoint}:{db_port}/{db_name}\";`")
        print("     Esempio per il client: `String SERVER_IP = \"{server_private_ip}\";`")
        print("4. **Ricompila l'applicazione Java** dopo le modifiche (se necessario, altrimenti ignora):")
        print("   `mvn clean install` (questo è già stato fatto dallo UserData, ma potrebbe servire dopo modifiche a `Config.java`)")
        print("5. **Avvia il server Java** (sull'istanza 'MusicAppServer'):")
        print("   `java -jar target/music-database-query-app-server.jar` (verifica il nome esatto del JAR nella directory 'target')")
        print("6. **Avvia i client Java** (sulle istanze 'MusicAppClient-*'):")
        print("   `java -jar target/music-database-query-app-client.jar` (verifica il nome esatto del JAR nella directory 'target')")
        print("\nRicorda di pulire le risorse AWS quando hai finito per evitare costi!")
        print(f"Per pulire: python {os.path.basename(__file__)} --clean")

    except ClientError as e:
        print(f"Si è verificato un errore AWS: {e}")
    except Exception as e:
        print(f"Si è verificato un errore inaspettato: {e}")
    finally:
        import sys
        if "--clean" in sys.argv:
            clean_up(sg_to_clean, DB_INSTANCE_IDENTIFIER, all_instance_ids, KEY_PAIR_NAME if key_pair_created else None)