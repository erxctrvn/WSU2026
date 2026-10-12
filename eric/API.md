# Target List API

A public REST API for managing the websites the crawler monitors. The list is stored in DynamoDB. Adding a website also creates its two CloudWatch alarms (ResponseTime and Availability), and deleting it removes them, so no redeploy is needed.

## Base URL

Each pipeline stage has its own API. The URL is the `ApiUrl` output of the stage's stack (CloudFormation console → `Beta-EricStack` → Outputs) and looks like:

```
https://<api-id>.execute-api.ap-southeast-2.amazonaws.com/v1/
```

There is no authentication. Request and response bodies are JSON.

## Identifying a target

A target is identified by its URL. To put a website URL inside the path it must be URL-encoded:

| Website | In the path |
| --- | --- |
| `https://github.com/` | `/targets/https%3A%2F%2Fgithub.com%2F` |

The same operations also accept the URL as a query string instead: `/targets?url=https://github.com/`.

## Endpoints

| Method | Path | What it does |
| --- | --- | --- |
| `GET` | `/targets` | List every target |
| `POST` | `/targets` | Add a target and create its alarms |
| `GET` | `/targets/{url}` | Read one target and the state of its alarms |
| `PUT` | `/targets/{url}` | Replace a target's URL |
| `DELETE` | `/targets/{url}` | Delete a target, its alarms and its alarm history |

### How to list targets

```
curl https://<api>/v1/targets
```

`200 OK`

```json
{
  "count": 3,
  "targets": [
    {"url": "https://facebook.com/"},
    {"url": "https://github.com/"},
    {"url": "https://youtube.com/"}
  ]
}
```

### How to add a target

```
curl -X POST https://<api>/v1/targets -H "Content-Type: application/json" -d "{\"url\": \"https://example.com/\"}"
```

`201 Created`

```json
{
  "url": "https://example.com/",
  "alarms": [
    "Beta-EricStack-ResponseTime-example-com",
    "Beta-EricStack-Availability-example-com"
  ]
}
```

The crawler picks the new website up on its next run (every 15 minutes).

### Read one target

```
curl https://<api>/v1/targets/https%3A%2F%2Fexample.com%2F
```

`200 OK`

```json
{
  "url": "https://example.com/",
  "alarms": [
    {"name": "Beta-EricStack-ResponseTime-example-com", "state": "OK"},
    {"name": "Beta-EricStack-Availability-example-com", "state": "ALARM"}
  ]
}
```

`state` is `OK`, `ALARM` or `INSUFFICIENT_DATA`.

### Update a target

Replaces the website's URL. The old URL's alarms and alarm history are deleted and alarms are created for the new URL.

```
curl -X PUT https://<api>/v1/targets/https%3A%2F%2Fexample.com%2F -H "Content-Type: application/json" -d "{\"url\": \"https://example.org/\"}"
```

`200 OK`

```json
{
  "url": "https://example.org/",
  "replaced": "https://example.com/",
  "alarms": [
    "Beta-EricStack-ResponseTime-example-org",
    "Beta-EricStack-Availability-example-org"
  ]
}
```

### Delete a target

Cascades: the DynamoDB item, both CloudWatch alarms, and every row those alarms wrote to the alarm history table.

```
curl -X DELETE https://<api>/v1/targets/https%3A%2F%2Fexample.org%2F
```

`200 OK`

```json
{
  "deleted": "https://example.org/",
  "alarmsDeleted": [
    "Beta-EricStack-ResponseTime-example-org",
    "Beta-EricStack-Availability-example-org"
  ],
  "historyRowsDeleted": 4
}
```

## Errors

Errors have the shape `{"error": "<message>"}`.

| Status | When |
| --- | --- |
| `400` | The body is not valid JSON, `url` is missing, or the URL does not start with `http://` or `https://` |
| `404` | The target is not in the list |
| `409` | A target with that URL already exists |
| `500` | Unexpected error (details are in the CRUD Lambda's CloudWatch logs) |

## URL rules

- Must start with `http://` or `https://` and include a host.
- Stored exactly as sent: `https://github.com` and `https://github.com/` are two different targets.
