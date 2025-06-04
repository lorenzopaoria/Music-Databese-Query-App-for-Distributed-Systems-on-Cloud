USE piattaforma_streaming_musicale;
INSERT INTO utente(`email`, `nome`, `cognome`, `passw`, `tipo`, `num_telefono`, `cf`) 
VALUES 
('margheritaursino@gmail.com', 'margherita', 'ursino', 'marghe02', 0, '3398423455', 'MRGURSN015H865R'),
('benedettostraquadanio@gmail.com', 'benedetto', 'straquadanio', 'bene03', 1, '3397534691', 'BNDT02S1412H534T'),
('mariorossi@gmail.com', 'mario', 'rossi', 'rossi04', 0, '3317212117', 'MRRSSQ86SH152S'),
('annapistorio@gmail.com', 'anna', 'pistorio', 'anna04', 1, '3324621589', 'NPSTRQ99S54H563R'),
('robertarusso@gmail.com', 'roberta', 'russo', 'russo07', 0, '3341256355', 'RBRTRS01F34H154S'),
('federicafirrito@gmail.com', 'federica', 'firrito', 'fede88', 1, '3362145711', 'FDRCFR02S10H163S');

USE piattaforma_streaming_musicale;
INSERT INTO Tipo_Utente(`tipo`)
VALUES 
('premium'),
('premium'),
('premium'),
('free'),
('free'),
('free');

USE piattaforma_streaming_musicale;
INSERT INTO contenuto(`nome`, `duarata`, `riproduzione`, `tipo`) 
VALUES 
('bello', 215, 0, 0),
('podcast tranquillo', 1024, 0, 1),
('another day', 305, 0, 0),
('francesco totti', 252, 0, 0),
('la storia dei DBS', 2052, 0, 1),
('katy', 310, 0, 0),
('rossana', 213, 0, 0),
('tonto', 330, 0, 0),
('muschio', 2215, 0, 1),
('risica', 206, 0, 0);

USE piattaforma_streaming_musicale;
INSERT INTO Crea_Contenuto(`idContenuto`,`nomeArtista`) 
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

USE piattaforma_streaming_musicale;
INSERT INTO Tipo_Contenuto(`idTipoContenuto`,`tipo`)
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

USE piattaforma_streaming_musicale;
INSERT INTO Preferenza_Genere(`email`, `idGenere`)
VALUES
('margheritaursino@gmail.com',  1),
('benedettostraquadanio@gmail.com', 1),
('mariorossi@gmail.com', 3),
('annapistorio@gmail.com', 2),
('robertarusso@gmail.com', 7),
('federicafirrito@gmail.com', 5);

USE piattaforma_streaming_musicale;
INSERT INTO Genere(`idGenere`, `genere`)
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

USE piattaforma_streaming_musicale;
INSERT INTO playlist(`email`, `nomePlaylist`,`num_tracce_P`)
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

USE piattaforma_streaming_musicale;
INSERT INTO Artista(`nomeArtista`) 
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

USE piattaforma_streaming_musicale;
INSERT INTO Appartiene_Genere(`idGenere`, `idContenuto`)
VALUES
(3,1),
(1,2),
(5,3),
(6,4),
(3,5),
(9,6),
(7,9),
(2,7),
(6,8),
(9,10);

USE piattaforma_streaming_musicale;
INSERT INTO Abbonamento(`idAbbonamento`, `tipo`,`email`)
VALUES 
(1,'premium','benedettostraquadanio@gmail.com'),
(2,'premium','federicafirrito@gmail.com'),
(3,'premium','annapistorio@gmail.com'),
(4,'premium','benedettostraquadanio@gmail.com'),
(5,'premium','federicafirrito@gmail.com'),
(6,'premium','benedettostraquadanio@gmail.com'),
(7,'premium','federicafirrito@gmail.com'),
(8,'premium','annapistorio@gmail.com'),
(9,'premium','annapistorio@gmail.com'),
(10,'premium','federicafirrito@gmail.com');

USE piattaforma_streaming_musicale;
INSERT INTO Album(`nomeArtista`, `titolo`,`data_pubblicazione`,`num_tracce`)
VALUES 
('alaimo','DBS', '2006/11/15','15'),
('another love','love','2015/05/22','7'),
('baffo','baffissimo','2001/04/12','15'),
('bello figo gu','erroma','2009/11/15','17'),
('joji','depressione','2008/02/07','4'),
('non rosica','ride bene','2007/01/11','10'),
('perry','horse','2019/12/01','21'),
('perry','dark','2015/05/12','6'),
('toto','pinuccio','1999/06/07','5'),
('tha supreme','3s72r0','2020/10/10','17'),
('joji','nulla','1995/12/12','12'),
('non rosica','chi ride ultimo','2003/06/12','23'),
('joji','per niente','2015/05/17','7'),
('perry','consolation','2009/05/05','6'),
('baffo','pelle','2000/02/02','6'),
('another love','distorsione','2022/12/22','7');

USE piattaforma_streaming_musicale;
INSERT INTO contenuti_playlist(`idContenuto`, `nomePlaylist`, `email`)
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

USE piattaforma_streaming_musicale;
INSERT INTO Metodo_Di_Pagamento(`idMet_Pag`, `CVV`, `num_carta`,`data_scadenza`, `email`)
VALUES 
(1,123,123145874125,'2024/12/05','annapistorio@gmail.com'),
(2,456,156423451539,'2023/11/11','benedettostraquadanio@gmail.com'),
(3,789,752315249854,'2026/05/15','federicafirrito@gmail.com');

USE piattaforma_streaming_musicale;
INSERT INTO pagamento(`idAbbonamento`, `data`, `email`)
VALUES
(1,'2023/02/15','benedettostraquadanio@gmail.com'),
(2,'2023/02/02','annapistorio@gmail.com'),
(3,'2023/02/11','federicafirrito@gmail.com');

USE piattaforma_streaming_musicale;
INSERT INTO Riproduzione_Contenuto(`idContenuto`, `email`, `data`)
VALUES
(1,'benedettostraquadanio@gmail.com','2023/02/22'),
(4,'annapistorio@gmail.com','2023/02/04'),
(1,'federicafirrito@gmail.com','2023/02/20'),
(1,'mariorossi@gmail.com','2023/02/06'),
(5,'benedettostraquadanio@gmail.com','2023/02/22');













