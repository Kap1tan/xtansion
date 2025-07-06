"""
Вспомогательные функции для бота клуба X10.
"""
import re
import base64
import hashlib
from typing import Optional, Union, Dict, Any
import datetime
from aiogram import Bot
from aiogram.types import User

from config import Config

def generate_ref_link(bot_username: str, user_id: int) -> str:
    """
    Генерация реферальной ссылки
    :param bot_username: Имя пользователя бота
    :param user_id: ID пользователя-реферера
    :return: Реферальная ссылка
    """
    encoded_id = base64.urlsafe_b64encode(str(user_id).encode()).decode().rstrip('=')
    return f"https://t.me/{bot_username}?start=ref_{encoded_id}"

def extract_referrer_id(start_param: str) -> Optional[int]:
    """
    Извлечение ID реферера из параметра start
    :param start_param: Параметр start
    :return: ID реферера или None, если параметр неверный
    """
    if not start_param or not start_param.startswith('ref_'):
        return None

    try:
        # Добавляем недостающие символы = для декодирования base64
        encoded_id = start_param[4:]
        padding = '=' * (4 - len(encoded_id) % 4)
        decoded = base64.urlsafe_b64decode((encoded_id + padding).encode()).decode()
        return int(decoded)
    except (ValueError, UnicodeDecodeError):
        return None

def format_time_left(end_date: Union[str, datetime.datetime]) -> str:
    """
    Форматирование оставшегося времени до окончания подписки
    :param end_date: Дата окончания подписки
    :return: Отформатированная строка
    """
    if isinstance(end_date, str):
        end_date = datetime.datetime.fromisoformat(end_date.replace('Z', '+00:00'))

    now = datetime.datetime.now()
    if end_date < now:
        return "Подписка истекла"

    delta = end_date - now
    days = delta.days
    hours = delta.seconds // 3600
    minutes = (delta.seconds % 3600) // 60

    if days > 0:
        return f"{days} дн. {hours} ч."
    elif hours > 0:
        return f"{hours} ч. {minutes} мин."
    else:
        return f"{minutes} мин."

def get_user_name(user: User) -> str:
    """
    Получение имени пользователя для обращения
    :param user: Объект пользователя
    :return: Имя пользователя
    """
    if user.first_name:
        return user.first_name
    elif user.username:
        return user.username
    else:
        return "Пользователь"

async def kick_user_from_group(bot: Bot, config: Config, user_id: int) -> bool:
    """
    Исключение пользователя из группы
    :param bot: Объект бота
    :param config: Конфигурация
    :param user_id: ID пользователя
    :return: True, если исключение успешно, иначе False
    """
    try:
        await bot.ban_chat_member(
            chat_id=config.bot.group_id,
            user_id=user_id,
            until_date=datetime.datetime.now() + datetime.timedelta(seconds=35)  # Бан на 35 секунд (кик)
        )
        return True
    except Exception as e:
        print(f"Ошибка при исключении пользователя {user_id} из группы: {e}")
        return False

async def check_user_in_group(bot: Bot, config: Config, user_id: int) -> bool:
    """
    Проверка, состоит ли пользователь в группе
    :param bot: Объект бота
    :param config: Конфигурация
    :param user_id: ID пользователя
    :return: True, если пользователь в группе, иначе False
    """
    try:
        member = await bot.get_chat_member(chat_id=config.bot.group_id, user_id=user_id)
        return member.status not in ["left", "kicked"]
    except Exception as e:
        print(f"Ошибка при проверке пользователя {user_id} в группе: {e}")
        return False

def get_payment_description(product_type: str, config: Config) -> Dict[str, Any]:
    """
    Получение описания платежа
    :param product_type: Тип продукта
    :param config: Конфигурация
    :return: Словарь с описанием платежа
    """
    if product_type == "club":
        return {
            "name": "Клуб Х10",
            "description": "Доступ к Клубу Х10 на 1 месяц",
            "amount": config.payment.club_price,
            "days": 30
        }
    elif product_type == "vietnam":
        return {
            "name": "Экскурсия по Вьетнаму",
            "description": "VIP продукт: экскурсия по Вьетнаму",
            "amount": config.payment.vietnam_tour_price,
            "days": 0
        }
    elif product_type == "consultation":
        return {
            "name": "Консультация основателя",
            "description": "Персональная консультация с основателем Клуба Х10",
            "amount": config.payment.consultation_price,
            "days": 0
        }
    else:
        return {
            "name": "Неизвестный продукт",
            "description": "Описание недоступно",
            "amount": 0,
            "days": 0
        }


def parse_callback_data(callback_data: str) -> Dict[str, str]:
    """
    Парсинг данных из callback_data
    :param callback_data: Строка callback_data
    :return: Словарь с данными
    """
    parts = callback_data.split(':')
    print(f"Разбор callback_data: {callback_data} на части: {parts}")  # Отладочная информация

    result = {"action": parts[0]}

    if len(parts) > 1:
        result["product"] = parts[1]

    if len(parts) > 2:
        result["method"] = parts[2]

    if len(parts) > 3:
        result["id"] = parts[3]

    print(f"Результат парсинга: {result}")  # Отладочная информация
    return result

def get_subscription_end_text(user_id: int, days_left: int) -> str:
    """
    Получение текста уведомления об окончании подписки
    :param user_id: ID пользователя
    :param days_left: Количество дней до окончания подписки
    :return: Текст уведомления
    """
    if days_left == 3:
        return (
            f"Здравствуйте!\n\n"
            f"Напоминаем, что осталось 3 дня до окончания доступа к продукту Клуб Х10.\n\n"
            f"Для продления действующей подписки нажмите кнопку Продлить доступ"
        )
    elif days_left == 1:
        return (
            f"Здравствуйте!\n\n"
            f"Напоминаем, что осталось 1 день до окончания доступа к продукту Клуб Х10.\n\n"
            f"Для продления действующей подписки нажмите кнопку Продлить доступ"
        )
    else:
        return (
            f"Здравствуйте!\n\n"
            f"Сообщаем, что Вам ограничен доступ к продукту Клуб Х10.\n\n"
            f"Для приобретения новой подписки нажмите кнопку Доступ Х10"
        )

def get_formatted_referral_count(count: int) -> str:
    """
    Получение правильного склонения для количества рефералов
    :param count: Количество рефералов
    :return: Отформатированная строка
    """
    if count % 10 == 1 and count % 100 != 11:
        return f"{count} друга"
    elif 2 <= count % 10 <= 4 and (count % 100 < 10 or count % 100 >= 20):
        return f"{count} друга"
    else:
        return f"{count} друзей"

def validate_phone_number(phone: str) -> bool:
    """
    Проверка корректности номера телефона
    :param phone: Номер телефона
    :return: True, если номер корректный, иначе False
    """
    # Упрощенная проверка - только цифры, длина 10-15 символов без учета +
    cleaned_phone = re.sub(r'[^\d]', '', phone)
    return 10 <= len(cleaned_phone) <= 15

def generate_payment_id(user_id: int, timestamp: datetime.datetime) -> str:
    """
    Генерация уникального ID платежа
    :param user_id: ID пользователя
    :param timestamp: Временная метка
    :return: Уникальный ID платежа
    """
    hash_input = f"{user_id}_{timestamp.isoformat()}"
    return hashlib.md5(hash_input.encode()).hexdigest()[:8]

def format_payment_amount(amount: int) -> str:
    """
    Форматирование суммы платежа
    :param amount: Сумма в рублях
    :return: Отформатированная строка
    """
    return f"{amount:,}".replace(',', ' ') + " руб."