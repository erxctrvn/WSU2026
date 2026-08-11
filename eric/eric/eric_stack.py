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
    aws_cloudtrail as cloudtrail,
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
            schedule=events.Schedule.rate(Duration.minutes(5)),
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
    
    #Create the dashboard for cloudwatch (using the metrics obtained)
        responsetimedash = cloudwatch.Metric(
            namespace="WebsiteMonitoring",
            metric_name="ResponseTime",
        )
        statuscodedash = cloudwatch.Metric(
            namespace="WebsiteMonitoring",
            metric_name= "StatusCode",
        )
        availabilitydash = cloudwatch.Metric(
            namespace="WebsiteMonitoring", 
            metric_name="Availability",
        )
        dashboard = cloudwatch.Dashboard(self, "MetricMonitoringDashboard")
        dashboard.add_widgets(
            cloudwatch.GraphWidget(title="ResponseTime", left=[responsetimedash]),
            cloudwatch.GraphWidget(title="HTTPS Status", left=[statuscodedash]),
            cloudwatch.GraphWidget(title="Availability", left=[availabilitydash]),
        )
            
        
