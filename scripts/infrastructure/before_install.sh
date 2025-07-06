#!/bin/bash
mkdir -p /home/ec2-user/musicapp
chmod +x /home/ec2-user/musicapp/*.jar 2>/dev/null || true
chmod +x /home/ec2-user/scripts/infrastructure/restart_server.sh