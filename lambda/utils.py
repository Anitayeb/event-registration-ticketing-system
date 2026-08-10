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


def get_cors_headers(event: dict) -> dict:
    """Return CORS headers for an approved frontend origin."""

    request_headers = event.get("headers") or {}

    origin = (
        request_headers.get("origin")
        or request_headers.get("Origin")
        or ""
    )

    headers = {
        "Access-Control-Allow-Headers": "Content-Type,Authorization",
        "Access-Control-Allow-Methods": "OPTIONS,POST,GET,DELETE",
    }

    if origin in ALLOWED_ORIGINS:
        headers["Access-Control-Allow-Origin"] = origin

    return headers


class DecimalEncoder(json.JSONEncoder):
    """DynamoDB returns Decimal types; json.dumps can't serialize them natively."""

    def default(self, o):
        if isinstance(o, decimal.Decimal):
            return int(o) if o % 1 == 0 else float(o)

        return super().default(o)


def response(
    status_code: int,
    body: dict,
    event: dict | None = None
) -> dict:
    """Standard API Gateway Lambda proxy response."""

    return {
        "statusCode": status_code,
        "headers": {
            **get_cors_headers(event or {}),
            "Content-Type": "application/json",
        },
        "body": json.dumps(body, cls=DecimalEncoder),
    }


def error_response(
    status_code: int,
    message: str,
    event: dict | None = None
) -> dict:
    """Standard API error response."""

    logger.error(message)

    return response(
        status_code,
        {"error": message},
        event
    )


def parse_body(event: dict) -> dict:
    """Safely parse the JSON body from an API Gateway proxy event."""

    try:
        return json.loads(event.get("body") or "{}")

    except json.JSONDecodeError:
        raise ValueError("Request body is not valid JSON")