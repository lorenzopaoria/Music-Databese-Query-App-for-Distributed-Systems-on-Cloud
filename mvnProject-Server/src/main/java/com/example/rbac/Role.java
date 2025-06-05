package com.example.rbac;

import java.util.List;
import java.util.ArrayList;

public class Role {
    private String name;
    private List<Permission> permissions;

    public Role(String name) {
        this.name = name;
        this.permissions = new ArrayList<>();//array di permessi per un determinato ruolo
    }

    public void addPermission(Permission permission) {//aggiunge permesso
        permissions.add(permission);
    }

    public boolean hasPermission(Permission permission) {//controlla esistenza permesso
        return permissions.contains(permission);
    }

    public String name() {//resistuisce nome di ruolo
        return name;
    }
}