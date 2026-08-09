from aws_cdk import (
    # Duration,
    # Import stack here like AWS Lambda, or any infrastructure.
    # Define what web URL you want to monitor and choose 
    # 3 different metrics for it and visualise it.
    # Use Event to invoke every x minutes for graph
    Stack,
    aws_lambda as _lambda,
    aws_cloudtrail as cloudtrail,
    aws_events as events,
    aws_iam as iam,
    aws_events_targets as targets,
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
    _lambda.addtorolepolicy(
        iam.PolicyStatement(
            actions=["cloudwatch:PutMetricData"],
            resources=["*"],
        )
    )

    #Link to lambda
    
