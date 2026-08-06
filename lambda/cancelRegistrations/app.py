"""
DELETE /registration/{id}
Cancels (deletes) a registration by its registrationId, and
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
    registration_id = path_params.get("id")

    if not registration_id:
        return error_response(400, "registration id path parameter is required")

    # ---- Confirm it exists first, so we can return a clean 404 ----
    try:
        lookup = registrations_table.get_item(Key={"registrationId": registration_id})
    except ClientError as e:
        # Safely access nested keys on the ClientError response to avoid TypedDict access errors
        resp = getattr(e, "response", {}) or {}
        err = resp.get("Error", {}) or {}
        msg = err.get("Message") or str(e)
        return error_response(500, f"Could not look up registration: {msg}")

    if "Item" not in lookup:
        return error_response(404, f"Registration '{registration_id}' not found")
