package com.example.dao;

import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;

public class UserDAO {
    private final Connection connection;

    public UserDAO(Connection connection) {
        this.connection = connection;//inzializza connessione
    }

    public String authenticate(String email, String password) throws SQLException {//metodo di autenticazione
        String query =  "SELECT u.tipo \n" +
                        "FROM Utente u \n" +
                        "WHERE u.email = ? AND u.passw = ?";
        try (PreparedStatement stmt = connection.prepareStatement(query)) {//preparedstatement per evitare SQL injection
            stmt.setString(1, email);
            stmt.setString(2, password);
            ResultSet rs = stmt.executeQuery();
            if (rs.next()) {
                int tipoUtente = rs.getString("tipo");
                return tipoUtente == 0 ? "free" : "premium";
            }
            return null;
        }
    }

    public String executeQuery(String query) throws SQLException {//metodo per eseguire le queries
        try (PreparedStatement stmt = connection.prepareStatement(query)) {
            boolean isSelect = query.trim().toUpperCase().startsWith("SELECT");
            if (isSelect) {
                ResultSet rs = stmt.executeQuery();
                return formatResultSet(rs);
            } else {
                int rowsAffected = stmt.executeUpdate();
                return rowsAffected + " rows affected";
            }
        }
    }

    private String formatResultSet(ResultSet rs) throws SQLException {//metodo per il formattamento dei risultati
        StringBuilder result = new StringBuilder();
        int columnCount = rs.getMetaData().getColumnCount();
        
        for (int i = 1; i <= columnCount; i++) {
            result.append(rs.getMetaData().getColumnName(i)).append("\t");
        }
        result.append("\n");

        while (rs.next()) {
            for (int i = 1; i <= columnCount; i++) {
                result.append(rs.getString(i)).append("\t");
            }
            result.append("\n");
        }
        return result.toString();
    }
}