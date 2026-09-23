import aws_cdk as core
import aws_cdk.assertions as assertions

from eric.eric_stack import EricStack

# example tests. To run these tests, uncomment this file along with the example
# resource in eric/eric_stack.py
# add about 10 unit tests, 8 functional tests, and 5 integration tests do this for web health application 
# as many as you want for applied project, 2-1-1 anything extra will get extra credits
# 1-2 slides for presentation before demonstration/

def test_sqs_queue_created():
    app = core.App()
    stack = EricStack(app, "eric")
    template = assertions.Template.from_stack(stack)

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })
