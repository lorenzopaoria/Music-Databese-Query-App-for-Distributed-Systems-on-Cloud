package com.example;

import com.example.factory.DatabaseProxyFactory;
import com.example.proxy.IDatabaseProxy;
import com.formdev.flatlaf.FlatLightLaf;
import javax.swing.*;
import java.awt.*;
import java.awt.event.*;
import javax.swing.border.EmptyBorder;
import java.awt.datatransfer.StringSelection;
import java.awt.datatransfer.Clipboard;

public class QueryGUI {
    private final IDatabaseProxy databaseProxy;
    private JFrame mainFrame;
    private JTextArea resultArea;
    private JTextField queryField;
    private JTextField emailField;
    private JPasswordField passwordField;

    public QueryGUI() {
        this.databaseProxy = DatabaseProxyFactory.getProxy();
        createLoginFrame();
    }

    private void createLoginFrame() { //creo finestra login
        JFrame loginFrame = new JFrame("Database Login");
        loginFrame.setSize(500, 500); 
        loginFrame.setDefaultCloseOperation(JFrame.EXIT_ON_CLOSE);
        
        JPanel panel = new JPanel(new GridBagLayout());
        GridBagConstraints gbc = new GridBagConstraints();
        gbc.insets = new Insets(5, 5, 5, 5);
    
        ImageIcon logoIcon = new ImageIcon("src\\main\\java\\com\\example\\queryGUI.png"); //logo
        Image image = logoIcon.getImage();
        Image scaledImage = image.getScaledInstance(250, -1, Image.SCALE_SMOOTH); 
        ImageIcon scaledIcon = new ImageIcon(scaledImage); 
        JLabel logoLabel = new JLabel(scaledIcon);
    
        emailField = new JTextField(20);
        passwordField = new JPasswordField(20);
        JButton loginButton = new JButton("Login");
        JLabel statusLabel = new JLabel(" ");
    
        emailField.addKeyListener(new KeyAdapter() { //listener tasto invio
            @Override
            public void keyPressed(KeyEvent e) {
                if (e.getKeyCode() == KeyEvent.VK_ENTER) {
                    passwordField.requestFocus();
                }
            }
        });
    
        passwordField.addKeyListener(new KeyAdapter() {
            @Override
            public void keyPressed(KeyEvent e) {
                if (e.getKeyCode() == KeyEvent.VK_ENTER) {
                    loginButton.doClick();
                }
            }
        });
    
        loginButton.addActionListener(e -> { //bottone di login invio credenziali tramite il proxy
            try {
                String response = databaseProxy.authenticate(
                    emailField.getText(), 
                    new String(passwordField.getPassword())
                );
                
                if (response.startsWith("Authentication successful")) { //login success allora entro nella finestra principale
                    loginFrame.dispose();
                    createMainFrame();
                } else {
                    statusLabel.setText(response);
                }
            } catch (Exception ex) {
                statusLabel.setText("Login failed: " + ex.getMessage());
            }
        });
    
        gbc.gridx = 0; gbc.gridy = 0; gbc.gridwidth = 2; //modificatori per componenti finestre
        gbc.anchor = GridBagConstraints.CENTER; 
        gbc.fill = GridBagConstraints.NONE;
        panel.add(logoLabel, gbc);

        gbc.gridy = 1;
        gbc.gridwidth = 2;
        panel.add(Box.createVerticalStrut(20), gbc);
    
        gbc.gridx = 0; gbc.gridy = 1; gbc.gridwidth = 1;
        panel.add(new JLabel("Email:"), gbc);
        gbc.gridx = 1;
        panel.add(emailField, gbc);
        
        gbc.gridx = 0; gbc.gridy = 2;
        panel.add(new JLabel("Password:"), gbc);
        gbc.gridx = 1;
        panel.add(passwordField, gbc);
    
        gbc.gridx = 1; gbc.gridy = 3;
        panel.add(loginButton, gbc);
        
        gbc.gridy = 4;
        panel.add(statusLabel, gbc);
    
        loginFrame.add(panel);
        loginFrame.setLocationRelativeTo(null);
        loginFrame.setVisible(true);
    }    

    private void createMainFrame() { // creo finestra principale
        mainFrame = new JFrame("Database Query Interface");
        mainFrame.setSize(800, 600);
        mainFrame.setDefaultCloseOperation(JFrame.EXIT_ON_CLOSE);

        queryField = new JTextField();
        resultArea = new JTextArea();
        resultArea.setEditable(false);
        resultArea.setFont(new Font(Font.MONOSPACED, Font.PLAIN, 12));
        
        JButton executeButton = new JButton("Execute Query");
        JButton copyButton = new JButton("Copy Results");
        queryField.addKeyListener(new KeyAdapter() { // listener tasto invio per inviare query tramite metodo
            @Override
            public void keyPressed(KeyEvent e) {
                if (e.getKeyCode() == KeyEvent.VK_ENTER) {
                    executeQuery();
                }
            }
        });

        executeButton.addActionListener(e -> executeQuery()); //tramite bottone
        
        copyButton.addActionListener(e -> { // bottone copia risultati
            StringSelection stringSelection = new StringSelection(resultArea.getText());
            Clipboard clipboard = Toolkit.getDefaultToolkit().getSystemClipboard();
            clipboard.setContents(stringSelection, null);
            JOptionPane.showMessageDialog(mainFrame, "Results copied to clipboard!");
        });

        mainFrame.setLayout(new BorderLayout()); // layout finestra principale
        JPanel topPanel = new JPanel(new BorderLayout());
        JPanel buttonPanel = new JPanel(new FlowLayout(FlowLayout.RIGHT));
        buttonPanel.add(executeButton);
        buttonPanel.add(copyButton);
        
        topPanel.add(queryField, BorderLayout.CENTER);
        topPanel.add(buttonPanel, BorderLayout.EAST);

        JPanel resultPanel = new JPanel(new BorderLayout());
        resultPanel.setBorder(new EmptyBorder(10, 10, 10, 10));
        resultPanel.add(new JScrollPane(resultArea), BorderLayout.CENTER);

        mainFrame.add(topPanel, BorderLayout.NORTH);
        mainFrame.add(resultPanel, BorderLayout.CENTER);

        mainFrame.addWindowListener(new WindowAdapter() {//chiusura finestra chiusura connessione 
            @Override
            public void windowClosing(WindowEvent e) {
                databaseProxy.close();
            }
        });

        mainFrame.setLocationRelativeTo(null);
        mainFrame.setVisible(true);
    }

    private void executeQuery() { //prende la query e la esegue tramite proxy
        String query = queryField.getText();
        if (query.isEmpty()) {
            JOptionPane.showMessageDialog(mainFrame, "Please enter a query");
            return;
        }

        try {
            String result = databaseProxy.executeQuery(query);
            String formattedResult = formatQueryResult(result);
            resultArea.setText(formattedResult);
        } catch (Exception e) {
            JOptionPane.showMessageDialog(mainFrame, "Error executing query: " + e.getMessage());
        }
    }

    private String formatQueryResult(String result) {// formattazione per le query a schermo
        if (result == null || result.isEmpty()) return "";
        
        String[] lines = result.split("\n");
        if (lines.length < 2) return result;

        String[] headers = lines[0].split("\t");
        int[] maxWidths = new int[headers.length];
        for (int i = 0; i < headers.length; i++) {
            maxWidths[i] = headers[i].length();
        }
        for (int i = 1; i < lines.length; i++) {
            String[] cells = lines[i].split("\t");
            for (int j = 0; j < cells.length && j < maxWidths.length; j++) {
                maxWidths[j] = Math.max(maxWidths[j], cells[j].length());
            }
        }
        StringBuilder formatted = new StringBuilder();
        for (int i = 0; i < headers.length; i++) {
            formatted.append(padRight(headers[i], maxWidths[i])).append("  ");
        }
        formatted.append("\n");
        for (int width : maxWidths) {
            formatted.append("-".repeat(width)).append("  ");
        }
        formatted.append("\n");
        for (int i = 1; i < lines.length; i++) {
            String[] cells = lines[i].split("\t");
            for (int j = 0; j < cells.length && j < maxWidths.length; j++) {
                formatted.append(padRight(cells[j], maxWidths[j])).append("  ");
            }
            formatted.append("\n");
        }
        
        return formatted.toString();
    }

    private String padRight(String s, int n) {
        return String.format("%-" + n + "s", s);
    }

    public static void main(String[] args) {
        FlatLightLaf.setup();//tema
        SwingUtilities.invokeLater(() -> new QueryGUI());
    }
}