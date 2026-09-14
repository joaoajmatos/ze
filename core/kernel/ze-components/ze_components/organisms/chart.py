from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class ChartPoint:
    x: str
    y: float
    series: str | None = None


@dataclass
class Chart:
    chart_type: Literal["line", "bar", "area", "pie"]
    data: list[ChartPoint]
    series_labels: dict[str, str] | None = None
    x_label: str | None = None
    y_label: str | None = None
    title: str | None = None
    legend: bool = True
    type: Literal["chart"] = field(default="chart", init=False)


def chart(
    chart_type: Literal["line", "bar", "area", "pie"],
    data: list[ChartPoint],
    *,
    series_labels: dict[str, str] | None = None,
    x_label: str | None = None,
    y_label: str | None = None,
    title: str | None = None,
    legend: bool = True,
) -> Chart:
    return Chart(
        chart_type=chart_type,
        data=data,
        series_labels=series_labels,
        x_label=x_label,
        y_label=y_label,
        title=title,
        legend=legend,
    )
