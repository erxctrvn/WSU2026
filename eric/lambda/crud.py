#Different from wiring lambda as it fires through API requests
import json
import os
import re
from urllib.parse import unquote, urlparse

import boto3
from botocore.exceptions import ClientError

dynamodb = boto3.resource("dynamodb")
cloudwatch = boto3.client("cloudwatch")

TABLE_TARGETS = os.environ["TABLE_TARGETS"]
TABLE_ALARM = os.environ["TABLE_ALARM"]
TOPIC_ARN = os.environ["TOPIC_ARN"]
STACK_NAME = os.environ["STACK_NAME"]

targets_table = dynamodb.Table(TABLE_TARGETS)
alarm_table = dynamodb.Table(TABLE_ALARM)

NAMESPACE = "WebsiteMonitoring"
ALARM_PERIOD_SECONDS = 300
RESPONSE_TIME_THRESHOLD_MS = 1
MAX_URL_LENGTH = 1024

#Helpers
#API gateway requires this format
def respond(status, body):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }

#Turns the url into stage and stack name because CRUD calls it so names will always be the same
def alarm_names(url):
    without_scheme = re.sub(r"^https?://", "", url)
    safe_id = re.sub(r"[^A-Za-z0-9]+", "-", without_scheme).strip("-")[:150]
    return {
        "ResponseTime": f"{STACK_NAME}-ResponseTime-{safe_id}",
        "Availability": f"{STACK_NAME}-Availability-{safe_id}",
    }

#CREATE AND READ HELPERS

#Returns error message or none if URL is fine - CREATE
def validate_url(url):
    if not isinstance(url, str) or not url.strip():
        return "url is required"
    if len(url) > MAX_URL_LENGTH:
        return f"url must be {MAX_URL_LENGTH} characters or fewer"
    if not url.isascii():
        return "url must only contain ASCII characters"
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return "url must start with http:// or https:// and include a host"
    return None

#For POST, it parses with json.loads
def url_from_body(event):
    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return None, "request body must be valid JSON"
    if not isinstance(body, dict):
        return None, 'request body must be a JSON object like {"url": "https://example.com/"}'
    url = body.get("url")
    if isinstance(url, str):
        url = url.strip()
    return url, validate_url(url)

#For requests with only one target, unquote decodes the URL in the path
def url_from_request(event):
    path_params = event.get("pathParameters") or {}
    if path_params.get("url"):
        return unquote(path_params["url"])
    query = event.get("queryStringParameters") or {}
    return query.get("url")

#Moving alarm loop to run time 
def create_alarms(url):
    names = alarm_names(url)
    dimensions = [{"Name": "Website", "Value": url}]
    cloudwatch.put_metric_alarm(
        AlarmName=names["ResponseTime"],
        AlarmDescription=f"Response time is too high for {url}",
        Namespace=NAMESPACE,
        MetricName="ResponseTime",
        Dimensions=dimensions,
        Statistic="Average",
        Period=ALARM_PERIOD_SECONDS,
        EvaluationPeriods=2,
        Threshold=RESPONSE_TIME_THRESHOLD_MS,
        ComparisonOperator="GreaterThanThreshold",
        TreatMissingData="breaching",
        AlarmActions=[TOPIC_ARN],
    )
    cloudwatch.put_metric_alarm(
        AlarmName=names["Availability"],
        AlarmDescription=f"{url} is not reachable",
        Namespace=NAMESPACE,
        MetricName="Availability",
        Dimensions=dimensions,
        Statistic="Average",
        Period=ALARM_PERIOD_SECONDS,
        EvaluationPeriods=1,
        Threshold=1,
        ComparisonOperator="LessThanThreshold",
        TreatMissingData="breaching",
        AlarmActions=[TOPIC_ARN],
    )
    return list(names.values())

#Reads every URL from the table
#https://docs.aws.amazon.com/boto3/latest/reference/services/dynamodb/table/scan.html
#(scan, get item, put item)
# READ
def scan_targets():
    urls = []
    scan_args = {}
    while True:
        page = targets_table.scan(**scan_args)
        urls.extend(item["url"] for item in page["Items"])
        if "LastEvaluatedKey" not in page:
            break
        scan_args["ExclusiveStartKey"] = page["LastEvaluatedKey"]
    return sorted(urls)

# response for GET /targets
def list_targets():
    urls = scan_targets()
    return respond(200, {"count": len(urls), "targets": [{"url": url} for url in urls]})

# response for GET /targets{url}
#(describe alarm (read only state) https://docs.aws.amazon.com/boto3/latest/reference/services/cloudwatch/client/describe_alarms.html)
# READ
def get_target(url):
    if "Item" not in targets_table.get_item(Key={"url": url}):
        return respond(404, {"error": "target not found", "url": url})
    names = list(alarm_names(url).values())
    found = cloudwatch.describe_alarms(AlarmNames=names)["MetricAlarms"]
    alarms = [{"name": a["AlarmName"], "state": a["StateValue"]} for a in found]
    return respond(200, {"url": url, "alarms": alarms})

# write a row only if it is a new URL - CREATE
def put_new_target(url):
    #only write if following is true
    #https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Expressions.ConditionExpressions.html
    try:
        targets_table.put_item(Item={"url": url}, ConditionExpression="attribute_not_exists(#u)",
                               ExpressionAttributeNames={"#u": "url"})
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return False
        raise

#response for POST /targets - CREATE
def create_target(event):
    # CREATE
    url, error = url_from_body(event)
    if error:
        return respond(400, {"error": error})
    if not put_new_target(url):
        return respond(409, {"error": "target already exists", "url": url})
    alarms = create_alarms(url)
    return respond(201, {"url": url, "alarms": alarms})

#Moving alarm to lambda for CRUD changes to apply at runtime
#fills new table and creates alarm 
def seed_targets(urls):
    for url in urls:
        targets_table.put_item(Item={"url": url})
        create_alarms(url)
    return {"seeded": len(urls)}

#cleans up alarm on delete
#https://docs.aws.amazon.com/boto3/latest/reference/services/cloudwatch/client/delete_alarms.html
def purge_all_alarms():
    names = []
    for page in cloudwatch.get_paginator("describe_alarms").paginate(AlarmNamePrefix=f"{STACK_NAME}-"):
        names.extend(alarm["AlarmName"] for alarm in page["MetricAlarms"])
    for i in range(0, len(names), 100):
        cloudwatch.delete_alarms(AlarmNames=names[i:i + 100])
    return {"alarmsDeleted": len(names)}


#API will call this for every request - READ
def handler(event, context):
    if event.get("action") == "seed":
        return seed_targets(event.get("urls", []))
    if event.get("action") == "purge":
        return purge_all_alarms()
    method = event.get("httpMethod")
    url = url_from_request(event)
    try:
        if method == "GET":
            return get_target(url) if url else list_targets()
        if method == "POST":
            return create_target(event)
        if method in ("PUT", "DELETE") and not url:
            return respond(400, {"error": "say which target: /targets/{url-encoded url} or /targets?url=..."})
        if method == "PUT":
            return update_target(url, event)
        if method == "DELETE":
            return delete_target(url)
        return respond(405, {"error": f"method {method} not allowed"})
    except Exception as e:
        print(f"Unhandled error on {method} {url}: {e}")
        return respond(500, {"error": "internal server error"})

#UPDATE AND DELETE HELPERS

#DELETE
def purge_alarm_history(alarm_name):
    deleted = 0
    query_args = {
        "KeyConditionExpression": "AlarmName = :name",
        "ExpressionAttributeValues": {":name": alarm_name},
        "ProjectionExpression": "AlarmName, #ts",
        "ExpressionAttributeNames": {"#ts": "Timestamp"},
    }
    with alarm_table.batch_writer() as batch:
        while True:
            page = alarm_table.query(**query_args)
            for item in page["Items"]:
                batch.delete_item(Key={"AlarmName": item["AlarmName"], "Timestamp": item["Timestamp"]})
                deleted += 1
            if "LastEvaluatedKey" not in page:
                break
            query_args["ExclusiveStartKey"] = page["LastEvaluatedKey"]
    return deleted


def delete_alarms_and_history(url):
    names = list(alarm_names(url).values())
    cloudwatch.delete_alarms(AlarmNames=names)
    history_rows = sum(purge_alarm_history(name) for name in names)
    return names, history_rows

#Swap the row, two alarms, and history rows - UPDATE
def update_target(old_url, event):
    new_url, error = url_from_body(event)
    if error:
        return respond(400, {"error": error})
    if "Item" not in targets_table.get_item(Key={"url": old_url}):
        return respond(404, {"error": "target not found", "url": old_url})
    if new_url == old_url:
        return respond(200, {"url": new_url, "alarms": create_alarms(new_url)})
    if not put_new_target(new_url):
        return respond(409, {"error": "target already exists", "url": new_url})
    alarms = create_alarms(new_url)
    targets_table.delete_item(Key={"url": old_url})
    delete_alarms_and_history(old_url)
    return respond(200, {"url": new_url, "replaced": old_url, "alarms": alarms})

#Removes row and if there is alarm and history remove those as well
# DELETE helper
def delete_target(url):
    old = targets_table.delete_item(Key={"url": url}, ReturnValues="ALL_OLD")
    if "Attributes" not in old:
        return respond(404, {"error": "target not found", "url": url})
    alarms, history_rows = delete_alarms_and_history(url)
    return respond(200, {"deleted": url, "alarmsDeleted": alarms, "historyRowsDeleted": history_rows})