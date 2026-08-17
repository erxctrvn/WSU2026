#This is the application where metric and values 
#From web resource
#This runs on top of the stack.
#CDK is for infrastructure creation
#SDK is for runtime.
import json,time,urllib.request,boto3
cloudwatch = boto3.client('cloudwatch')

def loadmultwebs():
    with open('websites.json') as f:
        return json.load(f)

def crawl_func(url): #used for just one website
    start_time = time.time()
    try:
        response = urllib.request.urlopen(url, timeout = 10)
        status_code = response.getcode()
        is_up = 1
    except Exception as e:
        print(f"Error {url}: {e}")
        status_code = 0
        is_up = 0

    latency_ms = (time.time() - start_time) * 1000
    cloudwatch.put_metric_data(
        Namespace="WebsiteMonitoring",
        #Dimensions creates a list, category ('name'), value ('url'), 
        # value is in through latency_ms = (time.time() - start_time) * 1000
        # unit is in ms
        MetricData=[
            {'MetricName': 'ResponseTime', 'Dimensions': [{'Name':'Website','Value': url}], 'Value': latency_ms, 'Unit': 'Milliseconds'},
            {'MetricName': 'StatusCode', 'Dimensions': [{'Name':'Website','Value': url}], 'Value' : status_code, 'Unit': 'None'},
            {'MetricName': 'Availability', 'Dimensions': [{'Name': 'Website', 'Value': url}], 'Value' : is_up, 'Unit' : 'Count'}

        ]
    )
def helloworldfunc(event,context): #looped for multiple
    websites_json = loadmultwebs() #websites.json reference
    for url in websites_json: # loop through json 
        crawl_func(url) # use the crawl_func to check metrics one for each websites
        #{length(websites)}
    return{'statusCode': 200, 'body': json.dumps(f"Checked {len(websites_json)} websites")}
            
    #Obtain metrics (not same a dashboard)
    #MetricName is name space/package, all metrics belong under it.
