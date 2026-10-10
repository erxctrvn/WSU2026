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
def test_lambda_functions_created(template):
    """mylambda (crawler), alarmlambda (alarm handler) and crudlambda (CRUD API)."""
    template.resource_count_is("AWS::Lambda::Function", 3)
 
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

#Test to check that stack has url as partition key
def test_targets_table_has_url_partition_key(template):
    template.has_resource_properties("AWS::DynamoDB::Table", {
        "KeySchema": [
            {"AttributeName": "url", "KeyType": "HASH"},
        ],
    })

#Checks CRUD lambda exists and points to right crud lambda file
def test_crud_lambda_handler_is_correct(template):
    template.has_resource_properties("AWS::Lambda::Function", {
        "Handler": "crud.handler",
        "Runtime": "python3.13",
    })

#Tests API has all CRUD routes nad is public
def test_api_exposes_all_crud_methods(template):
    template.resource_count_is("AWS::ApiGateway::RestApi", 1)
    template.resource_count_is("AWS::ApiGateway::Method", 7)
    for method in ["GET", "POST", "PUT", "DELETE"]:
        template.has_resource_properties("AWS::ApiGateway::Method", {
            "HttpMethod": method,
            "AuthorizationType": "NONE",
        })

def test_lambda_functions_created(template):
    """mylambda (crawler), alarmlambda (alarm handler), crudlambda (CRUD API),
    plus one CDK adds itself to run the seeding step."""
    template.resource_count_is("AWS::Lambda::Function", 4)

#Testing if stack creates no alarms as it is in Lambda now
def test_stack_declares_no_alarms(template):
    """Alarms are created by the CRUD Lambda now. Two owners would overwrite each other."""
    template.resource_count_is("AWS::CloudWatch::Alarm", 0)

#Making sure crawler is told name of the targets in table
def test_crawler_reads_targets_from_dynamodb(template):
    template.has_resource_properties("AWS::Lambda::Function", {
        "Handler": "wiring.helloworldfunc",
        "Environment": {"Variables": {"TABLE_TARGETS": assertions.Match.any_value()}},
    })

#Tests to see if stack still creates one dashboard
def test_dashboard_created(template):
    template.resource_count_is("AWS::CloudWatch::Dashboard", 1)