import boto3
import json
import time
import datetime
import pytz

REGION = 'us-east-1'
QUEUE_NAME = 'musicapp-sns-logging-queue'

def format_timestamp(timestamp_str):
    if not timestamp_str:
        return "N/A"
    try:
        dt = datetime.datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        utc_tz = pytz.UTC
        rome_tz = pytz.timezone('Europe/Rome')
        
        if dt.tzinfo is None:
            dt = utc_tz.localize(dt)
        elif dt.tzinfo != utc_tz:
            dt = dt.astimezone(utc_tz)
        
        rome_time = dt.astimezone(rome_tz)
        
        return rome_time.strftime('%Y-%m-%d %H:%M:%S Roma')
    except Exception as e:
        print(f"[WARNING] Errore conversione timestamp {timestamp_str}: {e}")
        return timestamp_str

def read_and_display_messages(sqs_client, queue_url):
    try:
        response = sqs_client.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=10,
            WaitTimeSeconds=20,
            AttributeNames=['All'],
            MessageAttributeNames=['All']
        )
        
        messages = response.get('Messages', [])
        
        for message in messages:
            try:
                sns_message = json.loads(message['Body'])
                
                # Mostra il nuovo messaggio
                timestamp = format_timestamp(sns_message.get('Timestamp'))
                subject = sns_message.get('Subject') or 'N/A'
                msg_content = sns_message.get('Message', '')
                topic = sns_message.get('TopicArn', '').split(':')[-1] if sns_message.get('TopicArn') else 'N/A'
                
                print(f"\n[NEW] NUOVO MESSAGGIO - {timestamp}")
                print(f"      Subject: {subject}")
                print(f"      Message: {msg_content[:150]}{'...' if len(msg_content) > 150 else ''}")
                print(f"      Topic: {topic}")
                print("-" * 60)
                
                sqs_client.delete_message(
                    QueueUrl=queue_url,
                    ReceiptHandle=message['ReceiptHandle']
                )
                
            except json.JSONDecodeError:
                print(f"[WARNING] Messaggio non JSON ricevuto: {message['Body'][:100]}...")
            except Exception as msg_error:
                print(f"[ERROR] Errore processamento messaggio: {msg_error}")
        
        return len(messages)
        
    except Exception as e:
        print(f"[ERROR] Errore lettura coda: {e}")
        return 0

def monitor_queue():

    sqs_client = boto3.client('sqs', region_name=REGION)
    queue_url = sqs_client.get_queue_url(QueueName=QUEUE_NAME)['QueueUrl']
    
    print(f"[INFO] Monitoraggio coda SNS avviato")
    print(f"[INFO] Coda: {QUEUE_NAME}")
    print(f"[INFO] In ascolto di nuovi messaggi...")
    print(f"[INFO] Orario: Fuso orario di Roma")
    print(f"[INFO] Premere Ctrl+C per terminare")
    print("-" * 60)
    
    message_count = 0
    
    while True:
        try:
            new_message_count = read_and_display_messages(sqs_client, queue_url)
            message_count += new_message_count
            
            if new_message_count == 0:
                current_time = datetime.datetime.now().strftime('%H:%M:%S')
                print(f"[WAIT] {current_time} - In ascolto... (Tot: {message_count})", end='\r')
            
        except KeyboardInterrupt:
            print(f"\n\n[SUCCESS] Monitoraggio terminato. Messaggi processati: {message_count}")
            break
        except Exception as e:
            print(f"\n[ERROR] Errore durante il monitoraggio: {e}")
            time.sleep(5)

def main():
    monitor_queue()

if __name__ == "__main__":
    main()
