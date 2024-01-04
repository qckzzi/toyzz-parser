from dataclasses import (
    dataclass,
    field,
)


@dataclass
class ToyzzCategoryDTO:
    name: str
    id: int = 0


@dataclass
class ToyzzAttributeDTO:
    name: str
    id: int = 0


@dataclass
class ToyzzAttributeValueDTO:
    value: str
    attribute: ToyzzAttributeDTO
    id: int = 0


@dataclass
class ToyzzBrandDTO:
    name: str
    id: int = 0


@dataclass
class ToyzzProductDTO:
    id: int
    name: str
    product_group_code: int
    url: str
    code: str
    product_code: str
    category: ToyzzCategoryDTO
    brand: ToyzzBrandDTO
    stock: int
    price: float
    discounted_price: float
    weight: float
    width: float
    height: float
    depth: float
    description: str = None
    image_urls: list[str] = field(default_factory=list)
    values: list[ToyzzAttributeValueDTO] = field(default_factory=list)
