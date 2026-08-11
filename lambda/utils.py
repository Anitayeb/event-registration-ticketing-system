"""
Shared helper functions used by all Lambda handlers.
Keeps CORS headers, response formatting, JSON serialization,
and logging consistent across every endpoint.
"""

import json
import logging
import decimal

logger = logging.getLogger()
logger.setLevel(logging.INFO)


ALLOWED_ORIGINS = {
    "https://regevents.online",
    "https://www.regevents.online",
}


CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",  # tighten to your domain in prod
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "OPTIONS,POST,GET,DELETE",
}


class DecimalEncoder(json.JSONEncoder):
    """DynamoDB returns Decimal types; json.dumps can't serialize them natively."""

    def default(self, o):
        if isinstance(o, decimal.Decimal):
            return int(o) if o % 1 == 0 else float(o)
        return super().default(o)


def response(status_code: int, body: dict) -> dict:
    """Standard API Gateway Lambda proxy response."""
    return {
        "statusCode": status_code,
        "headers": {**CORS_HEADERS, "Content-Type": "application/json"},
        "body": json.dumps(body, cls=DecimalEncoder),
    }


def error_response(status_code: int, message: str) -> dict:
    logger.error(message)
    return response(status_code, {"error": message})


def parse_body(event: dict) -> dict:
    """Safely parse the JSON body from an API Gateway proxy event."""
    try:
        return json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        raise ValueError("Request body is not valid JSON")




