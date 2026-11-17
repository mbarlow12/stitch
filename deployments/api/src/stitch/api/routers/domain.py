from __future__ import annotations
from stitch.ogsi.model import OGSISrcKey
from functools import partial
from stitch.api.db.model import OilGasFieldSourceValueModel, OilGasFieldSourceModel
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from stitch.api.db.model.common import Base
from stitch.models.types import JsonValue
from abc import ABC
import datetime
from uuid import UUID

from collections.abc import Collection, Callable
from dataclasses import dataclass
from stitch.ogsi.model.og_field import OilGasFieldBase
from typing import Protocol, Any


class SourceProto[T, TKey: str, TMeta: object](Protocol):
    @property
    def key(self) -> TKey: ...

    @property
    def data(self) -> T: ...


class ResourceProto[TEnt, TKey: str, TMeta: object](Protocol):
    @property
    def sources(self) -> Collection[SourceProto[TEnt, TKey, TMeta]]: ...


class Persisted[TId: int | UUID](Protocol):
    @property
    def id(self) -> TId: ...


class StoredSourceProto[T, TId: int | UUID, TKey: str, TMeta: object](
    SourceProto[T, TKey, TMeta], Persisted[TId], Protocol
): ...


class StoredResourceProto[T, TId: int | UUID, TKey: str, TMeta: object](
    ResourceProto[T, TKey, TMeta], Persisted[TId], Protocol
): ...


type ISource[T, TId: int | UUID, TKey: str, TMeta: object] = (
    StoredSourceProto[T, TId, TKey, TMeta] | SourceProto[T, TKey, TMeta]
)

type IResource[T, TId: int | UUID, TKey: str, TMeta: object] = (
    StoredResourceProto[T, TId, TKey, TMeta] | ResourceProto[T, TKey, TMeta]
)


@dataclass
class ResourceV2[T, TKey: str, TSrcMeta: SourceV2Metadata](ABC):
    _id: UUID
    provenance: tuple[int, ...]
    sources: Collection[SourceV2[T, TKey, TSrcMeta]]

    @property
    def id(self):
        return self._id


class SourceV2Metadata(Protocol):
    observed_at: datetime.datetime


@dataclass(frozen=True)
class SourceV2[T, TKey: str, TMeta: SourceV2Metadata](ABC):
    id: int
    data: T
    metadata: TMeta
    key: TKey


class AbstractSourceRepository[T, TId: int | UUID, TKey: str, TMeta: object](Protocol):
    async def get(self, key: TId) -> StoredSourceProto[T, TId, TKey, TMeta] | None: ...

    async def create(self, entity: T) -> StoredSourceProto[T, TId, TKey, TMeta]: ...

    async def query(
        self, limit: int, offset: int, *args, **kwargs
    ) -> Collection[StoredSourceProto[T, TId, TKey, TMeta]]: ...

    async def update(
        self, key: TId, entity: T
    ) -> StoredSourceProto[T, TId, TKey, TMeta]: ...

    async def delete(self, key: TId) -> None: ...


class AbstractResourceRepository[T, TId: int | UUID, TKey: str, TMeta: object](
    Protocol
):
    async def get(
        self, key: TId
    ) -> StoredResourceProto[T, TId, TKey, TMeta] | None: ...

    async def create(self, entity: T) -> StoredResourceProto[T, TId, TKey, TMeta]: ...

    async def query(
        self, limit: int, offset: int, *args, **kwargs
    ) -> Collection[StoredResourceProto[T, TId, TKey, TMeta]]: ...

    async def update(
        self, key: TId, entity: T
    ) -> StoredResourceProto[T, TId, TKey, TMeta]: ...

    async def delete(self, key: TId) -> None: ...


class Repository[TEntity, TId: int | UUID, TKey: str, TMeta: object](Protocol):
    type StoredItem = (
        StoredSourceProto[TEntity, TId, TKey, TMeta]
        | StoredResourceProto[TEntity, TId, TKey, TMeta]
    )

    type FreeItem = (
        SourceProto[TEntity, TKey, TMeta] | ResourceProto[TEntity, TKey, TMeta]
    )

    async def get(self, key: TId) -> StoredItem | None: ...

    async def create(self, entity: FreeItem) -> StoredItem: ...

    async def query(
        self, limit: int, offset: int, *args, **kwargs
    ) -> Collection[StoredItem]:
        """
        - add sort params
        - need an interface to execute custom queries?
        """

    async def update(self, entity: StoredItem) -> StoredItem: ...

    async def delete(self, key: TId) -> None: ...


class PersistenceFacadeProto[T, TId: int | UUID, TKey: str, M: SourceV2Metadata](
    Protocol
):
    @property
    def resources(self) -> AbstractResourceRepository[T, TId, TKey, M]: ...

    @property
    def sources(self) -> AbstractSourceRepository[T, TId, TKey, M]: ...


@dataclass
class OGSourceMeta:
    observed_at: datetime.datetime
    run_id: int
    key: str
    producer: str
    payload: JsonValue


@dataclass(frozen=True)
class OGFieldSource(SourceV2[OilGasFieldBase, OGSISrcKey, OGSourceMeta]): ...


class SARepository[Ent, TId, Row: Base](ABC):
    _session: AsyncSession
    _orm_model: type[Row]

    def __init__(
        self,
        session: AsyncSession,
        model: type[Row],
        data_to_entity: Callable[[Row], Ent],
        entity_to_data: Callable[[Ent], Row],
    ) -> None:
        self._session = session
        self._orm_model = model
        self._to_entity = data_to_entity
        self._insert_values = entity_to_data

    # async def get(self, key: TId) -> Ent | None:
    #     row = await self._session.get(self._orm_model, key)
    #     return self._to_entity(row) if row is not None else None
    #
    # async def create(self, entity: Ent) -> None:
    #     row = self._insert_values(entity).__dict__
    #     stmt = insert(self._orm_model).values(**row)
    #     await self._session.execute(stmt)


class SqlResourceRepository(
    SARepository[OilGasFieldBase, int, OilGasFieldSourceModel],
    AbstractResourceRepository[OilGasFieldBase, int, OGSISrcKey, OGSourceMeta],
):
    type RType = StoredResourceProto[OilGasFieldBase, int, OGSISrcKey, OGSourceMeta]

    async def get(self, key: int) -> RType | None: ...


class SqlSourceRepository(
    SARepository[OilGasFieldBase, int, OilGasFieldSourceModel],
    AbstractSourceRepository[OilGasFieldBase, int, OGSISrcKey, OGSourceMeta],
):
    type SourceType = StoredSourceProto[OilGasFieldBase, int, OGSISrcKey, OGSourceMeta]

    async def get(self, key: int) -> SourceType | None:
        row = await self._session.get(self._orm_model, key)
        if row is None:
            return None
        ent = self._to_entity(row)
        meta = OGSourceMeta(**row.source_record)
        return OGFieldSource(id=key, key=row.source, data=ent, metadata=meta)

    async def create(self, entity: OilGasFieldBase, **kwargs: Any) -> SourceType:
        row = self._insert_values(entity)
        self._session.add(row)
        meta = OGSourceMeta(**row.source_record)
        return OGFieldSource(id=row.id, key=row.source, data=entity, metadata=meta)

    async def query(
        self, limit: int, offset: int, *args, **kwargs
    ) -> Collection[SourceType]:

        stmt = select(self._orm_model).limit(limit).offset(offset)

        ret = []
        res = await self._session.scalars(stmt)
        for result in res:
            ent = self._to_entity(result)
            meta = OGSourceMeta(**result.source_record)
            ret.append(
                OGFieldSource(id=result.id, key=result.source, data=ent, metadata=meta)
            )

        return ret

    async def update(self, key: int, entity: OilGasFieldBase) -> SourceType:
        stored = await self._session.get(self._orm_model, key)
        if stored is not None:
            stored_ent = self._to_entity(stored)
            merged = stored_ent.model_copy(update=entity.model_dump(mode="json"))
            stored = self._insert_values(merged)
        else:
            stored = self._insert_values(entity)
        self._session.add(stored)
        await self._session.flush()
        return OGFieldSource(
            id=stored.id,
            key=stored.source,
            data=self._to_entity(stored),
            metadata=OGSourceMeta(**stored.source_record),
        )

    async def delete(self, key: int) -> None:
        stmt = delete(self._orm_model).where(self._orm_model.id == key)
        await self._session.execute(stmt)
        return None


def source_ent_to_data(e: OGFieldSource) -> OilGasFieldSourceModel:
    dumped = e.data.model_dump()
    vals = [OilGasFieldSourceValueModel.from_attribute(c, v) for c, v in dumped.items()]
    return OilGasFieldSourceModel(source=e.key, values=vals)


def data_to_source_ent(data: OilGasFieldSourceModel) -> OGFieldSource:
    vals = dict(map(lambda x: x.to_attribute(), data.values))
    meta = OGSourceMeta(
        observed_at=datetime.datetime.now(),
        run_id=443,
        key=data.source,
        producer="'murika",
        payload={},
    )
    return OGFieldSource(
        id=data.id, data=OilGasFieldBase(**vals), metadata=meta, key=data.source
    )


def source_repo_factory() -> Callable[[AsyncSession], SqlSourceRepository]:
    return partial(
        SqlSourceRepository,
        model=OilGasFieldSourceModel,
        data_to_entity=data_to_source_ent,
        entity_to_data=source_ent_to_data,
    )


@dataclass
class OGPersistence:
    sources: SqlSourceRepository

    resources: SqlResourceRepository


def get_persistence_layer(
    session: AsyncSession,
) -> PersistenceFacadeProto[OilGasFieldBase, UUID, OGSISrcKey, OGSourceMeta]: ...


def persistence_factory(config: Any): ...
