package com.example.session;

import com.example.rbac.Role;
import java.util.*;
import java.time.LocalDateTime;

public class Session {
    private final String sessionId;
    private final String userId;
    private final Set<Role> activeRoles;
    private LocalDateTime lastAccessTime;
    private static final int SESSION_TIMEOUT_MINUTES = 5;//session timeout

    public String getUserId() {
        return userId;
    }

    public Session(String userId) {//crea sessione per un utente
        this(userId, UUID.randomUUID().toString());//genera sessionId usando UUID
    }

    public Session(String userId, String sessionId) {//inizializzazione di una sessione con un insieme di ruoli
        this.userId = userId;
        this.sessionId = sessionId;
        this.activeRoles = new HashSet<>();
        updateLastAccessTime();//aggiorno tempo di accesso
    }

    public void activate(Role role) {
        activeRoles.add(role);
        updateLastAccessTime();
    }

    public Set<Role> getActiveRoles() {
        updateLastAccessTime();
        return Collections.unmodifiableSet(activeRoles);
    }

    public boolean isExpired() {//controlla se la sessione è scaduta
        return LocalDateTime.now().minusMinutes(SESSION_TIMEOUT_MINUTES)
                .isAfter(lastAccessTime);
    }

    private void updateLastAccessTime() {
        lastAccessTime = LocalDateTime.now();
    }

    public String getSessionId() {
        return sessionId;
    }
}