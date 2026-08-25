import boto3
import os
import json
from datetime import datetime, timezone
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['TABLE_ALARM'])


def handle_alarm(event, context):
    for record in event['Records']:
        message = record['Sns']['Message']
        message_str = json.loads(message)
        alarm_name = message_str['AlarmName']
        new_state = message_str['NewStateValue']
        reason = message_str['NewStateReason']
        timestamp = datetime.now(timezone.utc).isoformat()
        table.put_item(
            Item= {
                'AlarmName' : alarm_name,
                'Timestamp' : timestamp,
                'NewStateValue': new_state,
                'Reason': reason,
            }
        )
        print(f"Logged alarm '{alarm_name}' ({new_state}) to DynamoDB")
    return {'statusCode': 200}