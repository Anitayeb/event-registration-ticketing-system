# Event Registration & Ticketing System

A serverless event registration API built with AWS SAM, AWS Lambda, API Gateway, and DynamoDB.

## Live App
## Live App

- Frontend: https://regevents.online
- API: [https://7x9t6hky1e.execute-api.us-east-1.amazonaws.com/prod]
(https://7x9t6hky1e.execute-api.us-east-1.amazonaws.com/prod)

## Architecture

![Event Registration & Ticketing System architecture](docs/architecture.png)

## Features

- List available events.
- Register participants with an email address and optional phone number.
- Prevent duplicate registrations for the same event and email.
- Enforce event capacity.
- Retrieve registrations by email.
- Cancel registrations and update the event headcount.

## API Endpoints

### Register a participant

`POST /register`

Request body:

```json
{
	"eventId": "evt_001",
	"email": "jane@example.com",
	"name": "Jane Doe",
	"phone": "+233 55 000 0000"
}
```

The `phone` field is optional. When provided, it must contain a valid phone number. Blank phone values are omitted from the registration record.

Possible responses include:

- `201` registration created
- `400` invalid or missing input
- `404` event not found
- `409` duplicate registration or event is full

### List events

`GET /events`

Optional query parameters:

- `limit` limits the number of returned events.
- `lastKey` continues a paginated scan.

### Get registrations

`GET /registrations/{email}`

Returns all registrations associated with the email address using the `EmailIndex` DynamoDB index.

### Cancel a registration

`DELETE /registration/{id}`

Deletes the registration and decrements the related event's `registeredCount`.

## Project Structure

```text
lambda/
	registerParticipants/app.py
	getEvents/app.py
	getRegistrations/app.py
	cancelRegistrations/app.py
	utils.py
tests/
	test_handlers.py
frontend/
	index.html
	script.js
	styles.css
docs/
	architecture.png
template.yml
samconfig.toml
```

## DynamoDB Tables

- `Events`: partition key `eventId`; supports `capacity` and `registeredCount`.
- `Registrations`: partition key `registrationId`; includes the `EmailIndex` global secondary index on `email`.

## Local Development

Install the dependencies from the project root:

```powershell
python -m pip install -r requirements.txt
```

Run the tests:

```powershell
python -m pytest tests/ -v
```

Build and deploy with AWS SAM:

```powershell
sam build
sam deploy --guided
```

The Lambda functions use these environment variables:

- `EVENTS_TABLE`
- `REGISTRATIONS_TABLE`

These values are configured by `template.yml`.

