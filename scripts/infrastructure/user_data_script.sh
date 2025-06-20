#!/bin/bash
sudo dnf update -y # Or yum update -y for older Amazon Linux
sudo dnf install -y java-17-amazon-corretto-devel git maven # Or yum install for older versions
git clone https://github.com/lorenzopaoria/Music-Databese-Query-App-for-Distributed-Systems-on-Cloud.git /home/ec2-user/Music-Databese-Query-App-for-Distributed-Systems-on-Cloud
sudo chown -R ec2-user:ec2-user /home/ec2-user/Music-Databese-Query-App-for-Distributed-Systems-on-Cloud
echo "User data script finished execution on $(date)" | tee /var/log/cloud-init-output.log