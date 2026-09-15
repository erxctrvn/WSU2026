from aws_cdk import (
    Stack, 
    Stage, #stage is a container that can get deployed together
    pipelines,
    SecretValue,
)   
from constructs import Construct
#import website monitoring stack
from eric.eric_stack import EricStack

#Custom stage type
class WebsiteMonitoringStage(Stage):
    #instantiate existing application stack
    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id,**kwargs)
        EricStack(self, "EricStack")

class PipelineStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, ** kwargs):
        super().__init__(scope, construct_id, **kwargs)

        pipeline = pipelines.CodePipeline(
            self, "Pipeline",
            synth= pipelines.ShellStep(
                "Synth",
                input=pipelines.CodePipelineSource.git_hub(
                    "erxctrvn/WSU2026",
                    "main",
                    authentication=SecretValue.secrets_manager("github-token"),
                ),
                commands=[
                    "cd eric",
                    "npm install -g aws-cdk",
                    "python -m pip install -r requirements.txt",
                    "cdk synth",
                ],
                primary_output_directory="eric/cdk.out",
            ),
        )
        #creation of seperate copies of WebsiteMonitoringStage wrapped to my full stack
        #making 3 so if something breaks it never reaches prod
        pipeline.add_stage(WebsiteMonitoringStage(self, "Beta"))
        pipeline.add_stage(WebsiteMonitoringStage(self, "Gamma"))
        pipeline.add_stage(WebsiteMonitoringStage(self, "Prod"))
