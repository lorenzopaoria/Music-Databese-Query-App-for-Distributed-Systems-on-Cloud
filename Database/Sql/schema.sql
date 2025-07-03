CREATE TABLE IF NOT EXISTS "Tipo_Utente" (
    "tipo" VARCHAR(50) PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS utente (
    "email" VARCHAR(255) PRIMARY KEY,
    "nome" VARCHAR(255) NOT NULL,
    "cognome" VARCHAR(255) NOT NULL,
    "passw" VARCHAR(255) NOT NULL,
    "tipo" VARCHAR(50),
    "num_telefono" VARCHAR(20),
    "cf" VARCHAR(16) UNIQUE,
    FOREIGN KEY ("tipo") REFERENCES "Tipo_Utente"("tipo") ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS Artista (
    "nomeArtista" VARCHAR(255) PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS Album (
    "nomeArtista" VARCHAR(255),
    "titolo" VARCHAR(255),
    "data_pubblicazione" DATE,
    "num_tracce" INT,
    PRIMARY KEY ("nomeArtista", "titolo"),
    FOREIGN KEY ("nomeArtista") REFERENCES Artista("nomeArtista") ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS contenuto (
    "idContenuto" SERIAL PRIMARY KEY,
    "nome" VARCHAR(255) NOT NULL,
    "durata" INT, -- Corretto da 'duarata' a 'durata'
    "riproduzione" INT,
    "tipo" INT
);

CREATE TABLE IF NOT EXISTS "Crea_Contenuto" (
    "idContenuto" INT,
    "nomeArtista" VARCHAR(255),
    PRIMARY KEY ("idContenuto", "nomeArtista"),
    FOREIGN KEY ("idContenuto") REFERENCES contenuto("idContenuto") ON DELETE CASCADE,
    FOREIGN KEY ("nomeArtista") REFERENCES Artista("nomeArtista") ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS "Tipo_Contenuto" (
    "idTipoContenuto" SERIAL PRIMARY KEY,
    "tipo" VARCHAR(50) NOT NULL
);

CREATE TABLE IF NOT EXISTS Genere (
    "idGenere" SERIAL PRIMARY KEY,
    "genere" VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS "Preferenza_Genere" (
    "email" VARCHAR(255),
    "idGenere" INT,
    PRIMARY KEY ("email", "idGenere"),
    FOREIGN KEY ("email") REFERENCES utente("email") ON DELETE CASCADE,
    FOREIGN KEY ("idGenere") REFERENCES Genere("idGenere") ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS "playlist_utente" (
    "email" VARCHAR(255),
    "nomePlaylist" VARCHAR(255),
    "num_tracce_P" INT,
    PRIMARY KEY ("email", "nomePlaylist"),
    FOREIGN KEY ("email") REFERENCES utente("email") ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS Abbonamento (
    "idAbbonamento" SERIAL PRIMARY KEY,
    "tipo" VARCHAR(50),
    "email" VARCHAR(255),
    FOREIGN KEY ("email") REFERENCES utente("email") ON DELETE CASCADE,
    FOREIGN KEY ("tipo") REFERENCES "Tipo_Utente"("tipo") ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS "contenuti_playlist" (
    "idContenuto" INT,
    "nomePlaylist" VARCHAR(255),
    "email" VARCHAR(255),
    PRIMARY KEY ("idContenuto", "nomePlaylist", "email"),
    FOREIGN KEY ("idContenuto") REFERENCES contenuto("idContenuto") ON DELETE CASCADE,
    FOREIGN KEY ("email", "nomePlaylist") REFERENCES "playlist_utente"("email", "nomePlaylist") ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS "Metodo_Di_Pagamento" (
    "idMet_Pag" SERIAL PRIMARY KEY,
    "CVV" INT,
    "num_carta" BIGINT UNIQUE,
    "data_scadenza" DATE,
    "email" VARCHAR(255) UNIQUE,
    FOREIGN KEY ("email") REFERENCES utente("email") ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS pagamento (
    "idAbbonamento" INT,
    "data" DATE,
    "email" VARCHAR(255),
    PRIMARY KEY ("idAbbonamento", "email", "data"),
    FOREIGN KEY ("idAbbonamento") REFERENCES Abbonamento("idAbbonamento") ON DELETE CASCADE,
    FOREIGN KEY ("email") REFERENCES utente("email") ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS "Riproduzione_Contenuto" (
    "idContenuto" INT,
    "email" VARCHAR(255),
    "data" DATE,
    PRIMARY KEY ("idContenuto", "email", "data"),
    FOREIGN KEY ("idContenuto") REFERENCES contenuto("idContenuto") ON DELETE CASCADE,
    FOREIGN KEY ("email") REFERENCES utente("email") ON DELETE CASCADE
);