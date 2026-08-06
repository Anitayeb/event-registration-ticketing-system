"""
GET /events
Returns all events. Supports optional pagination via
?limit=20&lastKey=<eventId> query string params.
"""

import os
from typing import Any
import boto3
from botocore.exceptions import ClientError
from utils import response, error_response

dynamodb = boto3.resource("dynamodb")
events_table = dynamodb.Table(os.environ["EVENTS_TABLE"])


def lambda_handler(event, context):
    params = event.get("queryStringParameters") or {}
    limit = int(params.get("limit", 20))
    last_key = params.get("lastKey")

    scan_kwargs: dict[str, Any] = {"Limit": limit}
    if last_key:
        scan_kwargs["ExclusiveStartKey"] = {"eventId": last_key}

    try:
        result = events_table.scan(**scan_kwargs)
    except ClientError as e:
        error_message = e.response.get("Error", {}).get("Message") or str(e)
        return error_response(500, f"Could not list events: {error_message}")

    payload = {"events": result.get("Items", [])}
    if "LastEvaluatedKey" in result:
        payload["lastKey"] = result["LastEvaluatedKey"]["eventId"]

    return response(200, payload)
