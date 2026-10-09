#CRUD unit test for CRUD lambda 
#someone calls API / runtime job
import json
import os
import sys
from unittest import mock

import pytest

#CRUD unit test
os.environ.setdefault("AWS_DEFAULT_REGION", "ap-southeast-2")
os.environ.setdefault("TABLE_TARGETS", "FakeTargetsTable")
os.environ.setdefault("TABLE_ALARM", "FakeTable")
os.environ.setdefault("TOPIC_ARN", "arn:aws:sns:ap-southeast-2:123456789012:FakeTopic")
os.environ.setdefault("STACK_NAME", "Test-EricStack")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lambda"))

import tests.unit.test_crud as test_crud

SITE = "https://example.com/"
RESPONSE_ALARM = "Test-EricStack-ResponseTime-example-com"
AVAILABILITY_ALARM = "Test-EricStack-Availability-example-com"

#Fixture swaps real table for a fake table and accepts and calls.
@pytest.fixture
def aws():
    with mock.patch.object(test_crud, "targets_table") as targets_table, \
         mock.patch.object(test_crud, "alarm_table") as alarm_table, \
         mock.patch.object(test_crud, "cloudwatch") as cloudwatch:
        alarm_table.query.return_value = {"Items": []}
        yield mock.Mock(targets_table=targets_table, alarm_table=alarm_table, cloudwatch=cloudwatch)
#Fake request 
def post_event(url):
    return {"httpMethod": "POST", "body": json.dumps({"url": url})}
#Calls handler with the fake request
def test_post_saves_target_and_creates_two_alarms(aws):
    response = test_crud.handler(post_event(SITE), None)

    assert response["statusCode"] == 201
    assert aws.targets_table.put_item.call_args.kwargs["Item"] == {"url": SITE}
    assert aws.cloudwatch.put_metric_alarm.call_count == 2
    assert json.loads(response["body"])["alarms"] == [RESPONSE_ALARM, AVAILABILITY_ALARM]
