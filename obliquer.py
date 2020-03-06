import boto3
import botocore
import datetime
import random
from time import time
import logging
import bot_functions
import obliques

import os
import sys

here = os.path.dirname(os.path.realpath(__file__))
sys.path.append(os.path.join(here, "./vendored"))
import pytz


events_client = boto3.client("events")
lambda_client = boto3.client("lambda")
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table("oblique_beni")


NEXT_SCHEDULE_MIN_DELAY = 4
NEXT_SCHEDULE_MAX_DELAY = 6
NEXT_SCHEDULE_EARLIEST_HOUR = 8
NEXT_SCHEDULE_LATEST_HOUR = 23
HOURS_ON_EARTH = 24  #:P


def calculate_postpone(current_hour: int) -> int:
    """Calculate the postponed hours if necessary, taking the PST hours into account.

    The intention is to send the oblique strategies during the daytime and sleep during the night.
    However, this bot is only intended to be a gift to my husband and we live in PST.
    So the perks only apply to us >;)
    """
    if current_hour > NEXT_SCHEDULE_LATEST_HOUR - NEXT_SCHEDULE_MAX_DELAY:
        return (
            HOURS_ON_EARTH
            - current_hour
            + NEXT_SCHEDULE_EARLIEST_HOUR
            - NEXT_SCHEDULE_MIN_DELAY
        )
    return 0


def calculate_next_schedule() -> int:
    """Calculate how many minutes after the next run would be, taking the extra sleep time into account. 

    For the sleep details, check calculate_postpone function.
    """
    utc_now = datetime.datetime.now(datetime.timezone.utc)
    pacific_now = utc_now.astimezone(pytz.timezone("US/Pacific"))
    pacific_hour = pacific_now.hour
    postponed_hours = calculate_postpone(pacific_hour)
    logging.info(f"Postponed hours is {postponed_hours}")

    return random.randint(
        (postponed_hours + NEXT_SCHEDULE_MIN_DELAY) * 60,
        (postponed_hours + NEXT_SCHEDULE_MAX_DELAY) * 60,
    )


FN_NAME = "serverless-obliqueBeniBot-dev-obliquer"
FN_ARN = "arn:aws:lambda:us-west-1:510608237778:function:serverless-obliqueBeniBot-dev-obliquer"


def schedule_self() -> None:
    """Creates/updates a rule under CloudWatch Events, to re-run self."""

    next_after = calculate_next_schedule()
    logging.info(f"Our next scheduled run is after: {next_after} minutes")
    frequency = f"rate({next_after} minutes)"

    rule_name = f"{FN_NAME}-Trigger"
    rule_response = events_client.put_rule(
        Name=rule_name, ScheduleExpression=frequency, State="ENABLED",
    )
    if "RuleArn" in rule_response:
        rule_arn = rule_response["RuleArn"]
        event_response = events_client.put_targets(
            Rule=rule_name, Targets=[{"Id": "obliquerLambdaTriggerID", "Arn": FN_ARN}]
        )
        failed_entry_count = event_response["FailedEntryCount"]
        if failed_entry_count == 0:
            try:
                lambda_client.add_permission(
                    FunctionName=FN_NAME,
                    StatementId="obliquerLambdaTriggerStatementID",
                    Action="lambda:InvokeFunction",
                    Principal="events.amazonaws.com",
                    SourceArn=rule_arn,
                )
            except botocore.exceptions.ClientError as e:
                # Ignore the ResourceConflictException as this can happen for consecutive runs; bubble up other exceptions
                if e.response["Error"]["Code"] != "ResourceConflictException":
                    raise
        else:
            logging.error("Failed to add the rule target.")
    else:
        logging.error("Failed to put rule for self-scheduling.")


def save_timestamp(chat_id: str) -> None:
    """Saves the current time as the last_msgd_at attribute of our table records."""

    table.update_item(
        Key={"chat_id": chat_id},
        UpdateExpression="SET last_msgd_at = :val1",
        ExpressionAttributeValues={":val1": int(time())},
    )


CONCURRENT_LAMBDA_BUFFER = 3


def lambda_handler(event: dict, context: object) -> dict:
    """After getting triggered by a CloudWatch Event Rule
       2. Gets all chatted user records from DynamoDB
       3. Gets the latest timestamp for messaging any user
       4. Checks if this execution is due to CloudWatch's multiple Lambda triggering issue
       5. If not, sends a random oblique strategy to each user
       6. Saves the latest message timestamp for each user record
       7. Re-schedules self execution
    """
    chat_ids = []
    latest_msgd_at = 0

    items = table.scan()["Items"]
    for item in items:
        chat_id = item["chat_id"]
        chat_ids.append(chat_id)
        last_msgd_at = item["last_msgd_at"]
        if last_msgd_at > latest_msgd_at:
            latest_msgd_at = last_msgd_at

    # CloudWatch event rules can trigger lambda functions multiple times consecutively, although you set up your rule for a single trigger. This is a workaround to discard the rest of the subsequently fired Lambdas and prevent doing the same job again
    diff = int(time()) - latest_msgd_at
    if diff > (60 * CONCURRENT_LAMBDA_BUFFER):
        for chat_id in chat_ids:
            bot_functions.send_message(obliques.random_oblique(), chat_id)
            save_timestamp(chat_id)
        schedule_self()
    else:
        logging.info(
            f"Diff between now and latest message time was: {diff} seconds so I'm skipping this execution."
        )

    return {"statusCode": 200}
