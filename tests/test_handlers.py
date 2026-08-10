"""
Unit tests for the register Lambda, using moto to mock DynamoDB so
tests run in CI with no real AWS calls or credentials needed.

Run locally:
    pytest tests/ -v
"""

import json
import os
import sys
import boto3
import pytest
from moto import mock_aws

# make lambdas/ importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lambdas"))


@pytest.fixture
def aws_credentials():
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"


@pytest.fixture
def dynamodb_tables(aws_credentials):
    with mock_aws():
        os.environ["EVENTS_TABLE"] = "Events"
        os.environ["REGISTRATIONS_TABLE"] = "Registrations"

        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")

        events_table = dynamodb.create_table(
            TableName="Events",
            KeySchema=[{"AttributeName": "eventId", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "eventId", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )

        registrations_table = dynamodb.create_table(
            TableName="Registrations",
            KeySchema=[{"AttributeName": "registrationId", "KeyType": "HASH"}],
            AttributeDefinitions=[
                {"AttributeName": "registrationId", "AttributeType": "S"},
                {"AttributeName": "email", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "EmailIndex",
                    "KeySchema": [{"AttributeName": "email", "KeyType": "HASH"}],
                    "Projection": {"ProjectionType": "ALL"},
                }
            ],
        )

        events_table.put_item(
            Item={"eventId": "evt_001", "name": "Test Conference", "capacity": 2, "registeredCount": 0}
        )

        yield {"events": events_table, "registrations": registrations_table}


def _invoke(module_name, event):
    """Reload the handler module fresh so it re-reads env vars per test."""
    if module_name in sys.modules:
        del sys.modules[module_name]
    module = __import__(module_name)
    return module.lambda_handler(event, None)


def make_event(body=None, path_params=None):
    return {
        "body": json.dumps(body) if body is not None else None,
        "pathParameters": path_params,
        "queryStringParameters": None,
    }


class TestRegister:
    def test_successful_registration(self, dynamodb_tables):
        event = make_event({"eventId": "evt_001", "email": "jane@example.com", "name": "Jane Doe"})
        result = _invoke("register", event)

        assert result["statusCode"] == 201
        body = json.loads(result["body"])
        assert body["registration"]["email"] == "jane@example.com"

    def test_missing_fields_returns_400(self, dynamodb_tables):
        event = make_event({"eventId": "evt_001"})
        result = _invoke("register", event)
        assert result["statusCode"] == 400

    def test_invalid_email_returns_400(self, dynamodb_tables):
        event = make_event({"eventId": "evt_001", "email": "not-an-email", "name": "Jane"})
        result = _invoke("register", event)
        assert result["statusCode"] == 400

    def test_unknown_event_returns_404(self, dynamodb_tables):
        event = make_event({"eventId": "evt_999", "email": "jane@example.com", "name": "Jane"})
        result = _invoke("register", event)
        assert result["statusCode"] == 404

    def test_duplicate_registration_returns_409(self, dynamodb_tables):
        event = make_event({"eventId": "evt_001", "email": "jane@example.com", "name": "Jane"})
        _invoke("register", event)
        result = _invoke("register", event)
        assert result["statusCode"] == 409

    def test_full_event_returns_409(self, dynamodb_tables):
        dynamodb_tables["events"].update_item(
            Key={"eventId": "evt_001"},
            UpdateExpression="SET registeredCount = :c",
            ExpressionAttributeValues={":c": 2},
        )
        event = make_event({"eventId": "evt_001", "email": "new@example.com", "name": "New Person"})
        result = _invoke("register", event)
        assert result["statusCode"] == 409

    def test_valid_phone_is_stored(self, dynamodb_tables):
        event = make_event(
            {"eventId": "evt_001", "email": "jane@example.com", "name": "Jane Doe", "phone": "+233 55 000 0000"}
        )
        result = _invoke("register", event)
        assert result["statusCode"] == 201
        body = json.loads(result["body"])
        assert body["registration"]["phone"] == "+233 55 000 0000"

    def test_missing_phone_is_omitted_not_stored_as_empty(self, dynamodb_tables):
        event = make_event({"eventId": "evt_001", "email": "jane@example.com", "name": "Jane Doe"})
        result = _invoke("register", event)
        body = json.loads(result["body"])
        assert "phone" not in body["registration"]

    def test_invalid_phone_returns_400(self, dynamodb_tables):
        event = make_event(
            {"eventId": "evt_001", "email": "jane@example.com", "name": "Jane Doe", "phone": "abc"}
        )
        result = _invoke("register", event)
        assert result["statusCode"] == 400


class TestListEvents:
    def test_returns_events(self, dynamodb_tables):
        event = make_event()
        result = _invoke("list_events", event)
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert len(body["events"]) == 1


class TestGetRegistrations:
    def test_returns_empty_list_for_unknown_email(self, dynamodb_tables):
        event = make_event(path_params={"email": "nobody@example.com"})
        result = _invoke("get_registrations", event)
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["registrations"] == []

    def test_returns_registrations_after_signup(self, dynamodb_tables):
        _invoke("register", make_event({"eventId": "evt_001", "email": "jane@example.com", "name": "Jane"}))
        result = _invoke("get_registrations", make_event(path_params={"email": "jane@example.com"}))
        body = json.loads(result["body"])
        assert len(body["registrations"]) == 1


class TestCancelRegistration:
    def test_cancel_unknown_id_returns_404(self, dynamodb_tables):
        result = _invoke("cancel_registration", make_event(path_params={"id": "does-not-exist"}))
        assert result["statusCode"] == 404

    def test_cancel_existing_registration(self, dynamodb_tables):
        reg_result = _invoke(
            "register", make_event({"eventId": "evt_001", "email": "jane@example.com", "name": "Jane"})
        )
        reg_id = json.loads(reg_result["body"])["registration"]["registrationId"]

        cancel_result = _invoke("cancel_registration", make_event(path_params={"id": reg_id}))
        assert cancel_result["statusCode"] == 200

        # confirm it's actually gone
        lookup = _invoke("get_registrations", make_event(path_params={"email": "jane@example.com"}))
        assert json.loads(lookup["body"])["registrations"] == []
