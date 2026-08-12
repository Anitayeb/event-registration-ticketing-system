"""
POST /register
Registers an attendee for an event.

Expected JSON body:
{
    "eventId": "evt_001",
    "email": "jane@example.com",
    "name": "Jane Doe",
    "phone": "+233550000000"   # optional
}
"""

import os
import re
import uuid
import boto3
from datetime import datetime, timezone
from botocore.exceptions import ClientError
from utils import response, error_response, parse_body

dynamodb = boto3.resource("dynamodb")
events_table = dynamodb.Table(os.environ["EVENTS_TABLE"])
registrations_table = dynamodb.Table(os.environ["REGISTRATIONS_TABLE"])

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
# Loose international phone check: optional leading +, 7-15 digits, spaces/dashes allowed.
PHONE_RE = re.compile(r"^\+?[\d\s\-()]{7,20}$")
# eventId comes from the seeded Events table, not free text — keep it to a
# predictable shape so it can never carry anything unexpected downstream.
EVENT_ID_RE = re.compile(r"^[A-Za-z0-9_\-]{1,64}$")

MAX_NAME_LENGTH = 100
# Strips control/non-printable characters (form-feed, null bytes, etc.) that
# have no legitimate reason to be in a person's name — defense in depth for
# clients that bypass the frontend entirely (curl, Postman, a script).
CONTROL_CHAR_RE = re.compile(r"[\x00-\x1f\x7f]")


def lambda_handler(event, context):
    try:
        body = parse_body(event)
    except ValueError as e:
        return error_response(400, str(e))

    event_id = (body.get("eventId") or "").strip()
    email = (body.get("email") or "").strip().lower()
    name = CONTROL_CHAR_RE.sub("", (body.get("name") or "")).strip()[:MAX_NAME_LENGTH]
    phone = (body.get("phone") or "").strip()

    # ---- Input validation ----
    if not event_id or not email or not name:
        return error_response(400, "eventId, email, and name are required")

    if not EVENT_ID_RE.match(event_id):
        return error_response(400, "Invalid eventId format")

    if not EMAIL_RE.match(email):
        return error_response(400, "Invalid email format")

    if phone and not PHONE_RE.match(phone):
        return error_response(400, "Invalid phone number format")

    # ---- Confirm the event exists ----
    try:
        event_lookup = events_table.get_item(Key={"eventId": event_id})
    except ClientError as e:
        return error_response(500, f"Could not verify event: {e.response['Error']['Message']}")

    if "Item" not in event_lookup:
        return error_response(404, f"Event '{event_id}' not found")

    event_item = event_lookup["Item"]

    # ---- Prevent duplicate registration (same email, same event) ----
    try:
        existing = registrations_table.query(
            IndexName="EmailIndex",
            KeyConditionExpression=boto3.dynamodb.conditions.Key("email").eq(email),
        )
        for reg in existing.get("Items", []):
            if reg["eventId"] == event_id:
                return error_response(409, "This email is already registered for this event")
    except ClientError as e:
        return error_response(500, f"Could not check existing registrations: {e.response['Error']['Message']}")

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
        return error_response(500, f"Could not save registration: {e.response['Error']['Message']}")

    return response(201, {"message": "Registration successful", "registration": item})