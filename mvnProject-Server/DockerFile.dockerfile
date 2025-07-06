# Usa un'immagine base di Java con Corretto 17
FROM amazoncorretto:17-alpine-jdk

# Imposta la directory di lavoro all'interno del container
WORKDIR /app

# Copia il JAR compilato dalla fase di build di CodeBuild
# Assumiamo che il JAR sarà disponibile nella directory target dopo la build Maven
COPY target/*.jar app.jar

# Espone la porta su cui l'applicazione Java è in ascolto (es. 8080)
EXPOSE 8080

# Comando per eseguire l'applicazione quando il container viene avviato
ENTRYPOINT ["java", "-jar", "app.jar"]