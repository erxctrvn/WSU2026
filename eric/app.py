#!/usr/bin/env python3
import os
import aws_cdk as cdk

from eric.pipeline_stack import PipelineStack


app = cdk.App()
PipelineStack(app, "PipelineStack",
              env=cdk.Environment(account="758862546029", region="ap-southeast-2"),
              )

app.synth()
