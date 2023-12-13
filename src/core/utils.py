import logging
import time
import traceback

import requests

import config
from markets_bridge.dtos import (
    MBBrandDTO,
    MBCategoryDTO,
    MBProductDTO,
)
from markets_bridge.utils import (
    Sender,
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


# TODO: Декомпозировать
def product_card_processing(url: str):
    formatter = Formatter()
    toyzz_products = Parser.parse_products_by_card_url(url)

    for product in toyzz_products:
        formatter.toyzz_product = product

        mb_category = formatter.get_category()
        Sender.send_category(mb_category)

        mb_brand = formatter.get_brand()
        Sender.send_brand(mb_brand)

        mb_product = formatter.get_product()
        existed_product_response = Sender.send_product(mb_product)

        if existed_product_response.status_code == 201:
            existed_product = existed_product_response.json()

            for image_url in product.image_urls:
                try:
                    image = fetch_image(image_url)
                except IOError as e:
                    handle_exception(e)
                    continue
                else:
                    Sender.send_image(image, existed_product['id'])


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


class Formatter:
    """Преобразователь из Toyzz DTOs в Markets-Bridge DTOs."""

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
