"""
Модуль с клавиатурами для бота.
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

# Основное меню
def main_menu_kb() -> InlineKeyboardMarkup:
    """
    Клавиатура основного меню
    """
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="Клуб Х10", callback_data="club"))
    builder.add(InlineKeyboardButton(text="Мероприятия", callback_data="events"))
    builder.add(InlineKeyboardButton(text="Мои рефералы", callback_data="my_referrals"))
    builder.add(InlineKeyboardButton(text="Мой баланс", callback_data="my_balance"))
    builder.adjust(2)  # 2 кнопки в ряду
    return builder.as_markup()

# Меню клуба
def club_menu_kb() -> InlineKeyboardMarkup:
    """
    Клавиатура меню клуба
    """
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="Оплатить доступ", callback_data="pay_club"))
    builder.add(InlineKeyboardButton(text="О клубе", callback_data="about_club"))
    builder.add(InlineKeyboardButton(text="Главное меню", callback_data="main_menu"))
    builder.adjust(2)
    return builder.as_markup()

# Способы оплаты
def payment_methods_kb(product_type: str) -> InlineKeyboardMarkup:
    """
    Клавиатура с выбором способа оплаты
    """
    # Используем простой подход без использования Builder для отладки
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Банковская карта", callback_data=f"pay_method:{product_type}:card")],
        [InlineKeyboardButton(text="Telegram Stars ⭐", callback_data=f"pay_method:{product_type}:stars")],
        [InlineKeyboardButton(text="Криптовалюта 🪙", callback_data=f"pay_method:{product_type}:crypto")],
        [InlineKeyboardButton(text="Назад", callback_data="club")],
        [InlineKeyboardButton(text="Главное меню", callback_data="main_menu")],
    ])

    return keyboard

# Выбор криптовалюты
# Выбор криптовалюты
def crypto_assets_kb(product_type: str, assets: list) -> InlineKeyboardMarkup:
    """
    Клавиатура с выбором криптовалюты для оплаты
    :param product_type: Тип продукта (club, vietnam, consultation)
    :param assets: Список доступных криптовалют
    :return: Клавиатура для выбора криптовалюты
    """
    builder = InlineKeyboardBuilder()

    # Добавляем кнопки для каждой криптовалюты
    for asset in assets:
        builder.add(InlineKeyboardButton(
            text=f"{asset} 🪙",
            callback_data=f"crypto_asset:{product_type}:{asset}"
        ))

    # Кнопки навигации
    builder.add(InlineKeyboardButton(text="Назад к способам оплаты", callback_data=f"pay_club"))
    builder.add(InlineKeyboardButton(text="Главное меню", callback_data="main_menu"))

    builder.adjust(2, 1, 1)  # По две кнопки в первом ряду, затем по одной
    return builder.as_markup()

# Клавиатура для оплаты криптовалютой
def crypto_payment_kb(invoice_url: str, payment_id: int = None) -> InlineKeyboardMarkup:
    """
    Клавиатура для оплаты криптовалютой
    :param invoice_url: URL инвойса Crypto Bot
    :param payment_id: ID платежа в нашей системе (опционально)
    :return: Клавиатура с ссылкой на оплату
    """
    builder = InlineKeyboardBuilder()

    # Кнопка для оплаты
    builder.add(InlineKeyboardButton(text="Оплатить криптовалютой", url=invoice_url))

    # Кнопка для проверки статуса платежа (если есть ID платежа)
    if payment_id:
        builder.add(InlineKeyboardButton(
            text="Проверить статус платежа",
            callback_data=f"check_crypto_payment:{payment_id}"
        ))

    # Кнопка отмены
    builder.add(InlineKeyboardButton(text="Отмена", callback_data="cancel_payment"))

    builder.adjust(1)  # По одной кнопке в ряду
    return builder.as_markup()

# Мероприятия
def events_kb() -> InlineKeyboardMarkup:
    """
    Клавиатура с выбором мероприятий
    """
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="Экскурсия по Вьетнаму", callback_data="event:vietnam"))
    builder.add(InlineKeyboardButton(text="Консультация Анатолия", callback_data="event:consultation"))
    builder.add(InlineKeyboardButton(text="Главное меню", callback_data="main_menu"))
    builder.adjust(1)
    return builder.as_markup()

# Подтверждение оплаты
def payment_confirmation_kb(payment_id: int) -> InlineKeyboardMarkup:
    """
    Клавиатура для подтверждения оплаты
    """
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="Я оплатил", callback_data=f"confirm_payment:{payment_id}"))
    builder.add(InlineKeyboardButton(text="Нужна помощь", callback_data="need_help"))
    builder.add(InlineKeyboardButton(text="Отмена", callback_data="cancel_payment"))
    builder.adjust(1)
    return builder.as_markup()

# Клавиатура для оплаты звездами
def stars_payment_kb(amount: int, payment_id: int) -> InlineKeyboardMarkup:
    """
    Клавиатура для оплаты Telegram Stars
    """
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text=f"Оплатить {amount} ⭐", pay=True))
    builder.add(InlineKeyboardButton(text="Отмена", callback_data="cancel_payment"))
    builder.adjust(1)
    return builder.as_markup()

# Реферальная система
def referral_kb(referral_link: str) -> InlineKeyboardMarkup:
    """
    Клавиатура для реферальной системы
    """
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="Реферальная ссылка", callback_data=f"get_ref_link"))
    builder.add(InlineKeyboardButton(text="Мои рефералы", callback_data="my_referrals"))
    builder.add(InlineKeyboardButton(text="Главное меню", callback_data="main_menu"))
    builder.adjust(1)
    return builder.as_markup()

# Продление подписки
def extend_subscription_kb() -> InlineKeyboardMarkup:
    """
    Клавиатура для продления подписки
    """
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="Продлить доступ", callback_data="extend_subscription"))
    builder.add(InlineKeyboardButton(text="Не сейчас", callback_data="not_now"))
    builder.adjust(1)
    return builder.as_markup()

# Клавиатура для вступления в клуб
def join_club_kb() -> InlineKeyboardMarkup:
    """
    Клавиатура для вступления в клуб
    """
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="Войти", callback_data="join_club"))
    builder.add(InlineKeyboardButton(text="Узнать больше", callback_data="learn_more"))
    builder.adjust(1)
    return builder.as_markup()

# Клавиатура для доступа к клубу (после оплаты)
def club_access_kb() -> InlineKeyboardMarkup:
    """
    Клавиатура для доступа к клубу
    """
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="ВОЙТИ", callback_data="access_club"))
    builder.add(InlineKeyboardButton(text="Главное меню", callback_data="main_menu"))
    builder.adjust(1)
    return builder.as_markup()

# Клавиатура для получения реферальной ссылки
def get_referral_link_kb() -> InlineKeyboardMarkup:
    """
    Клавиатура для получения реферальной ссылки
    """
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="Получить ссылку", callback_data="generate_ref_link"))
    builder.add(InlineKeyboardButton(text="Главное меню", callback_data="main_menu"))
    builder.adjust(1)
    return builder.as_markup()

# Клавиатура для VIP мероприятий
def vip_events_kb() -> InlineKeyboardMarkup:
    """
    Клавиатура для VIP мероприятий
    """
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="Узнать о VIP продукте", callback_data="about_vip"))
    builder.add(InlineKeyboardButton(text="Больше о Клубе Х10", callback_data="about_club"))
    builder.add(InlineKeyboardButton(text="Об основателе", callback_data="about_founder"))
    builder.adjust(1)
    return builder.as_markup()

# Клавиатура для получения VIP доступа
def get_vip_access_kb() -> InlineKeyboardMarkup:
    """
    Клавиатура для получения VIP доступа
    """
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="Получить доступ", callback_data="get_vip_access"))
    builder.add(InlineKeyboardButton(text="Главное меню", callback_data="main_menu"))
    builder.adjust(1)
    return builder.as_markup()

# Клавиатура для получения консультации
def get_consultation_kb() -> InlineKeyboardMarkup:
    """
    Клавиатура для получения консультации
    """
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="Получить консультацию", callback_data="get_consultation"))
    builder.add(InlineKeyboardButton(text="Главное меню", callback_data="main_menu"))
    builder.adjust(1)
    return builder.as_markup()

# Клавиатура "Нужна помощь"
def need_help_kb() -> InlineKeyboardMarkup:
    """
    Клавиатура для обращения за помощью
    """
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="Связаться с менеджером", url="https://t.me/anatoliy_lobanov"))
    builder.add(InlineKeyboardButton(text="Назад", callback_data="back"))
    builder.adjust(1)
    return builder.as_markup()