import json
import os
import uuid
import urllib.error
import urllib.parse
import urllib.request

os.environ.setdefault("AWS_DEFAULT_REGION", "ap-southeast-2")

import boto3
import pytest

API_URL = os.environ.get("API_URL")

pytestmark = pytest.mark.skipif(not API_URL, reason="API_URL not set")


def call_api(method, path="", body=None):
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        f"{API_URL.rstrip('/')}/targets{path}",
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def as_path(url):
    return "/" + urllib.parse.quote(url, safe="")


def alarms_that_exist(names):
    found = boto3.client("cloudwatch").describe_alarms(AlarmNames=names)["MetricAlarms"]
    return sorted(alarm["AlarmName"] for alarm in found)


def test_full_crud_lifecycle_through_the_api():
    run_id = uuid.uuid4().hex
    site = f"https://example.com/crud-test-{run_id}"
    renamed = f"https://example.com/crud-test-{run_id}-renamed"

    try:
        # CREATE
        status, created = call_api("POST", body={"url": site})
        assert status == 201
        assert len(created["alarms"]) == 2
        assert alarms_that_exist(created["alarms"]) == sorted(created["alarms"])

        status, _ = call_api("POST", body={"url": site})
        assert status == 409

        # READ
        status, listing = call_api("GET")
        assert status == 200
        assert {"url": site} in listing["targets"]

        status, single = call_api("GET", as_path(site))
        assert status == 200
        assert single["url"] == site

        # UPDATE
        status, updated = call_api("PUT", as_path(site), body={"url": renamed})
        assert status == 200
        assert updated["url"] == renamed
        assert alarms_that_exist(created["alarms"]) == []
        assert alarms_that_exist(updated["alarms"]) == sorted(updated["alarms"])

        # DELETE
        status, deleted = call_api("DELETE", as_path(renamed))
        assert status == 200
        assert alarms_that_exist(updated["alarms"]) == []

        status, _ = call_api("GET", as_path(renamed))
        assert status == 404
    finally:
        call_api("DELETE", as_path(site))
        call_api("DELETE", as_path(renamed))