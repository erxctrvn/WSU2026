#This is the application where metric and values 
#From web resource
#This runs on top of the stack.


import json
def helloworldfunc(event,context):
    print("Recieved event:")
    return {
        'statusCode':200,
        'body':json.dumps("Hello World")
    }
#Create the three custom metrics
