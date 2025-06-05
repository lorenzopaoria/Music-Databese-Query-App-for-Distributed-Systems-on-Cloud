package com.example.logging;

import org.aspectj.lang.JoinPoint;
import org.aspectj.lang.annotation.AfterReturning;
import org.aspectj.lang.annotation.Aspect;
import org.aspectj.lang.annotation.Before;
import org.aspectj.lang.annotation.Pointcut;

@Aspect
public class DatabaseAuditAspect {
    private final DatabaseAuditLogger auditLogger = DatabaseAuditLogger.getInstance();//instanza per chiamare funzioni di scrittura
    private final ThreadLocal<AuthContext> authContextHolder = new ThreadLocal<>();//contesti di autentificazione e query per thread in modo da gestire il servizio multithread
    private final ThreadLocal<QueryContext> queryContextHolder = new ThreadLocal<>();

    private static class AuthContext {
        String clientId;
        String sessionId;
        String email;
    }

    private static class QueryContext {
        String sessionId;
        String query;
    }

    //Pointcut che intercetta la chiamata al metodo readObject() della classe ObjectInputStream, usato nel contesto di autenticazione
    @Pointcut("call(* java.io.ObjectInputStream.readObject()) && within(com.example.DatabaseServer.ClientHandler)")
    public void readObjectPointcut() {}

    // Pointcut che intercetta l'esecuzione del metodo handleAuthentication(
    @Pointcut("execution(* com.example.DatabaseServer.ClientHandler.handleAuthentication())")
    public void authenticationPointcut() {}

    // Pointcut che intercetta l'esecuzione del metodo handleQuery()
    @Pointcut("execution(* com.example.DatabaseServer.ClientHandler.handleQuery())")
    public void queryPointcut() {}

    // Prima dell'autenticazione, inizializza il contesto di autenticazione
    @Before("authenticationPointcut()")

    public void beforeAuthentication(JoinPoint joinPoint) {
        AuthContext context = new AuthContext();
        context.clientId = ((com.example.DatabaseServer.ClientHandler) joinPoint.getTarget()).getClientId();
        authContextHolder.set(context);
    }

    // Dopo aver letto i dati di autenticazione, aggiorna il contesto
    @AfterReturning(
        pointcut = "readObjectPointcut() && withincode(* handleAuthentication())",
        returning = "result"
    )

    public void afterReadAuthData(JoinPoint joinPoint, Object result) {
        if (result instanceof String) {
            AuthContext context = authContextHolder.get();
            if (context != null) {
                if (context.email == null) {
                    context.email = (String) result;
                }
            }
        }
    }

    // Prima di eseguire la query, inizializza il contesto per la query
    @Before("queryPointcut()")
    public void beforeQuery(JoinPoint joinPoint) {
        QueryContext context = new QueryContext();
        queryContextHolder.set(context);
    }

    // Dopo aver letto i dati della query, aggiorna il contesto della query
    @AfterReturning(
        pointcut = "readObjectPointcut() && withincode(* handleQuery())",
        returning = "result"
    )

    public void afterReadQueryData(JoinPoint joinPoint, Object result) {
        if (result instanceof String) {
            QueryContext context = queryContextHolder.get();
            if (context != null) {
                if (context.sessionId == null) {
                    context.sessionId = (String) result;
                } else if (context.query == null) {
                    context.query = (String) result;
                }
            }
        }
    }

    // Dopo l'autenticazione, esegue il log delle informazioni relative all'autenticazione
    @AfterReturning(
    pointcut = "authenticationPointcut()",
    returning = "result"
    )

    public void afterAuthentication(JoinPoint joinPoint, Object result) {
        AuthContext context = authContextHolder.get();
        if (context != null) {
            com.example.DatabaseServer.ClientHandler handler = (com.example.DatabaseServer.ClientHandler) joinPoint.getTarget();
            
            String currentRole = handler.getCurrentUserRole();
            boolean success = currentRole != null;
            
            auditLogger.logAuthentication(
                context.clientId,
                context.sessionId,
                context.email,
                currentRole,
                success
            );
            authContextHolder.remove();
        }
    }

    // Dopo l'esecuzione della query, esegue il log delle informazioni relative all'esecuzione della query
    @AfterReturning(
    pointcut = "queryPointcut()",
    returning = "result"
    )

    public void afterQuery(JoinPoint joinPoint, Object result) {
        QueryContext context = queryContextHolder.get();
        if (context != null) {
            com.example.DatabaseServer.ClientHandler handler = (com.example.DatabaseServer.ClientHandler) joinPoint.getTarget();
            
            String currentResult = handler.getResult();
            boolean success = !currentResult.equals("Access denied: Insufficient permissions") && !currentResult.startsWith("Query execution error:");

            auditLogger.logQuery(
                context.sessionId,
                context.query,
                success
            );
            queryContextHolder.remove();
        }
    }
}