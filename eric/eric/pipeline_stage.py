from aws_cdk import Stage
from constructs import Construct
from eric.eric_stack import EricStack

#represents one environment
class WebsiteMonitoringStage(Stage):
    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)
        EricStack(self, "EricStack")


    