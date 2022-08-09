import time
import logging
import os
import sys

import requests
import telegram

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.DEBUG,
    filename='logs.log',
    filemode='w',
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(stream=sys.stdout)
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s - %(message)s'
)
handler.setFormatter(formatter)
logger.addHandler(handler)

PRACTICUM_TOKEN = os.getenv('PRAC_TOKEN')
TELEGRAM_TOKEN = os.getenv('BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELE_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot, message):
    """Отправляет сообщение."""
    try:
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message
        )
        logger.info('Сообщение отправлено')
    except Exception as error:
        logger.error(f'Сообщение не отправлено, ошибка:{error}')


def get_api_answer(current_timestamp):
    """Получает ответ от API и переводит в данные Python."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    response = requests.get(
        ENDPOINT, headers=HEADERS, params=params
    )
    logger.error(f'Доступность эндпоинта {response.status_code}')
    if response.status_code != 200:
        raise Exception('Эндпоинт недоступен')
    else:
        response = response.json()
        return response


def check_response(response):
    """Проверяет корректность ответа API."""
    key_list = ('current_date', 'homeworks')
    for key in key_list:
        if key in response:
            logger.error(f'Ключ {key} есть')
        else:
            logger.error(f'Ключа {key} нет')
    if response['homeworks']:
        status = response['homeworks'][0].get('status')
        logger.error(f'Статус домашки {status}')
    else:
        logger.debug('Обновлений нет')
    return response['homeworks']


def parse_status(homework):
    """Формирует сообщение для телеграмма."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяет все ли токены на месте."""
    token_list = [PRACTICUM_TOKEN, TELEGRAM_TOKEN]
    tokens_exist = True
    for token in token_list:
        if not token:
            tokens_exist = False
    logger.critical(f'Переменные {tokens_exist}')
    return tokens_exist


def main():
    """Основная логика работы бота."""
    token_check = check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    while token_check:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            if homeworks:
                status_message = parse_status(homeworks[0])
                send_message(bot, status_message)
            else:
                message = 'Обновлений нет'
                send_message(bot, message)

            current_timestamp = response['current_date']
            time.sleep(RETRY_TIME)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
            logger.error(f'Сбой {error}')
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
