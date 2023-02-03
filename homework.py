import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

from exeptions import UnexpectedStatusError, WrongResponseStatusCode

load_dotenv()

CURRENT_TIME = int(time.time())
PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger(__name__)

logger.setLevel(logging.DEBUG)


def check_tokens():
    """Проверяет доступность переменных окружения."""
    return all((PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID))


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        logging.debug('Начало отправки статуса в telegram')
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except telegram.error.TelegramError as error:
        logging.error(f'Ошибка отправки статуса в telegram: {error}')
    else:
        logging.debug('Успешная отправка сообщения!')


def get_api_answer(timestamp):
    """Делаем запрос к единственному эндпоинту API-сервиса."""
    current_time = timestamp
    params = {'from_date': current_time}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        if response.status_code != HTTPStatus.OK:
            text = 'Ответ от API не содержит статус 200'
            logging.error('Недоступен Эдпоинт')
            raise WrongResponseStatusCode(f'{text}')
        return response.json()
    except Exception as error:
        message = ('Ответ от API не содержит статус 200')
        raise WrongResponseStatusCode(message, error)


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    if type(response) is not dict:
        raise TypeError('Ответ от API имеет неверный тип объекта')
    if type(response.get('homeworks')) is not list:
        raise TypeError(
            'Ответ от API имеет неверный тип по ключу "homeworks"'
        )
    if "homeworks" not in response:
        raise KeyError('Ответ от API не содержит ключ "homework"')
    if "current_date" not in response:
        raise KeyError('Ответ от API не содержит ключ "current_date"')
    if len(response.get('homeworks')) > 0:
        return response.get('homeworks')
    else:
        logger.debug('Ответ от API не имеент домашних работ')


def parse_status(homework):
    """Информация о конкретной домашней работе."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if 'homework_name' not in homework:
        raise KeyError('Имя работы отсутствует')
    if 'status' not in homework:
        raise KeyError('Статуса нет в homeworks')
    if homework_status not in HOMEWORK_VERDICTS:
        raise KeyError('В домашней работе нет необходимого статуса')
    if not homework_status:
        raise UnexpectedStatusError('Неожиданный статус домашней работы')
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    logger.debug('Запуск бота')
    if not check_tokens():
        logging.critical(
            'Отсутствует один из токенов, работа программы остановлена'
        )
        sys.exit('Проверьте наличие всех токенов')

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = CURRENT_TIME

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if homeworks is not None:
                homework = homeworks[0]
                message = parse_status(homework)
                current_response = homework
                last_response = None
                if current_response != last_response:
                    send_message(bot, message)
            else:
                logger.debug('Новых статусов нет')
                text = 'Новых статусов нет'
                message = f'{text}'
                send_message(bot, message)

        except Exception as error:
            logger.error(f'Сбой в работе программы: {error}')
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
