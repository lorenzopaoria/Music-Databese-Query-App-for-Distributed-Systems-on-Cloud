package com.example.factory;

import com.example.config.DatabaseConfig;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.SQLException;

public class DatabaseFactory {
    private static Connection connection;

    public static Connection getConnection() {
        if (connection == null) {
            try {
                connection = DriverManager.getConnection(//connessione configurata tramite i parametri passati da databaseConfig
                    DatabaseConfig.getDatabaseUrl(),
                    DatabaseConfig.getDatabaseUser(),
                    DatabaseConfig.getDatabasePassword()
                );
            } catch (SQLException e) {
                throw new RuntimeException("Failed to create database connection", e);
            }
        }
        return connection;
    }
}