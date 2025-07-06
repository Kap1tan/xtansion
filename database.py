"""
Модуль для работы с базой данных.
Содержит функции для взаимодействия с SQLite.
"""
import sqlite3
import aiosqlite
import asyncio
import datetime
from typing import List, Dict, Any, Optional, Tuple, Union


class Database:
    def __init__(self, db_path: str):
        """
        Инициализация базы данных
        :param db_path: путь к файлу базы данных
        """
        self.db_path = db_path

    async def create_tables(self):
        """Создание необходимых таблиц в базе данных"""
        async with aiosqlite.connect(self.db_path) as db:
            # Пользователи
            await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                balance INTEGER DEFAULT 0,
                is_admin BOOLEAN DEFAULT 0
            )
            ''')

            # Подписки на клуб
            await db.execute('''
            CREATE TABLE IF NOT EXISTS subscriptions (
                subscription_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                start_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                end_date TIMESTAMP,
                status TEXT DEFAULT 'active',
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
            ''')

            # Платежи
            await db.execute('''
            CREATE TABLE IF NOT EXISTS payments (
                payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount INTEGER,
                product_type TEXT,
                payment_method TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                confirmed_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
            ''')

            # Реферальная система
            await db.execute('''
            CREATE TABLE IF NOT EXISTS referrals (
                referral_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                referrer_id INTEGER,
                join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 1,
                FOREIGN KEY (user_id) REFERENCES users (user_id),
                FOREIGN KEY (referrer_id) REFERENCES users (user_id)
            )
            ''')

            # Мероприятия и регистрации
            await db.execute('''
            CREATE TABLE IF NOT EXISTS events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                description TEXT,
                event_date TIMESTAMP,
                price INTEGER,
                max_participants INTEGER DEFAULT NULL
            )
            ''')

            await db.execute('''
            CREATE TABLE IF NOT EXISTS event_registrations (
                registration_id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER,
                user_id INTEGER,
                payment_id INTEGER,
                registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'registered',
                FOREIGN KEY (event_id) REFERENCES events (event_id),
                FOREIGN KEY (user_id) REFERENCES users (user_id),
                FOREIGN KEY (payment_id) REFERENCES payments (payment_id)
            )
            ''')

            # Добавляем таблицу для криптоплатежей
            await db.execute('''
            CREATE TABLE IF NOT EXISTS crypto_payments (
                payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                invoice_id TEXT,
                asset TEXT,
                amount TEXT,
                product_type TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                paid_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
            ''')

            await db.commit()

    # Методы для работы с пользователями
    async def add_user(self, user_id: int, username: str = None, first_name: str = None, last_name: str = None) -> bool:
        """
        Добавление нового пользователя или обновление существующего
        """
        async with aiosqlite.connect(self.db_path) as db:
            # Проверяем, существует ли пользователь
            cursor = await db.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
            user = await cursor.fetchone()

            if user:
                # Обновляем информацию о пользователе
                await db.execute(
                    "UPDATE users SET username = ?, first_name = ?, last_name = ? WHERE user_id = ?",
                    (username, first_name, last_name, user_id)
                )
            else:
                # Добавляем нового пользователя
                await db.execute(
                    "INSERT INTO users (user_id, username, first_name, last_name) VALUES (?, ?, ?, ?)",
                    (user_id, username, first_name, last_name)
                )

            await db.commit()
            return True

    async def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Получение информации о пользователе
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = sqlite3.Row
            cursor = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            user = await cursor.fetchone()

            if user:
                return dict(user)
            return None

    async def update_user_balance(self, user_id: int, amount: int) -> int:
        """
        Обновление баланса пользователя
        """
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE users SET balance = balance + ? WHERE user_id = ?",
                (amount, user_id)
            )
            await db.commit()

            # Получаем обновленный баланс
            cursor = await db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
            result = await cursor.fetchone()
            return result[0] if result else 0

    # Методы для работы с подписками
    async def add_subscription(self, user_id: int, days: int) -> int:
        """
        Добавление подписки для пользователя
        """
        end_date = datetime.datetime.now() + datetime.timedelta(days=days)

        async with aiosqlite.connect(self.db_path) as db:
            # Проверяем наличие активной подписки
            cursor = await db.execute(
                "SELECT subscription_id, end_date FROM subscriptions WHERE user_id = ? AND status = 'active' ORDER BY end_date DESC LIMIT 1",
                (user_id,)
            )
            existing_sub = await cursor.fetchone()

            if existing_sub:
                # Если есть активная подписка, продлеваем ее
                subscription_id, current_end = existing_sub

                # Конвертируем строку в datetime, если необходимо
                if isinstance(current_end, str):
                    current_end = datetime.datetime.fromisoformat(current_end.replace('Z', '+00:00'))

                # Если дата окончания в прошлом, используем текущую дату
                if current_end < datetime.datetime.now():
                    new_end_date = end_date
                else:
                    new_end_date = current_end + datetime.timedelta(days=days)

                await db.execute(
                    "UPDATE subscriptions SET end_date = ? WHERE subscription_id = ?",
                    (new_end_date.isoformat(), subscription_id)
                )
            else:
                # Создаем новую подписку
                cursor = await db.execute(
                    "INSERT INTO subscriptions (user_id, end_date) VALUES (?, ?)",
                    (user_id, end_date.isoformat())
                )
                subscription_id = cursor.lastrowid

            await db.commit()
            return subscription_id

    async def check_subscription(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Проверка активной подписки пользователя
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = sqlite3.Row
            cursor = await db.execute(
                "SELECT * FROM subscriptions WHERE user_id = ? AND status = 'active' AND end_date > datetime('now') ORDER BY end_date DESC LIMIT 1",
                (user_id,)
            )
            subscription = await cursor.fetchone()

            if subscription:
                return dict(subscription)
            return None

    async def get_expiring_subscriptions(self, days: int = 3) -> List[Dict[str, Any]]:
        """
        Получение списка подписок, которые истекают через указанное количество дней
        """
        target_date = (datetime.datetime.now() + datetime.timedelta(days=days)).date()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = sqlite3.Row
            cursor = await db.execute(
                """
                SELECT s.*, u.user_id, u.username, u.first_name, u.last_name
                FROM subscriptions s
                JOIN users u ON s.user_id = u.user_id
                WHERE s.status = 'active'
                AND date(s.end_date) = date(?)
                """,
                (target_date.isoformat(),)
            )

            subscriptions = await cursor.fetchall()
            return [dict(sub) for sub in subscriptions]

    async def get_expired_subscriptions(self) -> List[Dict[str, Any]]:
        """
        Получение списка истекших подписок, которые еще активны
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = sqlite3.Row
            cursor = await db.execute(
                """
                SELECT s.*, u.user_id, u.username, u.first_name, u.last_name
                FROM subscriptions s
                JOIN users u ON s.user_id = u.user_id
                WHERE s.status = 'active'
                AND datetime(s.end_date) < datetime('now')
                """
            )

            subscriptions = await cursor.fetchall()
            return [dict(sub) for sub in subscriptions]

    async def deactivate_subscription(self, subscription_id: int) -> bool:
        """
        Деактивация подписки
        """
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE subscriptions SET status = 'expired' WHERE subscription_id = ?",
                (subscription_id,)
            )
            await db.commit()
            return True

    # Методы для работы с платежами
    async def create_payment(self, user_id: int, amount: int, product_type: str, payment_method: str) -> int:
        """
        Создание новой записи о платеже
        """
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "INSERT INTO payments (user_id, amount, product_type, payment_method) VALUES (?, ?, ?, ?)",
                (user_id, amount, product_type, payment_method)
            )
            payment_id = cursor.lastrowid
            await db.commit()
            return payment_id

    async def confirm_payment(self, payment_id: int) -> bool:
        """
        Подтверждение платежа
        """
        async with aiosqlite.connect(self.db_path) as db:
            confirmed_at = datetime.datetime.now().isoformat()
            await db.execute(
                "UPDATE payments SET status = 'confirmed', confirmed_at = ? WHERE payment_id = ?",
                (confirmed_at, payment_id)
            )
            await db.commit()
            return True

    async def get_payment(self, payment_id: int) -> Optional[Dict[str, Any]]:
        """
        Получение информации о платеже
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = sqlite3.Row
            cursor = await db.execute("SELECT * FROM payments WHERE payment_id = ?", (payment_id,))
            payment = await cursor.fetchone()

            if payment:
                return dict(payment)
            return None

    # Методы для работы с криптоплатежами
    async def create_crypto_payment(self, user_id: int, invoice_id: str, asset: str, amount: str, product_type: str) -> int:
        """
        Создание новой записи о криптоплатеже
        :param user_id: ID пользователя
        :param invoice_id: ID инвойса из Crypto Bot
        :param asset: Криптовалюта (USDT, TON, BTC и т.д.)
        :param amount: Сумма в криптовалюте (строка)
        :param product_type: Тип продукта (club, vietnam, consultation)
        :return: ID платежа в нашей базе данных
        """
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "INSERT INTO crypto_payments (user_id, invoice_id, asset, amount, product_type) VALUES (?, ?, ?, ?, ?)",
                (user_id, invoice_id, asset, amount, product_type)
            )
            payment_id = cursor.lastrowid
            await db.commit()
            return payment_id

    async def confirm_crypto_payment(self, invoice_id: str) -> bool:
        """
        Подтверждение криптоплатежа
        :param invoice_id: ID инвойса из Crypto Bot
        :return: True, если платеж успешно подтвержден
        """
        async with aiosqlite.connect(self.db_path) as db:
            paid_at = datetime.datetime.now().isoformat()
            await db.execute(
                "UPDATE crypto_payments SET status = 'confirmed', paid_at = ? WHERE invoice_id = ?",
                (paid_at, invoice_id)
            )
            await db.commit()
            return True

    async def get_crypto_payment_by_invoice(self, invoice_id: str) -> Optional[Dict[str, Any]]:
        """
        Получение информации о криптоплатеже по ID инвойса
        :param invoice_id: ID инвойса из Crypto Bot
        :return: Информация о платеже или None
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = sqlite3.Row
            cursor = await db.execute("SELECT * FROM crypto_payments WHERE invoice_id = ?", (invoice_id,))
            payment = await cursor.fetchone()

            if payment:
                return dict(payment)
            return None

    async def get_crypto_payment_by_id(self, payment_id: int) -> Optional[Dict[str, Any]]:
        """
        Получение информации о криптоплатеже по его ID в нашей базе данных
        :param payment_id: ID платежа
        :return: Информация о платеже или None
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = sqlite3.Row
            cursor = await db.execute("SELECT * FROM crypto_payments WHERE payment_id = ?", (payment_id,))
            payment = await cursor.fetchone()

            if payment:
                return dict(payment)
            return None

    async def get_pending_crypto_payments(self) -> List[Dict[str, Any]]:
        """
        Получение списка ожидающих подтверждения криптоплатежей
        :return: Список платежей
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = sqlite3.Row
            cursor = await db.execute(
                """
                SELECT cp.*, u.username, u.first_name
                FROM crypto_payments cp
                LEFT JOIN users u ON cp.user_id = u.user_id
                WHERE cp.status = 'pending'
                ORDER BY cp.created_at DESC
                """
            )
            payments = await cursor.fetchall()
            return [dict(payment) for payment in payments]

    async def mark_crypto_payment_expired(self, invoice_id: str) -> bool:
        """
        Отметка криптоплатежа как истекшего
        :param invoice_id: ID инвойса из Crypto Bot
        :return: True, если успешно обновлено
        """
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE crypto_payments SET status = 'expired' WHERE invoice_id = ?",
                (invoice_id,)
            )
            await db.commit()
            return True

    # Методы для работы с реферальной системой
    async def add_referral(self, user_id: int, referrer_id: int) -> int:
        """
        Добавление записи о реферале
        """
        async with aiosqlite.connect(self.db_path) as db:
            # Проверяем, не является ли пользователь уже рефералом
            cursor = await db.execute(
                "SELECT referral_id FROM referrals WHERE user_id = ?",
                (user_id,)
            )
            existing = await cursor.fetchone()

            if existing:
                return 0  # Пользователь уже является рефералом

            # Добавляем запись о реферале
            cursor = await db.execute(
                "INSERT INTO referrals (user_id, referrer_id) VALUES (?, ?)",
                (user_id, referrer_id)
            )
            referral_id = cursor.lastrowid
            await db.commit()
            return referral_id

    async def get_user_referrals(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Получение списка рефералов пользователя
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = sqlite3.Row
            cursor = await db.execute(
                """
                SELECT r.*, u.username, u.first_name, u.last_name
                FROM referrals r
                JOIN users u ON r.user_id = u.user_id
                WHERE r.referrer_id = ? AND r.is_active = 1
                ORDER BY r.join_date DESC
                """,
                (user_id,)
            )

            referrals = await cursor.fetchall()
            return [dict(ref) for ref in referrals]

    async def get_user_referrer(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Получение информации о пригласившем пользователе
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = sqlite3.Row
            cursor = await db.execute(
                """
                SELECT u.*
                FROM referrals r
                JOIN users u ON r.referrer_id = u.user_id
                WHERE r.user_id = ? AND r.is_active = 1
                """,
                (user_id,)
            )

            referrer = await cursor.fetchone()
            return dict(referrer) if referrer else None

    async def count_user_referrals(self, user_id: int) -> int:
        """
        Подсчет количества рефералов пользователя
        """
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT COUNT(*) FROM referrals WHERE referrer_id = ? AND is_active = 1",
                (user_id,)
            )
            count = await cursor.fetchone()
            return count[0] if count else 0

    # Методы для работы с мероприятиями
    async def add_event(self, name: str, description: str, event_date: datetime.datetime, price: int,
                        max_participants: int = None) -> int:
        """
        Добавление нового мероприятия
        """
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "INSERT INTO events (name, description, event_date, price, max_participants) VALUES (?, ?, ?, ?, ?)",
                (name, description, event_date.isoformat(), price, max_participants)
            )
            event_id = cursor.lastrowid
            await db.commit()
            return event_id

    async def get_event(self, event_id: int) -> Optional[Dict[str, Any]]:
        """
        Получение информации о мероприятии
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = sqlite3.Row
            cursor = await db.execute("SELECT * FROM events WHERE event_id = ?", (event_id,))
            event = await cursor.fetchone()

            if event:
                return dict(event)
            return None

    async def register_for_event(self, event_id: int, user_id: int, payment_id: int = None) -> int:
        """
        Регистрация пользователя на мероприятие
        """
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "INSERT INTO event_registrations (event_id, user_id, payment_id) VALUES (?, ?, ?)",
                (event_id, user_id, payment_id)
            )
            registration_id = cursor.lastrowid
            await db.commit()
            return registration_id

    async def get_conn(self):
        """
        Получение соединения с базой данных для выполнения прямых SQL-запросов
        :return: Объект соединения с базой данных
        """
        # Исправленная версия метода
        return await aiosqlite.connect(self.db_path)