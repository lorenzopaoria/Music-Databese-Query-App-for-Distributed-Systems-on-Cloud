# Usa un'immagine ufficiale di Maven che include una JDK (Java Development Kit).
# Questo garantisce che Java e Maven siano già preinstallati e configurati correttamente.
# Abbiamo scelto Java 17, l'ultima versione LTS (Long Term Support), e Maven 3.9.6.
# 'slim-bullseye' indica che l'immagine base è una versione ridotta di Debian Bullseye,
# il che la rende più leggera.
FROM maven:3.9.6-jdk-17

# Imposta la directory di lavoro all'interno del container.
# Questo è il percorso dove copierai il tuo codice sorgente e dove verranno eseguiti i comandi Maven.
WORKDIR /app

# Non copiamo qui il codice sorgente del tuo progetto.
# Questo Dockerfile serve a creare un ambiente di compilazione generico.
# Il tuo codice sorgente verrà "montato" all'interno del container quando lo avvierai,
# permettendoti di compilare qualsiasi progetto Maven.

# Puoi aggiungere qui eventuali configurazioni Maven globali se necessario,
# ad esempio un settings.xml personalizzato, ma per la maggior parte dei casi non è richiesto.
# Esempio (se avessi un file settings.xml personalizzato):
# COPY settings.xml /usr/share/maven/ref/

# Definisci il comando predefinito quando il container viene avviato senza argomenti.
# In questo caso, avvierà Maven. Tuttavia, di solito sovrascriverai questo CMD
# quando avvierai il container per eseguire specifici comandi Maven (es. 'mvn clean install').
CMD ["mvn"]
