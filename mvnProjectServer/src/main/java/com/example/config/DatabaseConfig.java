package com.example.config;

import java.io.FileInputStream;
import java.io.IOException;
import java.util.Properties;

public class DatabaseConfig {
    private static final String CONFIG_FILE = "database.properties";
    private static Properties properties;

    static {
        properties = new Properties();
        try (FileInputStream fis = new FileInputStream(CONFIG_FILE)) {//prende dal file la configurazione
            properties.load(fis);
        } catch (IOException e) {
            // per vedere se funziona intanto
            properties.setProperty("server.host", "127.0.0.1");
            properties.setProperty("server.port", "12345");
            properties.setProperty("database.url", "jdbc:mysql://localhost:3306/piattaforma_streaming_musicale");
            properties.setProperty("database.user", "root");
            properties.setProperty("database.password", "");
        }
    }

    public static String getServerHost() {
        return properties.getProperty("server.host");
    }

    public static int getServerPort() {
        return Integer.parseInt(properties.getProperty("server.port"));
    }

    public static String getDatabaseUrl() {
        return properties.getProperty("database.url");
    }

    public static String getDatabaseUser() {
        return properties.getProperty("database.user");
    }

    public static String getDatabasePassword() {
        return properties.getProperty("database.password");
    }
}