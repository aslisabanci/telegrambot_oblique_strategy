import os
import sys

here = os.path.dirname(os.path.realpath(__file__))
sys.path.append(os.path.join(here, "./vendored"))
import requests


TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
URL = "https://api.telegram.org/bot{}/".format(TELEGRAM_TOKEN)


def send_message(text: str, chat_id: str) -> None:
    url = URL + "sendMessage?text={}&chat_id={}".format(text, chat_id)
    requests.get(url)
