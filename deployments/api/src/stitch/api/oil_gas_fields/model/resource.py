from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import (
    ForeignKey,
    Index,
    literal,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column, relationship
from stitch.api.db.errors import ResourceNotFoundError
from stitch.ogsi.model import OGFieldSource, OGFieldResource

from .membership import OilGasFieldMembershipModel, MembershipStatus
from .source import OilGasFieldSourceModel

from stitch.api.entities import User as UserEntity
from stitch.api.db.model.common import Base
from stitch.api.db.model.mixins import TimestampMixin, UserAuditMixin
from stitch.api.db.model.types import PORTABLE_BIGINT


class OilGasFieldResourceModel(TimestampMixin, UserAuditMixin, Base):
    __tablename__ = "oil_gas_field_resources"
    __table_args__ = (Index("ogf_res_rp_repointed_id_idx", "repointed_id"),)

    id: Mapped[int] = mapped_column(
        PORTABLE_BIGINT, primary_key=True, autoincrement=True
    )
    repointed_id: Mapped[int | None] = mapped_column(
        PORTABLE_BIGINT, ForeignKey("oil_gas_field_resources.id"), nullable=True
    )

    # SQLAlchemy will automatically see the foreign key `memberships.resource_id`
    # and configure the appropriate SQL statement to load the membership objects
    memberships: Mapped[list[OilGasFieldMembershipModel]] = relationship()

    def as_empty_entity(self):
        return OGFieldResource(
            id=self.id,
            source_data=[],
            constituents=frozenset(),
        )

    async def get_source_data(self, session: AsyncSession) -> Sequence[OGFieldSource]:
        stmt = (
            select(OilGasFieldMembershipModel.source_pk)
            .where(OilGasFieldMembershipModel.resource_id == self.id)
            .where(OilGasFieldMembershipModel.status == MembershipStatus.ACTIVE)
        )
        source_pks = (await session.scalars(stmt)).all()

        if not source_pks:
            return []

        stmt = select(OilGasFieldSourceModel).where(
            OilGasFieldSourceModel.id.in_(source_pks)
        )
        sources = (await session.scalars(stmt)).all()
        return [ofgsm.as_entity() for ofgsm in sources]

    async def get_root(self, session: AsyncSession):
        root = await session.scalar(self.__class__._root_select(self.id))
        if root is None:
            raise ResourceNotFoundError(
                f"No root ResourceModel found for `{repr(self)}`"
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
