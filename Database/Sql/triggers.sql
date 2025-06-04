#TRIGGER DI INTEGRITA': un utente di tipo 'free' può ascoltare un massimo di 10 contenuti al giorno
USE piattaforma_streaming_musicale;
DELIMITER $$
CREATE TRIGGER ascolti_free
AFTER INSERT ON Riproduzione_Contenuto FOR EACH ROW
BEGIN
	DECLARE Tipo_U VARCHAR(15);
    DECLARE numero_ascolti INT;
    SELECT Tipo_Utente.tipo INTO Tipo_U
    FROM utente JOIN tipo_account ON Utente.tipo = Tipo_Utente.idTipoUtente
    WHERE email = NEW.email;
    
    IF ( Tipo_U= 'free' ) THEN#se l'utente è free allora
        SELECT COUNT(*) INTO numero_ascolti
        FROM Riproduzione_Contenuto
        WHERE email = NEW.email AND data = CURRENT_DATE;
        IF (numero_ascolti IS NOT NULL AND numero_ascolti > 10) THEN
        	DELETE FROM Riproduzione_Contenuto 
            WHERE email = NEW.EMAIL AND idContenuto = NEW.idContenuto AND data = NEW.data;
        END IF;
    END IF;
    
END$$

DELIMITER ;

#TRIGGER DI INTEGRITA': un utente di tipo 'free' non può creare playlist
USE piattaforma_streaming_musicale;
DELIMITER $$
CREATE TRIGGER playlist_free
AFTER INSERT ON playlist FOR EACH ROW
BEGIN
	DECLARE Tipo_U VARCHAR(15);
    DECLARE numero_playlist INT;
    SELECT Tipo_Utente.tipo INTO Tipo_U
    FROM utente JOIN Tipo_Utente ON utente.tipo = Tipo_Utente.idTipoUtente
    WHERE email = NEW.email;
    IF ( Tipo_U = 'free' ) THEN
        SELECT COUNT(*) INTO numero_playlist
        FROM playlist
        WHERE email = NEW.email;
        IF (numero_playlist IS NOT NULL AND numero_playlist > 0) THEN
        	DELETE FROM playlist WHERE email = NEW.email AND nomePlaylist = NEW.nomePlaylist;
        END IF;
    END IF;
    
END$$

DELIMITER ;

#TRIGGER DI INTEGRITA': un utente può effettuare un upgrade a "premium" dopo il pagamento dell'abbonamento
USE piattaforma_streaming_musicale;
DELIMITER $$
CREATE TRIGGER free_to_premium
AFTER INSERT ON pagamento FOR EACH ROW
BEGIN
    DECLARE Tipo_U VARCHAR(15);
    SELECT Tipo_Utente.tipo INTO Tipo_U
    FROM Utente JOIN Tipo_Utente ON utente.tipo = Tipo_Utente.idTipoUtente
    WHERE email=NEW.email AND idAbbonamento=NEW.idAbbonamento AND data=NEW.data; 
    IF(Tipo_U!= 1) THEN
        UPDATE Utente
        SET tipo=1
        WHERE email= NEW.email;
    END IF;
END$$

DELIMITER ; 

#TRIGGER DATO: incrementare il numero di riproduzioni di un brano o podcast tutte le volte che viene riprodotto
USE piattaforma_streaming_musicale;
DELIMITER $$
CREATE TRIGGER numero_riproduzioni
AFTER INSERT ON Riproduzione_Contenuto FOR EACH ROW
BEGIN
    UPDATE contenuto
    SET riproduzione= riproduzione+1
    WHERE idContenuto=NEW.idContenuto AND email=NEW.email;
END$$

DELIMITER ;