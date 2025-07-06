"""
Обработчик криптоплатежей для бота клуба X10.
"""
import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import Database
from config import Config
from keyboards import main_menu_kb, crypto_assets_kb, payment_confirmation_kb
from utils import get_user_name, get_payment_description, parse_callback_data

router = Router()
logger = logging.getLogger(__name__)


# Определение состояний FSM
class CryptoPaymentStates(StatesGroup):
    """Состояния для обработки криптоплатежей"""
    payment_confirmation = State()  # Подтверждение оплаты (загрузка скриншота)


# Используем F вместо Text - это должно работать в вашей версии aiogram
@router.callback_query(F.data.startswith("pay_method:") & F.data.endswith(":crypto"))
async def callback_pay_method_crypto(callback: CallbackQuery, db: Database, config: Config):
    """
    Обработчик выбора способа оплаты криптовалютой
    """
    print(f"Вызван обработчик crypto с callback_data: {callback.data}")
    callback_data = parse_callback_data(callback.data)
    product_type = callback_data.get("product")

    if not product_type:
        await callback.message.edit_text(
            "Произошла ошибка при выборе способа оплаты. Пожалуйста, попробуйте снова.",
            reply_markup=main_menu_kb()
        )
        await callback.answer()
        return


    # Показываем доступные криптовалюты для оплаты
    allowed_assets = ["BTC", "ETH"]  # Можно вынести в конфигурацию
    await callback.message.edit_text(
        "Выберите криптовалюту для оплаты:",
        reply_markup=crypto_assets_kb(product_type, allowed_assets)
    )
    await callback.answer()


# Также изменим обработчик выбора криптовалюты, используя lambda вместо Text
@router.callback_query(lambda c: c.data and c.data.startswith("crypto_asset:"))
async def callback_crypto_asset(callback: CallbackQuery, bot: Bot, db: Database, config: Config, state: FSMContext):
    """
    Обработчик выбора криптовалюты для оплаты
    """
    logger.info(f"Вызван обработчик выбора криптовалюты с callback_data: {callback.data}")

    user_id = callback.from_user.id

    # Простой парсинг для отладки
    parts = callback.data.split(':')
    product_type = parts[1] if len(parts) > 1 else None
    asset = parts[2] if len(parts) > 2 else None

    if not product_type or not asset:
        await callback.message.edit_text(
            "Произошла ошибка при выборе криптовалюты. Пожалуйста, попробуйте снова.",
            reply_markup=main_menu_kb()
        )
        await callback.answer()
        return

    try:
        # Получаем информацию о продукте
        payment_info = get_payment_description(product_type, config)

        # Информация о кошельках для разных криптовалют
        crypto_wallets = {
            "BTC": "bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh",
            "ETH": "UQBz-nJfosXtTmW_2bG1-CvIw_B8TLCfylmRsgqmBWtO4zfr",
            "USDT": "0x8C99B0215379AB3FCc2A01743AF2D539FE783140"  # ERC-20
        }

        # Примерные курсы (в продакшене желательно использовать API биржи)
        crypto_rates = {
            "BTC": 60000,   # 1 BTC = 60000 USD
            "ETH": 30000,       # 1 TON = 5 USD
            "USDT": 1       # 1 USDT = 1 USD
        }

        # Курс рубля к доллару (примерно)
        rub_to_usd = 1 / 75.0

        # Конвертируем цену в рублях в криптовалюту
        amount_usd = payment_info["amount"] * rub_to_usd
        amount_crypto = amount_usd / crypto_rates[asset]

        # Округляем до 6 знаков после запятой для красивого отображения
        amount_crypto_str = "{:.6f}".format(amount_crypto)

        # Создаем запись о платеже в базе данных
        payment_id = await db.create_payment(
            user_id,
            payment_info["amount"],
            product_type,
            f"crypto:{asset}"
        )

        # Формируем сообщение с деталями для оплаты
        crypto_message = (
            f"💰 Оплата {payment_info['name']} криптовалютой {asset}\n\n"
            f"Сумма: {amount_crypto_str} {asset}\n"
            f"Кошелек для оплаты: `{crypto_wallets[asset]}`\n\n"
            f"Инструкция по оплате:\n"
            f"1. Отправьте точную сумму {amount_crypto_str} {asset} на указанный кошелек\n"
            f"2. Сделайте скриншот успешной транзакции\n"
            f"3. Нажмите кнопку 'Я оплатил' и отправьте скриншот\n"
            f"4. Ожидайте подтверждения от администратора\n\n"
            f"⚠️ Внимание! Для успешной идентификации вашего платежа, пожалуйста, перешлите ТОЧНУЮ сумму, указанную выше."
        )

        await callback.message.edit_text(
            crypto_message,
            reply_markup=payment_confirmation_kb(payment_id),
            parse_mode="Markdown"
        )

    except Exception as e:
        logger.error(f"Ошибка при создании крипто-платежа: {e}")
        await callback.message.edit_text(
            f"Произошла ошибка при создании платежа: {str(e)}\n"
            f"Пожалуйста, попробуйте позже или выберите другой способ оплаты.",
            reply_markup=main_menu_kb()
        )

    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("confirm_payment:"))
async def callback_confirm_crypto_payment(callback: CallbackQuery, state: FSMContext, db: Database, config: Config):
    """
    Обработчик подтверждения оплаты криптовалютой
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

    payment_method = payment.get('payment_method', '')

    # Проверяем, что это действительно криптоплатеж
    if not payment_method.startswith('crypto:'):
        await callback.message.edit_text(
            "Неверный тип платежа. Пожалуйста, обратитесь к менеджеру.",
            reply_markup=main_menu_kb()
        )
        await callback.answer()
        return

    # Для крипто-платежей - запрашиваем скриншот
    await state.set_state(CryptoPaymentStates.payment_confirmation)
    await state.update_data(payment_id=payment_id)

    await callback.message.edit_text(
        "Пожалуйста, отправьте скриншот подтверждения транзакции.\n\n"
        "Наш менеджер проверит его и подтвердит ваш платеж."
    )

    await callback.answer()


@router.message(CryptoPaymentStates.payment_confirmation)
async def process_crypto_payment_confirmation(message: Message, state: FSMContext, db: Database, config: Config):
    """
    Обработчик получения скриншота подтверждения криптоплатежа
    """
    data = await state.get_data()
    payment_id = data.get('payment_id')

    # Проверяем наличие фото или документа
    if not message.photo and not message.document:
        await message.answer(
            "Пожалуйста, отправьте скриншот транзакции в виде фото или документа.\n\n"
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
        "Как только платеж будет подтвержден, вы получите доступ к продукту.\n"
        "Обычно проверка занимает не более 24 часов.",
        reply_markup=main_menu_kb()
    )

    # Определяем тип криптовалюты из payment_method
    payment_method = payment.get('payment_method', '')
    crypto_type = payment_method.split(':')[1] if ':' in payment_method else 'Неизвестно'

    # Отправляем скриншот и информацию о платеже администраторам для подтверждения
    for admin_id in config.bot.admin_ids:
        try:
            # Формируем подпись к скриншоту
            caption = (
                f"Скриншот оплаты криптовалютой от пользователя {message.from_user.id} ({get_user_name(message.from_user)})\n"
                f"Платеж ID: {payment_id}\n"
                f"Продукт: {payment.get('product_type')}\n"
                f"Криптовалюта: {crypto_type}\n"
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

            logger.info(f"Скриншот криптоплатежа отправлен администратору {admin_id}")
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления администратору {admin_id}: {e}")

    # Сбрасываем состояние
    await state.clear()


# Добавим команду для администраторов, чтобы проверять ожидающие криптоплатежи
@router.message(Command("crypto_payments"))
async def cmd_crypto_payments(message: Message, db: Database, config: Config):
    """
    Команда для просмотра ожидающих криптоплатежей
    """
    user_id = message.from_user.id

    # Проверяем, является ли пользователь администратором
    if user_id not in config.bot.admin_ids:
        await message.answer("У вас нет прав для выполнения этой команды.")
        return

    # Получаем список ожидающих криптоплатежей из таблицы payments
    conn = await db.get_conn()
    try:
        # Используем row_factory для получения результатов как словарей
        conn.row_factory = lambda cursor, row: {col[0]: row[idx] for idx, col in enumerate(cursor.description)}
        cursor = await conn.execute(
            """
            SELECT p.payment_id, p.user_id, u.username, u.first_name, p.product_type, 
                  p.amount, p.payment_method, p.created_at
            FROM payments p
            LEFT JOIN users u ON p.user_id = u.user_id
            WHERE p.status = 'pending' AND p.payment_method LIKE 'crypto:%'
            ORDER BY p.created_at DESC
            """
        )
        payments = await cursor.fetchall()
    finally:
        await conn.close()

    if not payments:
        await message.answer("📝 Нет ожидающих криптоплатежей")
        return

    # Формируем сообщение со списком платежей
    payments_text = "📝 Список ожидающих криптоплатежей:\n\n"

    for payment in payments:
        payment_id = payment['payment_id']
        user_id = payment['user_id']
        username = payment.get('username') or payment.get('first_name') or f"Пользователь {user_id}"
        crypto_type = payment['payment_method'].split(':')[1] if ':' in payment['payment_method'] else 'Неизвестно'
        amount = payment['amount']
        product_type = payment['product_type']
        created_at = payment['created_at']

        payments_text += (
            f"ID платежа: {payment_id}\n"
            f"👤 Пользователь: {username} (ID: {user_id})\n"
            f"🛒 Продукт: {product_type}\n"
            f"💰 Сумма: {amount} рублей\n"
            f"🪙 Криптовалюта: {crypto_type}\n"
            f"📅 Создан: {created_at}\n"
            f"✅ Для подтверждения: /confirm_payment {payment_id}\n\n"
        )

    await message.answer(payments_text)


# Импортируем в конце, чтобы избежать циклических импортов
from keyboards import need_help_kb