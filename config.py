"""
Конфигурационный файл бота клуба X10.
Здесь хранятся все настройки и константы.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

# Импортируем настройки из конфигурационного файла
import config_settings as settings


@dataclass
class BotConfig:
    """Конфигурация бота"""
    token: str  # Токен бота
    admin_ids: List[int]  # Список ID администраторов
    group_id: int  # ID группы клуба X10
    channel_id: Optional[int] = None  # ID канала клуба X10 (опционально)


@dataclass
class DbConfig:
    """Конфигурация базы данных"""
    db_path: str  # Путь к файлу базы данных


@dataclass
class PaymentConfig:
    """Настройки платежей"""
    club_price: int = 1000  # Стоимость членства в клубе
    vietnam_tour_price: int = 1000  # Стоимость экскурсии по Вьетнаму
    consultation_price: int = 2000  # Стоимость консультации с основателем

    # Реквизиты для оплаты
    payment_details: Dict[str, str] = field(default_factory=dict)

    # Криптокошельки для оплаты
    crypto_wallets: Dict[str, str] = field(default_factory=dict)


@dataclass
class ReferralConfig:
    """Настройки реферальной системы"""
    points_per_referral: int = 1000  # Баллы за приглашение одного друга
    free_days: int = 7  # Количество бесплатных дней для приглашенного

    # Бонусы за количество приглашенных
    bonus_levels: Dict[int, str] = field(default_factory=dict)


@dataclass
class Config:
    """Общая конфигурация"""
    bot: BotConfig
    db: DbConfig
    payment: PaymentConfig
    referral: ReferralConfig


def load_config() -> Config:
    """Загрузка конфигурации из файла настроек"""
    return Config(
        bot=BotConfig(
            token=settings.BOT_TOKEN,
            admin_ids=settings.ADMIN_IDS,
            group_id=settings.GROUP_ID,
            channel_id=settings.CHANNEL_ID,
        ),
        db=DbConfig(
            db_path=settings.DB_PATH,
        ),
        payment=PaymentConfig(
            club_price=settings.CLUB_PRICE,
            vietnam_tour_price=settings.VIETNAM_TOUR_PRICE,
            consultation_price=settings.CONSULTATION_PRICE,
            payment_details={
                "Карта РФ (Сбербанк)": settings.PAYMENT_CARD,
            },
            crypto_wallets={
                "BTC": settings.BTC_WALLET,
                "TON": settings.TON_WALLET,
                "USDT": settings.USDT_WALLET,
            }
        ),
        referral=ReferralConfig(
            points_per_referral=settings.POINTS_PER_REFERRAL,
            free_days=settings.FREE_DAYS,
            bonus_levels={
                1: "1000 баллов",
                3: "доступ к VIP продукту экскурсия по Вьетнаму",
                5: "месяц бесплатного членства в Клубе Х10",
                10: "персональная консультация с основателем Клуба Х10",
            }
        )
    )