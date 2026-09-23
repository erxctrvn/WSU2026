import aws_cdk as core
import aws_cdk.assertions as assertions
import pytest

from eric.eric_stack import EricStack

# example tests. To run these tests, uncomment this file along with the example
# resource in eric/eric_stack.py
# add about 10 unit tests, 8 functional tests, and 5 integration tests do this for web health application 
# as many as you want for applied project, 2-1-1 anything extra will get extra credits
# 1-2 slides for presentation before demonstration/

@pytest.fixture(scope="module")
def template():
    app = core.App()
    stack = EricStack(app, "eric")
    return assertions.Template.from_stack(stack)

#confirms that mylambda(crawler) and alarmlambda are actually declared
def test_two_lambda_functions_created(template):
    """mylambda (crawler) and alarmlambda (alarm handler) should both exist."""
    template.resource_count_is("AWS::Lambda::Function", 2)
 
#checks crawler lambda is pointing at right function (helloworldfunc)
def test_crawler_lambda_handler_is_correct(template):
    template.has_resource_properties("AWS::Lambda::Function", {
        "Handler": "wiring.helloworldfunc",
        "Runtime": "python3.13",
    })
 
#checks alarm handler is pointing at right alarm
def test_alarm_lambda_handler_is_correct(template):
    template.has_resource_properties("AWS::Lambda::Function", {
        "Handler": "alarmhandler.handle_alarm",
        "Runtime": "python3.13",
    })
 
#checks if alarmtable put_item has right key name
def test_alarm_table_has_correct_key_schema(template):
    """AlarmTable: partition key AlarmName, sort key Timestamp."""
    template.has_resource_properties("AWS::DynamoDB::Table", {
        "KeySchema": [
            {"AttributeName": "AlarmName", "KeyType": "HASH"},
            {"AttributeName": "Timestamp", "KeyType": "RANGE"},
        ],
    })
 
#confirms that user is not accidentally allowing fixed read/write capacity (costs money)
def test_alarm_table_uses_pay_per_request_billing(template):
    template.has_resource_properties("AWS::DynamoDB::Table", {
        "BillingMode": "PAY_PER_REQUEST",
    })
 
#locks in the response time values from eric_stack, if changed it will fail
def test_response_time_alarm_has_correct_config(template):
    template.has_resource_properties("AWS::CloudWatch::Alarm", {
        "MetricName": "ResponseTime",
        "Threshold": 1,
        "ComparisonOperator": "GreaterThanThreshold",
        "EvaluationPeriods": 2,
    })


def test_alarm_count_matches_sites_times_metrics(template):
    """3 websites x 2 alarms each (ResponseTime, Availability) = 6 alarms."""
    template.resource_count_is("AWS::CloudWatch::Alarm", 6)
 
#confirms that notification topic is declared
def test_sns_topic_created_with_display_name(template):
    template.has_resource_properties("AWS::SNS::Topic", {
        "DisplayName": "Website Monitoring Alerts",
    })
 
#confirms crawler is scheduled to run at right duration
def test_eventbridge_rule_runs_every_15_minutes(template):
    template.has_resource_properties("AWS::Events::Rule", {
        "ScheduleExpression": "rate(15 minutes)",
    })