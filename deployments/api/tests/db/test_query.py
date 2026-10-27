from stitch.api.entities import PaginationParams


class TestPaginationParams:
    def test_first_page_defaults(self):
        params = PaginationParams()
        assert params.offset == 0
        assert params.limit == 50

    def test_page_to_offset(self):
        params = PaginationParams(page=2, page_size=10)
        assert params.offset == 10
        assert params.limit == 10
