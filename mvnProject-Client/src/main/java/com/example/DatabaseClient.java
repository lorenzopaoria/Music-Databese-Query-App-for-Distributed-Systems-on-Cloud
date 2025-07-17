package com.example;

import java.io.*;
import java.net.Socket;
import java.util.ArrayList;
import java.util.List;
import java.util.Scanner; // Import for reading user input

public class DatabaseClient {
    private static final String SERVER_HOST = "98.84.144.60";
    private static final int SERVER_PORT = 8080;

    private static final List<UserTest> TEST_USERS = new ArrayList<>();
    static {
        TEST_USERS.add(new UserTest("margheritaursino@gmail.com", "marghe02", "free"));
        TEST_USERS.add(new UserTest("annapistorio@gmail.com", "anna04", "premium"));
    }

    private static final List<QueryTest> AUTOMATED_QUERIES = new ArrayList<>();
    static {
        AUTOMATED_QUERIES.add(new QueryTest("SELECT * FROM contenuto LIMIT 5")); // Query SELECT (permessa a tutti)
        AUTOMATED_QUERIES.add(new QueryTest("UPDATE contenuto SET nome = 'Test Title PG' WHERE \"idContenuto\" = 1")); // Query UPDATE (permessa a premium e admin)
        AUTOMATED_QUERIES.add(new QueryTest("INSERT INTO contenuto (nome, durata, riproduzione, tipo) VALUES ('New Song PG', 180, 0, 1)")); // Query INSERT (permessa a admin)
        AUTOMATED_QUERIES.add(new QueryTest("DELETE FROM contenuto WHERE \"idContenuto\" = 1")); // Query DELETE (permessa solo ad admin)
    }

    public static void main(String[] args) {
        // 1. Esegui i test automatici
        System.out.println("--- Starting Automated Tests ---");
        TEST_USERS.forEach(DatabaseClient::runUserScenarioTest);
        System.out.println("\n--- Automated Tests Completed ---");

        // 2. Avvia la sessione interattiva
        System.out.println("\n--- Starting Interactive Session ---");
        runInteractiveSession();
    }

    private static void runUserScenarioTest(UserTest user) {
        System.out.println("\n--- Testing User: " + user.email + " (Role: " + user.role + ") ---");

        try (Socket socket = new Socket(SERVER_HOST, SERVER_PORT);
            ObjectOutputStream output = new ObjectOutputStream(socket.getOutputStream());
            ObjectInputStream input = new ObjectInputStream(socket.getInputStream())) {

            String sessionId = authenticate(output, input, user);
            if (sessionId == null) {
                System.out.println("Authentication failed for " + user.email);
                return;
            }

            AUTOMATED_QUERIES.forEach(query -> testQuery(output, input, sessionId, query, user));

            // Send EXIT command to gracefully close the connection
            output.writeObject("EXIT");
            output.flush();

        } catch (IOException | ClassNotFoundException e) {
            System.err.println("Error during automated test for user " + user.email + ": " + e.getMessage());
        }
    }

    private static String authenticate(ObjectOutputStream output, ObjectInputStream input, UserTest user) throws IOException, ClassNotFoundException {
        output.writeObject("AUTH");
        output.writeObject(user.email);
        output.writeObject(user.password);
        output.flush();

        String authResponse = (String) input.readObject();
        System.out.println("Authentication Result: " + authResponse);

        if (authResponse.startsWith("Authentication successful")) {
            return authResponse.split(":")[1].trim();
        }
        return null;
    }

    private static void testQuery(ObjectOutputStream output, ObjectInputStream input, String sessionId, QueryTest query, UserTest user) {
        try {
            output.writeObject("QUERY");
            output.writeObject(sessionId);
            output.writeObject(query.sql);
            output.flush();

            String queryResult = (String) input.readObject();
            boolean isExpectedAllowed;

            // Determina il permesso atteso in base al ruolo dell'utente e al tipo di query
            String trimmedSql = query.sql.trim().toUpperCase();
            if (user.role.equals("admin")) {
                isExpectedAllowed = true; // Admin può eseguire tutte le query
            } else if (user.role.equals("premium")) {
                // Premium può eseguire SELECT, UPDATE e INSERT. DELETE non è permesso.
                isExpectedAllowed = trimmedSql.startsWith("SELECT") || trimmedSql.startsWith("UPDATE") || trimmedSql.startsWith("INSERT");
            } else { // Utenti "free"
                isExpectedAllowed = trimmedSql.startsWith("SELECT"); // Free può eseguire solo SELECT
            }

            boolean actuallyAllowed = !queryResult.contains("Access denied"); // Verifica se il server ha effettivamente permesso l'accesso

            System.out.println("\nQuery Test:");
            System.out.println("SQL: " + query.sql);
            System.out.println("Ruolo Utente: " + user.role);
            System.out.println("Permesso Atteso (basato sulla logica del ruolo): " + isExpectedAllowed);
            System.out.println("Risultato Query: " + queryResult);
            System.out.println("Verifica Permesso: " +
                    (isExpectedAllowed == actuallyAllowed ? "PASS" : "FAIL"));

        } catch (IOException | ClassNotFoundException e) {
            System.err.println("Error during query test for user " + user.email + ", query: " + query.sql + ": " + e.getMessage());
            // e.printStackTrace(); // Rimuovi o commenta in produzione per output più pulito
        }
    }

    // --- Sezione per la sessione interattiva ---
    private static void runInteractiveSession() {
        Scanner scanner = new Scanner(System.in);
        String userEmail = null;
        String userPassword = null;
        String userRole = null; // Il ruolo verrà determinato dopo l'autenticazione, se il server lo restituisce

        System.out.print("Enter your email: ");
        userEmail = scanner.nextLine();
        System.out.print("Enter your password: ");
        userPassword = scanner.nextLine(); // Consider using Console for password input in a real app (hides input)

        UserTest interactiveUser = new UserTest(userEmail, userPassword, "unknown"); // Ruolo 'unknown' per l'autenticazione iniziale

        try (Socket socket = new Socket(SERVER_HOST, SERVER_PORT);
            ObjectOutputStream output = new ObjectOutputStream(socket.getOutputStream());
            ObjectInputStream input = new ObjectInputStream(socket.getInputStream())) {

            // Tentativo di autenticazione per l'utente interattivo
            System.out.println("\nAttempting interactive login...");
            output.writeObject("AUTH");
            output.writeObject(interactiveUser.email);
            output.writeObject(interactiveUser.password);
            output.flush();

            String authResponse = (String) input.readObject();
            System.out.println("Authentication Result: " + authResponse);

            String sessionId = null;
            if (authResponse.startsWith("Authentication successful")) {
                sessionId = authResponse.split(":")[1].trim(); // Estrai la sessionId
                // Se il server restituisce anche il ruolo, puoi parsing qui
                // Esempio: "Authentication successful: sessionId: role"
                if (authResponse.contains("role:")) { // Aggiungi questa parte se il tuo server restituisce il ruolo
                    userRole = authResponse.split("role:")[1].trim();
                } else {
                    // Se il server non restituisce il ruolo, potresti doverlo recuperare in altro modo o usarne uno predefinito
                    // Per questo esempio, se non c'è il ruolo, assumiamo che l'utente sia un 'premium' per la logica dei permessi
                    // In una vera applicazione, il ruolo dovrebbe essere confermato dal server.
                    userRole = "premium"; // Default o richiedi all'utente
                }
                interactiveUser.role = userRole; // Aggiorna il ruolo dell'oggetto UserTest

                System.out.println("Login successful. Session ID: " + sessionId);
                System.out.println("You can now enter SQL queries. Type 'exit' to quit.");

                String userInputQuery;
                while (true) {
                    System.out.print("Enter SQL query: ");
                    userInputQuery = scanner.nextLine();

                    if (userInputQuery.equalsIgnoreCase("exit")) {
                        System.out.println("Exiting interactive session.");
                        // Send EXIT command to server
                        output.writeObject("EXIT");
                        output.flush();
                        break;
                    }

                    // Esegui la query
                    try {
                        output.writeObject("QUERY");
                        output.writeObject(sessionId);
                        output.writeObject(userInputQuery);
                        output.flush();

                        String queryResult = (String) input.readObject();
                        
                        // Per la sessione interattiva, mostriamo semplicemente il risultato e se l'accesso è stato negato
                        System.out.println("Query Result: " + queryResult);
                        if (queryResult.contains("Access denied")) {
                            System.out.println("Permission Denied: The server denied access for this query.");
                        }

                    } catch (IOException | ClassNotFoundException e) {
                        System.err.println("Error sending/receiving query: " + e.getMessage());
                        // e.printStackTrace();
                    }
                }

            } else {
                System.out.println("Interactive login failed. Please check your credentials.");
            }

        } catch (IOException | ClassNotFoundException e) {
            System.err.println("Error during interactive session: " + e.getMessage());
            // e.printStackTrace();
        } finally {
            scanner.close(); // Chiudi lo scanner alla fine della sessione
        }
    }

    private static class UserTest {
        String email;
        String password;
        String role; // Il ruolo è importante per la logica di test lato client

        UserTest(String email, String password, String role) {
            this.email = email;
            this.password = password;
            this.role = role;
        }
    }

    private static class QueryTest {
        String sql;

        QueryTest(String sql) {
            this.sql = sql;
        }
    }
}