#!/bin/bash
set -e

JAR_PATH="/home/ec2-user/musicapp"
JAR_FILE=$(ls $JAR_PATH/*.jar | head -n 1)
APP_NAME="musicapp-server"

# Kill any running Java process for the app
PID=$(pgrep -f "$JAR_FILE" || true)
if [ -n "$PID" ]; then
  echo "Killing existing process $PID"
  kill $PID
  sleep 2
fi

# Start the new jar in background
echo "Starting $JAR_FILE"
nohup java -jar "$JAR_FILE" > $JAR_PATH/app.log 2>&1 &
echo "App started."