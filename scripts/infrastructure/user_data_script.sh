#!/bin/bash
sudo dnf update -y
# installa Java 17, Git, Maven, Docker, Ruby e AWS CLI
sudo dnf install -y java-17-amazon-corretto-devel git maven docker
sudo dnf install -y ruby
sudo dnf install -y awscli
sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker ec2-user
newgrp docker

# configura AWS CLI per ec2-user
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

# creo il file Dockerfile per il progetto server
cat <<EOF > $APP_DIR/Dockerfile
# Use an official Maven image with Java 17 as the base image
FROM maven:3.9-eclipse-temurin-17

# Set the working directory inside the container
WORKDIR /app

# Copy the entire project into the container
COPY . .

# Navigate to the server project directory and run 'mvn clean install'
RUN mvn -f mvnProject-Server/pom.xml clean install

# Set the working directory to the server project for the next command
WORKDIR /app/mvnProject-Server

# Expose port 8080 to allow traffic to the application
EXPOSE 8080

# Command to run the application using the 'server' profile
CMD ["mvn", "-Pserver", "exec:java"]
EOF

echo "Dockerfile created successfully in $APP_DIR"

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
sudo -u ec2-user aws sns publish --region us-east-1 --topic-arn $(sudo -u ec2-user aws sns list-topics --region us-east-1 --query "Topics[?contains(TopicArn, 'musicapp-server-setup-complete')].TopicArn" --output text) --subject "MusicApp Server Setup" --message "Il setup del server EC2 MusicApp è stato completato con successo."