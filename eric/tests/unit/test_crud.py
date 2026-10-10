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

import crud
SITE = "https://example.com/"
RESPONSE_ALARM = "Test-EricStack-ResponseTime-example-com"
AVAILABILITY_ALARM = "Test-EricStack-Availability-example-com"

#Fixture swaps real table for a fake table and accepts and calls.
@pytest.fixture
def aws():
    with mock.patch.object(crud, "targets_table") as targets_table, \
         mock.patch.object(crud, "alarm_table") as alarm_table, \
         mock.patch.object(crud, "cloudwatch") as cloudwatch:
        alarm_table.query.return_value = {"Items": []}
        yield mock.Mock(targets_table=targets_table, alarm_table=alarm_table, cloudwatch=cloudwatch)
#Fake request 
def post_event(url):
    return {"httpMethod": "POST", "body": json.dumps({"url": url})}
#Calls handler with the fake request
def test_post_saves_target_and_creates_two_alarms(aws):
    response = crud.handler(post_event(SITE), None)

    assert response["statusCode"] == 201
    assert aws.targets_table.put_item.call_args.kwargs["Item"] == {"url": SITE}
    assert aws.cloudwatch.put_metric_alarm.call_count == 2
    assert json.loads(response["body"])["alarms"] == [RESPONSE_ALARM, AVAILABILITY_ALARM]

#Tests DELETE by sending fake DELETE
# tests that row was deleted, alarms deleted, and hsitory is deleted
def test_delete_cascades_to_alarms_and_alarm_history(aws):
    aws.targets_table.delete_item.return_value = {"Attributes": {"url": SITE}}
    aws.alarm_table.query.side_effect = [
        {"Items": [{"AlarmName": RESPONSE_ALARM, "Timestamp": "2026-01-01T00:00:00+00:00"}]},
        {"Items": [{"AlarmName": AVAILABILITY_ALARM, "Timestamp": "2026-01-02T00:00:00+00:00"},
                   {"AlarmName": AVAILABILITY_ALARM, "Timestamp": "2026-01-03T00:00:00+00:00"}]},
    ]
    event = {"httpMethod": "DELETE", "pathParameters": {"url": "https%3A%2F%2Fexample.com%2F"}}

    response = crud.handler(event, None)

    assert response["statusCode"] == 200
    assert aws.targets_table.delete_item.call_args.kwargs["Key"] == {"url": SITE}
    aws.cloudwatch.delete_alarms.assert_called_once_with(AlarmNames=[RESPONSE_ALARM, AVAILABILITY_ALARM])
    batch = aws.alarm_table.batch_writer.return_value.__enter__.return_value
    assert batch.delete_item.call_count == 3
    assert json.loads(response["body"])["historyRowsDeleted"] == 3

def alarms_created(aws):
    return {call.kwargs["MetricName"]: call.kwargs
            for call in aws.cloudwatch.put_metric_alarm.call_args_list}


def test_response_time_alarm_has_correct_config(aws):
    crud.handler(post_event(SITE), None)

    alarm = alarms_created(aws)["ResponseTime"]
    assert alarm["Threshold"] == 1
    assert alarm["ComparisonOperator"] == "GreaterThanThreshold"
    assert alarm["EvaluationPeriods"] == 2

#Tests to see if when site is added if availability alarm is set to fire below 1 after a check
def test_availability_alarm_has_correct_config(aws):
    crud.handler(post_event(SITE), None)

    alarm = alarms_created(aws)["Availability"]
    assert alarm["Threshold"] == 1
    assert alarm["ComparisonOperator"] == "LessThanThreshold"
    assert alarm["EvaluationPeriods"] == 1

