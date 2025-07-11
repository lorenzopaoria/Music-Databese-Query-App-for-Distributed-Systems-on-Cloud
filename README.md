# Music Database Query App per Sistemi Distribuiti su Cloud

<div align="center">
  <img src="https://github.com/lorenzopaoria/Database-Project-Music-streaming-platform-for-distributed-systems/blob/e3a2e7c9ca2cd47907a189c038af8489a2f19306/Photo/queryGUI.png"/>
</div>

## Descrizione del Progetto

Questo progetto implementa una piattaforma di streaming musicale distribuita che utilizza AWS per l'infrastruttura cloud. L'applicazione è composta da un client Java e un server Java che comunicano con un database PostgreSQL su AWS RDS, il tutto orchestrato attraverso un Network Load Balancer (NLB) e tramite il sistema di avvisi SNS.

## Prerequisiti

- Java 11 o superiore
- Maven 3.6 o superiore
- Python 3.8 o superiore
- Account AWS con i seguenti privilegi:
  - EC2 (creazione e gestione istanze)
  - RDS (creazione e gestione database)
  - VPC e Security Groups
  - Load Balancer (Network Load Balancer)
  - SNS (Simple Notification Service)
- AWS CLI configurato
- Git configurato

## Installazione e Configurazione

### 1. Configurazione Credenziali AWS

Prima di tutto, configura le credenziali AWS nel file `~/.aws/credentials`:

```bash
# Su Windows
mkdir %USERPROFILE%\.aws
# Su Linux/Mac
mkdir ~/.aws
```

Crea il file `~/.aws/credentials` con il seguente contenuto:

```ini
[default]
aws_access_key_id = YOUR_ACCESS_KEY_ID
aws_secret_access_key = YOUR_SECRET_ACCESS_KEY
aws_session_token = YOUR_SESSION_TOKEN (opzionale, se usi credenziali temporanee)
```

### 2. Configurazione GitHub (Opzionale)

Per automatizzare gli aggiornamenti via GitHub Actions, crea un file `.env` nella root del progetto:

```bash
GITHUB_TOKEN=
GITHUB_TOKEN_API=
REPO=
SECRET_NAME=
PEM_PATH=
```

### 3. Installazione Dipendenze Python

```bash
pip install boto3 psycopg2 requests pynacl python-dotenv paramiko
```

## Utilizzo

### 1: Deployment Completo dell'Infrastruttura

Per deployare l'intera infrastruttura AWS da zero:

```bash
cd scripts/infrastructure
python deploy_music_app.py
```

**Cosa fa questo script:**

- Crea un'istanza EC2
- Configura un database PostgreSQL su AWS RDS
- Carica lo schema e i dati del database
- Crea un Network Load Balancer
- Configura tutti i Security Groups necessari
- Compila e avvia automaticamente il server Java sull'istanza EC2
- Crea un SNS per avvisare il completamento del setup per l'istanza EC2

**Tempo stimato:** 15-20 minuti

### 2: Aggiornamento GitHub Secrets

Per sincronizzare le configurazioni con GitHub Actions:

```bash
cd scripts/infrastructure
python update_github_secrets.py
```

**Cosa fa questo script:**

- Legge la configurazione dal file `deploy_config.json`
- Legge il file  `.env `
- Aggiorna i secrets nel repository GitHub
- Abilita la CI/CD pipeline per deployments automatici

### 3: Aggiornamento Configurazione Esistente

Se l'infrastruttura è già stata creata e vuoi solo aggiornare la configurazione Java:

```bash
cd scripts/infrastructure
python update_java_config_on_ec2.py
```

**Cosa fa questo script:**

- Aggiorna il codice Java dal repository Git localmente
- Fa una push alla repository Git che attiverà la Git Action
- La Git Action si connetterà tramite SSH all'instanza EC2 server e farà un deployment automatico

## Architettura del Sistema

### Componenti

1. **mvnProject-Client**: Client Java per l'interfaccia utente con GUI
2. **mvnProject-Server**: Server Java per la logica di business (containerizzato con Docker)
3. **AWS Infrastructure**:
   - EC2 (istanze per il server)
   - RDS (database PostgreSQL)
   - NLB (Network Load Balancer)
   - SNS (notifiche)
   - Security Groups (firewall)
   - CloudWatch (monitoring)
4. **GitHub Actions**: Pipeline CI/CD per deployment automatico
5. **Docker**: Containerizzazione dell'applicazione server

### Flusso delle Operazioni

1. L'utente interagisce con il **client Java**
2. Il client invia richieste TCP al **Network Load Balancer**
3. Il **NLB** distribuisce il carico tra le istanze EC2 del server inoltre farà un HealthCheck al server Java ogni 60 secondi
4. Il **server Java** (containerizzato con Docker) processa le richieste
5. Il server interroga il **database PostgreSQL** su AWS RDS
6. I risultati vengono restituiti al client attraverso la catena inversa
7. **SNS** invia notifiche per eventi critici (deployment completato, errori, ecc.)

### Deployment e CI/CD

1. **Developer** effettua una push su GitHub
2. **GitHub Actions** viene attivato automaticamente
3. Il workflow compila il progetto Maven
4. Crea l'immagine Docker del server
5. Si connette via SSH all'istanza EC2
6. Aggiorna il container Docker sul server
7. **SNS** notifica il completamento del deployment

## Configurazione del Database

Il database include le seguenti tabelle principali:

- `artisti`: Informazioni sugli artisti musicali
- `album`: Album musicali con metadati
- `brani`: Singoli brani con durata e genere
- `playlist`: Playlist utente personalizzate
- `utenti`: Gestione utenti con autenticazione

## Monitoraggio e Logging

- I log delle applicazioni vengono salvati in `database_audit.log`
- Lo stato dell'applicativo server si può monitorare tramite comando:
  ```bash
  docker logs -f musiapp-server
  ```
- Il completamento del server al deploy e successivi e notificato tramite SNS

### Pulizia Risorse

Per evitare costi AWS non necessari, ricorda di eliminare le risorse quando non sono più necessarie:

```bash
# Elimina tutta l'infrastruttura
python deploy_music_app.py --clean

# Elimina tutta l'infrastruttura a meno del database (tempo minore di pulizia)
python deploy_music_app.py --clean --nords
```

## Contribuire

1. Fork del repository
2. Crea un branch per la tua feature
3. Commit delle modifiche
4. Push al branch
5. Crea una Pull Request

## Licenza

Questo progetto è sviluppato per scopi educativi nell'ambito del corso di Sistemi Cloud.
