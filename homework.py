import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

from exeptions import (ProgramMalfunction,
                       WrongResponseStatusCode)

load_dotenv()

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


def check_tokens() -> bool:
    """Проверяет доступность переменных окружения."""
    return all((PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID))


def send_message(bot: telegram.bot.Bot, message: str) -> None:
    """Отправляет сообщение в Telegram чат."""
    try:
        logging.debug('Начало отправки статуса в telegram')
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except telegram.error.TelegramError as error:
        logging.error(f'Ошибка отправки статуса в telegram: {error}')
    else:
        logging.debug('Успешная отправка сообщения!')


def get_api_answer(timestamp: int) -> dict:
    """Делаем запрос к единственному эндпоинту API-сервиса."""
    current_time = timestamp or int(time.time())
    params = {'from_date': current_time}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except requests.exceptions.RequestException as error:
        message = ('Ответ от API не содержит статус 200')
        raise WrongResponseStatusCode(message, error)
    if response.status_code != HTTPStatus.OK:
        text = 'Ответ от API не содержит статус 200'
        logging.error('Не  содержит статус 200')
        raise WrongResponseStatusCode(f'{text}')
    return response.json()


def check_response(response: dict) -> bool:
    """Проверяет ответ API на соответствие документации."""
    if not isinstance(response, dict):
        raise TypeError('Ответ от API имеет неверный тип объекта')
    homework_response = response.get('homeworks')
    if not isinstance(homework_response, list):
        raise TypeError(
            'Ответ от API имеет неверный тип по ключу "homeworks"',
        )
    logging.debug('API вернул корректный ответ.')
    return homework_response


def parse_status(homework: bool) -> str:
    """Информация о конкретной домашней работе."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if not  homework_name:
        raise KeyError('Имя работы отсутствует')
    verdict = HOMEWORK_VERDICTS.get(homework_status)
    if not verdict:
        raise KeyError('В домашней работе нет необходимого статуса')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main() -> str:
    """Основная логика работы бота."""
    logger.debug('Запуск бота')
    if not check_tokens():
        logging.critical(
            'Отсутствует один из токенов, работа программы остановлена'
        )
        sys.exit('Проверьте наличие всех токенов')

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())

    while True:
        try:
            response = get_api_answer(timestamp)
            timestamp = response.get('current_date')
            homeworks = check_response(response)
            if homeworks:
                homework = homeworks[0]
                logger.debug('Статус изменился')
                message = parse_status(homework)
                if homework:
                    send_message(bot, message)
            else:
                logger.debug('Новых статусов нет')
                text = 'Новых статусов нет'
                message = f'{text}'
                send_message(bot, message)

        except (KeyError, TypeError, WrongResponseStatusCode) as error:
            logger.error(f'Сбой в работе программы: {error}')
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
