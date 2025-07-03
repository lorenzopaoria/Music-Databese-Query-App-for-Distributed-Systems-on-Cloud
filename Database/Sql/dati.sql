-- Nota: L'ordine degli INSERT è cruciale. Le tabelle referenziate devono essere popolate per prime.

INSERT INTO "Tipo_Utente"("tipo")
VALUES
('premium'),
('free');

INSERT INTO utente("email", "nome", "cognome", "passw", "tipo", "num_telefono", "cf")
VALUES
('margheritaursino@gmail.com', 'margherita', 'ursino', 'marghe02', 'free', '3398423455', 'MRGURSN015H865R'),
('benedettostraquadanio@gmail.com', 'benedetto', 'straquadanio', 'bene03', 'premium', '3397534691', 'BNDT02S1412H534T'),
('mariorossi@gmail.com', 'mario', 'rossi', 'rossi04', 'free', '3317212117', 'MRRSSQ86SH152S'),
('annapistorio@gmail.com', 'anna', 'pistorio', 'anna04', 'premium', '3324621589', 'NPSTRQ99S54H563R'),
('robertarusso@gmail.com', 'roberta', 'russo', 'russo07', 'free', '3341256355', 'RBRTRS01F34H154S'),
('federicafirrito@gmail.com', 'federica', 'firrito', 'fede88', 'premium', '3362145711', 'FDRCFR02S10H163S');

INSERT INTO contenuto("nome", "durata", "riproduzione", "tipo")
VALUES
('bello', 215, 0, 1),
('podcast tranquillo', 1024, 0, 2),
('another day', 305, 0, 3),
('francesco totti', 252, 0, 4),
('la storia dei DBS', 2052, 0, 5),
('katy', 310, 0, 6),
('rossana', 213, 0, 7),
('tonto', 330, 0, 8),
('muschio', 2215, 0, 9),
('risica', 206, 0, 10);

INSERT INTO Artista("nomeArtista")
VALUES
('joji'),
('baffo'),
('another love'),
('bello figo gu'),
('alaimo'),
('perry'),
('toto'),
('tha supreme'),
('selvaggio'),
('non rosica');

INSERT INTO "Crea_Contenuto"("idContenuto", "nomeArtista")
VALUES
(1,'joji'),
(2,'baffo'),
(3,'another love'),
(4,'bello figo gu'),
(5,'alaimo'),
(6,'perry'),
(7,'toto'),
(8,'tha supreme'),
(9,'selvaggio'),
(10,'non rosica');

INSERT INTO "Tipo_Contenuto"("idTipoContenuto", "tipo")
VALUES
(1,'brano'),
(2,'podcast'),
(3,'brano'),
(4,'brano'),
(5,'podcast'),
(6,'brano'),
(7,'brano'),
(8,'brano'),
(9,'podcast'),
(10,'brano');

INSERT INTO Genere("idGenere", "genere")
VALUES
(1,'classica'),
(2,'rock'),
(3,'trap'),
(4,'rap'),
(5,'disco'),
(6,'dance'),
(7,'punk'),
(8,'indie'),
(9,'folk'),
(10,'folklore');

INSERT INTO "Preferenza_Genere"("email", "idGenere")
VALUES
('margheritaursino@gmail.com', 1),
('benedettostraquadanio@gmail.com', 1),
('mariorossi@gmail.com', 3),
('annapistorio@gmail.com', 2),
('robertarusso@gmail.com', 7),
('federicafirrito@gmail.com', 5);

INSERT INTO "playlist_utente"("email", "nomePlaylist", "num_tracce_P")
VALUES
('benedettostraquadanio@gmail.com', 'tempo libero', 5),
('annapistorio@gmail.com', 'passatempo', 3),
('federicafirrito@gmail.com', 'macchina', 5),
('benedettostraquadanio@gmail.com', 'sonno', 8),
('annapistorio@gmail.com', 'studio', 7),
('federicafirrito@gmail.com', 'lavoro', 5),
('benedettostraquadanio@gmail.com', 'classica', 8),
('annapistorio@gmail.com', 'amici', 2),
('federicafirrito@gmail.com', 'giocare', 8),
('annapistorio@gmail.com', 'lettura', 6),
('federicafirrito@gmail.com', 'relazionefinita', 9);

-- Gli idAbbonamento sono SERIAL, quindi non vanno specificati manualmente.
-- Se vuoi mantenere questi valori, inserisci e poi esegui:
-- SELECT setval(pg_get_serial_sequence('"Abbonamento"', 'idAbbonamento'), 3, true);
INSERT INTO Abbonamento("tipo", "email")
VALUES
('premium','benedettostraquadanio@gmail.com'),
('premium','federicafirrito@gmail.com'),
('premium','annapistorio@gmail.com');

INSERT INTO Album("nomeArtista", "titolo", "data_pubblicazione", "num_tracce")
VALUES
('alaimo','DBS', '2006-11-15', 15),
('another love','love','2015-05-22', 7),
('baffo','baffissimo','2001-04-12', 15),
('bello figo gu','erroma','2009-11-15', 17),
('joji','depressione','2008-02-07', 4),
('non rosica','ride bene','2007-01-11', 10),
('perry','horse','2019-12-01', 21),
('perry','dark','2015-05-12', 6),
('toto','pinuccio','1999-06-07', 5),
('tha supreme','3s72r0','2020-10-10', 17),
('joji','nulla','1995-12-12', 12),
('non rosica','chi ride ultimo','2003-06-12', 23),
('joji','per niente','2015-05-17', 7),
('perry','consolation','2009-05-05', 6),
('baffo','pelle','2000-02-02', 6),
('another love','distorsione','2022-12-22', 7);

INSERT INTO "contenuti_playlist"("idContenuto", "nomePlaylist", "email")
VALUES
(1, 'tempo libero','benedettostraquadanio@gmail.com'),
(1, 'passatempo','annapistorio@gmail.com'),
(3, 'macchina', 'federicafirrito@gmail.com'),
(6, 'sonno','benedettostraquadanio@gmail.com'),
(9, 'studio', 'annapistorio@gmail.com'),
(7, 'lavoro','federicafirrito@gmail.com'),
(1, 'classica', 'benedettostraquadanio@gmail.com'),
(9, 'amici','annapistorio@gmail.com'),
(8, 'giocare', 'federicafirrito@gmail.com'),
(10, 'lettura', 'annapistorio@gmail.com'),
(6, 'relazionefinita', 'federicafirrito@gmail.com'),
(7, 'tempo libero','benedettostraquadanio@gmail.com'),
(6, 'tempo libero','benedettostraquadanio@gmail.com'),
(4, 'tempo libero','benedettostraquadanio@gmail.com'),
(3, 'tempo libero','benedettostraquadanio@gmail.com'),
(6, 'passatempo','annapistorio@gmail.com'),
(7, 'passatempo','annapistorio@gmail.com'),
(8, 'macchina', 'federicafirrito@gmail.com'),
(1, 'macchina', 'federicafirrito@gmail.com'),
(4, 'macchina', 'federicafirrito@gmail.com'),
(7, 'macchina', 'federicafirrito@gmail.com'),
(7, 'sonno','benedettostraquadanio@gmail.com'),
(2, 'sonno','benedettostraquadanio@gmail.com'),
(1, 'sonno','benedettostraquadanio@gmail.com'),
(5, 'sonno','benedettostraquadanio@gmail.com'),
(9, 'sonno','benedettostraquadanio@gmail.com'),
(10, 'sonno','benedettostraquadanio@gmail.com'),
(3, 'sonno','benedettostraquadanio@gmail.com'),
(10, 'studio', 'annapistorio@gmail.com'),
(6, 'studio', 'annapistorio@gmail.com'),
(3, 'studio', 'annapistorio@gmail.com'),
(1, 'studio', 'annapistorio@gmail.com'),
(2, 'studio', 'annapistorio@gmail.com'),
(4, 'studio', 'annapistorio@gmail.com'),
(1, 'lavoro','federicafirrito@gmail.com'),
(4, 'lavoro','federicafirrito@gmail.com'),
(8, 'lavoro','federicafirrito@gmail.com'),
(10, 'lavoro','federicafirrito@gmail.com'),
(3, 'classica', 'benedettostraquadanio@gmail.com'),
(8, 'classica', 'benedettostraquadanio@gmail.com'),
(9, 'classica', 'benedettostraquadanio@gmail.com'),
(7, 'classica', 'benedettostraquadanio@gmail.com'),
(4, 'classica', 'benedettostraquadanio@gmail.com'),
(10, 'classica', 'benedettostraquadanio@gmail.com'),
(6, 'classica', 'benedettostraquadanio@gmail.com'),
(10, 'amici','annapistorio@gmail.com'),
(1, 'giocare', 'federicafirrito@gmail.com'),
(6, 'giocare', 'federicafirrito@gmail.com'),
(5, 'giocare', 'federicafirrito@gmail.com'),
(4, 'giocare', 'federicafirrito@gmail.com'),
(9, 'giocare', 'federicafirrito@gmail.com'),
(10, 'giocare', 'federicafirrito@gmail.com'),
(7, 'giocare', 'federicafirrito@gmail.com'),
(1, 'lettura', 'annapistorio@gmail.com'),
(2, 'lettura', 'annapistorio@gmail.com'),
(4, 'lettura', 'annapistorio@gmail.com'),
(8, 'lettura', 'annapistorio@gmail.com'),
(9, 'lettura', 'annapistorio@gmail.com'),
(4, 'relazionefinita', 'federicafirrito@gmail.com'),
(7, 'relazionefinita', 'federicafirrito@gmail.com'),
(8, 'relazionefinita', 'federicafirrito@gmail.com'),
(9, 'relazionefinita', 'federicafirrito@gmail.com'),
(3, 'relazionefinita', 'federicafirrito@gmail.com'),
(2, 'relazionefinita', 'federicafirrito@gmail.com'),
(1, 'relazionefinita', 'federicafirrito@gmail.com'),
(10, 'relazionefinita', 'federicafirrito@gmail.com');

-- Anche qui, idMet_Pag è SERIAL, quindi non va specificato manualmente.
-- Dopo l'inserimento, puoi riallineare la sequence con:
-- SELECT setval(pg_get_serial_sequence('"Metodo_Di_Pagamento"', 'idMet_Pag'), 3, true);
INSERT INTO "Metodo_Di_Pagamento"("CVV", "num_carta", "data_scadenza", "email")
VALUES
(123,123145874125,'2024-12-05','annapistorio@gmail.com'),
(456,156423451539,'2023-11-11','benedettostraquadanio@gmail.com'),
(789,752315249854,'2026-05-15','federicafirrito@gmail.com');

INSERT INTO pagamento("idAbbonamento", "data", "email")
VALUES
(1,'2023-02-15','benedettostraquadanio@gmail.com'),
(2,'2023-02-02','annapistorio@gmail.com'),
(3,'2023-02-11','federicafirrito@gmail.com');

INSERT INTO "Riproduzione_Contenuto"("idContenuto", "email", "data")
VALUES
(1,'benedettostraquadanio@gmail.com','2023-02-22'),
(4,'annapistorio@gmail.com','2023-02-04'),
(1,'federicafirrito@gmail.com','2023-02-20'),
(1,'mariorossi@gmail.com','2023-02-06'),
(5,'benedettostraquadanio@gmail.com','2023-02-22');