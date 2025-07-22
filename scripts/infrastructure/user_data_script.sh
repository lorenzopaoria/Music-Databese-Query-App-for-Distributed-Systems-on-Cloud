#!/bin/bash
sudo dnf update -y
# installa Git, Docker e AWS CLI
sudo dnf install -y  git docker awscli
sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker ec2-user
newgrp docker

# configura AWS CLI per ec2-user, senza limitazioni learner lab avrei creato un ruolo per abilitare la ec2 a mandare messaggi tramite sns
sudo -u ec2-user mkdir -p /home/ec2-user/.aws
sudo -u ec2-user cat <<EOF > /home/ec2-user/.aws/credentials
[default]
aws_access_key_id=AWS_ACCESS_KEY_ID_PLACEHOLDER
aws_secret_access_key=AWS_SECRET_ACCESS_KEY_PLACEHOLDER
aws_session_token=AWS_SESSION_TOKEN_PLACEHOLDER
EOF

sudo -u ec2-user cat <<EOF > /home/ec2-user/.aws/config
[default]
region = us-east-1
output = json
EOF

# imposta i permessi corretti per i file AWS
sudo chown -R ec2-user:ec2-user /home/ec2-user/.aws
sudo chmod 600 /home/ec2-user/.aws/credentials
sudo chmod 644 /home/ec2-user/.aws/config

# definisco working directory
APP_DIR="/home/ec2-user/Music-Databese-Query-App-for-Distributed-Systems-on-Cloud"

# clono il repository GitHub e imposto i permessi
git clone https://github.com/lorenzopaoria/Music-Databese-Query-App-for-Distributed-Systems-on-Cloud.git $APP_DIR
sudo chown -R ec2-user:ec2-user $APP_DIR

# attendo che nlb sia pronto
#sleep 40 

# verifico che il Dockerfile esista nel repository
if [ -f "$APP_DIR/Dockerfile.dockerfile" ]; then
    # rinomino il Dockerfile esistente per Docker
    mv "$APP_DIR/Dockerfile.dockerfile" "$APP_DIR/Dockerfile"
    echo "Using existing Dockerfile from repository"
else
    echo "Warning: Dockerfile.dockerfile not found in repository"
    exit 1
fi

# build della Docker image
echo "Building the Docker image..."
cd $APP_DIR
docker build -t music-server-app .

# run del container Docker
echo "Running the Docker container..."
docker run -d -p 8080:8080 --name musicapp-server music-server-app

echo "Docker container 'music-server-container' is running."

echo "User data script finished execution on $(date)" | tee /var/log/cloud-init-output.log

# notifica SNS di completamento setup del server (eseguito come ec2-user)
sudo -u ec2-user aws sns publish --region us-east-1 --topic-arn $(sudo -u ec2-user aws sns list-topics --region us-east-1 --query "Topics[?contains(TopicArn, 'musicapp-server-setup-complete')].TopicArn" --output text) --subject "MusicApp Server Setup" --message "Il setup del server EC2 MusicApp e' stato completato con successo."