"""
Обработчик реферальной системы для бота клуба X10.
"""
import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from database import Database
from config import Config
from keyboards import referral_kb, main_menu_kb
from utils import generate_ref_link, get_user_name

router = Router()
logger = logging.getLogger(__name__)


@router.callback_query(F.data == "my_referrals")
async def callback_my_referrals(callback: CallbackQuery, bot: Bot, db: Database, config: Config):
    """
    Обработчик кнопки "Мои рефералы"
    """
    user_id = callback.from_user.id

    # Получаем рефералов пользователя
    referrals = await db.get_user_referrals(user_id)
    referrals_count = len(referrals)

    # Получаем информацию о пользователе
    user = await db.get_user(user_id)

    # Генерируем реферальную ссылку
    bot_info = await bot.get_me()
    ref_link = generate_ref_link(bot_info.username, user_id)

    # Формируем сообщение
    if referrals_count > 0:
        referral_text = f"Вы пригласили {referrals_count} {'человека' if 1 < referrals_count < 5 else 'человек'}:\n\n"
        for i, ref in enumerate(referrals, 1):
            ref_name = ref.get('first_name', '') or ref.get('username', 'Пользователь')
            referral_text += f"{i}. {ref_name}\n"

        # Добавляем информацию о бонусах
        referral_text += "\nБонусы за приглашенных друзей:\n"
        referral_text += f"🎯 1 друг – {config.referral.points_per_referral} баллов (1 балл = 1 рубль)\n"
        referral_text += f"🎯 3 друга – доступ к VIP продукту экскурсия по Вьетнаму\n"
        referral_text += f"🎯 5 друзей – месяц бесплатного членства в Клубе Х10\n"
        referral_text += f"🎯 10 друзей – персональная консультация с основателем Клуба Х10\n\n"

        # Показываем прогресс
        next_level = 3 if referrals_count < 3 else 5 if referrals_count < 5 else 10 if referrals_count < 10 else None
        if next_level:
            referral_text += f"🏆 Ваш текущий прогресс: {referrals_count}/{next_level}\n"
            referral_text += f"До следующего уровня осталось: {next_level - referrals_count}\n\n"
        else:
            referral_text += f"🎉 Поздравляем! Вы достигли максимального уровня в реферальной программе!\n\n"

        referral_text += f"🚀 Ваша ссылка: {ref_link}"
    else:
        referral_text = (
            "У вас пока нет рефералов.\n\n"
            "За каждого друга, которого вы приведете по своей ссылке, "
            f"вы получите {config.referral.points_per_referral} бонусных баллов равных "
            f"{config.referral.points_per_referral} рублям.\n\n"
            "Их можно обменять на скидки на занятия/абонемент с экспертами Клуба Х10\n\n"
            f"Ваша ссылка: {ref_link}\n\n"
            "🔍 Как делиться?\n"
            "Просто отправьте ее друзьям или разместите в соцсетях."
        )

    # Отправляем сообщение
    await callback.message.edit_text(
        referral_text,
        reply_markup=referral_kb(ref_link)
    )
    await callback.answer()


@router.callback_query(F.data == "get_ref_link")
async def callback_get_ref_link(callback: CallbackQuery, bot: Bot, db: Database):
    """
    Обработчик кнопки "Реферальная ссылка"
    """
    user_id = callback.from_user.id

    # Генерируем реферальную ссылку
    bot_info = await bot.get_me()
    ref_link = generate_ref_link(bot_info.username, user_id)

    await callback.message.edit_text(
        f"Ваша реферальная ссылка: {ref_link}\n\n"
        "🔍 Как делиться?\n"
        "Просто отправьте ее друзьям или разместите в соцсетях.\n"
        "Начните зарабатывать уже сегодня!",
        reply_markup=main_menu_kb()
    )
    await callback.answer()


@router.callback_query(F.data == "generate_ref_link")
async def callback_generate_ref_link(callback: CallbackQuery, bot: Bot, db: Database):
    """
    Обработчик кнопки "Получить ссылку"
    """
    user_id = callback.from_user.id

    # Генерируем реферальную ссылку
    bot_info = await bot.get_me()
    ref_link = generate_ref_link(bot_info.username, user_id)

    await callback.message.edit_text(
        f"Вот ваша ссылка: {ref_link}\n\n"
        "🔍 Как делиться?\n"
        "Просто отправьте ее друзьям или разместите в соцсетях.\n"
        "Начните зарабатывать уже сегодня!",
        reply_markup=main_menu_kb()
    )
    await callback.answer()


@router.callback_query(F.data == "about_vip")
async def callback_about_vip(callback: CallbackQuery):
    """
    Обработчик кнопки "Узнать о VIP продукте"
    """
    await callback.message.edit_text(
        "VIP продукт - Экскурсия по Вьетнаму 🌴\n\n"
        "Эксклюзивная онлайн-экскурсия по самым интересным местам Вьетнама с нашим экспертом.\n\n"
        "Вы узнаете:\n"
        "- Секретные места, о которых не пишут в путеводителях\n"
        "- Как сэкономить на путешествии во Вьетнам\n"
        "- Культурные особенности и традиции местных жителей\n\n"
        "Длительность: 2 часа\n"
        "Формат: онлайн через Zoom\n",
        reply_markup=main_menu_kb()
    )
    await callback.answer()


@router.callback_query(F.data == "about_club")
async def callback_about_club(callback: CallbackQuery):
    """
    Обработчик кнопки "Больше о Клубе Х10"
    """
    await callback.message.edit_text(
        "Клуб Х10 - это сообщество единомышленников, стремящихся к развитию и росту.\n\n"
        "Преимущества членства в клубе:\n"
        "- Доступ к закрытому чату с экспертами\n"
        "- Еженедельные вебинары на актуальные темы\n"
        "- Участие в мастер-классах и воркшопах\n"
        "- Нетворкинг с интересными людьми\n\n"
        "Стоимость: 1000 рублей в месяц",
        reply_markup=main_menu_kb()
    )
    await callback.answer()


@router.callback_query(F.data == "about_founder")
async def callback_about_founder(callback: CallbackQuery):
    """
    Обработчик кнопки "Об основателе"
    """
    await callback.message.edit_text(
        "Основатель Клуба Х10 - Анатолий\n\n"
        "Эксперт в области личностного роста и развития с опытом более 10 лет.\n"
        "Автор методики «Х10», позволяющей в 10 раз увеличить эффективность обучения.\n\n"
        "Персональная консультация с основателем - это уникальная возможность:\n"
        "- Получить индивидуальный план развития\n"
        "- Решить конкретные задачи под руководством эксперта\n"
        "- Определить приоритеты и стратегии для достижения целей",
        reply_markup=main_menu_kb()
    )
    await callback.answer()


@router.callback_query(F.data == "get_vip_access")
async def callback_get_vip_access(callback: CallbackQuery):
    """
    Обработчик кнопки "Получить доступ" (к VIP продукту)
    """
    await callback.message.edit_text(
        "Для получения доступа к VIP продукту 'Экскурсия по Вьетнаму', "
        "пожалуйста, свяжитесь с нашим менеджером.\n\n"
        "Он расскажет вам все детали и ответит на ваши вопросы.",
        reply_markup=need_help_kb()
    )
    await callback.answer()


@router.callback_query(F.data == "get_consultation")
async def callback_get_consultation(callback: CallbackQuery):
    """
    Обработчик кнопки "Получить консультацию"
    """
    await callback.message.edit_text(
        "Для планирования персональной консультации с основателем Клуба Х10, "
        "пожалуйста, свяжитесь с нашим менеджером.\n\n"
        "Он поможет выбрать удобное время и формат консультации.",
        reply_markup=need_help_kb()
    )
    await callback.answer()


# Импортируем в конце, чтобы избежать циклических импортов
from keyboards import need_help_kb