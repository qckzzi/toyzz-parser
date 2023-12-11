import logging
import uuid
from dataclasses import (
    asdict,
)

import requests
from requests import (
    Response,
)

import config
from markets_bridge.dtos import (
    MBBrandDTO,
    MBCategoryDTO,
    MBProductDTO,
)
from toyzz.dtos import (
    ToyzzProductDTO,
)


class Formatter:
    """Data formatter for Markets-Bridge service."""

    product_data_class = MBProductDTO
    category_data_class = MBCategoryDTO
    brand_data_class = MBBrandDTO

    def __init__(self):
        self._toyzz_product = None

    @property
    def toyzz_product(self) -> ToyzzProductDTO:
        return self._toyzz_product

    @toyzz_product.setter
    def toyzz_product(self, raw_product: ToyzzProductDTO):
        if not isinstance(raw_product, ToyzzProductDTO):
            raise ValueError('Toyzz product must be ToyzzProductDTO')

        self._toyzz_product = raw_product

    def get_product(self) -> product_data_class:
        product = self.product_data_class(
            external_id=self.toyzz_product.id,
            name=self.toyzz_product.name,
            url=self.toyzz_product.url,
            price=self.toyzz_product.price,
            discounted_price=self.toyzz_product.discounted_price,
            stock_quantity=self.toyzz_product.stock,
            product_code=self.toyzz_product.product_code,
            category_name=self.toyzz_product.category.name,
            brand_name=self.toyzz_product.brand.name,
            depth=self.toyzz_product.depth,
            width=self.toyzz_product.width,
            height=self.toyzz_product.height,
            weight=self.toyzz_product.weight,
            marketplace_id=config.marketplace_id,
        )

        return product

    def get_category(self) -> category_data_class:
        category = self.category_data_class(
            external_id=self.toyzz_product.category.id,
            name=self.toyzz_product.category.name,
            marketplace_id=config.marketplace_id,
        )

        return category

    def get_brand(self) -> brand_data_class:
        brand = self.brand_data_class(
            external_id=self.toyzz_product.brand.id,
            name=self.toyzz_product.brand.name,
            marketplace_id=config.marketplace_id,
        )

        return brand


class Sender:
    """Data sender to Markets-Bridge service."""

    @classmethod
    def send_product(cls, product: MBProductDTO):
        logging.info(f'Sending "{product.name}" product.')

        return cls._send_object(
            product,
            url=config.mb_products_url,
        )

    @classmethod
    def send_category(cls, category: MBCategoryDTO):
        logging.info(f'Sending "{category.name}" category.')

        return cls._send_object(
            category,
            url=config.mb_categories_url,
        )

    @classmethod
    def send_brand(cls, brand: MBBrandDTO):
        logging.info(f'Sending "{brand.name}" brand.')

        return cls._send_object(
            brand,
            url=config.mb_brands_url,
        )

    @classmethod
    def send_image(cls, image: bytes, product_id: int):
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
            response = cls.send_image(image, product_id)

        response.raise_for_status()

        return response

    @classmethod
    def _send_object(cls, obj, url) -> Response:
        headers = get_authorization_headers()
        response = requests.post(url, json=asdict(obj), headers=headers)

        if response.status_code == 401:
            accesser = Accesser()
            accesser.update_access_token()

            return cls._send_object(obj, url)

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
