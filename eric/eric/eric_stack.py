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
    Duration,

)
from constructs import Construct

class EricStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        mylambda = _lambda.Function(
            self,
            "myFunction",
            runtime=_lambda.Runtime.PYTHON_3_13,
            code=_lambda.Code.from_asset("lambda"),
            handler="wiring.helloworldfunc",
        )

    # Create the EventBridge Rule 
        eventRule = events.Rule(
            self,
            "myRule",
            schedule=events.Schedule.rate(Duration.minutes(30)),
        )

   
    #Add cloudwatch
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
            dashboard.add_widgets(
                cloudwatch.GraphWidget(title=f"ResponseTime - {url}", left=[responsetimedash]),
                cloudwatch.GraphWidget(title=f"HTTPS Status- {url}", left=[statuscodedash]),
                cloudwatch.GraphWidget(title=f"Availability- {url}", left=[availabilitydash]),
            )




        #Creating a cloudwatch alarm belongs in CDK/Infrastructure
        #Because it manages lifecycle, trhesholds and permissions.,
        #Cloudwatch alarm can invoke Lambda or through eventbridge
        #https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_cloudwatch/ComparisonOperator.html#aws_cdk.aws_cloudwatch.ComparisonOperator
        #Don't need to hardcode variables as it is inside a loop now.
            cloudwatch.Alarm(self, f"AlarmFromResponseTime-{alarm_id_safe}",
                    metric= responsetimedash,
                    threshold=200,
                    evaluation_periods=2,
                    comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
                    treat_missing_data=cloudwatch.TreatMissingData.BREACHING)
            cloudwatch.Alarm(self, f"AlarmFromURLStatus-{alarm_id_safe}",
                    metric=availabilitydash,
                    threshold=1,
                    evaluation_periods=1, 
                    comparison_operator=cloudwatch.ComparisonOperator.LESS_THAN_THRESHOLD,
                    treat_missing_data=cloudwatch.TreatMissingData.BREACHING)
        
