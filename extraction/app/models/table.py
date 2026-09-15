from pydantic import BaseModel, Field


class TableCell(BaseModel):
    row: int
    col: int
    text: str = ""
    bbox: list[float] = Field(default_factory=list)
    row_span: int = 1
    col_span: int = 1
    is_header: bool = False


class TableModel(BaseModel):
    id: str
    page: int
    bbox: list[float]
    caption: str | None = None
    headers: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)
    cells: list[TableCell] = Field(default_factory=list)
    row_count: int = 0
    col_count: int = 0
    footnotes: list[str] = Field(default_factory=list)
    units: dict[str, str] = Field(default_factory=dict)
    is_complex: bool = False
