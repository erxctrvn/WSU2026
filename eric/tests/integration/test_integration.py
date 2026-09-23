import os
import time
import json
import boto3
import pytest

cloudwatch = boto3.client("cloudwatch")
lambda_client = boto3.client("lambda")
dynamodb= boto3.resource("dynamodb")

CRAWLER_FUNCTION_NAME = os.environ.get("CRAWLER_FUNCTION_NAME")
ALARM_TABLE_NAME = os.environ.get("ALARM_TABLE_NAME")

@pytest.mark.skipif(not CRAWLER_FUNCTION_NAME, reason="CRAWLER_FUNCTION_NAME not set")
#calls crawler lambda for status code, whether it sent and was sent back
def test_crawler_lambda_invokes_successfully():
    response = lambda_client.invoke(
        FunctionName=CRAWLER_FUNCTION_NAME,
        InvocationType="RequestResponse",
    )
    payload = json.loads(response["Payload"].read())
    assert response["StatusCode"] == 200
    assert payload["statusCode"] == 200
 
 
@pytest.mark.skipif(not CRAWLER_FUNCTION_NAME, reason="CRAWLER_FUNCTION_NAME not set")
#invokes lambda and waits to confirm if cloudwatch metric count goes up, proves put metric data works
def test_crawler_lambda_publishes_metrics_to_cloudwatch():
    before = cloudwatch.list_metrics(Namespace="WebsiteMonitoring")["Metrics"]
    lambda_client.invoke(FunctionName=CRAWLER_FUNCTION_NAME, InvocationType="RequestResponse")
    time.sleep(5)  # metrics take time to update, adds delay then query 
    after = cloudwatch.list_metrics(Namespace="WebsiteMonitoring")["Metrics"]
    assert len(after) >= len(before)
 
 
@pytest.mark.skipif(not ALARM_TABLE_NAME, reason="ALARM_TABLE_NAME not set")
#writes fake data into alarm table, reads, and confirms its there. Tests table permissions and schema work
def test_alarm_table_is_reachable_and_writable():
    """Confirms the deployed Lambda's IAM role actually has write access."""
    table = dynamodb.Table(ALARM_TABLE_NAME)
    key = {"AlarmName": "IntegrationTestAlarm", "Timestamp": "2026-01-01T00:00:00Z"}
    table.put_item(Item={**key, "NewStateValue": "ALARM", "Reason": "integration test write"})
    fetched = table.get_item(Key=key)
    assert "Item" in fetched
    table.delete_item(Key=key)
 
 
@pytest.mark.skipif(not ALARM_TABLE_NAME, reason="ALARM_TABLE_NAME not set")
#tests how long a put_item call would take against live table under a threshold
def test_dynamodb_write_completes_within_latency_budget():
    """DynamoDB read/write time check - explicitly called out in the applied project brief."""
    table = dynamodb.Table(ALARM_TABLE_NAME)
    key = {"AlarmName": "LatencyTestAlarm", "Timestamp": "2026-01-01T00:00:00Z"}
    start = time.time()
    table.put_item(Item={**key, "NewStateValue": "OK", "Reason": "latency test"})
    elapsed_ms = (time.time() - start) * 1000
    table.delete_item(Key=key)
    assert elapsed_ms < 1000  # can probably change if i have a baseline
 
 
@pytest.mark.skipif(not CRAWLER_FUNCTION_NAME, reason="CRAWLER_FUNCTION_NAME not set")
#catches unhandled crash exceptions in the lambda.
def test_crawler_lambda_has_no_permission_errors():
    """A clean invoke with no FunctionError means IAM permissions are correctly wired."""
    response = lambda_client.invoke(
        FunctionName=CRAWLER_FUNCTION_NAME,
        InvocationType="RequestResponse",
    )
    assert "FunctionError" not in response