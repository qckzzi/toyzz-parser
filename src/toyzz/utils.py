import json
import re
from math import (
    ceil,
)

import requests
from bs4 import (
    BeautifulSoup,
)
from selenium import (
    webdriver,
)
from selenium.webdriver.common.by import (
    By,
)
from selenium.webdriver.support import (
    expected_conditions as EC,
)
from selenium.webdriver.support.wait import (
    WebDriverWait,
)

import config
from toyzz.dtos import (
    ToyzzAttributeDTO,
    ToyzzAttributeValueDTO,
    ToyzzBrandDTO,
    ToyzzCategoryDTO,
    ToyzzProductDTO,
)


class Parser:
    """Toyzz information parser."""

    product_data_class = ToyzzProductDTO
    category_data_class = ToyzzCategoryDTO
    attribute_data_class = ToyzzAttributeDTO
    attribute_value_data_class = ToyzzAttributeValueDTO
    brand_data_class = ToyzzBrandDTO

    product_re_pattern = r'var\s+data\s*=\s*{[^{}]*}'
    synonyms_for_mass = ('ağırlık', 'ağırlığı')

    # TODO: Декомпозировать; Переписать dirty code
    @classmethod
    def parse_product_urls_by_category_url(cls, url: str) -> list[str]:
        response_text = cls.send_category_request(url)

        soup = BeautifulSoup(response_text, 'html.parser')
        product_tags = soup.find_all('div', class_='product-box')

        product_urls = []

        for tag in product_tags:
            a_tag = tag.find('a', class_='image')

            if a_tag:
                product_urls.append(a_tag['href'])

        product_quantity_tag = soup.find('span', class_='fs-16')
        product_quantity = int(re.sub('[^0-9]', '', product_quantity_tag.text))

        pages_count = ceil(product_quantity/30)

        for page in range(2, pages_count+1):
            response_text = cls.send_category_request(url, page=page)
            soup = BeautifulSoup(response_text, 'html.parser')
            product_tags = soup.find_all('div', class_='product-box')

            for tag in product_tags:
                a_tag = tag.find('a', class_='image')

                if a_tag and '{{' not in a_tag['href']:
                    product_urls.append(a_tag['href'])

        marketplace_url = config.toyzz_domain
        product_urls = [f'{marketplace_url}{url}' for url in product_urls]

        return product_urls

    @classmethod
    def send_category_request(cls, url: str, page: int = 1) -> str:
        page_parameter = 'q=/page/'
        url = f'{url}?{page_parameter}{page}'

        with webdriver.Chrome() as driver:
            driver.get(url)
            WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.CLASS_NAME, 'pagination')))
            page_source = driver.page_source

        return page_source

    @classmethod
    def parse_product_urls_by_product_card_url(cls, url: str) -> list[str]:
        pass

    # TODO: Декомпозировать; Переписать dirty code
    @classmethod
    def parse_product_by_url(cls, url: str) -> product_data_class:
        response = requests.get(url)
        response.raise_for_status()

        matches = re.search(cls.product_re_pattern, response.text, re.MULTILINE)
        data_str = matches.group()

        data_str_clean = re.sub(r'//[^\n]*', '', data_str)

        regex = r'{[^{}]*}'
        matches = re.search(regex, data_str_clean, re.MULTILINE)
        data_str = matches.group()

        raw_product = json.loads(data_str.replace('\'', '"'))

        brand_name = raw_product['brand']
        brand = cls.brand_data_class(brand_name)

        soup = BeautifulSoup(response.text, 'html.parser')
        discounted_price_tag = soup.find('span', class_='a fs-22')

        if discounted_price_tag:
            discounted_price = discounted_price_tag.text
        else:
            discounted_price = raw_product['price']

        image_tags = soup.find_all('img', class_='rsTmb noDrag')
        image_urls = [
            image.get('src').replace('300x300', 'orj') for image in image_tags
            if 'data-rsvideo' not in image.parent.attrs
        ]
        paragraphs = soup.find_all('p')

        weight = '0'
        width = '0'
        height = '0'
        depth = '0'

        for p in paragraphs:
            text = p.get_text(strip=True)
            match = re.search(r':\s*(.*)', text)

            if match:
                value = match.group(1)
                text = text.lower()

                if any(mass_word in text for mass_word in cls.synonyms_for_mass):
                    weight = value.replace(' kg', '')
                elif 'kutu ölçüsü' in text:
                    dimensions = value.replace(' cm', '').strip('.').split(" x ")

                    if len(dimensions) == 3:
                        width, depth, height = dimensions

        category_breadcrumb = soup.find('ol', class_='breadcrumb')
        category_name = category_breadcrumb.contents[5].text
        category = cls.category_data_class(category_name)

        product = cls.product_data_class(
            id=int(raw_product['id'].strip()),
            name=raw_product['name'].strip(),
            url=url,
            category=category,
            brand=brand,
            stock=int(raw_product['stock'].strip()),
            price=float(raw_product['price'].replace('.', '').replace(',', '.').strip()),
            discounted_price=float(discounted_price.replace('.', '').replace(',', '.').strip()),
            product_group_code=raw_product['productGroupCode'].strip(),
            product_code=raw_product['productCode'].strip(),
            code=raw_product['code'].strip(),
            weight=float(weight.replace(',', '.').strip()),
            width=float(width.replace(',', '.').strip()),
            height=float(height.replace(',', '.').strip()),
            depth=float(depth.replace(',', '.').strip()),
            image_urls=image_urls,
        )

        return product
