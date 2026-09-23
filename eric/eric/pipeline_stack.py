from aws_cdk import (
    Stack, 
    Stage, #stage is a container that can get deployed together
    pipelines,
    SecretValue,
)   

##Current pipeline protects against deployment level failures like
##Syntax, missing iports, Permission issues etc. Pipeline will stop and will not move on from Beta --> Gamma --> Prod
##Can push

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
        #making 4 so if something breaks it never reaches prod

        #Alpha for unit test 
        alpha_stage = pipeline.add_stage(
            WebsiteMonitoringStage(self, "Alpha"),
            # pre because its first stage
            pre=[
                pipelines.ShellStep(
                    "UnitTests",
                    commands=[
                        "cd eric",
                        "python -m pip install -r requirements.txt",
                        "python -m pytest tests/unit -v",
                    ],
                ),
            ],
        )

        #Beta for integration test    
        beta_stage = pipeline.add_stage(
            WebsiteMonitoringStage(self, "Beta"),
            post= [
                pipelines.ShellStep(
                    "IntegrationTest",
                    commands=[
                        "cd eric",
                        'python -m pip install -r requirements.txt',
                        "python -m pytest tests/integration -v",

                    ],
                ),
                pipelines.ManualApprovalStep("PromoteToGamma")
            ],
        )
        
        #Gamma for functional tests
        gamma-stage = pipeline.add_stage(
            WebsiteMonitoringStage(self, "Gamma"),
            post = [
                pipelines.ShellStep(
                    "FunctionalTests",
                    commands =[
                        "cd eric",
                        "python -m pip install -r requirements.txt",
                        "python -m pytest tests/integration -v",
                    ],
                ),
                pipelines.ManualApprovalStep("PromoteToProd"),
            ],
        )
        
        #Prod for production, no tests or approval needed 
        pipeline.add_stage(WebsiteMonitoringStage(self, "Prod"))
