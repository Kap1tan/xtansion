"""
Обработчики для администраторов бота клуба X10.
"""
import logging
import asyncio
import sqlite3
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import Database
from config import Config
from keyboards import main_menu_kb, club_access_kb
from utils import get_user_name, get_payment_description

router = Router()
logger = logging.getLogger(__name__)


@router.message(Command("admin"))
async def cmd_admin(message: Message, config: Config):
    """
    Команда для вывода админ-панели
    """
    user_id = message.from_user.id

    # Проверяем, является ли пользователь администратором
    if user_id not in config.bot.admin_ids:
        await message.answer("У вас нет прав для использования этой команды.")
        return

    # Выводим админ-панель
    admin_text = (
        f"🔑 Административная панель 🔑\n\n"
        f"Доступные команды:\n"
        f"/confirm_payment [ID платежа] - подтвердить платеж\n"
        f"/payments_list - список ожидающих платежей\n"
        f"/user_info [ID пользователя] - информация о пользователе\n"
        f"/stats - статистика бота\n"
        f"/broadcast - отправить сообщение всем пользователям\n"
        f"/export_users - выгрузить список пользователей"
    )

    await message.answer(admin_text)


@router.message(Command("confirm_payment"))
async def cmd_confirm_payment(message: Message, bot: Bot, db: Database, config: Config):
    """
    Команда для подтверждения платежа администратором
    Формат: /confirm_payment ID_платежа
    """
    user_id = message.from_user.id

    # Проверяем, является ли пользователь администратором
    if user_id not in config.bot.admin_ids:
        await message.answer("У вас нет прав для выполнения этой команды.")
        return

    # Получаем ID платежа из аргументов команды
    args = message.text.split()
    if len(args) != 2:
        await message.answer("Неверный формат команды. Используйте: /confirm_payment ID_платежа")
        return

    try:
        payment_id = int(args[1])
    except ValueError:
        await message.answer("ID платежа должен быть числом.")
        return

    # Получаем информацию о платеже
    payment = await db.get_payment(payment_id)

    if not payment:
        await message.answer(f"⚠️ Платеж с ID {payment_id} не найден.")
        return

    if payment.get('status') == 'confirmed':
        await message.answer(f"ℹ️ Платеж с ID {payment_id} уже подтвержден.")
        return

    # Подтверждаем платеж
    await db.confirm_payment(payment_id)

    # Получаем данные о пользователе и продукте
    customer_id = payment.get('user_id')
    product_type = payment.get('product_type')
    payment_method = payment.get('payment_method')
    amount = payment.get('amount')

    # Получаем данные о пользователе
    user_data = await db.get_user(customer_id)
    user_name = get_user_name(user_data) if user_data else f"Пользователь {customer_id}"

    # В зависимости от типа продукта выполняем действия
    if product_type == "club":
        # Добавляем подписку на месяц
        payment_info = get_payment_description(product_type, config)
        await db.add_subscription(customer_id, payment_info["days"])

        # Отправляем уведомление пользователю
        try:
            await bot.send_message(
                customer_id,
                "🎉 Поздравляем! Ваш платеж подтвержден.\n\n"
                "Доступ к клубу X10 активирован.\n\n"
                "Теперь вы можете присоединиться к клубу, нажав на кнопку ниже:",
                reply_markup=club_access_kb()
            )
            confirm_status = "✅ Уведомление отправлено пользователю"
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления пользователю {customer_id}: {e}")
            confirm_status = f"⚠️ Ошибка при отправке уведомления: {e}"

    else:
        # Для других продуктов (мероприятия)
        try:
            await bot.send_message(
                customer_id,
                f"🎉 Поздравляем! Ваш платеж за {product_type} подтвержден.\n\n"
                f"Наш менеджер свяжется с вами для предоставления дополнительной информации."
            )
            confirm_status = "✅ Уведомление отправлено пользователю"
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления пользователю {customer_id}: {e}")
            confirm_status = f"⚠️ Ошибка при отправке уведомления: {e}"

    # Уведомление администратору
    admin_confirm_text = (
        f"✅ Платеж с ID {payment_id} успешно подтвержден\n\n"
        f"👤 Пользователь: {user_name} (ID: {customer_id})\n"
        f"🛒 Продукт: {product_type}\n"
        f"💰 Сумма: {amount} рублей\n"
        f"💳 Способ оплаты: {payment_method}\n\n"
        f"{confirm_status}"
    )

    await message.answer(admin_confirm_text)

    # Логирование действия
    logger.info(f"Администратор {user_id} подтвердил платеж {payment_id} для пользователя {customer_id}")


@router.message(Command("payments_list"))
async def cmd_payments_list(message: Message, db: Database, config: Config):
    """
    Команда для вывода списка ожидающих платежей
    """
    user_id = message.from_user.id

    # Проверяем, является ли пользователь администратором
    if user_id not in config.bot.admin_ids:
        await message.answer("У вас нет прав для выполнения этой команды.")
        return

    # Получаем список ожидающих платежей из базы данных
    conn = await db.get_conn()
    try:
        conn.row_factory = sqlite3.Row
        cursor = await conn.execute(
            """
            SELECT p.payment_id, p.user_id, u.username, u.first_name, p.product_type, p.amount, p.payment_method, p.created_at
            FROM payments p
            LEFT JOIN users u ON p.user_id = u.user_id
            WHERE p.status = 'pending'
            ORDER BY p.created_at DESC
            LIMIT 15
            """
        )
        payments = await cursor.fetchall()
    finally:
        await conn.close()

    if not payments:
        await message.answer("📝 Нет ожидающих платежей")
        return

    # Формируем сообщение со списком платежей
    payments_text = "📝 Список ожидающих платежей:\n\n"

    for payment in payments:
        payment_id = payment['payment_id']
        user_id = payment['user_id']
        username = payment['username'] or payment['first_name'] or f"Пользователь {user_id}"
        product_type = payment['product_type']
        amount = payment['amount']
        payment_method = payment['payment_method']
        created_at = payment['created_at']

        # Определяем тип платежа для отображения
        is_crypto = payment_method.startswith('crypto:')
        payment_method_display = f"Криптовалюта ({payment_method.split(':')[1]})" if is_crypto else payment_method

        payments_text += (
            f"ID платежа: {payment_id}\n"
            f"👤 Пользователь: {username} (ID: {user_id})\n"
            f"🛒 Продукт: {product_type}\n"
            f"💰 Сумма: {amount} рублей\n"
            f"💳 Метод: {payment_method_display}\n"
            f"📅 Создан: {created_at}\n"
            f"✅ Для подтверждения: /confirm_payment {payment_id}\n\n"
        )

    await message.answer(payments_text)


@router.message(Command("user_info"))
async def cmd_user_info(message: Message, db: Database, config: Config):
    """
    Команда для получения информации о пользователе
    Формат: /user_info ID_пользователя
    """
    admin_id = message.from_user.id

    # Проверяем, является ли пользователь администратором
    if admin_id not in config.bot.admin_ids:
        await message.answer("У вас нет прав для выполнения этой команды.")
        return

    # Получаем ID пользователя из аргументов команды
    args = message.text.split()
    if len(args) != 2:
        await message.answer("Неверный формат команды. Используйте: /user_info ID_пользователя")
        return

    try:
        user_id = int(args[1])
    except ValueError:
        await message.answer("ID пользователя должен быть числом.")
        return

    # Получаем информацию о пользователе
    user = await db.get_user(user_id)

    if not user:
        await message.answer(f"Пользователь с ID {user_id} не найден.")
        return

    # Получаем информацию о подписке
    subscription = await db.check_subscription(user_id)

    # Получаем информацию о рефералах
    referrals = await db.get_user_referrals(user_id)
    referrer = await db.get_user_referrer(user_id)

    # Формируем информацию о пользователе
    user_info_text = (
        f"👤 Информация о пользователе:\n\n"
        f"ID: {user_id}\n"
        f"Username: {user.get('username') or 'Нет'}\n"
        f"Имя: {user.get('first_name') or 'Нет'}\n"
        f"Фамилия: {user.get('last_name') or 'Нет'}\n"
        f"Баланс: {user.get('balance') or 0} баллов\n"
        f"Дата регистрации: {user.get('registration_date') or 'Неизвестно'}\n"
    )

    # Добавляем информацию о подписке
    if subscription:
        from datetime import datetime
        end_date = subscription.get('end_date')
        if end_date:
            end_date_obj = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            days_left = (end_date_obj - datetime.now()).days
            user_info_text += (
                f"\n📢 Статус подписки: Активна\n"
                f"Дата окончания: {end_date}\n"
                f"Осталось дней: {days_left}\n"
            )
    else:
        user_info_text += "\n📢 Статус подписки: Неактивна\n"

    # Добавляем информацию о рефералах
    user_info_text += f"\n👥 Количество рефералов: {len(referrals)}\n"

    if referrer:
        referrer_username = referrer.get('username') or referrer.get('first_name') or f"ID: {referrer.get('user_id')}"
        user_info_text += f"🔗 Приглашен пользователем: {referrer_username}\n"

    await message.answer(user_info_text)


@router.message(Command("stats"))
async def cmd_stats(message: Message, db: Database, config: Config):
    """
    Команда для вывода статистики бота
    """
    user_id = message.from_user.id

    # Проверяем, является ли пользователь администратором
    if user_id not in config.bot.admin_ids:
        await message.answer("У вас нет прав для выполнения этой команды.")
        return

    # Получаем статистику из базы данных
    conn = await db.get_conn()
    try:
        # Общее количество пользователей
        cursor = await conn.execute("SELECT COUNT(*) FROM users")
        total_users = (await cursor.fetchone())[0]

        # Количество пользователей с активной подпиской
        cursor = await conn.execute(
            "SELECT COUNT(*) FROM subscriptions WHERE status = 'active' AND end_date > datetime('now')"
        )
        active_subscriptions = (await cursor.fetchone())[0]

        # Количество платежей
        cursor = await conn.execute("SELECT COUNT(*) FROM payments")
        total_payments = (await cursor.fetchone())[0]

        # Сумма подтвержденных платежей
        cursor = await conn.execute(
            "SELECT SUM(amount) FROM payments WHERE status = 'confirmed'"
        )
        total_revenue = (await cursor.fetchone())[0] or 0

        # Платежи за последние 7 дней
        cursor = await conn.execute(
            "SELECT COUNT(*) FROM payments WHERE created_at > datetime('now', '-7 days')"
        )
        recent_payments = (await cursor.fetchone())[0]

        # Количество рефералов
        cursor = await conn.execute("SELECT COUNT(*) FROM referrals")
        total_referrals = (await cursor.fetchone())[0]
    finally:
        await conn.close()

    # Формируем сообщение со статистикой
    stats_text = (
        f"📊 Статистика бота клуба X10:\n\n"
        f"👥 Всего пользователей: {total_users}\n"
        f"🔑 Активных подписок: {active_subscriptions}\n"
        f"💰 Всего платежей: {total_payments}\n"
        f"💵 Общий доход: {total_revenue} руб.\n"
        f"📈 Платежей за 7 дней: {recent_payments}\n"
        f"🔗 Всего рефералов: {total_referrals}\n"
    )

    await message.answer(stats_text)


# Импортируем необходимые модули для работы с пользователями
# Определяем состояния для FSM
class BroadcastStates(StatesGroup):
    """Состояния для рассылки"""
    waiting_for_message = State()  # Ожидание сообщения для рассылки
    confirmation = State()  # Подтверждение рассылки


import os
import csv
import io
from aiogram.types import BufferedInputFile
from datetime import datetime


@router.message(Command("export_users"))
async def cmd_export_users(message: Message, db: Database, config: Config):
    """
    Команда для экспорта списка пользователей в CSV-файл
    """
    user_id = message.from_user.id

    # Проверяем, является ли пользователь администратором
    if user_id not in config.bot.admin_ids:
        await message.answer("У вас нет прав для выполнения этой команды.")
        return

    # Получаем всех пользователей из базы данных
    conn = await db.get_conn()
    try:
        conn.row_factory = sqlite3.Row
        cursor = await conn.execute(
            """
            SELECT u.user_id, u.username, u.first_name, u.last_name, u.registration_date, u.balance,
                   (SELECT COUNT(*) FROM referrals r WHERE r.referrer_id = u.user_id) as referrals_count,
                   (CASE WHEN EXISTS (
                       SELECT 1 FROM subscriptions s 
                       WHERE s.user_id = u.user_id AND s.status = 'active' AND s.end_date > datetime('now')
                   ) THEN 'Активна' ELSE 'Неактивна' END) as subscription_status
            FROM users u
            ORDER BY u.registration_date DESC
            """
        )
        users = await cursor.fetchall()
    finally:
        await conn.close()

    if not users:
        await message.answer("Нет пользователей для экспорта.")
        return

    # Создаем CSV в памяти
    output = io.StringIO()
    fieldnames = ['ID', 'Username', 'Имя', 'Фамилия', 'Дата регистрации', 'Баланс', 'Рефералы', 'Статус подписки']
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()

    for user in users:
        writer.writerow({
            'ID': user['user_id'],
            'Username': user['username'] or 'Нет',
            'Имя': user['first_name'] or 'Нет',
            'Фамилия': user['last_name'] or 'Нет',
            'Дата регистрации': user['registration_date'] or 'Неизвестно',
            'Баланс': user['balance'] or 0,
            'Рефералы': user['referrals_count'],
            'Статус подписки': user['subscription_status']
        })

    # Готовим CSV-файл для отправки
    csv_bytes = output.getvalue().encode('utf-8-sig')  # UTF-8 с BOM для корректного отображения кириллицы в Excel
    current_date = datetime.now().strftime("%Y-%m-%d")
    file_name = f"club_x10_users_{current_date}.csv"

    # Отправляем файл
    input_file = BufferedInputFile(csv_bytes, filename=file_name)
    await message.answer_document(
        document=input_file,
        caption=f"📊 Экспорт пользователей ({len(users)})"
    )


@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message, state: FSMContext, config: Config):
    """
    Команда для начала рассылки сообщений всем пользователям
    """
    user_id = message.from_user.id

    # Проверяем, является ли пользователь администратором
    if user_id not in config.bot.admin_ids:
        await message.answer("У вас нет прав для выполнения этой команды.")
        return

    # Устанавливаем состояние ожидания сообщения для рассылки
    await state.set_state(BroadcastStates.waiting_for_message)

    await message.answer(
        "📣 Режим рассылки\n\n"
        "Отправьте сообщение, которое нужно разослать всем пользователям.\n\n"
        "Поддерживаемые форматы:\n"
        "- Текст\n"
        "- Фото с подписью\n"
        "- Видео с подписью\n"
        "- Документ с подписью\n\n"
        "Для отмены рассылки напишите /cancel"
    )


@router.message(Command("cancel"), BroadcastStates)
async def cmd_cancel_broadcast(message: Message, state: FSMContext):
    """
    Отмена рассылки
    """
    await state.clear()
    await message.answer("Рассылка отменена")


@router.message(BroadcastStates.waiting_for_message)
async def process_broadcast_message(message: Message, state: FSMContext):
    """
    Обработчик получения сообщения для рассылки
    """
    # Проверяем, есть ли в сообщении какой-либо контент
    if not (message.text or message.photo or message.video or message.document):
        await message.answer(
            "Пожалуйста, отправьте текст, фото, видео или документ для рассылки.\n"
            "Для отмены рассылки напишите /cancel"
        )
        return

    # Сохраняем данные о сообщении
    await state.update_data(
        message_type="text" if message.text else
        "photo" if message.photo else
        "video" if message.video else
        "document" if message.document else "unknown",
        message_text=message.text if message.text else message.caption or "",
        photo_id=message.photo[-1].file_id if message.photo else None,
        video_id=message.video.file_id if message.video else None,
        document_id=message.document.file_id if message.document else None
    )

    # Переходим в состояние подтверждения
    await state.set_state(BroadcastStates.confirmation)

    # Формируем сообщение для подтверждения
    content_type = (
        "Текст" if message.text else
        "Фото с подписью" if message.photo else
        "Видео с подписью" if message.video else
        "Документ с подписью" if message.document else "Неизвестный контент"
    )

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    await message.answer(
        f"📣 Подтверждение рассылки\n\n"
        f"Тип содержимого: {content_type}\n"
        f"Текст: {message.text or message.caption or 'Нет'}\n\n"
        f"Начать рассылку? Это действие нельзя отменить после запуска.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да, начать рассылку", callback_data="confirm_broadcast")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_broadcast")]
        ])
    )


@router.callback_query(F.data == "cancel_broadcast", BroadcastStates.confirmation)
async def callback_cancel_broadcast(callback: CallbackQuery, state: FSMContext):
    """
    Отмена рассылки через callback
    """
    await state.clear()
    await callback.message.edit_text("Рассылка отменена")
    await callback.answer()


@router.callback_query(F.data == "confirm_broadcast", BroadcastStates.confirmation)
async def callback_confirm_broadcast(callback: CallbackQuery, state: FSMContext, bot: Bot, db: Database):
    """
    Подтверждение и начало рассылки
    """
    # Получаем данные о сообщении для рассылки
    data = await state.get_data()
    message_type = data.get("message_type")
    message_text = data.get("message_text", "")
    photo_id = data.get("photo_id")
    video_id = data.get("video_id")
    document_id = data.get("document_id")

    # Сбрасываем состояние
    await state.clear()

    # Уведомляем о начале рассылки
    status_message = await callback.message.edit_text("Начинаем рассылку... ⏳")

    # Получаем всех активных пользователей из базы данных
    conn = await db.get_conn()
    try:
        conn.row_factory = sqlite3.Row
        cursor = await conn.execute("SELECT user_id FROM users WHERE 1=1")  # Можно добавить условие для фильтрации
        users = await cursor.fetchall()
    finally:
        await conn.close()

    # Счетчики успешных и неуспешных отправок
    success_count = 0
    error_count = 0
    total_users = len(users)

    # Обновляем статус каждые 10 пользователей
    update_interval = 10

    # Запускаем рассылку
    for i, user in enumerate(users, 1):
        user_id = user["user_id"]

        try:
            # Отправляем сообщение в зависимости от типа
            if message_type == "text":
                await bot.send_message(user_id, message_text)
            elif message_type == "photo":
                await bot.send_photo(user_id, photo_id, caption=message_text)
            elif message_type == "video":
                await bot.send_video(user_id, video_id, caption=message_text)
            elif message_type == "document":
                await bot.send_document(user_id, document_id, caption=message_text)

            success_count += 1
        except Exception as e:
            error_count += 1
            logger.error(f"Ошибка при отправке сообщения пользователю {user_id}: {e}")

        # Обновляем статус каждые update_interval пользователей или в конце
        if i % update_interval == 0 or i == total_users:
            try:
                await status_message.edit_text(
                    f"Рассылка в процессе... ⏳\n\n"
                    f"Прогресс: {i}/{total_users} ({int(i / total_users * 100)}%)\n"
                    f"Успешно: {success_count}\n"
                    f"Ошибок: {error_count}"
                )
            except Exception as e:
                logger.error(f"Ошибка при обновлении статуса рассылки: {e}")

        # Добавляем небольшую задержку, чтобы избежать ограничений API Telegram
        await asyncio.sleep(0.05)

    # Отправляем финальный статус
    final_status = (
        f"✅ Рассылка завершена!\n\n"
        f"Всего пользователей: {total_users}\n"
        f"Успешно отправлено: {success_count}\n"
        f"Ошибок: {error_count}\n"
        f"Эффективность: {int(success_count / total_users * 100 if total_users else 0)}%"
    )

    await status_message.edit_text(final_status)
    await callback.answer()


# Импортируем необходимые типы в конце файла
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton