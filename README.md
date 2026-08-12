# Event Registration & Ticketing System

A serverless event registration and ticketing platform built on AWS SAM, Lambda, API Gateway, DynamoDB, S3, CloudFront, and CloudWatch.

## Live App

- Frontend: https://regevents.online
- API: https://7x9t6hky1e.execute-api.us-east-1.amazonaws.com/prod

## Phase 4 Highlights

This project includes the Phase 4 operational and deployment enhancements:

- CloudFront distribution for the static frontend hosted from an S3 bucket
- Custom domain support for the frontend (`regevents.online` and `www.regevents.online`)
- AWS Budget alerting with email notifications
- SNS topic for operational alerts and notifications
- CloudWatch alarms for Lambda error rate, API Gateway 5xx errors, and function duration
- CI/CD deployment workflow for backend and frontend deployment
- Monitoring and alerting support for production health checks

## Architecture

![Event Registration & Ticketing System architecture](docs/architecture.png)

## Features

- List available events
- Register participants with an email address and optional phone number
- Prevent duplicate registrations for the same event and email
- Enforce event capacity
- Retrieve registrations by email
- Cancel registrations and update the event headcount
- Serve the frontend through CloudFront using an S3 origin
- Monitor backend health with CloudWatch metrics and alarms
- Notify stakeholders through SNS and budget alerts

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

- `limit` limits the number of returned events
- `lastKey` continues a paginated scan

### Get registrations

`GET /registrations/{email}`

Returns all registrations associated with the email address using the `EmailIndex` DynamoDB index.

### Cancel a registration

`DELETE /registration/{id}`

Deletes the registration and decrements the related event's `registeredCount`.

## Project Structure

```text
.github/
  workflows/
    ci.yml
bucket-policy.json
cloudfront-config.json
frontend/
  index.html
  script.js
  styles.css
  config.js
lambda/
  registerParticipants/app.py
  getEvents/app.py
  getRegistrations/app.py
  cancelRegistrations/app.py
  utils.py
tests/
  test_handlers.py
  test_handler_monitoring.py
docs/
  architecture.png
README.md
requirements.txt
template.yml
samconfig.toml
```

## DynamoDB Tables

- `Events`: partition key `eventId`; stores event metadata such as `name`, `date`, `capacity`, and `registeredCount`
- `Registrations`: partition key `registrationId`; includes the `EmailIndex` global secondary index on `email`

## Monitoring and Alerts

The SAM template includes:

- SNS topic for alert notifications
- Email subscription via `AlertEmail`
- AWS Budgets cost threshold monitoring
- Lambda error rate alarms for all API handlers
- API Gateway 5xx alarm
- Lambda duration alarm for the register path

These are configured in `template.yml` under the monitoring and alerting resources.

## CI/CD Deployment

The repository includes a GitHub Actions workflow that deploys:

1. the backend via AWS SAM
2. the frontend contents to the S3 bucket
3. CloudFront cache invalidation after frontend changes

This workflow is defined in `.github/workflows/ci.yml`.

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

## Notes

- The frontend is served through CloudFront at `https://regevents.online`.
- The API still uses the generated API Gateway URL for the deployed backend endpoint.
- The project is designed to be simple, serverless, and low-maintenance while supporting production-style monitoring and deployment automation.

