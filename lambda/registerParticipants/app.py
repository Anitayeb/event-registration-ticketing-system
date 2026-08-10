"""
POST /register
Registers an attendee for an event.

Expected JSON body:
{
    "eventId": "evt_001",
    "email": "jane@example.com",
    "name": "Jane Doe"
}
"""

import os
import re
import uuid
import boto3  # type: ignore
from datetime import datetime, timezone
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
from utils import response, error_response, parse_body

dynamodb = boto3.resource("dynamodb")
events_table = dynamodb.Table(os.environ["EVENTS_TABLE"])
registrations_table = dynamodb.Table(os.environ["REGISTRATIONS_TABLE"])

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^\+?[0-9][0-9\s\-()]{6,19}$")


def _extract_client_error_message(error: ClientError) -> str:
    return error.response.get("Error", {}).get("Message", str(error))


def lambda_handler(event, context):
    try:
        body = parse_body(event)
    except ValueError as e:
        return error_response(400, str(e))

    event_id = body.get("eventId")
    email = (body.get("email") or "").strip().lower()
    name = (body.get("name") or "").strip()
    phone = body.get("phone")
    if phone is not None:
        phone = str(phone).strip()

    # ---- Input validation ----
    if not event_id or not email or not name:
        return error_response(400, "eventId, email, and name are required")

    if not EMAIL_RE.match(email):
        return error_response(400, "Invalid email format")

    if phone and not PHONE_RE.match(phone):
        return error_response(400, "Invalid phone number")

    # ---- Confirm the event exists ----
    try:
        event_lookup = events_table.get_item(Key={"eventId": event_id})
    except ClientError as e:
        error_msg = _extract_client_error_message(e)
        return error_response(500, f"Could not verify event: {error_msg}")

    if "Item" not in event_lookup:
        return error_response(404, f"Event '{event_id}' not found")

    event_item = event_lookup["Item"]

    # ---- Prevent duplicate registration (same email, same event) ----
    try:
        existing = registrations_table.query(
            IndexName="EmailIndex",
            KeyConditionExpression=Key("email").eq(email),
        )
        for reg in existing.get("Items", []):
            if reg["eventId"] == event_id:
                return error_response(409, "This email is already registered for this event")
    except ClientError as e:
        error_msg = _extract_client_error_message(e)
        return error_response(500, f"Could not check existing registrations: {error_msg}")

    # ---- Capacity check (optional field on the event item) ----
    capacity = event_item.get("capacity")
    registered_count = event_item.get("registeredCount", 0)
    if capacity is not None and registered_count >= capacity:
        return error_response(409, "This event is fully booked")

    # ---- Write the registration ----
    registration_id = str(uuid.uuid4())
    item = {
        "registrationId": registration_id,
        "eventId": event_id,
        "email": email,
        "name": name,
        "status": "confirmed",
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }
    if phone:
        item["phone"] = phone

    try:
        registrations_table.put_item(Item=item)
        # keep a running headcount on the event record
        events_table.update_item(
            Key={"eventId": event_id},
            UpdateExpression="SET registeredCount = if_not_exists(registeredCount, :zero) + :inc",
            ExpressionAttributeValues={":inc": 1, ":zero": 0},
        )
    except ClientError as e:
        error_msg = _extract_client_error_message(e)
        return error_response(500, f"Could not save registration: {error_msg}")

    return response(201, {"message": "Registration successful", "registration": item})
