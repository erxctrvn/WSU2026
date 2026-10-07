import os
import time
import json
from datetime import datetime, timedelta, timezone

# boto3 clients are created at import time, so a region must exist first.
os.environ.setdefault("AWS_DEFAULT_REGION", "ap-southeast-2")

import boto3
import pytest

cloudwatch = boto3.client("cloudwatch")
lambda_client = boto3.client("lambda")
dynamodb = boto3.resource("dynamodb")

CRAWLER_FUNCTION_NAME = os.environ.get("CRAWLER_FUNCTION_NAME")
ALARM_TABLE_NAME = os.environ.get("ALARM_TABLE_NAME")

# one of the sites in lambda/websites.json, used to look up its metrics
TEST_SITE = "https://github.com/"


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
#invokes lambda, then polls cloudwatch for a fresh Availability datapoint, proves put_metric_data works
def test_crawler_lambda_publishes_metrics_to_cloudwatch():
    started = datetime.now(timezone.utc)
    lambda_client.invoke(FunctionName=CRAWLER_FUNCTION_NAME, InvocationType="RequestResponse")

    datapoints = []
    for _ in range(12):  # metrics take time to show up, show for 60 seconds
        time.sleep(5)
        response = cloudwatch.get_metric_statistics(
            Namespace="WebsiteMonitoring",
            MetricName="Availability",
            Dimensions=[{"Name": "Website", "Value": TEST_SITE}],
            StartTime=started,
            EndTime=datetime.now(timezone.utc),
            Period=60,
            Statistics=["SampleCount"],
        )
        datapoints = response["Datapoints"]
        if datapoints:
            break

    assert datapoints, "no new Availability datapoint appeared within ~60s of invoking the crawler"


@pytest.mark.skipif(not ALARM_TABLE_NAME, reason="ALARM_TABLE_NAME not set")
#writes fake data into alarm table, reads, and confirms its there. shows test table works and the schema is there
def test_alarm_table_is_reachable_and_writable():
    """Confirms the deployed AlarmTable is reachable and its key schema accepts a write
    (uses the pipeline's credentials, not the Lambda's IAM role)."""
    table = dynamodb.Table(ALARM_TABLE_NAME)
    key = {"AlarmName": "IntegrationTestAlarm", "Timestamp": "2026-01-01T00:00:00Z"}
    try:
        table.put_item(Item={**key, "NewStateValue": "ALARM", "Reason": "integration test write"})
        fetched = table.get_item(Key=key)
        assert "Item" in fetched
    finally:
        table.delete_item(Key=key)  # cleans up even if fails


@pytest.mark.skipif(not ALARM_TABLE_NAME, reason="ALARM_TABLE_NAME not set")
#tests how long a put_item call takes against the live table, under a threshold
def test_dynamodb_write_completes_within_latency_budget():
    """DynamoDB read/write time check - explicitly called out in the applied project brief."""
    table = dynamodb.Table(ALARM_TABLE_NAME)
    key = {"AlarmName": "LatencyTestAlarm", "Timestamp": "2026-01-01T00:00:00Z"}

    table.get_item(Key=key)  # warm-up 
    try:
        start = time.perf_counter()
        table.put_item(Item={**key, "NewStateValue": "OK", "Reason": "latency test"})
        elapsed_ms = (time.perf_counter() - start) * 1000
    finally:
        table.delete_item(Key=key)

    assert elapsed_ms < 1000  # can probably change if i have a baseline


@pytest.mark.skipif(not CRAWLER_FUNCTION_NAME, reason="CRAWLER_FUNCTION_NAME not set")
#catches unhandled crash exceptions in the lambda.
def test_crawler_lambda_has_no_permission_errors():
    """A clean invoke with no FunctionError means the Lambda ran without an unhandled
    exception (a missing IAM permission is one possible cause)."""
    response = lambda_client.invoke(
        FunctionName=CRAWLER_FUNCTION_NAME,
        InvocationType="RequestResponse",
    )
    assert "FunctionError" not in response