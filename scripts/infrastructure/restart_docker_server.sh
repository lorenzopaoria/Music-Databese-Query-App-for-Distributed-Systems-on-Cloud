#!/bin/bash
set -e

APP_NAME="musicapp-server"
ECR_REPO="123456789012.dkr.ecr.us-east-1.amazonaws.com/musicapp-server:latest" # Sostituisci con il tuo Account ID AWS e regione ECR

# Assicurati che il ruolo IAM dell'istanza EC2 abbia i permessi per pullare da ECR
echo "Logging in to Amazon ECR..."
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 123456789012.dkr.ecr.us-east-1.amazonaws.com

# Pull della nuova immagine Docker
echo "Pulling latest Docker image from ECR: $ECR_REPO"
docker pull $ECR_REPO

# Interrompi e rimuovi il container Docker esistente (se in esecuzione)
echo "Stopping and removing existing Docker container (if any)..."
if docker ps -a --format '{{.Names}}' | grep -q "$APP_NAME"; then
  docker stop $APP_NAME
  docker rm $APP_NAME
  echo "Existing container stopped and removed."
else
  echo "No existing container named '$APP_NAME' found."
fi

# Variabili d'ambiente per il container Docker (ad esempio, le credenziali del database)
# Queste variabili devono essere accessibili da questo script.
# Ad esempio, puoi leggerle da un file di configurazione copiato sull'EC2.
# Ho usato jq per leggere dal tuo deploy_config.json, assicurati che sia presente.
DB_ENDPOINT=$(jq -r '.rds_endpoint' /home/ec2-user/musicapp/deploy_config.json)
DB_USERNAME=$(jq -r '.db_username' /home/ec2-user/musicapp/deploy_config.json)
DB_PASSWORD=$(jq -r '.db_password' /home/ec2-user/musicapp/deploy_config.json)
DB_NAME=$(jq -r '.db_name' /home/ec2-user/musicapp/deploy_config.json)

# Avvia il nuovo container Docker
echo "Starting new Docker container..."
docker run -d \
  --name $APP_NAME \
  -p 8080:8080 \
  -e SPRING_DATASOURCE_URL="jdbc:postgresql://$DB_ENDPOINT:5432/$DB_NAME" \
  -e SPRING_DATASOURCE_USERNAME="$DB_USERNAME" \
  -e SPRING_DATASOURCE_PASSWORD="$DB_PASSWORD" \
  $ECR_REPO

echo "Docker container '$APP_NAME' started."
docker ps -a