CREATE DATABASE piattaforma_streaming_musicale;

CREATE TABLE IF NOT EXISTS Artista ( 
    nomeArtista VARCHAR(100) NOT NULL,
    PRIMARY KEY (nomeArtista)
)ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE IF NOT EXISTS Tipo_Contenuto (
	idTipoContenuto INT UNSIGNED AUTO_INCREMENT,
    tipo VARCHAR(100) NOT NULL ,
    PRIMARY KEY (idTipoContenuto)
)ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE IF NOT EXISTS Tipo_Utente (
	idTipoUtente INT UNSIGNED AUTO_INCREMENT,
    tipo VARCHAR(100) NOT NULL,
    PRIMARY KEY (idTipoUtente)
)ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE IF NOT EXISTS Contenuto (
	idContenuto INT UNSIGNED AUTO_INCREMENT,
    nome VARCHAR(100) NOT NULL,
    duarata INT UNSIGNED NOT NULL,
    riproduzione INT UNSIGNED NOT NULL DEFAULT 0,
    tipo INT UNSIGNED,
    PRIMARY KEY (idContenuto),
    FOREIGN KEY (tipo)
        REFERENCES Tipo_Contenuto(idTipoContenuto)
)ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE IF NOT EXISTS Album ( 
    nomeArtista VARCHAR(100) NOT NULL,
    titolo VARCHAR(100) NOT NULL,
    data_pubblicazione DATE NOT NULL,
    num_tracce TINYINT NOT NULL DEFAULT 1,
    PRIMARY KEY (nomeArtista, titolo),
    UNIQUE KEY (nomeArtista, titolo),
    FOREIGN KEY (nomeArtista)
    	REFERENCES Artista(nomeArtista)
    	ON UPDATE CASCADE ON DELETE CASCADE
)ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE IF NOT EXISTS Crea_Contenuto (
	idContenuto INT UNSIGNED,
    nomeArtista VARCHAR(100) NOT NULL,
    PRIMARY KEY (idContenuto, nomeArtista),
    UNIQUE KEY (idContenuto, nomeArtista),
    FOREIGN KEY (idContenuto)
    	REFERENCES Contenuto(idContenuto)
    	ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (nomeArtista)
    	REFERENCES Artista(nomeArtista)
    	ON UPDATE CASCADE ON DELETE CASCADE
)ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE IF NOT EXISTS Contenuti_Playlist (
	idContenuto INT UNSIGNED,
    nomePlaylist VARCHAR(100),
    email VARCHAR(100),
    PRIMARY KEY (idContenuto, nomePlaylist, email),
    UNIQUE KEY (idContenuto, nomePlaylist, email),
    FOREIGN KEY (idContenuto)
    	REFERENCES Contenuto(idContenuto)
    	ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (nomePlaylist)
    	REFERENCES Playlist(nomePlaylist)
    	ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (email)
    	REFERENCES Utente(email)
    	ON UPDATE CASCADE ON DELETE CASCADE
)ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE IF NOT EXISTS Riproduzione_Contenuto (
	idContenuto INT UNSIGNED,
    email VARCHAR(100),
    data DATE NOT NULL,
    PRIMARY KEY (idContenuto, email),
    UNIQUE KEY (idContenuto, email),
    FOREIGN KEY (idContenuto)
    	REFERENCES Contenuto(idContenuto)
    	ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (email)
    	REFERENCES Utente(email)
    	ON UPDATE CASCADE ON DELETE CASCADE
)ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE IF NOT EXISTS Appartiene_Genere (
	idGenere INT UNSIGNED,
    idContenuto INT UNSIGNED,
    PRIMARY KEY (idGenere, idContenuto),
    UNIQUE KEY (idGenere, idContenuto),
    FOREIGN KEY (idContenuto)
    	REFERENCES Contenuto(idContenuto)
    	ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (idGenere)
    	REFERENCES Genere(idGenere)
    	ON UPDATE CASCADE ON DELETE CASCADE
)ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE IF NOT EXISTS Genere (
	idGenere INT UNSIGNED,
    genere VARCHAR(50) NOT NULL UNIQUE,
    PRIMARY KEY (idGenere)
)ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE IF NOT EXISTS Utente (
    email VARCHAR(100),
    nome VARCHAR(50) NOT NULL,
    cognome VARCHAR(50),
    passw VARCHAR(50),
    tipo INT UNSIGNED NOT NULL,#0 free, 1 premium
    num_telefono INT NOT NULL,
    cf VARCHAR(15),
    PRIMARY KEY (email),
    FOREIGN KEY (tipo)
    	REFERENCES Tipo_Utente(idTipoUtente)
    	ON UPDATE CASCADE ON DELETE CASCADE
)ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE IF NOT EXISTS Playlist (#non la inserisce phpMyAdmin
    email VARCHAR(100),
    nomePlaylist VARCHAR(50),
    num_tracce_P TINYINT NOT NULL DEFAULT 0,
    PRIMARY KEY (nomePlaylist, email),
    UNIQUE KEY (email, nomePlaylist),
    FOREIGN KEY (email) 
        REFERENCES Utente(email)
        ON UPDATE CASCADE ON DELETE CASCADE
)ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE IF NOT EXISTS Preferenza_Genere (
    email VARCHAR(100),
    idGenere INT UNSIGNED,
    PRIMARY KEY (email, idGenere),
    UNIQUE KEY (email, idGenere),
    FOREIGN KEY (email)
    	REFERENCES Utente(email)
    	ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (idGenere)
    	REFERENCES Genere(idGenere)
    	ON UPDATE CASCADE ON DELETE CASCADE
)ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE IF NOT EXISTS Metodo_Di_Pagamento (
    idMet_Pag INT UNSIGNED AUTO_INCREMENT,
    CVV SMALLINT UNSIGNED NOT NULL,
    num_carta BIGINT UNSIGNED NOT NULL,
    data_scadenza DATE NOT NULL,
    email VARCHAR(100),
    PRIMARY KEY (idMet_Pag),
    FOREIGN KEY (email)
    	REFERENCES Utente(email)
    	ON UPDATE CASCADE ON DELETE CASCADE
)ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE IF NOT EXISTS Pagamento (
    idAbbonamento TINYINT UNSIGNED,
    data DATE,
    email VARCHAR(100),
    PRIMARY KEY (idAbbonamento,data,email),
    UNIQUE KEY (idAbbonamento,data,email),
    FOREIGN KEY (idAbbonamento)
    	REFERENCES Abbonamento(idAbbonamento)
    	ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (email)
    	REFERENCES Utente(email)
    	ON UPDATE CASCADE ON DELETE CASCADE
)ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE IF NOT EXISTS Abbonamento (
    idAbbonamento TINYINT UNSIGNED AUTO_INCREMENT,
    tipo VARCHAR(50),
    email VARCHAR(100),
    PRIMARY KEY (idAbbonamento),
    FOREIGN KEY (email)
    	REFERENCES Utente(email)
    	ON UPDATE CASCADE ON DELETE CASCADE
)ENGINE=InnoDB DEFAULT CHARSET=utf8;






