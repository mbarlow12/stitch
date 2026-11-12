from fastapi import APIRouter

router = APIRouter(tags=["oil-gas-fields"])


@router.post("/")
def create_resource(): ...


@router.get("/")
def query_resources():
    return []


@router.get("/{id}")
def get_resource_by_id(id: int): ...


@router.get("/{id}/suggest")
def get_attribute_suggestions(id: int): ...


@router.put("/{id}")
def replace_resource(id: int): ...


@router.patch("/{id}")
def update_resource(id: int): ...
