import json
import os
from aws_cdk import (
    
    # Duration,
    # Import stack here like AWS Lambda, or any infrastructure.
    # Define what web URL you want to monitor and choose 
    # 3 different metrics for it and visualise it.
    # Use Event to invoke every x minutes for graph
    # Project is to use AWS compute resources, create and deploy application on AWS.
    # Application is to monitor web URL.
    Stack,
    aws_lambda as _lambda,
    aws_events as events,
    aws_iam as iam,
    aws_events_targets as targets,
    aws_cloudwatch as cloudwatch,
    aws_sns as sns,
    aws_sns_subscriptions as subscriptions,
    aws_dynamodb as dynamodb,
    RemovalPolicy,
    Duration,
    ArnFormat,
    aws_apigateway as apigateway,
    custom_resources as cr,

)
from constructs import Construct
from aws_cdk import CfnOutput

class EricStack(Stack):
    
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        #https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_lambda/Function.html
        #https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_lambda/Code.html
        mylambda = _lambda.Function(
            self,
            "myFunction",
            runtime=_lambda.Runtime.PYTHON_3_13,
            code=_lambda.Code.from_asset("lambda"),
            handler="wiring.helloworldfunc",
            timeout= Duration.seconds(30),
        )

        ## cloudformation that attaches outside my deployed stack, pipeline and test
        ## do not havae to read a stack name in advance now
        ## solves telling lambda "function_name = "
        self.crawler_name_output = CfnOutput(self, "CrawlerFunctionName", value=mylambda.function_name)

    # Create the EventBridge Rule 
    # https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_events/Schedule.html

        eventRule = events.Rule(
            self,
            "myRule",
            schedule=events.Schedule.rate(Duration.minutes(15)),
        )

    

    #Adding SNS Topic to stack
    # https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_sns/README.html
        topic = sns.Topic(self, "WebsiteMonitoringTopic",
                          display_name = "Website Monitoring Alerts")
        

    #TODO - WRITE TO DYNAMO DB, CREATE IT IN STACK/ARCHITECTURE
    #Table Name : AlarmTable
    #Partition Key : [AlarmName, STRING]
    #Sort Key: [Timestamp, STRING]
        table = dynamodb.Table(self, "AlarmTable",
                               partition_key=dynamodb.Attribute(
                                   name = "AlarmName",
                                   type=dynamodb.AttributeType.STRING
                               ),
                               # Need this to log each unique record that fires
                               sort_key=dynamodb.Attribute(
                                   name="Timestamp",
                                   type=dynamodb.AttributeType.STRING
                               ),
                               billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
                               removal_policy=RemovalPolicy.DESTROY,
                               )
        
        self.alarm_table_output = CfnOutput(self, "AlarmTableName", value=table.table_name)
        
    #Lambda Subscription, needs seperate Lambda function
        alarmlambda = _lambda.Function(
            self, "AlarmLambdaFunction",
            runtime=_lambda.Runtime.PYTHON_3_13,
            code = _lambda.Code.from_asset("lambda"),
            handler = "alarmhandler.handle_alarm",
            #reference the dynamodb table created
            environment={
                "TABLE_ALARM": table.table_name
            }
        )
        topic.add_subscription(
            subscriptions.LambdaSubscription(alarmlambda)
        )
        # Grant permission to write to database
        table.grant_write_data(alarmlambda)

    #Add cloudwatch
    # https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_iam/PolicyStatement.html

        mylambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=["cloudwatch:PutMetricData"],
                resources=["*"],
                )
            )
        

        #Link to lambda
        eventRule.add_target(targets.LambdaFunction(mylambda))
        #Storing the websites in a DynamoDB managed through CRUD API
        #Used by wiring.py and CRUD Lambda
        #Using URL as partition key 
        #https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_dynamodb/Table.html
        targets_table = dynamodb.Table(self, "TargetsTable",
            partition_key=dynamodb.Attribute(
                name="url",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )
        self.targets_table_output = CfnOutput(self, "TargetsTableName", value=targets_table.table_name)
        
        dashboard = cloudwatch.Dashboard(self, "MetricMonitoringDashboard")

        def all_websites(metric_name):
            return cloudwatch.MathExpression(
                expression=f"SEARCH('{{WebsiteMonitoring,Website}} MetricName=\"{metric_name}\"', 'Average', 300)",
                using_metrics={},
                label="",
            )
        
        #https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch_Dashboards.html
        dashboard.add_widgets(
            cloudwatch.GraphWidget(title="ResponseTime (ms) - all websites", left=[all_websites("ResponseTime")]),
            cloudwatch.GraphWidget(title="HTTPS Status - all websites", left=[all_websites("StatusCode")]),
            cloudwatch.GraphWidget(title="Availability - all websites", left=[all_websites("Availability")]),
        )
        
        #Add environment tells the crawler the table name made above
        mylambda.add_environment("TABLE_TARGETS", targets_table.table_name)
        #Gives read only permissions to the crawler 
        targets_table.grant_read_data(mylambda)
        stack_name = Stack.of(self).stack_name

        #Tells stack to deploy crud.py as a Lambda function
        #Hands the four settings it needs
        #https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_lambda/Function.html
        crudlambda = _lambda.Function(
            self, "CrudLambdaFunction",
            runtime=_lambda.Runtime.PYTHON_3_13,
            code=_lambda.Code.from_asset("lambda"),
            handler="crud.handler",
            timeout=Duration.seconds(30),
            environment={
                "TABLE_TARGETS": targets_table.table_name,
                "TABLE_ALARM": table.table_name,
                "TOPIC_ARN": topic.topic_arn,
                "STACK_NAME": stack_name,
            },
        )
        #Grant permission for CRUD Lambda to do what crud.py wnats
        #https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_dynamodb/Table.html
        targets_table.grant_read_write_data(crudlambda)
        table.grant_read_write_data(crudlambda)
        crudlambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=["cloudwatch:PutMetricAlarm", "cloudwatch:DeleteAlarms"],
                resources=[self.format_arn(
                    service="cloudwatch",
                    resource="alarm",
                    resource_name=f"{stack_name}-*",
                    arn_format=ArnFormat.COLON_RESOURCE_NAME,
                )],
            )
        )
        crudlambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=["cloudwatch:DescribeAlarms"],
                resources=["*"],
            )
        )

        #API Gateway Gives HTTPS URL, receives requests from net nad passes it to CRUD Lambda
        #RESTful API Gateway, RESTful because resources have own URLS, HTTP method says what to do
        #Status code reports outcome
        #Stateless
        #https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_apigateway/RestApi.html
        #https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_apigateway/LambdaIntegration.html
        api = apigateway.RestApi(
            self, "TargetsApi",
            rest_api_name=f"{stack_name}-TargetsApi",
            description="CRUD API for the web crawler's target list",
            deploy_options=apigateway.StageOptions(stage_name="v1"),
            cloud_watch_role=False,
        )
        crud_integration = apigateway.LambdaIntegration(crudlambda)
        targets_resource = api.root.add_resource("targets")
        target_resource = targets_resource.add_resource("{url}")
        for method in ["GET", "POST", "PUT", "DELETE"]:
            targets_resource.add_method(method, crud_integration)
        for method in ["GET", "PUT", "DELETE"]:
            target_resource.add_method(method, crud_integration)

        self.api_url_output = CfnOutput(self, "ApiUrl", value=api.url)

        #Make cloudformation invode CRUD Lambda when stage is first deployed, and when stack is deleted
        #Cleans up alarms and seeds table
        websites_path = os.path.join(os.path.dirname(__file__), "..", "lambda", "websites.json")
        with open(websites_path) as f:
            websites = json.load(f)

        seed_call = cr.AwsSdkCall(
            service="Lambda",
            action="invoke",
            parameters={
                "FunctionName": crudlambda.function_name,
                "Payload": json.dumps({"action": "seed", "urls": websites}),
            },
            physical_resource_id=cr.PhysicalResourceId.of("SeedTargets"),
            output_paths=["StatusCode"],
        )
        seed = cr.AwsCustomResource(
            self, "SeedTargets",
            on_create=seed_call,
            on_update=seed_call,
            on_delete=cr.AwsSdkCall(
                service="Lambda",
                action="invoke",
                parameters={
                    "FunctionName": crudlambda.function_name,
                    "Payload": json.dumps({"action": "purge"}),
                },
                output_paths=["StatusCode"],
            ),
            policy=cr.AwsCustomResourcePolicy.from_statements([
                iam.PolicyStatement(
                    actions=["lambda:InvokeFunction"],
                    resources=[crudlambda.function_arn],
                ),
            ]),
            install_latest_aws_sdk=False,
        )
        seed.node.add_dependency(crudlambda)
        seed.node.add_dependency(targets_table)
