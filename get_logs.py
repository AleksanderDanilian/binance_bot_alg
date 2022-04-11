from pprint import pprint
import requests
from urllib.parse import urljoin

api_token = "a92e6e2dabab5f3f36a43029dc1110bcfc4fbdc4"
username = "AlexD2334"
pythonanywhere_host = "www.pythonanywhere.com"

api_base = "https://{pythonanywhere_host}/api/v0/user/{username}/".format(
    pythonanywhere_host=pythonanywhere_host,
    username=username,
)

resp = requests.get(
    urljoin(api_base, "files/path/home/{username}/binance_bot_alg/logs/binance.log".format(username=username)),
    headers={"Authorization": "Token {api_token}".format(api_token=api_token)}
)

open('c:/users/ale-d/downloads/logs.txt', 'wb').write(resp.content)


def get_balance(log_file_path='c:/users/ale-d/downloads/logs.txt'):
    with open(log_file_path, 'r', encoding="Latin-1") as file:
        match_list = []

        for line in file:
            if 'XRP' in line:
                try:
                    temp = [line.partition('[')[0][:-5], int(eval(eval(line.partition('\'USDT\': ')[2].rpartition(', \'TRX\'')[0])))]
                    match_list.append(temp)
                except:
                    continue


    file.close()

    pprint(match_list)


get_balance()
