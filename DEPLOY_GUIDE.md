# Deploy Automatico - Guida Rapida

## Panoramica del Sistema

Il sistema di deploy è strutturato in 3 fasi:

1. **Deploy Iniziale** - Crea l'infrastruttura AWS
2. **Update Locale** - Aggiorna le configurazioni del codice
3. **Deploy Automatico** - GitHub Action gestisce il deploy

## Setup Iniziale

### 1. Configura le variabili d'ambiente

Crea un file `.env` nella root del progetto:

```bash
# AWS Credentials
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key

# GitHub Configuration
GITHUB_TOKEN=your_github_token
REPO=username/repository-name
```

### 2. Configura i GitHub Secrets

Vai su GitHub > Settings > Secrets and variables > Actions e aggiungi:

- `DOCKER_USERNAME` - Username di DockerHub
- `DOCKER_PASSWORD` - Password/Token di DockerHub
- `EC2_HOST` - IP pubblico dell'istanza EC2
- `EC2_SSH_KEY` - Chiave privata SSH (contenuto del file .pem)

## Processo di Deploy

### Deploy Iniziale (Solo la prima volta)

```bash
# Esegui il deploy dell'infrastruttura
python scripts/infrastructure/deploy_music_app.py

# Questo creerà:
# - Istanza EC2
# - Database RDS
# - Security Groups
# - File deploy_config.json
```

### Update e Deploy Automatico

```bash
# Usa lo script unificato (RACCOMANDATO)
python scripts/infrastructure/update_and_deploy.py

# Oppure manualmente:
python scripts/infrastructure/update_java_config_on_ec2.py
git add .
git commit -m "Update config"
git push
```

## Cosa Succede Durante il Deploy Automatico

1. **Trigger**: Push su branch main/master
2. **GitHub Action**:
   - Builda l'immagine Docker
   - Pusha su DockerHub
   - Si connette all'EC2 via SSH
   - Legge le configurazioni da `deploy_config.json`
   - Ferma il container esistente
   - Scarica l'immagine aggiornata
   - Avvia il nuovo container con le variabili d'ambiente corrette

## Monitoraggio

### Controllo del Deploy

```bash
# Verifica lo stato dell'applicazione
curl http://YOUR_EC2_IP:8080

# Connessione SSH all'EC2
ssh -i your-key.pem ec2-user@YOUR_EC2_IP

# Verifica container Docker
docker ps
docker logs musicapp-server
```

### Log della GitHub Action

Vai su GitHub > Actions per vedere il progresso del deploy.

## Risoluzione Problemi

### Container non si avvia

```bash
# Controlla i log
docker logs musicapp-server

# Verifica le variabili d'ambiente
docker inspect musicapp-server | grep -A 20 "Env"

# Riavvia manualmente
docker restart musicapp-server
```

### Configurazioni non aggiornate

```bash
# Verifica che deploy_config.json sia presente
cat /home/ec2-user/deploy_config.json

# Verifica che jq sia installato
which jq
```

### Database non raggiungibile

```bash
# Testa la connessione al database
telnet YOUR_RDS_ENDPOINT 5432

# Verifica i Security Groups
# Assicurati che il SG del RDS permetta connessioni dal SG dell'EC2
```

## File Importanti

- `.github/workflows/deploy-ec2.yaml` - GitHub Action per il deploy
- `deploy_config.json` - Configurazioni generate dal deploy iniziale
- `scripts/infrastructure/update_and_deploy.py` - Script unificato per update e deploy
- `Dockerfile.dockerfile` - Definizione dell'immagine Docker

## Flusso Completo

```
1. Deploy iniziale → Crea infrastruttura + deploy_config.json
2. Modifiche al codice → Usa update_and_deploy.py
3. GitHub Action → Automaticamente:
   - Build Docker image
   - Push to DockerHub
   - Deploy su EC2
   - Restart container
4. Applicazione aggiornata → Disponibile su http://EC2_IP:8080
```

## Note

- Il deploy è automatico solo dopo il setup iniziale
- Le configurazioni vengono lette da `deploy_config.json` sull'EC2
- Il container viene sempre ricreato per garantire l'aggiornamento
- L'applicazione è accessibile sulla porta 8080
