import logging
import os
import sys
import time

import requests
import telegram
from dotenv import load_dotenv

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TOKEN')
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
    Проверяет доступность переменных окружения.
    которые необходимы для работы программы.
    """
    logging.info('check_tokens(), проверка переменных.')
    if PRACTICUM_TOKEN is None or not PRACTICUM_TOKEN:
        message = (
            'check_tokens(), '
            'Переменная "PRACTICUM_TOKEN" не доступна.'
            'Работа программы принудительно завершена.'
        )
        logging.critical(message)
        sys.exit(message)
    if TELEGRAM_TOKEN is None or not TELEGRAM_TOKEN:
        message = (
            'check_tokens(), '
            'Переменная "TELEGRAM_TOKEN" не доступна.'
            'Работа программы принудительно завершена.'
        )
        logging.critical(message)
        sys.exit(message)
    if TELEGRAM_CHAT_ID is None or not TELEGRAM_CHAT_ID:
        message = (
            'check_tokens(), '
            'Переменная "TELEGRAM_CHAT_ID" не доступна.'
            'Работа программы принудительно завершена.'
        )
        logging.critical(message)
        sys.exit(message)
    else:
        logging.info('check_tokens(), проверка переменных успешно завершена.')


def send_message(bot, message):
    """Отправляет сообщения пользователю в телеграмм."""
    try:
        logging.info('send_message(). Отправляю сообщение.')
        if type(message) != str:
            logging.error('send_message(). Ошибка типа сообщения.')
            raise TypeError('send_message(). Неверный тип сообщения.')
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logging.debug('send_message(). Сообщение отправлено.')
    except (telegram.error.ChatMigrated,
            telegram.error.NetworkError) as e:
        logging.error(f'send_message(). Ошибка {e} при отправке сообщения.')
        if isinstance(e, telegram.error.TimedOut):
            message = 'send_message(). Время ожидания соединения истекло.'
        else:
            message = 'send_message(). Ошибка при отправке сообщения.'
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
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
        if response.status_code != 200:
            message = (
                f'get_api_answer(), API не доступно. '
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

    try:
        if type(response) != dict:
            message = (
                'check_response(), входные данные '
                'не соответствуют ожидаемым "dict".'
                )
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
    except Exception as e:
        message = (
            f'check_response(), тип ошибки: {type(e)}, '
            f'ошибка: {e} при проверке данных из API')
        logging.error(message)


def parse_status(homework):
    """
    Проверяет полученные данные.
    Извлекает из словаря стату.
    Возвращает подготовленную строку для отправки.
    """
    logging.info('parse_status(), проверяю и извлекаю данныею')
    try:
        if 'status' in homework:
            value = homework['status']
            if value in HOMEWORK_VERDICTS:
                verdict = HOMEWORK_VERDICTS[value]
                logging.info('parse_status(), статус работы извлечен успешно.')
            else:
                message = f'parse_status(), неизвестный статус работы: {value}'
                logging.info(message)
                raise ValueError(message)
        else:
            message = 'parse_status(), нет ключа "status" в словаре homework'
            logging.info(message)
            raise KeyError(message)

        if 'homework_name' in homework:
            homework_name = homework['homework_name']
        else:
            message = (
                'parse_status(), '
                'нет ключа "homework_name" в словаре homework')
            logging.info(message)
            raise KeyError(message)

        logging.info('Данные из словаря получены успешно.')

        return (
            f'Изменился статус проверки работы: "{homework_name}", '
            f'вердикт: {verdict}')

    except KeyError as e:
        raise KeyError(f"Не найден ключ в словаре: {e}")
    except ValueError as e:
        raise ValueError(f"Ошибка: {e}")
    except Exception as e:
        logging.error(f"Ошибка: {type(e).__name__}. Ошибка словаря")
        return (f"Ошибка: {type(e).__name__}. Ошибка при обработке словаря."
                f'Работа ещё не принята в обработку')


def main():
    """Основная логика работы бота."""
    logging.info('main(), запуск приложения Homework_bot.')

    check_tokens()

    logging.info('main(), запускаю бот.')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    logging.info('main(), бот запущен.')

    timestamp = int(time.time())

    while True:
        try:
            homeworks = get_api_answer(timestamp)
            check_response(homeworks)

            if not homeworks['homeworks']:
                message = 'bot, домашняя работа не поступила на проверку'
                logging.info(message)
                send_message(bot, message)

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
