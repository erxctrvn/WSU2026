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
    aws_cloudwatch_actions as actions,
    aws_dynamodb as dynamodb,
    RemovalPolicy,
    Duration,

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
        )

        ## cloudformation that attaches outside my deployed stack, pipeline and test
        ## do not havae to read a stack name in advance now
        ## solves telling lambda "function_name = "
        CfnOutput(self, "CrawlerFunctionName", value=mylambda.function_name)

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
        
        # Create the dashboard for cloudwatch (using the metrics obtained)

        # Use os import to read same websitesjson as lambda
        # good for scale, dont need to update both files
        websites_path = os.path.join(os.path.dirname(__file__), "..", "lambda", "websites.json")
        with open(websites_path) as f:
            websites = json.load(f)

        dashboard = cloudwatch.Dashboard(self, "MetricMonitoringDashboard")



        # To-do create a for loop for each website linking to the json file that lambda uses
        # https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_cloudwatch/Metric.html
        for url in websites:
            alarm_id_safe = url.replace("https://", "").replace("/","").replace(".","")

            responsetimedash = cloudwatch.Metric(
                namespace="WebsiteMonitoring",
                metric_name="ResponseTime",
                dimensions_map={"Website": url},
            )
            statuscodedash = cloudwatch.Metric(
                namespace="WebsiteMonitoring",
                metric_name= "StatusCode",
                dimensions_map={"Website": url},
            )
            availabilitydash = cloudwatch.Metric(
                namespace="WebsiteMonitoring", 
                metric_name="Availability",
                dimensions_map={"Website": url},
            ) 
            # https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_cloudwatch/Dashboard.html
            dashboard.add_widgets(
                cloudwatch.GraphWidget(title=f"ResponseTime - {url}", left=[responsetimedash]),
                cloudwatch.GraphWidget(title=f"HTTPS Status- {url}", left=[statuscodedash]),
                cloudwatch.GraphWidget(title=f"Availability- {url}", left=[availabilitydash]),
            )




        #Creating a cloudwatch alarm belongs in CDK/Infrastructure
        #Because it manages lifecycle, trhesholds and permissions.,
        #Cloudwatch alarm can invoke Lambda or through eventbridge
        #https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_cloudwatch/ComparisonOperator.html#aws_cdk.aws_cloudwatch.ComparisonOperator
        #https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_cloudwatch/Alarm.html
        #Don't need to hardcode variables as it is inside a loop now.
            response_alarm = cloudwatch.Alarm(self, f"AlarmFromResponseTime-{alarm_id_safe}",
                    metric= responsetimedash,
                    threshold=1,
                    evaluation_periods=2,
                    comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
                    treat_missing_data=cloudwatch.TreatMissingData.BREACHING)
            #publishes notification from alarm to this sns topic
            #https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_cloudwatch/AlarmBase.html#aws_cdk.aws_cloudwatch.AlarmBase.add_alarm_action
            response_alarm.add_alarm_action(actions.SnsAction(topic))
            
            availability_alarm = cloudwatch.Alarm(self, f"AlarmFromURLStatus-{alarm_id_safe}",
                    metric=availabilitydash,
                    threshold=200,
                    evaluation_periods=1, 
                    comparison_operator=cloudwatch.ComparisonOperator.LESS_THAN_THRESHOLD,
                    treat_missing_data=cloudwatch.TreatMissingData.BREACHING)
            availability_alarm.add_alarm_action(actions.SnsAction(topic))
        
