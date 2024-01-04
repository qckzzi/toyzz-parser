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
    Parser,
)


def category_processing(url: str):
    product_url_list = Parser.parse_product_urls_by_category_url(url)

    for product_url in product_url_list:
        try:
            product_card_processing(product_url)
        except Exception as e:
            handle_exception(e)
            continue


def product_card_processing(url: str):
    toyzz_products = Parser.parse_products_by_card_url(url)

    for product in toyzz_products:
        product_processing(product)


def product_processing(product: ToyzzProductDTO):
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
    mb_category = CategoryFormatter.get_formatted_data(product)
    response = CategorySender.send(mb_category)

    return response


def _process_brand(product: ToyzzProductDTO):
    mb_brand = BrandFormatter.get_formatted_data(product)
    response = BrandSender.send(mb_brand)

    return response


def _process_characteristics(product: ToyzzProductDTO):
    mb_characteristics = CharacteristicFormatter.get_formatted_data(product)
    responses = []

    for char in mb_characteristics:
        responses.append(CharacteristicSender.send(char))

    return responses


def _process_characteristic_values(product: ToyzzProductDTO):
    mb_values = CharacteristicValueFormatter.get_formatted_data(product)
    responses = []

    for value in mb_values:
        responses.append(CharacteristicValueSender.send(value))

    return responses


def _process_product(product: ToyzzProductDTO):
    mb_product = ProductFormatter.get_formatted_data(product)
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


class BaseFormatter(ABC):
    """Базовый преобразователь из Toyzz DTO в MB DTO."""

    @staticmethod
    @abstractmethod
    def get_formatted_data(product: ToyzzProductDTO):
        """Форматирует данные, полученные от MBProductDTO."""


class ProductFormatter(BaseFormatter):
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


class CategoryFormatter(BaseFormatter):
    """Преобразователь категорий для Markets-Bridge."""

    @staticmethod
    def get_formatted_data(product: ToyzzProductDTO):
        category = MBCategoryDTO(
            external_id=product.category.id,
            name=product.category.name,
            marketplace_id=config.marketplace_id,
        )

        return category


class BrandFormatter(BaseFormatter):
    """Преобразователь брендов для Markets-Bridge."""

    @staticmethod
    def get_formatted_data(product: ToyzzProductDTO):
        brand = MBBrandDTO(
            external_id=product.brand.id,
            name=product.brand.name,
            marketplace_id=config.marketplace_id,
        )

        return brand


class CharacteristicFormatter(BaseFormatter):
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


class CharacteristicValueFormatter(BaseFormatter):
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
