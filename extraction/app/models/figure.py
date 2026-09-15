from pydantic import BaseModel, Field


class ChartSeries(BaseModel):
    name: str = ""
    values: list[float | str] = Field(default_factory=list)


class ChartModel(BaseModel):
    title: str | None = None
    x_axis: str | None = None
    y_axis: str | None = None
    units: str | None = None
    legend: list[str] = Field(default_factory=list)
    series: list[ChartSeries] = Field(default_factory=list)
    data_labels: list[str] = Field(default_factory=list)
    trend: str | None = None
    caption: str | None = None
    visible_values: list[str] = Field(default_factory=list)


class DiagramNode(BaseModel):
    id: str
    label: str = ""
    bbox: list[float] = Field(default_factory=list)


class DiagramEdge(BaseModel):
    source: str
    target: str
    label: str = ""


class DiagramModel(BaseModel):
    nodes: list[DiagramNode] = Field(default_factory=list)
    edges: list[DiagramEdge] = Field(default_factory=list)
    groups: list[str] = Field(default_factory=list)
    caption: str | None = None


class FigureModel(BaseModel):
    id: str
    page: int
    bbox: list[float]
    image_type: str = "image"
    original_asset: str | None = None
    crop_asset: str | None = None
    caption: str | None = None
    description: str | None = None
    ocr_text: str | None = None
    chart: ChartModel | None = None
    diagram: DiagramModel | None = None
