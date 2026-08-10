"""
DELETE /registration/{id}

Cancels (deletes) a registration by its registrationId and
decrements the event's registeredCount.
"""

import os

import boto3
from botocore.exceptions import ClientError

from utils import response, error_response

dynamodb = boto3.resource("dynamodb")

registrations_table = dynamodb.Table(os.environ["REGISTRATIONS_TABLE"])

events_table = dynamodb.Table(os.environ["EVENTS_TABLE"])


def lambda_handler(event, context):
    path_params = event.get("pathParameters") or {}
    registration_id = (path_params.get("id") or "").strip()

    # ---------------------------------------------------------
    # Validate registration ID
    # ---------------------------------------------------------
    if not registration_id:
        return error_response(400, "registration id path parameter is required")

    # ---------------------------------------------------------
    # Find registration
    # ---------------------------------------------------------
    try:
        lookup = registrations_table.get_item(Key={"registrationId": registration_id})
    except ClientError as e:
        error_message = e.response.get("Error", {}).get("Message") or str(e)

        return error_response(500, f"Could not look up registration: {error_message}")

    if "Item" not in lookup:
        return error_response(404, f"Registration '{registration_id}' not found")

    registration = lookup["Item"]

    # ---------------------------------------------------------
    # Delete registration
    # ---------------------------------------------------------
    try:
        registrations_table.delete_item(Key={"registrationId": registration_id})
    except ClientError as e:
        error_message = e.response.get("Error", {}).get("Message") or str(e)

        return error_response(500, f"Could not cancel registration: {error_message}")

    # ---------------------------------------------------------
    # Decrease event registeredCount
    # ---------------------------------------------------------
    event_id = registration.get("eventId")

    if event_id:
        try:
            events_table.update_item(
                Key={"eventId": event_id},
                UpdateExpression=(
                    "SET registeredCount = "
                    "if_not_exists(registeredCount, :zero) - :one"
                ),
                ExpressionAttributeValues={
                    ":zero": 0,
                    ":one": 1,
                },
            )
        except ClientError as e:
            error_message = e.response.get("Error", {}).get("Message") or str(e)

            return error_response(
                500,
                f"Registration cancelled, but event count "
                f"could not be updated: {error_message}",
            )

    # ---------------------------------------------------------
    # Successful cancellation
    # ---------------------------------------------------------
    return response(
        200,
        {
            "message": "Registration cancelled successfully",
            "registrationId": registration_id,
        },
    )
