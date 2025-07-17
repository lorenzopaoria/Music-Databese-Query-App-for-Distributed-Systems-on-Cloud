import boto3
import json
import time
import datetime
import pytz
import os
from dotenv import load_dotenv

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, "..", ".."))
env_path = os.path.join(project_root, ".env")
load_dotenv(env_path)

# configurazione da env
REGION = os.getenv('AWS_REGION', 'us-east-1')
QUEUE_NAME = os.getenv('SQS_QUEUE_NAME', 'musicapp-sns-logging-queue')
DEFAULT_TIMEZONE = os.getenv('DEFAULT_TIMEZONE', 'Europe/Rome')
MAX_MESSAGE_LENGTH = int(os.getenv('MAX_MESSAGE_LENGTH', '150'))
SEPARATOR_LENGTH = int(os.getenv('SEPARATOR_LENGTH', '60'))

def print_info(message):

    print(f"[INFO] {message}")

def print_success(message):

    print(f"[SUCCESS] {message}")

def print_error(message):

    print(f"[ERROR] {message}")

def print_warning(message):

    print(f"[WARNING] {message}")

def print_step(message):

    print(f"[STEP] {message}")

def print_wait(message):

    print(f"[WAIT] {message}", end='\r')

def print_new(message):

    print(f"\n[NEW] {message}")

def print_separator(char="-", length=None):

    if length is None:
        length = SEPARATOR_LENGTH
    print(char * length)

def convert_timestamp_to_rome(timestamp_str):

    if not timestamp_str:
        return "N/A"
    try:
        dt = datetime.datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        utc_tz = pytz.UTC
        rome_tz = pytz.timezone(DEFAULT_TIMEZONE)
        
        if dt.tzinfo is None:
            dt = utc_tz.localize(dt)
        elif dt.tzinfo != utc_tz:
            dt = dt.astimezone(utc_tz)
        
        rome_time = dt.astimezone(rome_tz)
        return rome_time.strftime('%Y-%m-%d %H:%M:%S Roma')
    except Exception as e:
        print_warning(f"Errore conversione timestamp {timestamp_str}: {e}")
        return timestamp_str

def get_current_time_string():

    return datetime.datetime.now().strftime('%H:%M:%S')

def extract_message_data(sns_message):

    timestamp = convert_timestamp_to_rome(sns_message.get('Timestamp'))
    subject = sns_message.get('Subject') or 'N/A'
    msg_content = sns_message.get('Message', '')
    topic = sns_message.get('TopicArn', '').split(':')[-1] if sns_message.get('TopicArn') else 'N/A'
    return timestamp, subject, msg_content, topic

def display_message_info(timestamp, subject, msg_content, topic):

    print_new(f"NUOVO MESSAGGIO - {timestamp}")
    print(f"      Subject: {subject}")
    print(f"      Message: {msg_content[:MAX_MESSAGE_LENGTH]}{'...' if len(msg_content) > MAX_MESSAGE_LENGTH else ''}")
    print(f"      Topic: {topic}")
    print_separator()

def process_single_message(message, sqs_client, queue_url):

    try:
        sns_message = json.loads(message['Body'])
        timestamp, subject, msg_content, topic = extract_message_data(sns_message)
        display_message_info(timestamp, subject, msg_content, topic)
        
        sqs_client.delete_message(
            QueueUrl=queue_url,
            ReceiptHandle=message['ReceiptHandle']
        )
        return True
        
    except json.JSONDecodeError:
        print_warning(f"Messaggio non JSON ricevuto: {message['Body'][:100]}...")
        return False
    except Exception as msg_error:
        print_error(f"Errore processamento messaggio: {msg_error}")
        return False

def get_sqs_queue_url(sqs_client, queue_name):
    try:
        return sqs_client.get_queue_url(QueueName=queue_name)['QueueUrl']
    except Exception as e:
        print_error(f"Errore ottenimento URL coda: {e}")
        raise

def receive_messages_from_queue(sqs_client, queue_url):

    try:
        response = sqs_client.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=10,
            WaitTimeSeconds=20,
            AttributeNames=['All'],
            MessageAttributeNames=['All']
        )
        return response.get('Messages', [])
    except Exception as e:
        print_error(f"Errore ricezione messaggi: {e}")
        return []

def read_and_display_messages(sqs_client, queue_url):

    try:
        messages = receive_messages_from_queue(sqs_client, queue_url)
        
        processed_count = 0
        for message in messages:
            if process_single_message(message, sqs_client, queue_url):
                processed_count += 1
        
        return processed_count
        
    except Exception as e:
        print_error(f"Errore lettura coda: {e}")
        return 0

def initialize_monitoring():

    sqs_client = boto3.client('sqs', region_name=REGION)
    queue_url = get_sqs_queue_url(sqs_client, QUEUE_NAME)
    
    print_info("Monitoraggio coda SNS avviato")
    print_info(f"Coda: {QUEUE_NAME}")
    print_info("In ascolto di nuovi messaggi...")
    print_separator()
    
    return sqs_client, queue_url

def monitor_queue():

    sqs_client, queue_url = initialize_monitoring()
    message_count = 0
    
    while True:
        try:
            new_message_count = read_and_display_messages(sqs_client, queue_url)
            message_count += new_message_count
            
            if new_message_count == 0:
                current_time = get_current_time_string()
                print_wait(f"{current_time} - In ascolto... (Tot: {message_count})")
            
        except KeyboardInterrupt:
            print(f"\n\n")
            print_success(f"Monitoraggio terminato. Messaggi processati: {message_count}")
            break
        except Exception as e:
            print(f"\n")
            print_error(f"Errore durante il monitoraggio: {e}")
            time.sleep(5)

def main():
    monitor_queue()

if __name__ == "__main__":
    main()
