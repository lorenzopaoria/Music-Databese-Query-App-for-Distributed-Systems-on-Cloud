package com.example.factory;

import com.example.proxy.DatabaseProxy;
import com.example.proxy.IDatabaseProxy;
import com.example.config.DatabaseConfig;

public class DatabaseProxyFactory {
    private static IDatabaseProxy instance;

    public static IDatabaseProxy getProxy() { // interfaccia come tipo di ritorno
        if (instance == null) {
            instance = new DatabaseProxy(DatabaseConfig.getServerHost(), DatabaseConfig.getServerPort());
        }
        return instance;
    }
}
