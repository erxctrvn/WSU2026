#INTEGRATION TESTS FOR BETA STAGE
import os
import re
import time
import json
import uuid

os.environ.setdefault("AWS_DEFAULT_REGION", "ap-southeast-2")

import boto3
import pytest

lambda_client = boto3.client("lambda")
dynamodb = boto3.resource("dynamodb")

CRAWLER_FUNCTION_NAME = os.environ.get("CRAWLER_FUNCTION_NAME")
TARGETS_TABLE_NAME = os.environ.get("TARGETS_TABLE_NAME")


@pytest.mark.skipif(not TARGETS_TABLE_NAME, reason="TARGETS_TABLE_NAME not set")
def test_targets_table_read_and_write_within_latency_budget():
    table = dynamodb.Table(TARGETS_TABLE_NAME)
    key = {"url": f"https://example.com/integration-test-{uuid.uuid4().hex}"}

    table.get_item(Key=key)  # warm-up
    try:
        start = time.perf_counter()
        table.put_item(Item=key)
        write_ms = (time.perf_counter() - start) * 1000

        start = time.perf_counter()
        fetched = table.get_item(Key=key, ConsistentRead=True)
        read_ms = (time.perf_counter() - start) * 1000
    finally:
        table.delete_item(Key=key)

    print(f"targets table write {write_ms:.0f} ms, read {read_ms:.0f} ms")
    assert fetched.get("Item") == key
    assert write_ms < 1000
    assert read_ms < 1000


@pytest.mark.skipif(not (CRAWLER_FUNCTION_NAME and TARGETS_TABLE_NAME),
                    reason="CRAWLER_FUNCTION_NAME / TARGETS_TABLE_NAME not set")
def test_crawler_checks_the_websites_in_the_targets_table():
    table = dynamodb.Table(TARGETS_TABLE_NAME)
    in_table = table.scan(Select="COUNT", ConsistentRead=True)["Count"]
    assert in_table > 0, "targets table is empty, the deploy-time seeding did not run"

    response = lambda_client.invoke(FunctionName=CRAWLER_FUNCTION_NAME, InvocationType="RequestResponse")
    payload = json.loads(response["Payload"].read())

    checked = int(re.search(r"Checked (\d+) websites", payload["body"]).group(1))
    assert checked == in_table