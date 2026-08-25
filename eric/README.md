# Website Monitoring Dashboard through AWS
This project uses AWS CDK which will monitor a website every 30 minutes to track metrics through Lambda, EventBridge, and Cloudwatch

# Metrics / Dashboard
- Availability: 1 = Online, 0 = Offline
- StatusCode: HTTP status code returned
- Response Time (ms): how long the site takes to respond

# Architecture
- AWS Lambda: reads list from the websites.json and checks each one, recording metrics
- Amazon EventBridge: triggers Lambda on a schedule every 5 minutes
- Amazon CloudWatch: stores the metrics for each websites and puts them into a dashboard, alarms are raised when thresholds are breached.

# Alarms
Two alarms are created
- High response time: triggers if response time exceeds threshold for consecutive checks (2)
- Low availability: Triggers if site is unreachable

# Monitored Websites
Configured in websites.json, add or reomve URLs to scale the monitoring. Both Lambda and the CDK stack read from this file.
Currently monitoring: 
- github
- facebook
- youtube

# How to run it 
- git clone <fork-url>
- cd eric
- python -m venv .venv
- .venv\Scripts\Activate.ps1
- python -m pip install -r requirements.txt
- cdk bootstrap
- cdk deploy

# Viewing Metrics and Dashboard
To view dashboard with metrics :
- AWS Console -> CloudWatch -> Metrics -> Dashboards -> WebsiteMonitoring.

# CDK instructions and scaling more Websites
Add a new URL to the 'websites.json' file and redeploy:
- cdk deploy
After deployment, destroy architecture by : 
- cdk destroy



