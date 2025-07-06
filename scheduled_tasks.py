"""
Модуль для запланированных задач бота клуба X10.
"""
import asyncio
import logging
import sqlite3
from datetime import datetime, timedelta
from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from database import Database
from config import Config
from utils import kick_user_from_group, get_subscription_end_text, get_user_name, get_payment_description
from keyboards import extend_subscription_kb, club_menu_kb, club_access_kb
from crypto_pay import CryptoPayAPI

logger = logging.getLogger(__name__)

class ScheduledTasks:
    def __init__(self, bot: Bot, db: Database, config: Config):
        """
        Инициализация планировщика задач
        :param bot: Объект бота
        :param db: Объект базы данных
        :param config: Объект конфигурации
        """
        self.bot = bot
        self.db = db
        self.config = config
        self.scheduler = AsyncIOScheduler()

        # Инициализация задач
        self._init_tasks()

    def _init_tasks(self):
        """
        Инициализация задач планировщика
        """
        # Проверка истекающих подписок (каждый день в 12:00)
        self.scheduler.add_job(
            self._check_expiring_subscriptions,
            CronTrigger(hour=12, minute=0),
            name="check_expiring_subscriptions"
        )

        # Проверка истекших подписок (каждый час)
        self.scheduler.add_job(
            self._check_expired_subscriptions,
            IntervalTrigger(hours=1),
            name="check_expired_subscriptions"
        )

        # Отправка напоминаний рефералам (каждый день в 10:00)
        self.scheduler.add_job(
            self._send_referral_reminders,
            CronTrigger(hour=10, minute=0),
            name="send_referral_reminders"
        )

        # Отправка ограниченных предложений (каждый месяц 1-го числа в 9:00)
        self.scheduler.add_job(
            self._send_limited_offers,
            CronTrigger(day=1, hour=9, minute=0),
            name="send_limited_offers"
        )

        # Обновление статистики (каждый день в 00:05)
        self.scheduler.add_job(
            self._update_statistics,
            CronTrigger(hour=0, minute=5),
            name="update_statistics"
        )

        # Проверка активности пользователей (каждую неделю в понедельник в 09:00)
        self.scheduler.add_job(
            self._check_user_activity,
            CronTrigger(day_of_week='mon', hour=9, minute=0),
            name="check_user_activity"
        )

    def start(self):
        """
        Запуск планировщика задач
        """
        self.scheduler.start()
        logger.info("Планировщик задач запущен")

    def shutdown(self):
        """
        Остановка планировщика задач
        """
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Планировщик задач остановлен")

    async def _check_expiring_subscriptions(self):
        """
        Проверка подписок, истекающих через 3 и 1 день
        """
        logger.info("Запуск проверки истекающих подписок")

        for days in [3, 1]:
            expiring = await self.db.get_expiring_subscriptions(days)
            logger.info(f"Найдено {len(expiring)} подписок, истекающих через {days} дней")

            for sub in expiring:
                user_id = sub['user_id']
                try:
                    # Отправка уведомления пользователю
                    await self.bot.send_message(
                        user_id,
                        get_subscription_end_text(user_id, days),
                        reply_markup=extend_subscription_kb()
                    )
                    logger.info(f"Отправлено уведомление об истечении подписки пользователю {user_id} (осталось {days} дней)")
                except Exception as e:
                    logger.error(f"Ошибка при отправке уведомления пользователю {user_id}: {e}")

    async def _check_expired_subscriptions(self):
        """
        Проверка и обработка истекших подписок
        """
        logger.info("Запуск проверки истекших подписок")

        expired = await self.db.get_expired_subscriptions()
        logger.info(f"Найдено {len(expired)} истекших подписок")

        for sub in expired:
            user_id = sub['user_id']
            subscription_id = sub['subscription_id']

            try:
                # Деактивация подписки
                await self.db.deactivate_subscription(subscription_id)

                # Исключение пользователя из группы
                kick_result = await kick_user_from_group(self.bot, self.config, user_id)

                # Отправка уведомления пользователю
                await self.bot.send_message(
                    user_id,
                    get_subscription_end_text(user_id, 0),
                    reply_markup=club_menu_kb()
                )

                if kick_result:
                    logger.info(f"Подписка {subscription_id} пользователя {user_id} истекла. Пользователь исключен из группы.")
                else:
                    logger.warning(f"Подписка {subscription_id} пользователя {user_id} истекла, но не удалось исключить из группы.")
            except Exception as e:
                logger.error(f"Ошибка при обработке истекшей подписки {subscription_id} пользователя {user_id}: {e}")

    async def _send_referral_reminders(self):
        """
        Отправка напоминаний по реферальной программе
        """
        logger.info("Запуск отправки напоминаний по реферальной программе")

        try:
            # Получаем всех пользователей
            conn = await self.db.get_conn()
            try:
                conn.row_factory = sqlite3.Row
                cursor = await conn.execute("SELECT user_id FROM users WHERE registration_date < datetime('now', '-3 day')")
                users = await cursor.fetchall()
            finally:
                await conn.close()

            bot_info = await self.bot.get_me()

            for user in users:
                user_id = user["user_id"]

                # Проверяем количество рефералов
                referrals_count = await self.db.count_user_referrals(user_id)

                # Если у пользователя менее 5 рефералов и прошло 3 дня с момента регистрации
                if referrals_count < 5:
                    # Генерируем реферальную ссылку
                    from utils import generate_ref_link
                    ref_link = generate_ref_link(bot_info.username, user_id)

                    # Получаем имя пользователя
                    user_data = await self.db.get_user(user_id)
                    user_name = user_data.get('first_name', 'Пользователь')

                    # Отправляем напоминание
                    try:
                        await self.bot.send_message(
                            user_id,
                            f"👋 Добрый день, {user_name}\n\n"
                            f"Не забыли о своей реферальной ссылке?\n\n"
                            f"Вот она: {ref_link}\n\n"
                            f"💡 Совет: Добавьте ссылку в подпись Telegram или делитесь в чатах с друзьями.\n\n"
                            f"За каждого приглашенного друга ты получаешь:\n"
                            f"🎯 1 друг – 1000 баллов (1 балл = 1 рубль)\n"
                            f"🎯 3 друга – доступ к VIP продукту экскурсия по Вьетнаму\n"
                            f"🎯 5 друзей – месяц бесплатного членства в Клубе Х10\n"
                            f"🎯 10 друзей – персональная консультация с основателем Клуба Х10",
                            reply_markup=None  # Здесь можно добавить клавиатуру
                        )
                        logger.info(f"Отправлено напоминание о реферальной программе пользователю {user_id}")
                    except Exception as e:
                        logger.error(f"Ошибка при отправке напоминания пользователю {user_id}: {e}")

        except Exception as e:
            logger.error(f"Ошибка при отправке напоминаний о реферальной программе: {e}")

    async def _send_limited_offers(self):
        """
        Отправка ограниченных предложений по реферальной программе
        """
        logger.info("Запуск отправки ограниченных предложений")

        try:
            # Получаем активных пользователей с хотя бы одним рефералом
            conn = await self.db.get_conn()
            try:
                conn.row_factory = sqlite3.Row
                cursor = await conn.execute("""
                    SELECT u.user_id, u.first_name 
                    FROM users u
                    JOIN referrals r ON u.user_id = r.referrer_id
                    GROUP BY u.user_id
                    HAVING COUNT(r.user_id) >= 1
                """)
                users = await cursor.fetchall()
            finally:
                await conn.close()

            bot_info = await self.bot.get_me()

            for user in users:
                user_id = user["user_id"]
                user_name = user["first_name"] or "Пользователь"

                # Генерируем реферальную ссылку
                from utils import generate_ref_link
                ref_link = generate_ref_link(bot_info.username, user_id)

                # Отправляем ограниченное предложение
                try:
                    await self.bot.send_message(
                        user_id,
                        f"⏳ Только 24 часа!\n\n"
                        f"За каждого нового друга по вашей ссылке вы получите\n"
                        f"в 2 раза больше баллов (2000 вместо 1000).\n"
                        f"(1 балл = 1 рубль)\n\n"
                        f"Успейте пригласить: {ref_link}",
                        reply_markup=None  # Здесь можно добавить клавиатуру
                    )
                    logger.info(f"Отправлено ограниченное предложение пользователю {user_id}")
                except Exception as e:
                    logger.error(f"Ошибка при отправке ограниченного предложения пользователю {user_id}: {e}")

        except Exception as e:
            logger.error(f"Ошибка при отправке ограниченных предложений: {e}")

    async def _update_statistics(self):
        """
        Обновление статистики использования бота
        """
        logger.info("Запуск обновления статистики")

        try:
            # Получаем общее количество пользователей
            conn = await self.db.get_conn()
            try:
                cursor = await conn.execute("SELECT COUNT(*) FROM users")
                total_users = (await cursor.fetchone())[0]

                # Получаем количество активных подписок
                cursor = await conn.execute(
                    "SELECT COUNT(*) FROM subscriptions WHERE status = 'active' AND end_date > datetime('now')"
                )
                active_subscriptions = (await cursor.fetchone())[0]

                # Получаем количество рефералов
                cursor = await conn.execute("SELECT COUNT(*) FROM referrals")
                total_referrals = (await cursor.fetchone())[0]

                # Получаем количество платежей за день
                cursor = await conn.execute(
                    "SELECT COUNT(*) FROM payments WHERE date(created_at) = date('now', '-1 day')"
                )
                daily_payments = (await cursor.fetchone())[0]
            finally:
                await conn.close()

            # Отправляем статистику администраторам
            stats_message = (
                f"📊 Статистика бота за {(datetime.now() - timedelta(days=1)).strftime('%d.%m.%Y')}:\n\n"
                f"👥 Всего пользователей: {total_users}\n"
                f"🔑 Активных подписок: {active_subscriptions}\n"
                f"👨‍👩‍👧‍👦 Всего рефералов: {total_referrals}\n"
                f"💰 Платежей за день: {daily_payments}"
            )

            for admin_id in self.config.bot.admin_ids:
                try:
                    await self.bot.send_message(admin_id, stats_message)
                except Exception as e:
                    logger.error(f"Ошибка при отправке статистики администратору {admin_id}: {e}")

        except Exception as e:
            logger.error(f"Ошибка при обновлении статистики: {e}")

    async def _check_user_activity(self):
        """
        Проверка активности пользователей и отправка напоминаний неактивным
        """
        logger.info("Запуск проверки активности пользователей")

        try:
            # Получаем пользователей с активной подпиской, которые не взаимодействовали с ботом более 7 дней
            # В данном примере мы не отслеживаем последнюю активность, поэтому просто выбираем всех с активной подпиской
            conn = await self.db.get_conn()
            try:
                conn.row_factory = sqlite3.Row
                cursor = await conn.execute("""
                    SELECT u.user_id, u.first_name 
                    FROM users u
                    JOIN subscriptions s ON u.user_id = s.user_id
                    WHERE s.status = 'active' AND s.end_date > datetime('now')
                """)
                users = await cursor.fetchall()
            finally:
                await conn.close()

            for user in users:
                user_id = user["user_id"]
                user_name = user["first_name"] or "Пользователь"

                # Отправляем напоминание об активности
                try:
                    await self.bot.send_message(
                        user_id,
                        f"Привет, {user_name}!\n\n"
                        f"Давно не виделись в нашем клубе. Загляните к нам, у нас много интересного:\n\n"
                        f"- Новые материалы в закрытом чате\n"
                        f"- Актуальные темы для обсуждения\n"
                        f"- Возможность общения с экспертами\n\n"
                        f"Не забывайте, что ваша подписка активна, используйте её возможности по максимуму!",
                        reply_markup=None  # Здесь можно добавить клавиатуру
                    )
                    logger.info(f"Отправлено напоминание об активности пользователю {user_id}")
                except Exception as e:
                    logger.error(f"Ошибка при отправке напоминания об активности пользователю {user_id}: {e}")

        except Exception as e:
            logger.error(f"Ошибка при проверке активности пользователей: {e}")

    async def _check_pending_crypto_payments(self):
        """
        Периодическая проверка статуса ожидающих криптоплатежей
        """
        logger.info("Запуск проверки ожидающих криптоплатежей")

        try:
            # Получаем список ожидающих криптоплатежей
            payments = await self.db.get_pending_crypto_payments()

            if not payments:
                logger.info("Нет ожидающих криптоплатежей")
                return

            logger.info(f"Найдено {len(payments)} ожидающих криптоплатежей")

            # Инициализируем Crypto Pay API
            crypto_pay = CryptoPayAPI(
                api_token=self.config.crypto_pay.api_token,
                is_testnet=self.config.crypto_pay.is_testnet
            )

            for payment in payments:
                try:
                    invoice_id = payment.get('invoice_id')
                    user_id = payment.get('user_id')
                    product_type = payment.get('product_type')

                    logger.info(f"Проверка платежа {invoice_id} пользователя {user_id}")

                    # Проверяем статус инвойса
                    invoice = await crypto_pay.check_invoice(invoice_id)
                    status = invoice.get('status')

                    if status == 'paid':
                        logger.info(f"Платеж {invoice_id} оплачен, обновляем статус")

                        # Подтверждаем платеж в базе данных
                        await self.db.confirm_crypto_payment(invoice_id)

                        # Если это оплата клуба, активируем подписку
                        if product_type == "club":
                            payment_info = get_payment_description(product_type, self.config)
                            await self.db.add_subscription(user_id, payment_info["days"])

                            # Отправляем уведомление пользователю
                            try:
                                await self.bot.send_message(
                                    user_id,
                                    f"🎉 Поздравляем! Ваш платеж в криптовалюте подтвержден.\n\n"
                                    f"Доступ к клубу X10 активирован на {payment_info['days']} дней.\n\n"
                                    f"Теперь вы можете присоединиться к клубу, нажав на кнопку ниже:",
                                    reply_markup=club_access_kb()
                                )
                                logger.info(f"Отправлено уведомление пользователю {user_id} о подтверждении платежа")
                            except Exception as e:
                                logger.error(f"Ошибка при отправке уведомления пользователю {user_id}: {e}")

                        else:
                            # Для других продуктов (мероприятия)
                            try:
                                await self.bot.send_message(
                                    user_id,
                                    f"🎉 Поздравляем! Ваш платеж в криптовалюте за {product_type} подтвержден.\n\n"
                                    f"Наш менеджер свяжется с вами для предоставления дополнительной информации."
                                )
                                logger.info(f"Отправлено уведомление пользователю {user_id} о подтверждении платежа")
                            except Exception as e:
                                logger.error(f"Ошибка при отправке уведомления пользователю {user_id}: {e}")

                        # Уведомляем администраторов
                        for admin_id in self.config.bot.admin_ids:
                            try:
                                user_data = await self.db.get_user(user_id)
                                user_name = get_user_name(user_data) if user_data else f"Пользователь {user_id}"

                                await self.bot.send_message(
                                    admin_id,
                                    f"💰 Новый платеж в криптовалюте подтвержден!\n\n"
                                    f"Пользователь: {user_name} (ID: {user_id})\n"
                                    f"Продукт: {product_type}\n"
                                    f"Криптовалюта: {payment.get('asset')}\n"
                                    f"Сумма: {payment.get('amount')} {payment.get('asset')}\n"
                                    f"Статус: ✅ Подтвержден"
                                )
                            except Exception as e:
                                logger.error(f"Ошибка при отправке уведомления администратору {admin_id}: {e}")

                    elif status == 'expired':
                        # Помечаем платеж как истекший в базе данных
                        await self.db.mark_crypto_payment_expired(invoice_id)
                        logger.info(f"Платеж {invoice_id} истек")

                        # Уведомляем пользователя
                        try:
                            await self.bot.send_message(
                                user_id,
                                f"Срок действия вашего платежа в криптовалюте истек.\n\n"
                                f"Если вы все еще хотите произвести оплату, пожалуйста, создайте новый платеж.\n\n"
                                f"Нажмите на кнопку Оплатить доступ в меню клуба."
                            )
                        except Exception as e:
                            logger.error(f"Ошибка при отправке уведомления пользователю {user_id} об истекшем платеже: {e}")

                    else:
                        logger.info(f"Платеж {invoice_id} в статусе {status}, пропускаем")

                except Exception as e:
                    logger.error(f"Ошибка при проверке платежа {payment.get('invoice_id')}: {e}")

        except Exception as e:
            logger.error(f"Ошибка при проверке криптоплатежей: {e}")

    async def run_startup_tasks(self):
        """
        Выполнение задач при запуске бота
        """
        logger.info("Выполнение стартовых задач")

        # Проверка истекших подписок при запуске
        await self._check_expired_subscriptions()

        logger.info("Стартовые задачи выполнены")