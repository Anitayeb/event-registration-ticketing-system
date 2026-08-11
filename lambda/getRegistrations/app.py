"""
GET /registrations/{email}
Returns every registration made by a given email address.
Requires a Global Secondary Index named "EmailIndex" on the
Registrations table, partition key = email.
"""

import os
import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
from utils import response, error_response

dynamodb = boto3.resource("dynamodb")
registrations_table = dynamodb.Table(os.environ["REGISTRATIONS_TABLE"])


def lambda_handler(event, context):
    path_params = event.get("pathParameters") or {}
    email = (path_params.get("email") or "").strip().lower()

    if not email:
        return error_response(400, "email path parameter is required")

    try:
        result = registrations_table.query(
            IndexName="EmailIndex",
            KeyConditionExpression=Key("email").eq(email),
        )
    except ClientError as e:
        error_message = e.response.get("Error", {}).get("Message") or str(e)
        return error_response(500, f"Could not fetch registrations: {error_message}")

    items = result.get("Items", [])
    if not items:
        return response(
            200,
            {"email": email, "registrations": [], "message": "No registrations found"},
        )

    return response(200, {"email": email, "registrations": items})
