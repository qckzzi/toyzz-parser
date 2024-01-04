import logging
import uuid
from abc import (
    ABC,
    abstractmethod,
)
from dataclasses import (
    asdict,
)

import requests

import config
from markets_bridge.dtos import (
    MBBrandDTO,
    MBCategoryDTO,
    MBCharacteristicDTO,
    MBCharacteristicValueDTO,
    MBProductDTO,
)


class BaseSender(ABC):
    """Базовый отправитель данных к Markets-Bridge."""

    @classmethod
    @abstractmethod
    def send(cls, obj):
        """Отправляет данные к Markets-Bridge.

        Args:
            obj: Markets-Bridge DTO.
        """

    @classmethod
    def _send(cls, obj, url: str):
        """Базовый метод отправления данных к Markets-Bridge.

        Args:
            obj: Markets-Bridge DTO;
            url: адрес отправки данных.
        """

        headers = get_authorization_headers()
        logging.info(f'Отправка "{obj}" класса "{obj.__class__.__name__}".')
        response = requests.post(url, json=asdict(obj), headers=headers)

        if response.status_code == 401:
            accesser = Accesser()
            accesser.update_access_token()

            return cls._send(obj, url)

        response.raise_for_status()

        return response


class ProductSender(BaseSender):
    """Отправитель товаров к Markets-Bridge."""

    @classmethod
    def send(cls, obj: MBProductDTO):
        return cls._send(obj, url=config.mb_products_url)


class CategorySender(BaseSender):
    """Отправитель категорий к Markets-Bridge."""

    @classmethod
    def send(cls, obj: MBCategoryDTO):
        return cls._send(obj, url=config.mb_categories_url)


class BrandSender(BaseSender):
    """Отправитель брендов к Markets-Bridge."""

    @classmethod
    def send(cls, obj: MBBrandDTO):
        return cls._send(obj, url=config.mb_brands_url)


class CharacteristicSender(BaseSender):
    """Отправитель характеристик к Markets-Bridge."""

    @classmethod
    def send(cls, obj: MBCharacteristicDTO):
        return cls._send(obj, url=config.mb_characteristics_url)


class CharacteristicValueSender(BaseSender):
    """Отправитель значений характеристик к Markets-Bridge."""

    @classmethod
    def send(cls, obj: MBCharacteristicValueDTO):
        return cls._send(obj, url=config.mb_characteristic_values_url)


def send_image(image: bytes, product_id: int):
    """Отправляет изображение в виде байтов в систему Markets-Bridge, присваивая его товару с product_id."""

    headers = get_authorization_headers()
    response = requests.post(
        config.mb_product_images_url,
        data={'product': product_id},
        files={'image': (f'{uuid.uuid4().hex}.jpg', image)},
        headers=headers,
    )

    if response.status_code == 401:
        accesser = Accesser()
        accesser.update_access_token()
        response = send_image(image, product_id)

    response.raise_for_status()

    return response


class Singleton:
    _instance = None
    _initialized = False

    def __new__(cls):
        if not isinstance(cls._instance, cls):
            cls._instance = object.__new__(cls)
        return cls._instance


class Accesser(Singleton):
    """Получатель доступа к сервису Markets-Bridge.

    При первичном получении токена доступа генерируется JWT. При истечении access токена необходимо вызывать
    update_access_token(). В случае, если refresh токен умер, вызывается метод update_jwt().
    """

    def __init__(self):
        if not self._initialized:
            self._refresh_token = None
            self._access_token = None

            self._initialized = True

    @property
    def access_token(self) -> str:
        if not self._access_token:
            self.update_jwt()

        return self._access_token

    def update_jwt(self):
        login_data = {
            'username': config.mb_login,
            'password': config.mb_password
        }

        response = requests.post(config.mb_token_url, data=login_data)
        response.raise_for_status()
        token_data = response.json()
        self._access_token = token_data['access']
        self._refresh_token = token_data['refresh']

    def update_access_token(self):
        body = {'refresh': self._refresh_token}

        response = requests.post(config.mb_token_refresh_url, json=body)

        if response.status_code == 401:
            self.update_jwt()
            self.update_access_token()

            return

        response.raise_for_status()

        token_data = response.json()
        self._access_token = token_data['access']


def write_log_entry(message: str):
    """Создает записи логов в сервисе Markets-Bridge."""

    body = {'service_name': 'Toyzz parser', 'entry': message}
    headers = get_authorization_headers()
    response = requests.post(config.mb_logs_url, json=body, headers=headers)

    if response.status_code == 401:
        accesser = Accesser()
        accesser.update_access_token()

        return write_log_entry(message)

    response.raise_for_status()


def get_authorization_headers() -> dict:
    accesser = Accesser()
    access_token = accesser.access_token
    headers = {'Authorization': f'Bearer {access_token}'}

    return headers
