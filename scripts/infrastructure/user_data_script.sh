#!/bin/bash
sudo dnf update -y
# Install necessary tools: Java, Git, Maven, and Docker
sudo dnf install -y java-17-amazon-corretto-devel git maven docker
sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker ec2-user
newgrp docker # Apply group changes immediately

# Define the project directory
APP_DIR="/home/ec2-user/Music-Databese-Query-App-for-Distributed-Systems-on-Cloud"

# Clone the Git repository
git clone https://github.com/lorenzopaoria/Music-Databese-Query-App-for-Distributed-Systems-on-Cloud.git $APP_DIR
sudo chown -R ec2-user:ec2-user $APP_DIR

# --- Dockerization Steps ---

# Create the Dockerfile inside the cloned repository
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

# Build the Docker image from the Dockerfile
echo "Building the Docker image..."
cd $APP_DIR
docker build -t music-server-app .

# Run the Docker container
echo "Running the Docker container..."
docker run -d -p 8080:8080 --name music-server-container music-server-app

echo "Docker container 'music-server-container' is running."

# --- CodeDeploy Agent Installation ---
cd /home/ec2-user
sudo dnf install -y ruby
wget https://aws-codedeploy-us-east-1.s3.us-east-1.amazonaws.com/latest/install
chmod +x ./install
sudo ./install auto
sudo systemctl start codedeploy-agent
sudo systemctl enable codedeploy-agent

echo "User data script finished execution on $(date)" | tee /var/log/cloud-init-output.log