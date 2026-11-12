"""Mapping and tree operations shared by independent resource tables."""

import pytest
from sqlalchemy import MetaData, inspect, select
from sqlalchemy.exc import IntegrityError

from stitch.api.db.errors import ResourceNotFoundError
from stitch.api.db.model import ResourceBase, ResourceModel, StitchBase, UserModel


@pytest.fixture(scope="module")
def resource_types():
    resource_metadata = MetaData()
    UserModel.__table__.to_metadata(resource_metadata)

    class ExampleResource(ResourceBase):
        metadata = resource_metadata

    class NamedResource(ResourceBase):
        metadata = resource_metadata
        __tablename__ = "custom_resources"

    return ExampleResource, NamedResource


def test_base_is_unmapped():
    assert inspect(ResourceBase, raiseerr=False) is None
    assert "__table__" not in ResourceBase.__dict__
    assert "resourcebase" not in StitchBase.metadata.tables


def test_subclasses_have_independent_self_references(resource_types):
    example, named = resource_types
    assert example.__tablename__ == "exampleresource"
    assert named.__tablename__ == "custom_resources"
    for model in (example, named, ResourceModel):
        table = model.__table__
        (fk,) = table.c.repointed_id.foreign_keys
        assert fk.column is table.c.id
        assert table.c.repointed_id.nullable
        assert inspect(model).inherits is None
    assert example.__table__.c.id is not named.__table__.c.id
    assert example.__table__.c.repointed_id is not named.__table__.c.repointed_id
    (example_index,) = example.__table__.indexes
    (named_index,) = named.__table__.indexes
    assert example_index is not named_index
    assert example_index.table is example.__table__
    assert named_index.table is named.__table__
    assert example_index.name != named_index.name
    assert "memberships" not in inspect(example).relationships


def test_existing_resource_mapping_is_preserved():
    table = ResourceModel.__table__
    assert table.name == "og_field_resources"
    assert {index.name for index in table.indexes} == {"rp_repointed_id_idx"}
    assert inspect(ResourceModel).relationships.memberships.mapper.class_.__name__ == (
        "MembershipModel"
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "resource_type", [0, 1, None], ids=["default", "named", "existing"]
)
async def test_resource_tree_operations(
    resource_types, resource_type, seeded_integration_session, test_user
):
    session = seeded_integration_session
    if resource_type is None:
        model = ResourceModel
    else:
        model = resource_types[resource_type]
        connection = await session.connection()
        await connection.run_sync(model.metadata.create_all)

    root = model.create(created_by=test_user)
    session.add(root)
    await session.flush()
    middle = model.create(created_by=test_user, repointed_to=root.id)
    session.add(middle)
    await session.flush()
    leaf = model.create(created_by=test_user, repointed_to=middle.id)
    unrelated = model.create(created_by=test_user)
    session.add_all([leaf, unrelated])
    await session.flush()

    assert root.created_by_id == test_user.id
    assert root.last_updated_by_id == test_user.id
    assert await leaf.get_root(session) is root
    assert await root.get_root(session) is root
    assert {r.id for r in await root.get_constituents(session)} == {
        root.id,
        middle.id,
        leaf.id,
    }
    assert {r.id for r in await middle.get_constituents(session)} == {
        middle.id,
        leaf.id,
    }
    tree = model._complete_tree_cte(middle.id)
    assert set((await session.scalars(select(tree.c.id))).all()) == {
        root.id,
        middle.id,
        leaf.id,
    }
    with pytest.raises(ResourceNotFoundError):
        await model(id=-1).get_root(session)

    # The database must enforce the subclass's own self-reference.
    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            session.add(model.create(created_by=test_user, repointed_to=-1))
            await session.flush()
