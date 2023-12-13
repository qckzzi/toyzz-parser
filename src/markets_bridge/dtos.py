from dataclasses import (
    dataclass,
)


@dataclass
class MBCategoryDTO:
    external_id: int
    name: str
    marketplace_id: int


@dataclass
class MBBrandDTO:
    external_id: int
    name: str
    marketplace_id: int


@dataclass
class MBImageDTO:
    image_url: str
    product_id: int


@dataclass
class MBProductDTO:
    external_id: int
    name: str
    url: str
    price: float
    discounted_price: float
    stock_quantity: int
    weight: float
    width: float
    height: float
    depth: float
    product_code: str
    category_name: str
    brand_name: str
    marketplace_id: int
