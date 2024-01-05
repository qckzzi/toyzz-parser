import html
import json
import re
from abc import (
    ABC,
    abstractmethod,
)
from math import (
    ceil,
)
from urllib.parse import (
    parse_qs,
    urlparse,
    urlunparse,
)

import requests
from bs4 import (
    BeautifulSoup,
    NavigableString,
)
from selenium import (
    webdriver,
)
from selenium.webdriver.chrome.options import (
    Options,
)

import config
from toyzz.dtos import (
    ToyzzAttributeDTO,
    ToyzzAttributeValueDTO,
    ToyzzBrandDTO,
    ToyzzCategoryDTO,
    ToyzzProductDTO,
)


class BaseParser(ABC):
    """Базовый класс парсера."""

    @classmethod
    @abstractmethod
    def parse(cls, url: str) -> list[ToyzzProductDTO]:
        """Возвращает данные, полученные по переданному url."""


class CategoryParser(BaseParser):
    """Парсер категорий.

    Позволяет получить товары из целой категории (поиска) в магазине.
    """

    @classmethod
    def parse(cls, url: str) -> list[ToyzzProductDTO]:
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

        pages_count = ceil(product_quantity / 30)

        # FIXME: Захардкоженная двойка
        for page in range(2, pages_count + 1):
            response_text = cls.send_category_request(url, page=page)
            soup = BeautifulSoup(response_text, 'html.parser')
            product_tags = soup.find_all('div', class_='product-box')

            for tag in product_tags:
                a_tag = tag.find('a', class_='image')

                if a_tag and 'product.link_name' not in a_tag['href']:
                    product_urls.append(a_tag['href'])

        marketplace_url = config.toyzz_domain
        product_urls = {clean_query_in_url(f'{marketplace_url}{url}') for url in product_urls}
        products = []

        from core.utils import (
            handle_exception,
        )

        for product_url in product_urls:
            if '{{' in product_url:
                continue

            try:
                products.extend(ProductCardParser.parse(product_url))
            except Exception as e:
                handle_exception(e)
                continue

        return products

    @classmethod
    def send_category_request(cls, url: str, page: int = 1) -> str:
        page_parameter = '/page/'

        if has_query(url):
            url = f'{url}{page_parameter}{page}'
        else:
            url = f'{url}?q={page_parameter}{page}'

        chrome_options = Options()
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--disable-dev-shm-usage')

        with webdriver.Chrome(options=chrome_options) as driver:
            driver.get(url)
            page_source = driver.page_source

        return page_source


class ProductCardParser(BaseParser):
    """Парсер отдельной карточки товара.

    Позволяет получить варианты в одной карточке товара.
    """

    @classmethod
    def parse(cls, url: str) -> list[ToyzzProductDTO]:
        response = requests.get(url)
        response.raise_for_status()

        product_detail_data_re_pattern = r"<script>\s*window\['serials'\]\s*=\s*(?P<json_data>.*?)\s*</script>"
        detail_data_matches = re.search(product_detail_data_re_pattern, response.text)
        detail_data_str = detail_data_matches.group('json_data')

        product_common_data_re_pattern = (
            r'<script>\s*window\.addEventListener\("load", function\(\) '
            r'{\s*var data =({.*?});\s+dataLayer\.push\(data\);\s*}\);\s*</script>'
        )
        common_data_matches = re.search(product_common_data_re_pattern, response.text, re.DOTALL)
        common_data_str = common_data_matches.group(1)
        common_data_str_clean = re.sub(r'//[^\n]*', '', common_data_str)

        product_card_data = json.loads(detail_data_str)
        common_data = json.loads(common_data_str_clean.replace('\'', '"'))

        brand_name = html.unescape(common_data['brand'])
        brand = ToyzzBrandDTO(brand_name)

        soup = BeautifulSoup(response.text, 'html.parser')

        image_tags = soup.find_all('img', class_='rsTmb noDrag')
        image_tags = list(filter(lambda x: 'data-rsvideo' not in x.parent.attrs, image_tags))

        product_specs = soup.find(attrs={'class': 'product-specs'})
        product_specs = list(filter(lambda x: not isinstance(x, NavigableString), product_specs.contents))
        values = []

        for spec in product_specs:
            spec_data = list(filter(lambda x: not isinstance(x, NavigableString), spec.contents))
            name_tag, value_tag = spec_data

            if name_tag.text.lower().strip() in ('yaş aralığı', 'cinsiyet'):
                attribute = ToyzzAttributeDTO(name_tag.text.strip())
                attribute_value = ToyzzAttributeValueDTO(value_tag.text.lstrip(':').strip(), attribute)
                values.append(attribute_value)

        paragraphs = soup.find_all('p')

        weight = '0'
        width = '0'
        height = '0'
        depth = '0'
        synonyms_for_mass = ('ağırlık', 'ağırlığı')

        for p in paragraphs:
            text = p.get_text(strip=True)
            match = re.search(r'[:;]\s*(.*)', text)

            if match:
                value = match.group(1)
                text = text.lower()

                if any(mass_word in text for mass_word in synonyms_for_mass):
                    weight = value.replace(' kg', '')
                elif 'ölçüsü' in text:
                    dimensions = value.replace(' cm', '').strip('.').split(" x ")

                    if len(dimensions) == 3:
                        width, depth, height = dimensions

        annotation_block = soup.find(attrs={'class': 'text fs-16'})
        description_block = annotation_block.find('br')
        description_paragraphs = description_block.find_all('p')
        description_paragraph_strings = [
            p.text if '{{' not in p.text and 'Toyzz' not in p.text else '' for p in description_paragraphs
        ]
        description = ''.join(description_paragraph_strings)
        description = re.sub(r'[\n\t]', '', description)
        description = description.replace(r' ', ' ').strip()

        category_breadcrumb = soup.find('ol', class_='breadcrumb')
        category_tags = list(filter(lambda x: not isinstance(x, NavigableString), category_breadcrumb.contents))
        category_name = html.unescape(category_tags[-2].text)
        category = ToyzzCategoryDTO(category_name)

        cleaned_url = clean_query_in_url(url)

        products = []

        common_title = html.unescape(common_data['name'].strip())

        for product_unit in product_card_data:
            if len(product_card_data) == 1:
                image_urls = [tag.get('src').replace('300x300', 'orj') for tag in image_tags]
                name = common_title
            else:
                image_urls = [
                    tag.get('src').replace('300x300', 'orj') for tag in image_tags
                    if int(tag.get('data-id')) == product_unit['id']
                ]
                name = f'{common_title}, {product_unit["title"]}'

            # FIXME: Это полный Peace, Death!
            product = ToyzzProductDTO(
                id=product_unit['id'],
                name=name,
                url=f'{cleaned_url}?serial={product_unit["id"]}',
                category=category,
                brand=brand,
                stock=product_unit['stock'],
                price=product_unit['market_price'] or product_unit['price'],
                discounted_price=product_unit['price'],
                product_group_code=common_data['productGroupCode'].strip(),
                product_code=product_unit['serial_code'].strip(),
                code=common_data['code'].strip(),
                weight=float(weight.replace(',', '.').strip()),
                width=float(width.replace(',', '.').strip()),
                height=float(height.replace(',', '.').strip()),
                depth=float(depth.replace(',', '.').strip()),
                image_urls=image_urls,
                values=values,
                description=description,
            )

            products.append(product)

        return products


def clean_query_in_url(url: str) -> str:
    """Возвращает url с очищенными параметрами."""

    parsed_url = urlparse(url)
    clean_url = urlunparse((
        parsed_url.scheme,
        parsed_url.netloc,
        parsed_url.path,
        parsed_url.params,
        '',
        parsed_url.fragment,
    ))

    return clean_url


def has_query(url: str) -> bool:
    """Возвращает флаг, есть ли параметры в url."""

    parsed_url = urlparse(url)
    query_params = parse_qs(parsed_url.query)

    return bool(query_params)
