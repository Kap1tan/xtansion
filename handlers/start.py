"""
Обработчик команды /start для бота клуба X10.
"""
import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext

from database import Database
from config import Config
from keyboards import main_menu_kb, get_referral_link_kb
from utils import extract_referrer_id, get_user_name

router = Router()
logger = logging.getLogger(__name__)


@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot, db: Database, config: Config, state: FSMContext):
    """
    Обработчик команды /start
    """
    # Сбрасываем состояние FSM
    await state.clear()

    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    last_name = message.from_user.last_name

    # Добавляем пользователя в базу данных
    await db.add_user(user_id, username, first_name, last_name)

    # Проверяем параметр start для реферальной системы
    start_param = message.text.split()[-1] if len(message.text.split()) > 1 else None

    if start_param and start_param.startswith('ref_'):
        referrer_id = extract_referrer_id(start_param)

        if referrer_id and referrer_id != user_id:
            # Получаем информацию о реферере
            referrer = await db.get_user(referrer_id)

            if referrer:
                # Добавляем запись о реферале
                referral_id = await db.add_referral(user_id, referrer_id)

                if referral_id > 0:
                    # Начисляем бонусы рефереру
                    new_balance = await db.update_user_balance(referrer_id, config.referral.points_per_referral)

                    # Выдаем бесплатные дни приглашенному
                    await db.add_subscription(user_id, config.referral.free_days)

                    # Отправляем уведомление рефереру
                    referrer_name = get_user_name(message.from_user)
                    await bot.send_message(
                        referrer_id,
                        f"🎉 Поздравляем! Ты пригласил 1 друга! 🎉\n\n"
                        f"Твой счет пополнен на {config.referral.points_per_referral} баллов "
                        f"(1 балл = 1 рубль)\n"
                        f"Спасибо, что помогаешь нам расти!\n\n"
                        f"Продолжай в том же духе:\n"
                        f"💎 3 друга – доступ к VIP продукту экскурсия по Вьетнаму\n"
                        f"🚀 5 друзей – месяц бесплатного членства в Клубе Х10\n"
                        f"🌟 10 друзей – персональная консультация с основателем Клуба Х10\n\n"
                        f"👉 Продолжай приглашать друзей и получай еще больше бонусов!"
                    )

                    # Отправляем приветственное сообщение приглашенному
                    await message.answer(
                        f"🎉 Добро пожаловать в нашу реферальную программу!\n\n"
                        f"Вы получили {config.referral.free_days} дней безоплатного членства в клубе Х10\n"
                        f"Подробнее о клубе здесь (https://t.me/x10_club_info)",
                        reply_markup=main_menu_kb()
                    )

                    # Проверяем достижение бонусных уровней
                    await check_referrer_bonuses(bot, db, config, referrer_id)

                    return

    # Обычное приветственное сообщение
    await message.answer(
        f"Привет, {get_user_name(message.from_user)}! 👋\n\n"
        f"Добро пожаловать в бот клуба X10! Здесь ты можешь:\n"
        f"- Оплатить доступ к клубу и мероприятиям\n"
        f"- Использовать реферальную систему\n"
        f"- Проверить свой баланс и статус подписки\n\n"
        f"Выбери нужное действие в меню 👇",
        reply_markup=main_menu_kb()
    )


@router.message(Command("menu"))
async def cmd_menu(message: Message, state: FSMContext):
    """
    Обработчик команды /menu - вывод главного меню
    """
    await state.clear()
    await message.answer(
        f"Главное меню клуба X10:",
        reply_markup=main_menu_kb()
    )


@router.callback_query(F.data == "main_menu")
async def callback_main_menu(callback: CallbackQuery, state: FSMContext):
    """
    Обработчик нажатия кнопки "Главное меню"
    """
    await state.clear()
    await callback.message.edit_text(
        f"Главное меню клуба X10:",
        reply_markup=main_menu_kb()
    )
    await callback.answer()


@router.callback_query(F.data == "my_balance")
async def callback_my_balance(callback: CallbackQuery, db: Database):
    """
    Обработчик нажатия кнопки "Мой баланс"
    """
    user_id = callback.from_user.id
    user = await db.get_user(user_id)

    if user:
        balance = user.get('balance', 0)
        subscription = await db.check_subscription(user_id)

        subscription_text = ""
        if subscription:
            end_date = subscription.get('end_date')
            if end_date:
                from datetime import datetime
                end_date_obj = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                days_left = (end_date_obj - datetime.now()).days
                subscription_text = f"\n\nСтатус подписки: Активна\nДней осталось: {days_left}"
        else:
            subscription_text = "\n\nСтатус подписки: Неактивна"

        await callback.message.edit_text(
            f"Ваш баланс: {balance} баллов (1 балл = 1 рубль){subscription_text}",
            reply_markup=main_menu_kb()
        )
    else:
        await callback.message.edit_text(
            "Произошла ошибка при получении данных о балансе.",
            reply_markup=main_menu_kb()
        )

    await callback.answer()


@router.callback_query(F.data == "need_help")
async def callback_need_help(callback: CallbackQuery):
    """
    Обработчик нажатия кнопки "Нужна помощь"
    """
    from keyboards import need_help_kb

    await callback.message.edit_text(
        "Если у вас возникли вопросы или нужна помощь с оплатой, свяжитесь с нашим менеджером:",
        reply_markup=need_help_kb()
    )
    await callback.answer()


@router.callback_query(F.data == "back")
async def callback_back(callback: CallbackQuery):
    """
    Обработчик нажатия кнопки "Назад"
    """
    await callback.message.edit_text(
        "Главное меню клуба X10:",
        reply_markup=main_menu_kb()
    )
    await callback.answer()


async def check_referrer_bonuses(bot: Bot, db: Database, config: Config, referrer_id: int):
    """
    Проверка и выдача бонусов за достижение уровней реферальной программы
    :param bot: Объект бота
    :param db: Объект базы данных
    :param config: Объект конфигурации
    :param referrer_id: ID реферера
    """
    # Получаем количество рефералов пользователя
    referrals_count = await db.count_user_referrals(referrer_id)

    # Получаем информацию о пользователе
    user = await db.get_user(referrer_id)
    if not user:
        return

    # Проверяем достижение уровней
    # Уровень 3 (доступ к VIP продукту)
    if referrals_count == 3:
        from keyboards import get_vip_access_kb
        await bot.send_message(
            referrer_id,
            "🔥 Ты просто огонь! Ты пригласил 3 друзей! 🔥\n\n"
            "Теперь у тебя есть к доступ к VIP продукту экскурсия по Вьетнаму! 🎁\n"
            "Чтобы узнать детали, нажмите на кнопку Получить доступ\n\n"
            "Не останавливайся:\n"
            "🚀 5 друзей – месяц бесплатного членства в Клубе Х10\n"
            "🌟 10 друзей – персональная консультация с основателем Клуба Х10\n\n"
            "👉 Продолжай делиться своей реферальной ссылкой и получай еще больше наград!",
            reply_markup=get_vip_access_kb()
        )

    # Уровень 5 (месяц бесплатного членства)
    elif referrals_count == 5:
        from keyboards import club_access_kb

        # Добавляем подписку на месяц
        await db.add_subscription(referrer_id, 30)

        await bot.send_message(
            referrer_id,
            "🚀 Ты на высоте! Ты пригласил 5 друзей! 🚀\n\n"
            "Твой счет пополнен на месяц бесплатного членства в Клубе Х10 🎉\n"
            "Теперь у тебя есть еще больше возможностей!\n\n"
            "Следующая цель:\n"
            "🌟 10 друзей – персональная консультация с основателем Клуба Х10\n"
            "👉 Продолжай приглашать друзей и получай эксклюзивные бонусы!",
            reply_markup=club_access_kb()
        )

    # Уровень 10 (персональная консультация)
    elif referrals_count == 10:
        from keyboards import get_consultation_kb
        await bot.send_message(
            referrer_id,
            "🌟 Ты просто звезда! Ты пригласил 10 друзей!\n\n"
            "Ты достиг максимального уровня в нашей реферальной программе!\n"
            "Тебя ждет персональная консультация с основателем Клуба Х10\n"
            "Чтобы запланировать встречу, нажмите кнопку Получить консультацию\n\n"
            "Спасибо за твой вклад! Ты настоящий чемпион! 🏆\n\n"
            "👉 Если у тебя есть вопросы или пожелания, пиши – мы всегда на связи!",
            reply_markup=get_consultation_kb()
        )