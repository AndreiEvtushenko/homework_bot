import datetime
import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv
from exсeptions import TokensCustomException
from telegram.error import TelegramError

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(levelname)s - %(message)s')

file_handler = logging.FileHandler('log_bot.log', encoding='utf-8')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(
    logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logging.getLogger().addHandler(file_handler)

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """
    Проверяет доступность переменных окружения
    необходимые для работы программы.
    """
    logging.info('check_tokens(), проверка переменных.')

    tokens_list = [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]
    if all(tokens_list) is True:
        logging.info('check_tokens(), проверка переменных успешно завершена.')
        return True
    else:
        message = (
            'check_tokens(), '
            'Переменные окружения не доступны.'
        )
        logging.critical(message)
        raise TokensCustomException(message)


def send_message(bot, message):
    """Отправляет сообщения пользователю в телеграмм."""
    try:
        logging.info('send_message(). Отправляю сообщение.')
        if type(message) != str:
            logging.error('send_message(). Ошибка типа сообщения.')
            raise TypeError('send_message(). Неверный тип сообщения.')
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logging.debug(f'send_message(), {message}')
    except telegram.error.TimedOut as e:
        logging.error(
            f'send_message(), время ожидания соединения Telegram истекло: {e}')
    except telegram.error.RetryAfter as e:
        logging.error(
            f'send_message(), превышено количество запросов в Telegram: {e}')
    except TelegramError as e:
        logging.error(
            f'send_message(), ошибка Telegram при отправке сообщения: {e}')
    except Exception as e:
        logging.error(f'send_message(). Ошибка {e} при отправке сообщения.')


def get_api_answer(timestamp):
    """
    Делает запрос к эндпоинту API-сервиса.
    Возвращает словарь.
    """
    logging.info('get_api_answer(), делаю запрос к апи.')
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        if response.status_code != HTTPStatus.OK:
            message = (
                'get_api_answer(), API не доступно. '
                f'Ошибка: {response.status_code}'
            )
            logging.error(message)
            raise requests.HTTPError(message)
        elif response.status_code == 200:
            logging.info('get_api_answer(), запрос к API завершен успешно.')
            return response.json()
    except requests.exceptions.RequestException as e:
        message = f'get_api_answer(), сбой подключения к API: {e}'
        logging.error(message)
        raise ConnectionError(message)


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    logging.info('check_response(), проверяю данные из API')
    if type(response) != dict:
        message = (
            'check_response(), входные данные '
            'не соответствуют ожидаемым "dict".')
        logging.error(message)
        raise TypeError(message)
    if 'homeworks' not in response:
        message = ('check_response(), '
                   'словарь не содержит ключа "homeworks"')
        logging.error(message)
        raise KeyError(message)
    if type(response['homeworks']) != list:
        message = (
            'check_response(), входные данные '
            'не соответствуют ожидаемому типу: "list".')
        logging.error(message)
        raise TypeError(message)
    else:
        logging.info('check_response(), проверка завершена успешно')


def parse_status(homework):
    """
    Проверяет полученные данные.
    Извлекает из словаря стату.
    Возвращает подготовленную строку для отправки.
    """
    logging.info('parse_status(), проверяю и извлекаю данныею')
    if 'homework_name' not in homework:
        message = 'Ключа "homework_name" нет в ответе API домашки.'
        logging.error(message)
        raise KeyError(message)
    if 'status' in homework:
        value = homework['status']
        if value in HOMEWORK_VERDICTS:
            verdict = HOMEWORK_VERDICTS[value]
            logging.info('parse_status(), статус работы извлечен успешно.')
        else:
            message = f'parse_status(), неизвестный статус работы: {value}'
            logging.info(message)
            raise ValueError(message)

    homework_name = homework['homework_name']

    logging.info('Данные из словаря получены успешно.')

    return (
        'Изменился статус проверки работы '
        f'"{homework_name}"{verdict}')


def main():
    """Основная логика работы бота."""
    logging.info('main(), запуск приложения Homework_bot.')

    try:
        check_tokens()
    except TokensCustomException as e:
        message = f'Принудительное завершение работы программы. Ошибка: {e}.'
        logging.error(message)
        sys.exit(message)

    logging.info('main(), запускаю бот.')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    logging.info('main(), бот запущен.')

    # timestamp = int(time.time())
    dt = datetime.datetime(2020, 3, 1, 0, 0, 0)
    timestamp = int(time.mktime(dt.timetuple()))

    while True:
        try:
            homeworks = get_api_answer(timestamp)
            check_response(homeworks)

            if not homeworks['homeworks']:
                message = 'bot, домашняя работа не поступила на проверку'
                logging.info(message)

            else:
                homework = homeworks['homeworks'][0]
                message = parse_status(homework)
                send_message(bot, message)

        except Exception as e:
            message = f'Сбой в работе программы: {e}'
            logging.error(message)
            send_message(bot, message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
