# Use an official Maven image with Java 17 as the base image
FROM maven:3.9-eclipse-temurin-17

# Set the working directory inside the container
WORKDIR /app

# Copy the entire project into the container
COPY . .

# Navigate to the server project directory and run 'mvn clean install'
# This will compile the code and download dependencies
RUN mvn -f mvnProject-Server/pom.xml clean install

# Set the working directory to the server project for the next command
WORKDIR /app/mvnProject-Server

# Expose port 8080 to allow traffic to the application
EXPOSE 8080

# Command to run the application using the 'server' profile
# This is the command that will be executed when the container starts
CMD ["mvn", "-Pserver", "exec:java"]