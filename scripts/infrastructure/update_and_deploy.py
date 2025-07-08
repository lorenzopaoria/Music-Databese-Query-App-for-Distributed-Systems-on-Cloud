#!/usr/bin/env python3
"""
Script per aggiornare le configurazioni locali e avviare il deploy automatico.
Questo script combina l'update delle configurazioni locali con il push automatico.
"""

import os
import subprocess
import json
import sys
from pathlib import Path

def run_command(cmd, description="", check=True):
    """Esegue un comando e mostra il risultato."""
    print(f"🔄 {description}")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=check)
        if result.stdout:
            print(f"✅ {result.stdout}")
        return result
    except subprocess.CalledProcessError as e:
        print(f"❌ Errore: {e}")
        print(f"Stdout: {e.stdout}")
        print(f"Stderr: {e.stderr}")
        if check:
            raise

def check_deploy_config():
    """Verifica che esista il file di configurazione del deploy."""
    config_path = Path("deploy_config.json")
    if not config_path.exists():
        print("❌ File 'deploy_config.json' non trovato!")
        print("Devi prima eseguire il deploy iniziale con 'python scripts/infrastructure/deploy_music_app.py'")
        return False
    
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        required_keys = ['server_public_ip', 'rds_endpoint', 'db_username', 'db_password', 'db_name']
        missing_keys = [key for key in required_keys if key not in config]
        
        if missing_keys:
            print(f"❌ Chiavi mancanti nel file di configurazione: {missing_keys}")
            return False
        
        print("✅ File di configurazione valido trovato")
        print(f"   - Server IP: {config['server_public_ip']}")
        print(f"   - RDS Endpoint: {config['rds_endpoint']}")
        print(f"   - Database: {config['db_name']}")
        return True
    except Exception as e:
        print(f"❌ Errore nella lettura del file di configurazione: {e}")
        return False

def update_local_configs():
    """Aggiorna le configurazioni locali usando lo script esistente."""
    script_path = Path("scripts/infrastructure/update_java_config_on_ec2.py")
    if not script_path.exists():
        print("❌ Script 'update_java_config_on_ec2.py' non trovato!")
        return False
    
    try:
        print("🔄 Aggiornamento delle configurazioni locali...")
        result = run_command(f"python {script_path}", "Aggiornamento configurazioni Java")
        return True
    except Exception as e:
        print(f"❌ Errore nell'aggiornamento delle configurazioni: {e}")
        return False

def git_status():
    """Controlla lo stato del repository Git."""
    try:
        result = run_command("git status --porcelain", "Controllo stato Git", check=False)
        if result.stdout.strip():
            print("📝 File modificati trovati:")
            print(result.stdout)
            return True
        else:
            print("ℹ️  Nessuna modifica da committare")
            return False
    except Exception as e:
        print(f"❌ Errore nel controllo dello stato Git: {e}")
        return False

def git_commit_and_push():
    """Esegue commit e push delle modifiche."""
    try:
        # Aggiungi tutti i file modificati
        run_command("git add .", "Aggiunta file modificati")
        
        # Commit con messaggio descrittivo
        commit_message = "Update: Aggiornamento configurazioni per deploy automatico"
        run_command(f'git commit -m "{commit_message}"', "Commit modifiche")
        
        # Push al repository remoto
        run_command("git push", "Push al repository remoto")
        
        print("✅ Modifiche committate e pushate con successo!")
        return True
    except subprocess.CalledProcessError as e:
        if "nothing to commit" in str(e.stdout):
            print("ℹ️  Nessuna modifica da committare")
            return True
        else:
            print(f"❌ Errore nel commit/push: {e}")
            return False

def check_github_secrets():
    """Verifica che i secrets GitHub siano configurati."""
    print("ℹ️  Assicurati che i seguenti secrets siano configurati su GitHub:")
    print("   - DOCKER_USERNAME")
    print("   - DOCKER_PASSWORD")
    print("   - EC2_HOST")
    print("   - EC2_SSH_KEY")
    print("   Puoi verificarli in: Settings > Secrets and variables > Actions")

def main():
    """Funzione principale."""
    print("🚀 Script di Update e Deploy Automatico")
    print("=" * 50)
    
    # Verifica che siamo nella directory corretta
    if not Path("deploy_config.json").exists() and not Path("scripts/infrastructure").exists():
        print("❌ Esegui questo script dalla root del progetto!")
        sys.exit(1)
    
    # 1. Verifica configurazione del deploy
    if not check_deploy_config():
        sys.exit(1)
    
    # 2. Aggiorna le configurazioni locali
    if not update_local_configs():
        print("❌ Errore nell'aggiornamento delle configurazioni locali")
        sys.exit(1)
    
    # 3. Controlla se ci sono modifiche da committare
    has_changes = git_status()
    
    if has_changes:
        # 4. Commit e push
        if git_commit_and_push():
            print("\n🎉 Deploy automatico avviato!")
            print("📍 La GitHub Action si occuperà di:")
            print("   1. Build dell'immagine Docker")
            print("   2. Push su DockerHub")
            print("   3. Deploy sull'istanza EC2")
            print("   4. Restart del container")
            print("\n🔍 Monitora il progresso in:")
            print("   https://github.com/TUO_USERNAME/TUO_REPO/actions")
        else:
            print("❌ Errore nel commit/push")
            sys.exit(1)
    else:
        print("ℹ️  Nessuna modifica da deployare")
    
    # 5. Informazioni sui secrets
    print("\n" + "=" * 50)
    check_github_secrets()
    
    print("\n✅ Processo completato!")

if __name__ == "__main__":
    main()
