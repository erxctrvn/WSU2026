#This is the application where metric and values 
#From web resource
#This runs on top of the stack.
import json,time,urllib.request,boto3
cloudwatch = boto3.client('cloudwatch')
urltomonitor = "https://www.youtube.com/"


def helloworldfunc(event,context):
    start_time = time.time()
    try:
        response = urllib.request.urlopen(urltomonitor, timeout = 10)
        status_code = response.getcode()
        is_up = 1
    except Exception as e:
        print(f"Error: {e}")
        status_code = 0
        is_up = 0

    latency_ms = (time.time() - start_time) * 1000

    cloudwatch.put_metric_data(
        Namespace='WebsiteMonitoring',
        MetricData=[
            {'MetricName': 'ResponseTime', 'Value': latency_ms, 'Unit': 'Milliseconds'},
            {'MetricName': 'StatusCode', 'Value': status_code, 'Unit': 'None'},
            {'MetricName': 'Availability', 'Value': is_up, 'Unit': 'Count'}
        ]
    )
    return {'statusCode': 200, 'body': json.dumps("Checked website")}



#Create the three custom metrics

#Visualise them through a Dashboard