import logging
from logging.handlers import RotatingFileHandler
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

from exceptions import EmptyAPIResponseError, WorngStatusCodeError

load_dotenv()

BASE_DIR = os.path.dirname(__file__)
log_file = os.path.join(BASE_DIR, 'logs.log')
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(stream=sys.stdout)
file_handler = RotatingFileHandler(log_file, maxBytes=5000000, backupCount=5)
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s - %(message)s'
)
handler.setFormatter(formatter)
file_handler.setFormatter(formatter)
logger.addHandler(handler)
logger.addHandler(file_handler)

PRACTICUM_TOKEN = os.getenv('PRAC_TOKEN')
TELEGRAM_TOKEN = os.getenv('BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELE_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


STATUSES_VERDICT = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot, message):
    """Отправляет сообщение."""
    try:
        logger.info('Попытка отправки сообщения')
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message
        )
    except telegram.error.TelegramError as error:
        logger.error(f'Сообщение не отправлено, ошибка:{error}')
    else:
        logger.info('Сообщение отправлено')


def get_api_answer(current_timestamp):
    """Получает ответ от API и переводит в данные Python."""
    timestamp = current_timestamp
    params = {
        'url': ENDPOINT,
        'headers': HEADERS,
        'from_date': timestamp
    }
    logger.error(
        'Запрос к API. URL={url}, headers={headers}, '
        'from_date={from_date}'.format(
            url=params['url'],
            headers=params['headers'],
            from_date=params['from_date']
        )
    )
    try:
        response = requests.get(
            params['url'],
            headers=params['headers'],
            params=params
        )
        if response.status_code != HTTPStatus.OK:
            raise WorngStatusCodeError(f'Статус: {response.status_code}')
        return response.json()
    except ConnectionError:
        logger.error(
            'Запрос к API не удался. URL={url}, headers={headers}, '
            'from_date={from_date}'.format(
                url=params['url'],
                headers=params['headers'],
                from_date=params['from_date']
            )
        )


def check_response(response):
    """Проверяет корректность ответа API."""
    logger.info('Начало проверки response')
    key_list = ('current_date', 'homeworks')
    if type(response) != dict:
        raise TypeError('response - не словарь!')
    for key in key_list:
        if key in response:
            logger.error(f'Ключ {key} есть')
        else:
            raise EmptyAPIResponseError(f' Нет ключа {key}')
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise KeyError('Домашка не список!')
    logger.error('Проверка пройдена')
    return homeworks


def parse_status(homework):
    """Формирует сообщение для телеграмма."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if not homework_name:
        raise KeyError('Имя домашки нет в словаре')
    if not homework_status:
        raise KeyError('Статуса домашки нет в словаре')
    if homework_status not in STATUSES_VERDICT:
        raise ValueError('Статуса домшаки нет в словаре вердиктов')
    return (
        'Изменился статус проверки работы "{homework_name}". '
        '{verdict}'.format(
            homework_name=homework_name,
            verdict=STATUSES_VERDICT[homework_status]
        )
    )


def check_tokens():
    """Проверяет все ли токены на месте."""
    token_tuple = (
        ('PRACTICUM_TOKEN', PRACTICUM_TOKEN),
        ('TELEGRAM_TOKEN', TELEGRAM_TOKEN),
        ('TELGRAM_CHAT_ID', TELEGRAM_CHAT_ID)
    )
    for name, token in token_tuple:
        if not token:
            logging.critical(f'Токена {token} {name} нет')
            return False
        else:
            logging.critical('Токены есть')
            return True


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        raise KeyError('Нет токенов')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    current_report = {}
    prev_report = {}
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            if homeworks:
                status_message = parse_status(homeworks[0])
                current_report['message'] = status_message
                current_report['name'] = homeworks[0].get('homework_name')
                if current_report != prev_report:
                    logging.info('Есть обновления')
                    send_message(bot, status_message)
                    prev_report = current_report.copy()
            else:
                message = 'Обновлений нет'
                current_report['message'] = message
                if current_report != prev_report:
                    logging.info('Обновлений нет')
                    send_message(bot, message)
                    prev_report = current_report.copy()

            current_timestamp = response['current_date']

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            current_report['message'] = message
            if current_report != prev_report:
                send_message(bot, message)
                prev_report = current_report.copy()
                logger.error(f'Сбой {error}')
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        filename='logs.log',
        filemode='w',
        format=('%(asctime)s - %(name)s - %(levelname)s '
                '- %(funcName)s - %(message)s')
    )
    main()
