package com.example.proxy;

import java.io.IOException;

public interface IDatabaseProxy {
    String authenticate(String email, String password) throws IOException, ClassNotFoundException;
    String executeQuery(String query) throws IOException, ClassNotFoundException;
    void close();
}
