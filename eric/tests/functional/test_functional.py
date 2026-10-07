import json
import sys
import os
from unittest import mock
import pytest

# boto3 clients/resources are created at import time in wiring.py and
# alarmhandler.py, so a region must exist before they are imported
os.environ.setdefault("AWS_DEFAULT_REGION", "ap-southeast-2")
os.environ.setdefault("TABLE_ALARM", "FakeTable")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lambda"))


@pytest.fixture
def mock_cloudwatch():
    with mock.patch("wiring.cloudwatch") as mock_cw:
        yield mock_cw


def test_crawl_func_marks_reachable_site_up(mock_cloudwatch):
    import wiring
    with mock.patch("wiring.urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value.getcode.return_value = 200
        wiring.crawl_func("https://example.com/")

    call_kwargs = mock_cloudwatch.put_metric_data.call_args.kwargs
    metrics = {m["MetricName"]: m["Value"] for m in call_kwargs["MetricData"]}
    assert metrics["Availability"] == 1
    assert metrics["StatusCode"] == 200


def test_crawl_func_marks_unreachable_site_down(mock_cloudwatch):
    import wiring
    with mock.patch("wiring.urllib.request.urlopen", side_effect=Exception("timeout")):
        wiring.crawl_func("https://example.com/")

    call_kwargs = mock_cloudwatch.put_metric_data.call_args.kwargs
    metrics = {m["MetricName"]: m["Value"] for m in call_kwargs["MetricData"]}
    assert metrics["Availability"] == 0
    assert metrics["StatusCode"] == 0


def test_crawl_func_publishes_exactly_three_metrics(mock_cloudwatch):
    import wiring
    with mock.patch("wiring.urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value.getcode.return_value = 200
        wiring.crawl_func("https://example.com/")

    call_kwargs = mock_cloudwatch.put_metric_data.call_args.kwargs
    names = {m["MetricName"] for m in call_kwargs["MetricData"]}
    assert names == {"ResponseTime", "StatusCode", "Availability"}


def test_crawl_func_response_time_is_positive(mock_cloudwatch):
    import wiring
    with mock.patch("wiring.urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value.getcode.return_value = 200
        wiring.crawl_func("https://example.com/")

    call_kwargs = mock_cloudwatch.put_metric_data.call_args.kwargs
    metrics = {m["MetricName"]: m["Value"] for m in call_kwargs["MetricData"]}
    assert metrics["ResponseTime"] > 0


def test_helloworldfunc_checks_every_website(mock_cloudwatch):
    import wiring
    fake_sites = ["https://a.com/", "https://b.com/", "https://c.com/"]
    with mock.patch("wiring.loadmultwebs", return_value=fake_sites), \
         mock.patch("wiring.crawl_func") as mock_crawl:
        result = wiring.helloworldfunc({}, None)

    assert mock_crawl.call_count == 3
    assert result["statusCode"] == 200
    assert "Checked 3 websites" in result["body"]


def test_handle_alarm_extracts_alarm_name_and_state():
    import alarmhandler

    sns_message = json.dumps({
        "AlarmName": "Availability-examplecom",
        "NewStateValue": "ALARM",
        "NewStateReason": "Threshold crossed",
    })
    event = {"Records": [{"Sns": {"Message": sns_message}}]}

    with mock.patch.object(alarmhandler, "table") as mock_table:
        result = alarmhandler.handle_alarm(event, None)

    put_item_args = mock_table.put_item.call_args.kwargs["Item"]
    assert put_item_args["AlarmName"] == "Availability-examplecom"
    assert put_item_args["NewStateValue"] == "ALARM"
    assert result["statusCode"] == 200


def test_handle_alarm_writes_item_with_iso_timestamp():
    import alarmhandler

    sns_message = json.dumps({
        "AlarmName": "ResponseTime-examplecom",
        "NewStateValue": "OK",
        "NewStateReason": "Back to normal",
    })
    event = {"Records": [{"Sns": {"Message": sns_message}}]}

    with mock.patch.object(alarmhandler, "table") as mock_table:
        alarmhandler.handle_alarm(event, None)

    put_item_args = mock_table.put_item.call_args.kwargs["Item"]
    # ISO format timestamps contain a 'T' separator between date and time
    assert "T" in put_item_args["Timestamp"]


def test_handle_alarm_processes_multiple_records():
    import alarmhandler

    def make_record(name):
        return {"Sns": {"Message": json.dumps({
            "AlarmName": name, "NewStateValue": "ALARM", "NewStateReason": "test"
        })}}

    event = {"Records": [make_record("Availability-a"), make_record("Availability-b")]}

    with mock.patch.object(alarmhandler, "table") as mock_table:
        alarmhandler.handle_alarm(event, None)

    assert mock_table.put_item.call_count == 2
