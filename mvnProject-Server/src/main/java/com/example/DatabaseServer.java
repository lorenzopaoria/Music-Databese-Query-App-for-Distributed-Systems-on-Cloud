package com.example;

import com.example.rbac.Role;
import com.example.rbac.Permission;
import com.example.session.Session;
import com.example.dao.UserDAO;
import com.example.factory.DatabaseFactory;
import java.io.*;
import java.net.*;
import java.sql.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.logging.Level;
import java.util.logging.Logger;

public class DatabaseServer {
    private static final int PORT = 8080;
    private static final Logger LOGGER = Logger.getLogger(DatabaseServer.class.getName());//loggin tramite libreria stampo su terminale
    private final Map<String, Session> sessions = new ConcurrentHashMap<>();//mappa sessioni usata per i thread
    private final Map<String, Role> roles = new HashMap<>();//mappa ruoli disponibili
    private final ExecutorService threadPool;
    private final UserDAO userDAO; //per accesso ai dati utente
    private ServerSocket serverSocket;
    private boolean running;

    public DatabaseServer() {
        this.threadPool = Executors.newCachedThreadPool();//una pool di thread dinamica
        this.userDAO = new UserDAO(DatabaseFactory.getConnection());//crea connessione al database tramite il databaseFactory
        initializeRoles();
    }

    public static void main(String[] args) {
        LOGGER.info("Starting Database Server...");
        DatabaseServer server = new DatabaseServer();
        server.start();//avvio server
    }

    public void start() {
        try {
            serverSocket = new ServerSocket(PORT);//crea socket su porta specificata
            running = true;
            LOGGER.info("Server listening on port " + PORT);

            while (running) {
                try {
                    Socket clientSocket = serverSocket.accept();
                    LOGGER.info("New client connected: " + clientSocket.getInetAddress());
                    ClientHandler handler = new ClientHandler(clientSocket, this);//per ogni nuova connessione crea un clienthandler
                    threadPool.execute(handler);// e lo esegue in un thread nuovo
                } catch (IOException e) {
                    if (running) {
                        LOGGER.log(Level.SEVERE, "Error accepting client connection", e);
                    }
                }
            }
        } catch (IOException e) {
            LOGGER.log(Level.SEVERE, "Could not listen on port " + PORT, e);
        } finally {
            shutdown();
        }
    }

    public void shutdown() {
        running = false;
        try {
            if (serverSocket != null && !serverSocket.isClosed()) {
                serverSocket.close();//chiude socket
            }
            threadPool.shutdown();//chiude pool di thread
            if (!threadPool.awaitTermination(60, TimeUnit.SECONDS)) {
                threadPool.shutdownNow();//se il thread resta inattivo per piu di 60 secondi viene arrestato
            }
            DatabaseFactory.getConnection().close();//chiusura connessione al db
            LOGGER.info("Audit logger closed.");
        } catch (Exception e) {
            LOGGER.log(Level.SEVERE, "Error during server shutdown", e);
            threadPool.shutdownNow();
        }
    }
    

    public Role getRole(String roleName) {
        return roles.get(roleName);
    }

    public void addSession(Session session) {
        sessions.put(session.getSessionId(), session);
    }

    public Session getSession(String sessionId) {
        return sessions.get(sessionId);
    }//metodi get fatti per aspectlog

    private void initializeRoles() {//inizializzazione ruoli con permessi
        Role adminRole = new Role("admin");
        adminRole.addPermission(new Permission("SELECT", "*"));
        adminRole.addPermission(new Permission("INSERT", "*"));
        adminRole.addPermission(new Permission("UPDATE", "*"));
        adminRole.addPermission(new Permission("DELETE", "*"));
        adminRole.addPermission(new Permission("CREATE", "*"));
        adminRole.addPermission(new Permission("DROP", "*"));
        roles.put("admin", adminRole);

        Role premiumRole = new Role("premium");
        premiumRole.addPermission(new Permission("SELECT", "*"));
        premiumRole.addPermission(new Permission("INSERT", "*"));
        premiumRole.addPermission(new Permission("UPDATE", "*"));
        roles.put("premium", premiumRole);

        Role freeRole = new Role("free");
        freeRole.addPermission(new Permission("SELECT", "*"));
        roles.put("free", freeRole);
    }

    public class ClientHandler implements Runnable {
        private final Socket socket;
        private final DatabaseServer server;
        private ObjectInputStream input;
        private ObjectOutputStream output;
        @SuppressWarnings("unused")
        private Session session;
        private String clientId;

        public ClientHandler(Socket socket, DatabaseServer server) {
            this.socket = socket;
            this.server = server;
            this.clientId = UUID.randomUUID().toString().substring(0, 8);
        }

        private String currentUserRole;
        private String result;

        public String getClientId() {
            return this.clientId;
        }

        public String getCurrentUserRole() {
            return this.currentUserRole;
        }

        public String getResult() {
            return this.result;
        }

        @Override
        public void run() {
            try {
                input = new ObjectInputStream(socket.getInputStream());
                output = new ObjectOutputStream(socket.getOutputStream());

                while (true) {
                    String command = (String) input.readObject();
                    switch (command) {
                        case "AUTH":
                            handleAuthentication();//gestisce autenticazione
                            break;
                        case "QUERY":
                            handleQuery();//gestisce esecuzione query
                            break;
                        case "EXIT":
                            return;//esce quando il client si disconnette
                    }
                }
            } catch (IOException | ClassNotFoundException e) {
                LOGGER.log(Level.SEVERE, "Error handling client connection", e);
            } finally {
                try {
                    socket.close();
                } catch (IOException e) {
                    LOGGER.log(Level.WARNING, "Error closing client socket", e);
                }
            }
        }

        private void handleAuthentication() throws IOException, ClassNotFoundException {
            String email = (String) input.readObject();
            String password = (String) input.readObject();
        
            try {
                String userRole = userDAO.authenticate(email, password);
                if (userRole != null) {
                    this.currentUserRole = userRole;  // imposta il ruolo dell'utente
                    Session newSession = new Session(email);
                    newSession.activate(server.getRole(userRole));//attiva sessione con ruolo utente corretto
                    server.addSession(newSession);
                    session = newSession;
                    output.writeObject("Authentication successful:" + newSession.getSessionId());
                } else {
                    output.writeObject("Authentication failed");
                }
            } catch (SQLException e) {
                LOGGER.log(Level.SEVERE, "Authentication error", e);
                output.writeObject("Authentication error: " + e.getMessage());
            }
            output.flush();
        }
        
        private void handleQuery() throws IOException, ClassNotFoundException {
            String sessionId = (String) input.readObject();
            String query = (String) input.readObject();
        
            Session session = server.getSession(sessionId);
            if (session == null || session.isExpired()) {//caso base sessione scaduta
                result = "Session expired"; 
                output.writeObject(result);
                output.flush();
                return;
            }
        
            try {
                if (validateQueryPermissions(query, session.getActiveRoles())) {//prima controllo se posso eseguire, se posso allora la eseguo
                    result = userDAO.executeQuery(query);
                    output.writeObject(result);
                } else {
                    result = "Access denied: Insufficient permissions";
                    output.writeObject(result);
                }
            } catch (SQLException e) {
                LOGGER.log(Level.SEVERE, "Query execution error", e);
                result = "Query execution error: " + e.getMessage();
                output.writeObject(result);
            }
            output.flush();
        }
        

        private boolean validateQueryPermissions(String query, Set<Role> roles) {// controlla se la query può essere eseguita con i permessi impostati
            String operation = extractOperation(query);//estrare operazione
            String object = extractObject(query);//estrae oggetto

            return roles.stream()//controllo se almeno un ruole dell'utente ha i permessi necessari a eseguire la query
                .anyMatch(role -> role.hasPermission(new Permission(operation, object)) ||
                                role.hasPermission(new Permission(operation, "*")));
        }

        private String extractOperation(String query) {//estrae operazione e formatta
            String upperQuery = query.trim().toUpperCase();
            return upperQuery.split("\\s+")[0];
        }

        private String extractObject(String query) {//estrae oggetto e formatta
            String upperQuery = query.trim().toUpperCase();
            String[] parts = upperQuery.split("\\s+");
            for (int i = 0; i < parts.length; i++) {//cerca parola chiave per tabella e restiruisce il nome di riferimento
                if (parts[i].equals("FROM") || parts[i].equals("INTO") || 
                    parts[i].equals("UPDATE")) {
                    return parts[i + 1];//restiruisce la tabella associata all'operazione
                }
            }
            return "*";//altrimenti resturisce tutto
        }
    }
}



