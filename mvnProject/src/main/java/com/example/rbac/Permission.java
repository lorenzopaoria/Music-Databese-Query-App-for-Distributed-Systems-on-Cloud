package com.example.rbac;

public class Permission {
    private final String operation;
    private final String object;

    public Permission(String operation, String object) {//permesso per una certa operazione su un certo object=table
        this.operation = operation;
        this.object = object;
    }

    @Override
    public boolean equals(Object obj) {//per confronto di due permessi se sono uguali o meno
        if (!(obj instanceof Permission)) return false;
        Permission other = (Permission) obj;//converte object in un istanza di permission
        return operation.equals(other.operation) && object.equals(other.object);
    }
}