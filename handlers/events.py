"""
Обработчик мероприятий для бота клуба X10.
"""
import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, LabeledPrice, PreCheckoutQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import Database
from config import Config
from keyboards import events_kb, payment_methods_kb, main_menu_kb, payment_confirmation_kb, stars_payment_kb
from utils import get_user_name, get_payment_description, parse_callback_data

router = Router()
logger = logging.getLogger(__name__)


# Определение состояний FSM
class EventStates(StatesGroup):
    """Состояния для обработки событий"""
    payment_confirmation = State()  # Подтверждение оплаты (загрузка скриншота)


@router.callback_query(F.data == "events")
async def callback_events(callback: CallbackQuery):
    """
    Обработчик кнопки "Мероприятия"
    """
    await callback.message.edit_text(
        "Выберите мероприятие:",
        reply_markup=events_kb()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("event:"))
async def callback_event(callback: CallbackQuery, db: Database, config: Config):
    """
    Обработчик выбора мероприятия
    """
    event_type = callback.data.split(':')[1]

    if event_type == "vietnam":
        # Экскурсия по Вьетнаму
        event_title = "Экскурсия по Вьетнаму"
        event_description = (
            "VIP продукт - Экскурсия по Вьетнаму 🌴\n\n"
            "Эксклюзивная онлайн-экскурсия по самым интересным местам Вьетнама с нашим экспертом.\n\n"
            "Вы узнаете:\n"
            "- Секретные места, о которых не пишут в путеводителях\n"
            "- Как сэкономить на путешествии во Вьетнам\n"
            "- Культурные особенности и традиции местных жителей\n\n"
            "Длительность: 2 часа\n"
            "Формат: онлайн через Zoom\n"
            "Стоимость: 1000 рублей"
        )
    elif event_type == "consultation":
        # Консультация с основателем
        event_title = "Консультация с основателем"
        event_description = (
            "Персональная консультация с основателем Клуба Х10 🌟\n\n"
            "Это уникальная возможность:\n"
            "- Получить индивидуальный план развития\n"
            "- Решить конкретные задачи под руководством эксперта\n"
            "- Определить приоритеты и стратегии для достижения целей\n\n"
            "Длительность: 1 час\n"
            "Формат: онлайн через Zoom\n"
            "Стоимость: 2000 рублей"
        )
    else:
        # Неизвестное мероприятие
        await callback.message.edit_text(
            "Извините, данное мероприятие недоступно. Пожалуйста, выберите другое.",
            reply_markup=events_kb()
        )
        await callback.answer()
        return

    # Создаем инлайн-клавиатуру для оплаты
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Оплатить", callback_data=f"pay_event:{event_type}")],
        [InlineKeyboardButton(text="Назад", callback_data="events")],
        [InlineKeyboardButton(text="Главное меню", callback_data="main_menu")]
    ])

    await callback.message.edit_text(
        f"{event_title}\n\n{event_description}",
        reply_markup=markup
    )
    await callback.answer()


@router.callback_query(F.data.startswith("pay_event:"))
async def callback_pay_event(callback: CallbackQuery, db: Database, config: Config):
    """
    Обработчик оплаты мероприятия
    """
    event_type = callback.data.split(':')[1]

    await callback.message.edit_text(
        "Выберите способ оплаты:",
        reply_markup=payment_methods_kb(event_type)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("pay_method:"))
async def callback_pay_method_event(callback: CallbackQuery, db: Database, config: Config):
    """
    Обработчик выбора способа оплаты для мероприятий
    """
    user_id = callback.from_user.id
    callback_data = parse_callback_data(callback.data)

    product_type = callback_data.get("product")
    payment_method = callback_data.get("method")

    if not product_type or not payment_method:
        await callback.message.edit_text(
            "Произошла ошибка при выборе способа оплаты. Пожалуйста, попробуйте снова.",
            reply_markup=main_menu_kb()
        )
        await callback.answer()
        return

    # Получаем описание платежа
    payment_info = get_payment_description(product_type, config)
    amount = payment_info["amount"]

    # Создаем запись о платеже в базе данных
    payment_id = await db.create_payment(
        user_id,
        amount,
        product_type,
        payment_method
    )

    if payment_method == "card":
        # Оплата на карту - предоставляем реквизиты
        payment_details = f"💳 Банковская карта: {config.payment.payment_details.get('Карта РФ (Сбербанк)')}"

        # Формируем сообщение для мероприятия
        message_text = (
            f"Реквизиты для оплаты:\n{payment_details}\n\n"
            f"Вы оплачиваете:\n"
            f"Сумма: {payment_info['amount']} рублей\n"
            f"Продукт: {payment_info['name']}\n"
            f"Тип платежа: Одноразовый\n\n"
            f"После оплаты: Нажмите кнопку 'Я оплатил' и отправьте скриншот оплаты, "
            f"менеджер расскажет о дальнейших шагах."
        )

        await callback.message.edit_text(
            message_text,
            reply_markup=payment_confirmation_kb(payment_id)
        )

    elif payment_method == "stars":
        # Оплата звездами Telegram
        # Конвертируем рубли в звезды (1000р = 750 звезд)
        stars_amount = int(amount * 0.75)  # 75% от суммы в рублях

        await callback.message.edit_text(
            f"Вы выбрали оплату Telegram Stars\n\n"
            f"Сумма: {stars_amount} ⭐ (эквивалент {amount} руб.)\n"
            f"Продукт: {payment_info['name']}\n\n"
            f"Нажмите кнопку 'Оплатить {stars_amount} ⭐' для продолжения."
        )

        # Отправляем инвойс для оплаты звездами
        await callback.message.answer_invoice(
            title=f"Оплата {payment_info['name']}",
            description=f"{payment_info['description']}",
            payload=f"payment_{payment_id}",
            provider_token="",  # Для Telegram Stars используем пустую строку
            currency="XTR",    # Валюта для Telegram Stars
            prices=[LabeledPrice(label=payment_info['name'], amount=stars_amount)],
            reply_markup=stars_payment_kb(stars_amount, payment_id)
        )

    await callback.answer()


@router.callback_query(F.data == "cancel_payment")
async def callback_cancel_payment_event(callback: CallbackQuery, state: FSMContext):
    """
    Обработчик отмены оплаты
    """
    await state.clear()

    try:
        # Пробуем отредактировать сообщение
        await callback.message.edit_text(
            "Оплата отменена. Выберите нужное действие:",
            reply_markup=main_menu_kb()
        )
    except Exception as e:
        # В случае ошибки (например, сообщение нельзя редактировать)
        # отправляем новое сообщение вместо редактирования
        await callback.message.answer(
            "Оплата отменена. Выберите нужное действие:",
            reply_markup=main_menu_kb()
        )

    await callback.answer()


@router.callback_query(F.data.startswith("confirm_payment:"))
async def callback_confirm_payment_event(callback: CallbackQuery, state: FSMContext, db: Database, config: Config):
    """
    Обработчик подтверждения оплаты для мероприятий
    """
    payment_id = int(callback.data.split(':')[1])

    # Получаем информацию о платеже
    payment = await db.get_payment(payment_id)

    if not payment:
        await callback.message.edit_text(
            "Платеж не найден. Пожалуйста, попробуйте снова или обратитесь к менеджеру.",
            reply_markup=main_menu_kb()
        )
        await callback.answer()
        return

    # Для мероприятий - запрашиваем скриншот для подтверждения
    await state.set_state(EventStates.payment_confirmation)
    await state.update_data(payment_id=payment_id)

    await callback.message.edit_text(
        "Пожалуйста, отправьте скриншот оплаты для подтверждения.\n\n"
        "Наш менеджер проверит его и свяжется с вами для предоставления дополнительной информации."
    )

    await callback.answer()


@router.pre_checkout_query()
async def pre_checkout_handler_event(pre_checkout_query: PreCheckoutQuery):
    """
    Обработчик предварительной проверки платежа для мероприятий
    """
    await pre_checkout_query.answer(ok=True)


@router.message(F.successful_payment)
async def successful_payment_handler_event(message: Message, db: Database, config: Config):
    """
    Обработчик успешного платежа звездами для мероприятий
    """
    payment_payload = message.successful_payment.invoice_payload

    # Извлекаем ID платежа из payload
    if payment_payload.startswith("payment_"):
        payment_id = int(payment_payload.split("_")[1])

        # Получаем информацию о платеже
        payment = await db.get_payment(payment_id)

        if not payment:
            await message.answer(
                "Произошла ошибка при обработке платежа. Пожалуйста, обратитесь к менеджеру.",
                reply_markup=main_menu_kb()
            )
            return

        user_id = payment.get('user_id')
        product_type = payment.get('product_type')

        # Подтверждаем платеж
        await db.confirm_payment(payment_id)

        # Для мероприятий
        await message.answer(
            "Спасибо за оплату! 🎉\n\n"
            "Ваш платеж успешно обработан.\n"
            "В ближайшее время с вами свяжется менеджер для предоставления доступа к мероприятию.",
            reply_markup=main_menu_kb()
        )

        # Уведомляем администраторов о новом платеже
        for admin_id in config.bot.admin_ids:
            try:
                await message.bot.send_message(
                    admin_id,
                    f"Новый платеж звездами от пользователя {user_id} ({get_user_name(message.from_user)})\n"
                    f"Продукт: {product_type}\n"
                    f"Сумма: {payment.get('amount')} руб. ({int(payment.get('amount') * 0.75)} звезд)\n"
                    f"Статус: Подтвержден"
                )
            except Exception as e:
                logger.error(f"Ошибка при отправке уведомления администратору {admin_id}: {e}")


@router.message(EventStates.payment_confirmation)
async def process_event_payment_confirmation(message: Message, state: FSMContext, db: Database, config: Config):
    """
    Обработчик получения скриншота подтверждения оплаты мероприятия
    """
    data = await state.get_data()
    payment_id = data.get('payment_id')

    # Проверяем наличие фото или документа
    if not message.photo and not message.document:
        await message.answer(
            "Пожалуйста, отправьте скриншот оплаты в виде фото или документа.\n\n"
            "Если у вас возникли сложности, вы можете связаться с менеджером.",
            reply_markup=need_help_kb()
        )
        return

    # Получаем информацию о платеже
    payment = await db.get_payment(payment_id)

    if not payment:
        await message.answer(
            "Платеж не найден. Пожалуйста, попробуйте снова или обратитесь к менеджеру.",
            reply_markup=main_menu_kb()
        )
        await state.clear()
        return

    # Уведомляем пользователя о получении скриншота
    await message.answer(
        "Спасибо! Ваш скриншот отправлен на проверку.\n\n"
        "Как только платеж будет подтвержден, вы получите доступ к мероприятию.\n"
        "Наш менеджер свяжется с вами для предоставления дополнительной информации.",
        reply_markup=main_menu_kb()
    )

    # Отправляем скриншот и информацию о платеже администраторам для подтверждения
    for admin_id in config.bot.admin_ids:
        try:
            # Формируем подпись к скриншоту
            caption = (
                f"Скриншот оплаты мероприятия от пользователя {message.from_user.id} ({get_user_name(message.from_user)})\n"
                f"Платеж ID: {payment_id}\n"
                f"Мероприятие: {payment.get('product_type')}\n"
                f"Сумма: {payment.get('amount')} рублей\n\n"
                f"Для подтверждения платежа используйте команду: /confirm_payment {payment_id}"
            )

            # Пересылаем скриншот администратору
            if message.photo:
                await message.bot.send_photo(
                    chat_id=admin_id,
                    photo=message.photo[-1].file_id,
                    caption=caption
                )
            elif message.document:
                await message.bot.send_document(
                    chat_id=admin_id,
                    document=message.document.file_id,
                    caption=caption
                )

            logger.info(f"Скриншот оплаты мероприятия отправлен администратору {admin_id}")
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления администратору {admin_id} о платеже мероприятия: {e}")

    # Сбрасываем состояние
    await state.clear()


# Импортируем в конце, чтобы избежать циклических импортов
from keyboards import need_help_kb