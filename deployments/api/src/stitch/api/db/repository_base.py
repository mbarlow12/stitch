from sqlalchemy import insert
from collections.abc import Callable
from sqlalchemy.ext.asyncio import AsyncSession
from .model.common import Base


class SARepositoryBase[Entity, Key, Row: Base]:
    def __init__(
        self,
        session: AsyncSession,
        model: type[Row],
        to_entity: Callable[[Row], Entity],
        insert_values: Callable[[Entity], dict[str, object]],
    ) -> None:
        self._session = session
        self._model = model
        self._to_entity = to_entity
        self._insert_values = insert_values

    async def get(self, key: Key) -> Entity | None:
        row = await self._session.get(self._model, key)
        return self._to_entity(row) if row is not None else None

    async def add(self, entity: Entity) -> None:
        stmt = insert(self._model).values(**self._insert_values(entity))
        await self._session.execute(stmt)


class SAResources: ...
