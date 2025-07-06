#!/bin/bash
sudo dnf update -y
sudo dnf install -y java-17-amazon-corretto-devel git maven docker # Aggiungi 'docker' qui
sudo systemctl enable docker # Abilita il servizio docker all'avvio
sudo systemctl start docker # Avvia il servizio docker
sudo usermod -aG docker ec2-user # Aggiungi l'utente ec2-user al gruppo docker
newgrp docker # Per applicare il cambio di gruppo immediatamente (utile per script successivi)

git clone https://github.com/lorenzopaoria/Music-Databese-Query-App-for-Distributed-Systems-on-Cloud.git /home/ec2-user/Music-Databese-Query-App-for-Distributed-Systems-on-Cloud
sudo chown -R ec2-user:ec2-user /home/ec2-user/Music-Databese-Query-App-for-Distributed-Systems-on-Cloud
echo "User data script finished execution on $(date)" | tee /var/log/cloud-init-output.log
sudo dnf install -y ruby
cd /home/ec2-user
wget https://aws-codedeploy-us-east-1.s3.us-east-1.amazonaws.com/latest/install
chmod +x ./install
sudo ./install auto
sudo systemctl start codedeploy-agent
sudo systemctl enable codedeploy-agent