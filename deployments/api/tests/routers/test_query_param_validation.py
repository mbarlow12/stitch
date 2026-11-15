import pytest
from httpx import AsyncClient

from stitch.api.entities import OGFieldQueryParams, OGSI_SOURCE_DEFAULT


class TestOGFieldQueryParams:
    def test_source_defaults_to_all_ogsi_sources(self):
        params = OGFieldQueryParams()

        assert params.source == list(OGSI_SOURCE_DEFAULT)

    def test_explicit_source_list_is_preserved(self):
        params = OGFieldQueryParams(source=["gem", "wm"])

        assert params.source == ["gem", "wm"]


class TestResourceRouterParamValidation:
    @pytest.mark.anyio
    async def test_invalid_field_status_returns_422(self, async_client: AsyncClient):
        resp = await async_client.get(
            "/oil-gas-fields/", params={"field_status": "BadValue"}
        )
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_invalid_sort_by_returns_422(self, async_client: AsyncClient):
        resp = await async_client.get("/oil-gas-fields/", params={"sort_by": "owners"})
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_invalid_sort_order_returns_422(self, async_client: AsyncClient):
        resp = await async_client.get(
            "/oil-gas-fields/", params={"sort_order": "sideways"}
        )
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_invalid_location_type_returns_422(self, async_client: AsyncClient):
        resp = await async_client.get(
            "/oil-gas-fields/", params={"location_type": "Underground"}
        )
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_sort_by_source_returns_422(self, integration_client: AsyncClient):
        resp = await integration_client.get(
            "/oil-gas-fields/", params={"sort_by": "source"}
        )
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_unknown_field_in_sources_path_returns_422(
        self, async_client: AsyncClient
    ):
        resp = await async_client.get("/oil-gas-fields/1/fields/not_a_field/sources")
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_unknown_field_in_priority_path_returns_422(
        self, async_client: AsyncClient
    ):
        resp = await async_client.put(
            "/oil-gas-fields/1/fields/not_a_field/sources/priority",
            json={"ordered_source_pks": [1, 2]},
        )
        assert resp.status_code == 422


class TestSourceRouterParamValidation:
    @pytest.mark.anyio
    async def test_invalid_field_status_returns_422(self, async_client: AsyncClient):
        resp = await async_client.get(
            "/oil-gas-field-sources/", params={"field_status": "BadValue"}
        )
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_invalid_sort_by_returns_422(self, async_client: AsyncClient):
        resp = await async_client.get(
            "/oil-gas-field-sources/", params={"sort_by": "owners"}
        )
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_invalid_sort_order_returns_422(self, async_client: AsyncClient):
        resp = await async_client.get(
            "/oil-gas-field-sources/", params={"sort_order": "sideways"}
        )
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_invalid_source_returns_422(self, async_client: AsyncClient):
        resp = await async_client.get(
            "/oil-gas-field-sources/", params={"source": "not_a_source"}
        )
        assert resp.status_code == 422
