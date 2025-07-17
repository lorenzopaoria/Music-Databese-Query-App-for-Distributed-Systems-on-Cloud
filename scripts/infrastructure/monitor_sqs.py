import boto3
import json
import time
import datetime
from botocore.exceptions import ClientError

REGION = 'us-east-1'
QUEUE_NAME = 'musicapp-sns-logging-queue'

def format_timestamp(timestamp_str):

    if not timestamp_str:
        return "N/A"
    try:
        dt = datetime.datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d %H:%M:%S UTC')
    except:
        return timestamp_str

def read_and_display_messages(sqs_client, queue_url, processed_messages, is_existing=False):
    try:
        response = sqs_client.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=10,
            WaitTimeSeconds=20 if not is_existing else 2,  # Breve attesa anche per messaggi esistenti
            AttributeNames=['All'],
            MessageAttributeNames=['All']
        )
        
        messages = response.get('Messages', [])
        new_messages = []
        
        for message in messages:
            message_id = message.get('MessageId')
            if message_id not in processed_messages:
                try:
                    sns_message = json.loads(message['Body'])
                    log_entry = {
                        'timestamp': sns_message.get('Timestamp'),
                        'message_id': sns_message.get('MessageId'),
                        'subject': sns_message.get('Subject'),
                        'message': sns_message.get('Message'),
                        'topic_arn': sns_message.get('TopicArn'),
                        'type': sns_message.get('Type'),
                        'receipt_handle': message['ReceiptHandle']
                    }
                    new_messages.append(log_entry)
                    processed_messages.add(message_id)
                    
                    # Mostra il messaggio
                    timestamp = format_timestamp(log_entry['timestamp'])
                    if is_existing:
                        print(f"\n[EXISTING] MESSAGGIO - {timestamp}")
                        print(f"           Subject: {log_entry['subject'] or 'N/A'}")
                        print(f"           Message: {log_entry['message'][:150]}{'...' if len(log_entry['message'] or '') > 150 else ''}")
                        print(f"           Topic: {log_entry['topic_arn'].split(':')[-1] if log_entry['topic_arn'] else 'N/A'}")
                    else:
                        print(f"\n[NEW] NUOVO MESSAGGIO - {timestamp}")
                        print(f"      Subject: {log_entry['subject'] or 'N/A'}")
                        print(f"      Message: {log_entry['message'][:150]}{'...' if len(log_entry['message'] or '') > 150 else ''}")
                        print(f"      Topic: {log_entry['topic_arn'].split(':')[-1] if log_entry['topic_arn'] else 'N/A'}")
                    print("-" * 60)
                    
                except json.JSONDecodeError:
                    print(f"[WARNING] Messaggio non JSON ricevuto: {message['Body'][:100]}...")
        
        return new_messages
        
    except Exception as e:
        print(f"[ERROR] Errore lettura coda: {e}")
        return []

def monitor_queue():
    try:
        sqs_client = boto3.client('sqs', region_name=REGION)
        queue_url = sqs_client.get_queue_url(QueueName=QUEUE_NAME)['QueueUrl']
        
        print(f"[INFO] Monitoraggio coda SNS avviato")
        print(f"[INFO] Coda: {QUEUE_NAME}")
        print(f"[INFO] Premere Ctrl+C per terminare")
        print("-" * 60)
        
        processed_messages = set()
        
        print(f"[INFO] Lettura messaggi esistenti...")
        
        # Prima controlliamo quanti messaggi ci sono nella coda
        try:
            queue_attributes = sqs_client.get_queue_attributes(
                QueueUrl=queue_url,
                AttributeNames=['ApproximateNumberOfMessages']
            )
            approx_messages = int(queue_attributes['Attributes']['ApproximateNumberOfMessages'])
            print(f"[INFO] Messaggi approssimativi nella coda: {approx_messages}")
        except Exception as e:
            print(f"[WARNING] Non riesco a ottenere il numero di messaggi: {e}")
            approx_messages = 0
        
        existing_count = 0
        
        # Leggo tutti i messaggi esistenti - SQS restituisce max 10 messaggi per volta
        consecutive_empty_reads = 0
        max_empty_reads = 5  # Aumentato il numero di tentativi
        
        while consecutive_empty_reads < max_empty_reads:
            existing_messages = read_and_display_messages(sqs_client, queue_url, processed_messages, is_existing=True)
            
            if existing_messages:
                existing_count += len(existing_messages)
                consecutive_empty_reads = 0  # Reset del contatore se troviamo messaggi
                print(f"[DEBUG] Batch completato: {len(existing_messages)} messaggi letti (totale: {existing_count})")
            else:
                consecutive_empty_reads += 1
                if consecutive_empty_reads < max_empty_reads:
                    print(f"[DEBUG] Nessun messaggio in questo batch, riprovo... ({consecutive_empty_reads}/{max_empty_reads})")
                    time.sleep(1)  # Pausa un po' più lunga tra i tentativi
        
        if existing_count > 0:
            print(f"\n[INFO] Caricati {existing_count} messaggi esistenti")
        else:
            print(f"[INFO] Nessun messaggio esistente trovato")
        
        print(f"[INFO] Ora in attesa di nuovi messaggi...")
        print("-" * 60)
        
        message_count = existing_count
        
        while True:
            try:
                new_messages = read_and_display_messages(sqs_client, queue_url, processed_messages, is_existing=False)
                message_count += len(new_messages)
                
                if not new_messages:
                    current_time = datetime.datetime.now().strftime('%H:%M:%S')
                    print(f"[WAIT] {current_time} - In attesa di nuovi messaggi... (Tot: {message_count})", end='\r')
                
            except KeyboardInterrupt:
                print(f"\n\n[SUCCESS] Monitoraggio terminato. Messaggi processati: {message_count}")
                break
            except Exception as e:
                print(f"\n[ERROR] Errore durante il monitoraggio: {e}")
                time.sleep(5)
                
    except ClientError as e:
        if 'AWS.SimpleQueueService.NonExistentQueue' in str(e):
            print(f"[ERROR] Coda '{QUEUE_NAME}' non trovata.")
            print("[INFO] Esegui prima: python deploy_music_app.py")
        else:
            print(f"[ERROR] Errore accesso AWS: {e}")
    except Exception as e:
        print(f"[ERROR] Errore generale: {e}")

def main():
    monitor_queue()

if __name__ == "__main__":
    main()
