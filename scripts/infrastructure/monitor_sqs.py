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

def read_new_messages(sqs_client, queue_url, processed_messages):

    try:
        response = sqs_client.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=10,
            WaitTimeSeconds=20,  # Long polling
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
                    
                    # Mostra il nuovo messaggio
                    timestamp = format_timestamp(log_entry['timestamp'])
                    print(f"\n[LOG] NUOVO MESSAGGIO - {timestamp}")
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
        
        # leggo solo messaggi nuovi
        existing_response = sqs_client.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=10,
            WaitTimeSeconds=1,
            AttributeNames=['All']
        )
        
        for msg in existing_response.get('Messages', []):
            processed_messages.add(msg.get('MessageId'))
        
        if existing_response.get('Messages'):
            print(f"[INFO] Trovati {len(existing_response['Messages'])} messaggi esistenti (ignorati)")
            print("[INFO] Usa 'python deploy_music_app.py --read-logs' per leggerli")
            print("-" * 60)
        
        message_count = 0
        
        while True:
            try:
                new_messages = read_new_messages(sqs_client, queue_url, processed_messages)
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
