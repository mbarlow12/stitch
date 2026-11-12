from __future__ import annotations

from sqlalchemy import ForeignKey, Index, literal, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, declared_attr, mapped_column

from stitch.api.db.errors import ResourceNotFoundError
from stitch.api.entities import User as UserEntity

from .common import Base
from .mixins import TimestampMixin, UserAuditMixin
from .types import PORTABLE_BIGINT


class ResourceBase(TimestampMixin, UserAuditMixin, Base):
    """Unmapped resource columns and repoint-tree operations.

    Subclasses map independent tables. Override ``__tablename__`` to use an
    existing table name; the repoint foreign key follows that name.
    """

    __abstract__ = True

    @declared_attr.directive
    def __tablename__(cls) -> str:
        return cls.__name__.lower()

    @declared_attr.directive
    def __table_args__(cls) -> tuple[Index]:
        return (Index(f"{cls.__tablename__}_repointed_id_idx", "repointed_id"),)

    id: Mapped[int] = mapped_column(
        PORTABLE_BIGINT, primary_key=True, autoincrement=True
    )

    @declared_attr
    def repointed_id(cls) -> Mapped[int | None]:
        return mapped_column(
            PORTABLE_BIGINT, ForeignKey(f"{cls.__tablename__}.id"), nullable=True
        )

    async def get_root(self, session: AsyncSession):
        root = await session.scalar(self.__class__._root_select(self.id))
        if root is None:
            raise ResourceNotFoundError(
                f"No root {type(self).__name__} found for `{repr(self)}`"
            )
        return root

    async def get_constituents(self, session: AsyncSession):
        return await self.__class__.get_constituents_by_root_id(session, self.id)

    @classmethod
    def create(
        cls,
        created_by: UserEntity,
        repointed_to: int | None = None,
    ):
        return cls(
            repointed_id=repointed_to,
            created_by_id=created_by.id,
            last_updated_by_id=created_by.id,
        )

    @classmethod
    async def get_constituents_by_root_id(
        cls, session: AsyncSession, root_resource_id: int
    ):
        sub_cte = cls._subtree_cte(resource_id=root_resource_id)
        stmt = select(cls).join(sub_cte, cls.id == sub_cte.c.id)
        return (await session.scalars(stmt)).all()

    @classmethod
    def _parent_tree_cte(cls, *resource_ids: int):
        parent_tree = (
            select(cls.id)
            .where(cls.id.in_(resource_ids))
            .distinct()
            .cte(name="parent_tree", recursive=True)
        )

        ancestors = (
            select(cls.repointed_id)
            .join(parent_tree, cls.id == parent_tree.c.id)
            .where(cls.repointed_id.is_not(None))
        )
        return parent_tree.union_all(ancestors)

    @classmethod
    def _subtree_cte(cls, resource_id: int):
        subtree = (
            select(cls.id)
            .where(cls.id == resource_id)
            .cte(name="subtree", recursive=True)
        )

        children = select(cls.id).join(subtree, cls.repointed_id == subtree.c.id)
        return subtree.union_all(children)

    @classmethod
    def _complete_tree_cte(cls, resource_id: int):
        resolved = select(literal(resource_id).label("id")).cte(
            name="resolved", recursive=True
        )
        children = select(cls.id).join(resolved, cls.repointed_id == resolved.c.id)
        parents = (
            select(cls.repointed_id)
            .join(resolved, cls.id == resolved.c.id)
            .where(cls.repointed_id.is_not(None))
        )

        return resolved.union(children, parents)

    @classmethod
    def _root_select(cls, *resource_ids: int):
        parent_cte = cls._parent_tree_cte(*resource_ids)
        return (
            select(cls)
            .join(parent_cte, cls.id == parent_cte.c.id)
            .where(cls.repointed_id.is_(None))
        )
