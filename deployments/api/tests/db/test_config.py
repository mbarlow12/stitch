from unittest.mock import MagicMock

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from stitch.api.db.config import UnitOfWork


class TestUnitOfWork:
    def test_session_raises_before_enter(self):
        factory = MagicMock(spec=async_sessionmaker)
        uow = UnitOfWork(factory)

        with pytest.raises(RuntimeError, match="UnitOfWork not started"):
            _ = uow.session

    @pytest.mark.anyio
    async def test_session_available_after_enter(
        self, mock_session_factory, mock_session
    ):
        uow = UnitOfWork(mock_session_factory)

        async with uow:
            assert uow.session is mock_session

    @pytest.mark.anyio
    async def test_closes_session_on_exit(self, mock_session_factory, mock_session):
        uow = UnitOfWork(mock_session_factory)

        async with uow:
            pass

        mock_session.close.assert_awaited_once()

    @pytest.mark.anyio
    async def test_session_none_after_exit(self, mock_session_factory):
        uow = UnitOfWork(mock_session_factory)

        async with uow:
            pass

        with pytest.raises(RuntimeError, match="UnitOfWork not started"):
            _ = uow.session

    @pytest.mark.anyio
    async def test_rollback_on_exception(self, mock_session_factory, mock_session):
        uow = UnitOfWork(mock_session_factory)

        with pytest.raises(ValueError, match="test error"):
            async with uow:
                raise ValueError("test error")

        mock_session.rollback.assert_awaited_once()

    @pytest.mark.anyio
    async def test_no_rollback_on_success(self, mock_session_factory, mock_session):
        uow = UnitOfWork(mock_session_factory)

        async with uow:
            pass

        mock_session.rollback.assert_not_awaited()

    @pytest.mark.anyio
    async def test_auto_commits_on_success(self, mock_session_factory, mock_session):
        uow = UnitOfWork(mock_session_factory)

        async with uow:
            pass

        mock_session.commit.assert_awaited_once()

    @pytest.mark.anyio
    async def test_no_commit_on_exception(self, mock_session_factory, mock_session):
        uow = UnitOfWork(mock_session_factory)

        with pytest.raises(ValueError):
            async with uow:
                raise ValueError("test error")

        mock_session.commit.assert_not_awaited()

    @pytest.mark.anyio
    async def test_commit_method(self, mock_session_factory, mock_session):
        uow = UnitOfWork(mock_session_factory)

        async with uow:
            await uow.commit()

        assert mock_session.commit.await_count == 2

    @pytest.mark.anyio
    async def test_rollback_method(self, mock_session_factory, mock_session):
        uow = UnitOfWork(mock_session_factory)

        async with uow:
            await uow.rollback()

        mock_session.rollback.assert_awaited_once()
