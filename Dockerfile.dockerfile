# uso di un'immagine ufficiale di Maven con Java 17 come immagine di base
FROM maven:3.9-eclipse-temurin-17

# imposta la directory di lavoro all'interno del contenitore
WORKDIR /app

# copia l'intero progetto all'interno del contenitore
COPY . .

# Questo compilerà il codice e scaricherà le dipendenze
RUN mvn -f mvnProject-Server/pom.xml clean install

# Imposta la directory di lavoro sulla cartella del progetto server per il comando successivo
WORKDIR /app/mvnProject-Server

# espone la porta 8080 per consentire il traffico all'applicazione
EXPOSE 8080

# Questo è il comando che verrà eseguito all'avvio del contenitore
CMD ["mvn", "-Pserver", "exec:java"]