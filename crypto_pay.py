"""
Модуль для работы с Crypto Pay API.
Обеспечивает интеграцию с Crypto Bot для приема платежей в криптовалюте.
"""
import aiohttp
import logging
from typing import Dict, Any, Optional, List, Union
import json

logger = logging.getLogger(__name__)


class CryptoPayAPI:
    """
    Класс для работы с Crypto Pay API
    """

    def __init__(self, api_token: str, is_testnet: bool = False):
        """
        Инициализация Crypto Pay API
        :param api_token: Токен API приложения в Crypto Bot
        :param is_testnet: Использовать тестовую сеть (True) или основную (False)
        """
        self.api_token = api_token
        self.is_testnet = is_testnet
        self.base_url = "https://testnet-pay.crypt.bot/api" if is_testnet else "https://pay.crypt.bot/api"
        self.headers = {
            "Crypto-Pay-API-Token": api_token,
            "Content-Type": "application/json"
        }

    async def _make_request(self, method: str, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[
        str, Any]:
        """
        Выполнение запроса к API
        :param method: HTTP метод (GET, POST)
        :param endpoint: Конечная точка API
        :param params: Параметры запроса
        :return: Ответ от API
        """
        url = f"{self.base_url}/{endpoint}"

        try:
            async with aiohttp.ClientSession() as session:
                if method.upper() == "GET":
                    async with session.get(url, params=params, headers=self.headers) as response:
                        response_json = await response.json()
                elif method.upper() == "POST":
                    async with session.post(url, json=params, headers=self.headers) as response:
                        response_json = await response.json()
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")

                if not response_json.get("ok"):
                    error_msg = response_json.get("error", "Unknown error")
                    logger.error(f"Crypto Pay API error: {error_msg}")
                    raise Exception(f"Crypto Pay API error: {error_msg}")

                return response_json.get("result", {})
        except aiohttp.ClientError as e:
            logger.error(f"HTTP request error: {str(e)}")
            raise Exception(f"HTTP request error: {str(e)}")
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {str(e)}")
            raise Exception(f"JSON decode error: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            raise

    async def get_me(self) -> Dict[str, Any]:
        """
        Получение информации о приложении
        :return: Информация о приложении
        """
        return await self._make_request("GET", "getMe")

    async def create_invoice(
            self,
            amount: str,
            asset: str = "USDT",
            description: str = "",
            hidden_message: str = "",
            paid_btn_name: str = None,
            paid_btn_url: str = None,
            payload: str = "",
            allow_comments: bool = True,
            allow_anonymous: bool = True,
            expires_in: int = None
    ) -> Dict[str, Any]:
        """
        Создание инвойса для оплаты
        :param amount: Сумма платежа в формате строки (например, "10.5")
        :param asset: Криптовалюта (USDT, TON, BTC, ETH и др.)
        :param description: Описание платежа
        :param hidden_message: Скрытое сообщение, которое будет показано после оплаты
        :param paid_btn_name: Название кнопки после оплаты (viewItem, openChannel, openBot, callback)
        :param paid_btn_url: URL для кнопки после оплаты
        :param payload: Дополнительные данные к платежу (ID пользователя, ID товара и т.д.)
        :param allow_comments: Разрешить комментарии к платежу
        :param allow_anonymous: Разрешить анонимные платежи
        :param expires_in: Время жизни инвойса в секундах (от 1 до 2678400)
        :return: Данные созданного инвойса
        """
        params = {
            "asset": asset,
            "amount": amount,
            "description": description,
            "allow_comments": allow_comments,
            "allow_anonymous": allow_anonymous,
            "payload": payload,
        }

        # Добавляем опциональные параметры
        if hidden_message:
            params["hidden_message"] = hidden_message

        if paid_btn_name and paid_btn_url:
            params["paid_btn_name"] = paid_btn_name
            params["paid_btn_url"] = paid_btn_url

        if expires_in:
            params["expires_in"] = expires_in

        return await self._make_request("POST", "createInvoice", params)

    async def get_invoices(
            self,
            asset: str = None,
            invoice_ids: List[str] = None,
            status: str = None,
            offset: int = 0,
            count: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Получение списка инвойсов
        :param asset: Фильтр по криптовалюте
        :param invoice_ids: Список ID инвойсов для получения
        :param status: Фильтр по статусу (active, paid)
        :param offset: Смещение для пагинации
        :param count: Количество записей (от 1 до 1000)
        :return: Список инвойсов
        """
        params = {
            "offset": offset,
            "count": count
        }

        if asset:
            params["asset"] = asset

        if invoice_ids:
            params["invoice_ids"] = ",".join(invoice_ids)

        if status:
            params["status"] = status

        return await self._make_request("GET", "getInvoices", params)

    async def check_invoice(self, invoice_id: Union[int, str]) -> Dict[str, Any]:
        """
        Проверка статуса инвойса по его ID
        :param invoice_id: ID инвойса
        :return: Информация об инвойсе
        """
        params = {
            "invoice_ids": str(invoice_id)
        }

        invoices = await self._make_request("GET", "getInvoices", params)

        if not invoices:
            raise Exception(f"Invoice with ID {invoice_id} not found")

        return invoices[0]

    async def get_exchange_rates(self) -> List[Dict[str, Any]]:
        """
        Получение курсов обмена криптовалют
        :return: Список курсов обмена
        """
        return await self._make_request("GET", "getExchangeRates")

    async def get_currencies(self) -> List[str]:
        """
        Получение списка поддерживаемых валют
        :return: Список поддерживаемых валют
        """
        return await self._make_request("GET", "getCurrencies")

    async def delete_invoice(self, invoice_id: Union[int, str]) -> bool:
        """
        Удаление инвойса
        :param invoice_id: ID инвойса
        :return: True если успешно, иначе Exception
        """
        params = {
            "invoice_id": invoice_id
        }

        await self._make_request("POST", "deleteInvoice", params)
        return True