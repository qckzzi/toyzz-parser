import html
import json
import re
from math import (
    ceil,
)
from urllib.parse import (
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


# TODO: SRP
class Parser:
    """Toyzz information parser."""

    product_data_class = ToyzzProductDTO
    category_data_class = ToyzzCategoryDTO
    attribute_data_class = ToyzzAttributeDTO
    attribute_value_data_class = ToyzzAttributeValueDTO
    brand_data_class = ToyzzBrandDTO

    product_detail_data_re_pattern = r"<script>\s*window\['serials'\]\s*=\s*(?P<json_data>.*?)\s*</script>"
    product_common_data_re_pattern = (
        r'<script>\s*window\.addEventListener\("load", function\(\) '
        r'{\s*var data =({.*?});\s+dataLayer\.push\(data\);\s*}\);\s*</script>'
    )
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
    def parse_products_by_card_url(cls, url: str) -> list[product_data_class]:
        response = requests.get(url)
        response.raise_for_status()

        detail_data_matches = re.search(cls.product_detail_data_re_pattern, response.text)
        detail_data_str = detail_data_matches.group('json_data')

        common_data_matches = re.search(cls.product_common_data_re_pattern, response.text, re.DOTALL)
        common_data_str = common_data_matches.group(1)
        common_data_str_clean = re.sub(r'//[^\n]*', '', common_data_str)

        product_card_data = json.loads(detail_data_str)
        common_data = json.loads(common_data_str_clean.replace('\'', '"'))

        brand_name = html.unescape(common_data['brand'])
        brand = cls.brand_data_class(brand_name)

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
                attribute = cls.attribute_data_class(name_tag.text.strip())
                attribute_value = cls.attribute_value_data_class(value_tag.text.lstrip(':').strip(), attribute)
                values.append(attribute_value)

        paragraphs = soup.find_all('p')

        weight = '0'
        width = '0'
        height = '0'
        depth = '0'

        for p in paragraphs:
            text = p.get_text(strip=True)
            match = re.search(r'[:;]\s*(.*)', text)

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
        category_tags = list(filter(lambda x: not isinstance(x, NavigableString), category_breadcrumb.contents))
        category_name = html.unescape(category_tags[-2].text)
        category = cls.category_data_class(category_name)

        parsed_url = urlparse(url)
        clean_url = urlunparse((
            parsed_url.scheme,
            parsed_url.netloc,
            parsed_url.path,
            parsed_url.params,
            '',
            parsed_url.fragment,
        ))

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
                name = f'{common_title}, {product_unit['title']}'

            # FIXME: Это полный Peace, Death!
            product = cls.product_data_class(
                id=product_unit['id'],
                name=name,
                url=f'{clean_url}?serial={product_unit["id"]}',
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
            )

            products.append(product)

        return products
