package com.example.proxy;

import com.example.session.Session;
import java.io.*;
import java.net.Socket;

public class DatabaseProxy implements IDatabaseProxy {
    private Session session;
    private Socket socket;
    private ObjectOutputStream output;
    private ObjectInputStream input;
    private final String serverHost;
    private final int serverPort;

    public DatabaseProxy(String serverHost, int serverPort) {//costruttore per la connessione
        this.serverHost = serverHost;
        this.serverPort = serverPort;
        connect();
    }

    private void connect() {//metodo per la connessione
        try {
            socket = new Socket(serverHost, serverPort);
            output = new ObjectOutputStream(socket.getOutputStream());
            input = new ObjectInputStream(socket.getInputStream());
        } catch (IOException e) {
            throw new RuntimeException("Failed to connect to server", e);
        }
    }

    public String authenticate(String email, String password) throws IOException, ClassNotFoundException {//metodo per l'autenticazione
        output.writeObject("AUTH");
        output.writeObject(email);
        output.writeObject(password);
        output.flush();
        
        String response = (String) input.readObject();
        if (response.startsWith("Authentication successful")) {
            String[] parts = response.split(":");
            if (parts.length == 2) {
                String sessionId = parts[1].trim();
                session = new Session(email, sessionId);
                return "Authentication successful";
            }
        }
        return response;
    }
    
    public String executeQuery(String query) throws IOException, ClassNotFoundException {//metodo per esecuzione delle queries
        if (session == null || session.isExpired()) {
            throw new SecurityException("Session expired");
        }
        
        output.writeObject("QUERY");
        output.writeObject(session.getSessionId());
        output.writeObject(query);
        output.flush();
        
        return (String) input.readObject();
    }

    public void close() {
        try {
            if (socket != null && !socket.isClosed()) {
                output.writeObject("EXIT");
                output.flush();
                socket.close();
            }
        } catch (IOException e) {
            throw new SecurityException("Error closing socket", e);
        }
    }
}