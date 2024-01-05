import logging
import time
import traceback
from abc import (
    ABC,
    abstractmethod,
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
from markets_bridge.utils import (
    BrandSender,
    CategorySender,
    CharacteristicSender,
    CharacteristicValueSender,
    ProductSender,
    send_image,
    write_log_entry,
)
from toyzz.dtos import (
    ToyzzProductDTO,
)
from toyzz.utils import (
    CategoryParser,
    ProductCardParser,
)


def category_processing(url: str):
    toyzz_products = CategoryParser.parse(url)

    for product in toyzz_products:
        process_product(product)


def product_card_processing(url: str):
    toyzz_products = ProductCardParser.parse(url)

    for product in toyzz_products:
        process_product(product)


def process_product(product: ToyzzProductDTO):
    _process_category(product)
    _process_brand(product)
    _process_characteristics(product)
    _process_characteristic_values(product)
    product_response = _process_product(product)

    if product_response.status_code == 201:
        existed_product = product_response.json()

        for image_url in product.image_urls:
            try:
                image = fetch_image(image_url)
            except IOError as e:
                handle_exception(e)
                continue
            else:
                send_image(image, existed_product['id'])


def _process_category(product: ToyzzProductDTO):
    mb_category = CategoryAdapter.get_formatted_data(product)
    response = CategorySender.send(mb_category)

    return response


def _process_brand(product: ToyzzProductDTO):
    mb_brand = BrandAdapter.get_formatted_data(product)
    response = BrandSender.send(mb_brand)

    return response


def _process_characteristics(product: ToyzzProductDTO):
    mb_characteristics = CharacteristicAdapter.get_formatted_data(product)
    responses = []

    for char in mb_characteristics:
        responses.append(CharacteristicSender.send(char))

    return responses


def _process_characteristic_values(product: ToyzzProductDTO):
    mb_values = CharacteristicValueAdapter.get_formatted_data(product)
    responses = []

    for value in mb_values:
        responses.append(CharacteristicValueSender.send(value))

    return responses


def _process_product(product: ToyzzProductDTO):
    mb_product = ProductAdapter.get_formatted_data(product)
    response = ProductSender.send(mb_product)

    return response


def fetch_image(url: str, repeat_number: int = 1) -> bytes:
    if repeat_number >= 5:
        raise IOError('Max retries for fetch image.')

    try:
        image_response = requests.get(url)
    except (requests.HTTPError, requests.ConnectionError, requests.ConnectTimeout):
        logging.error('An error occurred while receiving the image. Try again...')
        repeat_number += 1
        time.sleep(1)
        image = fetch_image(url, repeat_number)
    else:
        image = image_response.content

    return image


# TODO: использовать Sentry
def handle_exception(e: Exception):
    error = f'There was a problem ({e.__class__.__name__}): {e}'
    write_log_entry(error)
    logging.exception(error)
    print(traceback.format_exc())


class BaseAdapter(ABC):
    """Базовый преобразователь из Toyzz DTO в MB DTO."""

    @staticmethod
    @abstractmethod
    def get_formatted_data(product: ToyzzProductDTO):
        """Форматирует данные, полученные от MBProductDTO."""


class ProductAdapter(BaseAdapter):
    """Преобразователь товаров для Markets-Bridge."""

    @staticmethod
    def get_formatted_data(product: ToyzzProductDTO):
        product = MBProductDTO(
            external_id=product.id,
            name=product.name,
            description=product.description,
            url=product.url,
            price=product.price,
            discounted_price=product.discounted_price,
            stock_quantity=product.stock,
            product_code=product.product_code,
            category_name=product.category.name,
            brand_name=product.brand.name,
            depth=product.depth,
            width=product.width,
            height=product.height,
            weight=product.weight,
            marketplace_id=config.marketplace_id,
            characteristic_values=[value.value for value in product.values],
        )

        return product


class CategoryAdapter(BaseAdapter):
    """Преобразователь категорий для Markets-Bridge."""

    @staticmethod
    def get_formatted_data(product: ToyzzProductDTO):
        category = MBCategoryDTO(
            external_id=product.category.id,
            name=product.category.name,
            marketplace_id=config.marketplace_id,
        )

        return category


class BrandAdapter(BaseAdapter):
    """Преобразователь брендов для Markets-Bridge."""

    @staticmethod
    def get_formatted_data(product: ToyzzProductDTO):
        brand = MBBrandDTO(
            external_id=product.brand.id,
            name=product.brand.name,
            marketplace_id=config.marketplace_id,
        )

        return brand


class CharacteristicAdapter(BaseAdapter):
    """Преобразователь характеристик для Markets-Bridge."""

    @staticmethod
    def get_formatted_data(product: ToyzzProductDTO):
        characteristic_list = []

        for value in product.values:

            characteristic = MBCharacteristicDTO(
                name=value.attribute.name,
                marketplace_id=config.marketplace_id,
            )

            characteristic_list.append(characteristic)

        return characteristic_list


class CharacteristicValueAdapter(BaseAdapter):
    """Преобразователь значений характеристик для Markets-Bridge."""

    @staticmethod
    def get_formatted_data(product: ToyzzProductDTO):
        values = []

        for toyzz_value in product.values:
            mb_value = MBCharacteristicValueDTO(
                value=toyzz_value.value,
                characteristic_name=toyzz_value.attribute.name,
                marketplace_id=config.marketplace_id,
            )

            values.append(mb_value)

        return values
