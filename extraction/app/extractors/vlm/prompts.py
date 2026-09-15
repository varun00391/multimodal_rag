CHART_PROMPT = """
You are extracting structured data from a chart image.
Return JSON only with this shape:
{
  "title": string or null,
  "x_axis": string or null,
  "y_axis": string or null,
  "units": string or null,
  "legend": [string],
  "series": [{"name": string, "values": [number or string]}],
  "data_labels": [string],
  "visible_values": [string],
  "trend": string or null,
  "caption": string or null
}
Do not invent values that are not visible. If a field is unknown, use null or [].
""".strip()

DIAGRAM_PROMPT = """
You are extracting a diagram/flowchart from an image.
Return JSON only with this shape:
{
  "nodes": [{"id": string, "label": string}],
  "edges": [{"from": string, "to": string, "label": string}],
  "groups": [string],
  "caption": string or null
}
Preserve visible labels. Do not invent nodes that are not shown.
""".strip()

REGION_PROMPT = """
Extract the visible content of this document region.
Return JSON only:
{
  "type": "heading|paragraph|list|table|image|chart|diagram|form|other",
  "text": string,
  "tables": [{"headers": [string], "rows": [[string]]}],
  "notes": string or null
}
Use only what is visible.
""".strip()
