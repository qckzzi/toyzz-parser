from core.utils import (
    category_processing,
    product_card_processing,
)


class EntityType:
    PRODUCT = 'PRODUCT'
    CATEGORY = 'CATEGORY'

    PROCESSING_MAP = {
        PRODUCT: product_card_processing,
        CATEGORY: category_processing
    }

    @classmethod
    def get_processing_function_for_entity_type(cls, entity_type: str):
        if entity_type not in cls.PROCESSING_MAP:
            raise ValueError(f'Entity type {entity_type} does not exist.')

        return cls.PROCESSING_MAP.get(entity_type)
