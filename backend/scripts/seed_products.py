import argparse
import asyncio
import json
import sys
from pathlib import Path

from pydantic import BaseModel, TypeAdapter
from sqlalchemy import select


class ProductSeed(BaseModel):
    name: str
    price_minor: int
    stock_quantity: int
    is_active: bool


async def seed_products(catalog_path: Path) -> None:
    from app.db.session import SessionFactory
    from app.models import Product

    product_seeds = TypeAdapter(list[ProductSeed]).validate_python(
        json.loads(catalog_path.read_text())
    )
    names = [product.name for product in product_seeds]
    if len(names) != len(set(names)):
        raise ValueError("The catalog contains duplicate product names")

    async with SessionFactory.begin() as session:
        existing_names = set(
            await session.scalars(select(Product.name).where(Product.name.in_(names)))
        )
        if existing_names:
            raise ValueError(
                "Products already exist: " + ", ".join(sorted(existing_names))
            )
        session.add_all(Product(**product.model_dump()) for product in product_seeds)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("catalog_path", type=Path)
    arguments = parser.parse_args()
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    asyncio.run(seed_products(arguments.catalog_path))


if __name__ == "__main__":
    main()
