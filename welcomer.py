import boto3
import botocore
import json

import bot_functions
import obliques

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table("oblique_beni")


def save_chat_id(chat_id: str) -> None:
    """Creates/updates a record on our DynamoDB for the given chat_id."""

    try:
        table.put_item(
            Item={"chat_id": chat_id, "last_msgd_at": 0},
            ConditionExpression="attribute_not_exists(chat_id)",
        )
    except botocore.exceptions.ClientError as e:
        if e.response["Error"]["Code"] != "ConditionalCheckFailedException":
            raise


def lambda_handler(event: dict, context: object) -> None:
    """1. Receives the telegram user's messages
       2. Creates/updates the chat_id records
       3. Checks the user's message:
            - Informs the user about its job if the message contains '/start'
            - Sends the user a random oblique strategy if the message contains '/ver'
            - Otherwise lets the user that it doesn't understand any other command.
    """
    message = json.loads(event["body"])
    chat_id = message["message"]["chat"]["id"]
    save_chat_id(str(chat_id))

    msg_text = message["message"]["text"]
    if "/start" in msg_text:
        bot_functions.send_message(
            "Aeyt buddy, seni kafama gore oblikliycem. You just go ahead and do your thing in the meantime.",
            chat_id,
        )
    elif "/ver" in msg_text:
        bot_functions.send_message(obliques.random_oblique(), chat_id)
    else:
        bot_functions.send_message(
            f"{msg_text} didin ama anlamadim, /start ya da /ver'den anliyorum ben bi.",
            chat_id,
        )

    return {"statusCode": 200}
