# Website Monitoring Dashboard through AWS
AWS CDK application that monitors the health of a list of websites wit ha public CRUD API for managing that list. Every change deployed goes through a four stage CI/CD pipeline, with automated tests at each stage and also manual approval required.

This project was split into two parts. The **Web Health project** added a crawler Lambda that will check each website every 15 minutes, CloudWatch metrics, alarms and a adashboard, SNS notifications, alarm history table, and a CodePipeline with Alpha, Beta, Gamma and Prod stages. The **Applied Project** moves the list of websites which originally were in a JSON file into DynamoDB, added a public REST API to create, read, update, and delete entries, and added more tests in every pipeline stage.

# Metrics / Dashboard
- Availability: 1 = Online, 0 = Offline
- StatusCode: HTTP status code returned
- Response Time (ms): how long the site takes to respond

## Architecture
![Architecture Diagram](architecture.png)

Components marked NEW were added for the applied project. The API Gateway, CRUD Lambda and the targets table.

- **Public REST API (API Gateway)** receives the HTTP requests for `\targets` and passes them to CRUD Lambda/
- **CRUD Lambda (`crud.py`)** creates, reads, updates, and deletes targets, and creates and deletes each targets alarms.
- **Targets table(DynamoDB)** holds the list of websites to monitor with `url` as the partition key.
- **Schedule (EventBridge)** triggers the crawler every 15 minutes.
- **Crawler Lambda (`wiring.py)** reads the targets table, checks each website and publishes the website to CloudWatch/
- **CloudWatch** stores three metrics per website, holds two alarms per website and holds a dashboard.
- **Alarm handler (`alarmhandler.py`)** is subscrbed to the topic and writes each alarm state change to the alarm history table.
- **Alarm history table (DynamoDB)** uses `AlarmName` as partition key and `Timestamp` as the sort key.

## How it works

### Adding a website

1. A user sends a `POST /targets` with `{"url": "https://example.com/"}`.
2. API Gateway applies the CRUD Lambda.
3. The Lambda validates the URL and writes it to the targets table. The write is conditional, so if a URL that already exists you will get a `409 Conflict` status.
4. The Lambda creates two CloudWatch alarms for that URL.
5. On the next run within 15 minutes the crawler will scan targets table, find new URL and start checking it.

No redeployment is needed. Before the applied project adding new websites would be manually editing `websites.json` and running the whole pipeline again

No redeployment is needed. Before the applied project, adding a website meant editing `websites.json` and running the whole pipeline.


### Monitoring a website

Every 15 minutes EventBridge will trigger the crawler. For each URL in the targets table it will set a GET request and publish those metrics to `WebsiteMonitoring`. `ResponseTime` is in milliseconds, `StatusCode` (0 if the request failed), and `Availability` (1 if the site responds and 0 if not).

Each website has two alarms named afte rthe stack and the website. The reponseTime alarm fires when the average response time is abvoe the threshhold for two consecutive periods. The Availability alarm fires when availability drops below 1. When an alarm changes fires, CloudWatch will notify the SNS topic, and the alarm handler records the change in the alarm history table.

# How to run it 
- git clone <fork-url>
- cd eric
- python -m venv .venv
- .venv\Scripts\Activate.ps1
- python -m pip install -r requirements.txt
- cdk bootstrap
- cdk deploy

# Viewing Metrics and Dashboard & Alarm History
To view dashboard with metrics :
- AWS Console -> CloudWatch -> Metrics -> Dashboards -> WebsiteMonitoring.
To view Alarm History
- AWS Console -> DynamoDB -> Tables -> AlarmTable -> Explore table items.


# CDK instructions and scaling more Websites
Add a new URL to the 'websites.json' file and redeploy:
- cdk deploy
After deployment, destroy architecture by : 
- cdk destroy



