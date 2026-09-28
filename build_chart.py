#!/usr/bin/env python3
"""Build an offline party-person temporal network with Plotly."""

from __future__ import annotations

import argparse
from html import escape
import json
from pathlib import Path
import re
import textwrap

import pandas as pd
import plotly.graph_objects as go


REQUIRED_FILES = (
    "organizations.csv",
    "people.csv",
    "tenures.csv",
    "events.csv",
    "organization_relations.csv",
)
PROJECT_ROOT = Path(__file__).resolve().parent


def project_path(value: Path) -> Path:
    path = (PROJECT_ROOT / value).resolve() if not value.is_absolute() else value.resolve()
    if not path.is_relative_to(PROJECT_ROOT):
        raise ValueError(f"路径必须位于项目目录内：{path}")
    return path


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")


def parse_date_column(frame: pd.DataFrame, column: str) -> None:
    frame[column] = pd.to_datetime(frame[column], errors="raise")


def load_data(data_dir: Path) -> dict[str, pd.DataFrame]:
    missing = [name for name in REQUIRED_FILES if not (data_dir / name).is_file()]
    if missing:
        raise FileNotFoundError(f"缺少数据文件：{', '.join(missing)}")

    file_names = list(REQUIRED_FILES)
    for optional_name in (
        "sources.csv",
        "background_events.csv",
        "organization_stages.csv",
        "organization_lanes.csv",
    ):
        if (data_dir / optional_name).is_file():
            file_names.append(optional_name)
    frames = {name.removesuffix(".csv"): read_csv(data_dir / name) for name in file_names}
    parse_date_column(frames["tenures"], "start_date")
    parse_date_column(frames["tenures"], "end_date")
    parse_date_column(frames["events"], "event_date")
    parse_date_column(frames["organization_relations"], "event_date")
    if "background_events" in frames:
        parse_date_column(frames["background_events"], "event_date")
        if "end_date" in frames["background_events"].columns:
            frames["background_events"]["end_date"] = pd.to_datetime(
                frames["background_events"]["end_date"], errors="coerce"
            )
    if "organization_stages" in frames:
        parse_date_column(frames["organization_stages"], "start_date")
        parse_date_column(frames["organization_stages"], "end_date")
    return frames


def validate_references(frames: dict[str, pd.DataFrame]) -> None:
    people = set(frames["people"]["person_id"])
    organizations = set(frames["organizations"]["org_id"])

    if "organization_lanes" in frames:
        if "lane_id" not in frames["organizations"].columns:
            raise ValueError(
                "存在 organization_lanes.csv 时，organizations.csv 必须包含 lane_id"
            )
        if frames["organization_lanes"]["lane_id"].duplicated().any():
            raise ValueError("organization_lanes.csv 含重复 lane_id")
        lane_table = frames["organization_lanes"]
        if "lane_type" not in lane_table.columns:
            lane_table["lane_type"] = "main"
        unknown_lane_types = sorted(set(lane_table["lane_type"]) - {"main", "branch"})
        if unknown_lane_types:
            raise ValueError("organization_lanes.csv 含未知 lane_type：" + str(unknown_lane_types))
        main_lanes = lane_table[lane_table["lane_type"] != "branch"]
        if main_lanes["display_order"].duplicated().any():
            raise ValueError("organization_lanes.csv 的主列含重复 display_order")
        lanes = set(lane_table["lane_id"])
        unknown_lanes = sorted(set(frames["organizations"]["lane_id"]) - lanes)
        if unknown_lanes:
            raise ValueError(
                "organizations.csv 含未知 lane_id：" + str(unknown_lanes)
            )
        if "parent_lane_id" not in lane_table.columns:
            lane_table["parent_lane_id"] = ""
        if "branch_offset" not in lane_table.columns:
            lane_table["branch_offset"] = ""
        branch_rows = lane_table[lane_table["lane_type"] == "branch"]
        if branch_rows["branch_offset"].eq("").any():
            raise ValueError("组织支线必须填写 branch_offset")
        missing_parents = sorted(set(branch_rows["parent_lane_id"]) - lanes)
        if missing_parents:
            raise ValueError("组织支线含未知 parent_lane_id：" + str(missing_parents))
        parent_types = dict(zip(lane_table["lane_id"], lane_table["lane_type"]))
        if any(parent_types.get(parent) == "branch" for parent in branch_rows["parent_lane_id"]):
            raise ValueError("组织支线的 parent_lane_id 必须指向主列")

    for table_name in ("tenures", "events"):
        table = frames[table_name]
        unknown_people = sorted(set(table["person_id"]) - people)
        unknown_orgs = sorted(set(table["org_id"]) - organizations)
        if unknown_people:
            raise ValueError(f"{table_name}.csv 含未知 person_id：{unknown_people}")
        if unknown_orgs:
            raise ValueError(f"{table_name}.csv 含未知 org_id：{unknown_orgs}")

    relations = frames["organization_relations"]
    relation_orgs = set(relations["source_org_id"]) | set(relations["target_org_id"])
    unknown_relation_orgs = sorted(relation_orgs - organizations)
    if unknown_relation_orgs:
        raise ValueError(
            "organization_relations.csv 含未知组织：" + str(unknown_relation_orgs)
        )
    if "related_person_ids" in relations.columns:
        related_people = {
            person_id.strip()
            for values in relations["related_person_ids"]
            for person_id in str(values).split(";")
            if person_id.strip()
        }
        unknown_related_people = sorted(related_people - people)
        if unknown_related_people:
            raise ValueError(
                "organization_relations.csv 含未知 related_person_ids："
                + str(unknown_related_people)
            )

    if "background_events" in frames:
        unknown_background_orgs = sorted(
            set(frames["background_events"]["org_id"]) - organizations
        )
        if unknown_background_orgs:
            raise ValueError(
                "background_events.csv 含未知组织：" + str(unknown_background_orgs)
            )

    if "organization_stages" in frames:
        unknown_stage_orgs = sorted(
            set(frames["organization_stages"]["org_id"]) - organizations
        )
        if unknown_stage_orgs:
            raise ValueError(
                "organization_stages.csv 含未知组织：" + str(unknown_stage_orgs)
            )
        stages = frames["organization_stages"]
        if "related_person_ids" in stages.columns:
            related_people = {
                person_id.strip()
                for values in stages["related_person_ids"]
                for person_id in str(values).split(";")
                if person_id.strip()
            }
            unknown_related_people = sorted(related_people - people)
            if unknown_related_people:
                raise ValueError(
                    "organization_stages.csv 含未知 related_person_ids："
                    + str(unknown_related_people)
                )


def wrap_hover(value: object, width: int = 38) -> str:
    """Escape and wrap long text so Chinese source excerpts remain readable."""
    text = str(value).strip()
    if not text:
        return ""
    lines: list[str] = []
    for paragraph in text.splitlines():
        lines.extend(
            textwrap.wrap(
                paragraph,
                width=width,
                break_long_words=True,
                break_on_hyphens=False,
                replace_whitespace=False,
            )
            or [""]
        )
    return "<br>".join(escape(line) for line in lines)


def build_event_hover(
    row: pd.Series,
    person_name: str = "",
) -> str:
    heading = f"<b>{escape(person_name)}</b><br>" if person_name else ""
    event_type = row["event_type"]
    if event_type == "public_office":
        category = "党外任职" if row["person_id"] == "raimajhi" else "政府任职"
    elif event_type == "government_action":
        category = "政府事件"
    elif event_type in {"formation", "split", "merge", "dissolution", "organization_action"}:
        category = "组织事件"
    elif event_type in {"context", "retirement"} and row["person_id"] == "raimajhi":
        category = "党外任职相关事件"
    elif event_type == "death":
        category = "生平事件"
    elif event_type in {"activity", "imprisonment", "background"}:
        category = "政治活动"
    else:
        category = "党内事件"
    heading += f"<b>{category}</b><br>"
    if "source_excerpt" in row.index and str(row["source_excerpt"]).strip():
        return heading + wrap_hover(row["source_excerpt"]) + "<extra></extra>"
    return heading + wrap_hover(row["description"]) + "<extra></extra>"


def build_background_hover(row: pd.Series) -> str:
    """Keep governmental authority and India relations distinct in context."""
    parts = [f"<b>{escape(str(row['title']))}</b>"]
    for column, label in (
        ("governing_authority", "当权者"),
        ("india_relations", "对印关系"),
    ):
        if column in row.index and str(row[column]).strip():
            parts.append(f"<b>{label}：</b>{wrap_hover(row[column])}")
    detail = (
        row["source_excerpt"]
        if "source_excerpt" in row.index and str(row["source_excerpt"]).strip()
        else row["description"]
    )
    if str(detail).strip():
        parts.append(wrap_hover(detail))
    return "<br>".join(parts) + "<extra></extra>"


def format_tenure_date(value: pd.Timestamp, precision: str) -> str:
    """Keep plotting placeholders from masquerading as attested calendar days."""
    if precision in {"year", "uncertain"}:
        return f"{value.year}年"
    if precision == "month":
        return f"{value.year}年{value.month}月"
    if precision == "mixed" and value.day == 1:
        if value.month == 1:
            return f"{value.year}年（制图定位）"
        return f"{value.year}年{value.month}月"
    return f"{value.year}年{value.month}月{value.day}日"


def spread_event_nodes(
    events: pd.DataFrame,
    base_x: list[float],
    x_pixels_per_unit: float,
    y_pixels_per_day: float,
) -> tuple[list[float], list[str]]:
    """Separate nearby event markers horizontally while keeping their dates."""
    count = len(events)
    if count < 2:
        return base_x, ["middle right"] * count

    radius_px = 15.0
    x_radius = radius_px / max(x_pixels_per_unit, 1.0)
    y_radius_days = radius_px / max(y_pixels_per_day, 0.01)
    dates = [value.toordinal() for value in events["event_date"]]
    adjusted_x: list[float] = []
    text_positions = [
        str(events.iloc[index].get("label_position", "") or "middle right")
        for index in range(count)
    ]
    spacing = x_radius * 1.1
    for index in range(count):
        candidates = [0.0]
        for step in range(1, count + 1):
            candidates.extend((step * spacing, -step * spacing))
        for candidate in candidates:
            proposed_x = base_x[index] + candidate
            overlaps = any(
                abs(proposed_x - adjusted_x[previous]) * x_pixels_per_unit < radius_px
                and abs(dates[index] - dates[previous]) * y_pixels_per_day < radius_px
                for previous in range(index)
            )
            if not overlaps:
                adjusted_x.append(proposed_x)
                if candidate:
                    text_positions[index] = "top center" if candidate > 0 else "bottom center"
                break
    return adjusted_x, text_positions


def build_figure(frames: dict[str, pd.DataFrame], title: str) -> go.Figure:
    organizations = frames["organizations"].copy()
    people = frames["people"].copy()
    tenures = frames["tenures"].copy()
    events = frames["events"].copy()
    events = events.sort_values(["event_date", "person_id"])
    relations = frames["organization_relations"].copy()
    backgrounds = frames.get("background_events", pd.DataFrame()).copy()
    stages = frames.get("organization_stages", pd.DataFrame()).copy()
    lanes = frames.get("organization_lanes", pd.DataFrame()).copy()

    organizations["display_order"] = organizations["display_order"].astype(int)
    organizations = organizations.sort_values("display_order")
    if lanes.empty:
        display_lanes = organizations[
            ["org_id", "short_name", "color", "display_order", "branch_note"]
        ].rename(columns={"org_id": "lane_id"})
        organizations["lane_id"] = organizations["org_id"]
        display_lanes["lane_type"] = "main"
        display_lanes["parent_lane_id"] = ""
        display_lanes["branch_offset"] = ""
    else:
        lanes["display_order"] = lanes["display_order"].astype(int)
        if "lane_type" not in lanes.columns:
            lanes["lane_type"] = "main"
        if "parent_lane_id" not in lanes.columns:
            lanes["parent_lane_id"] = ""
        if "branch_offset" not in lanes.columns:
            lanes["branch_offset"] = ""
        display_lanes = lanes[lanes["lane_type"] != "branch"].sort_values("display_order")
    # Branch rows may reuse their parent's source display_order. Repack only
    # the rendered main columns so removing a full column does not leave an
    # empty gap in the axis.
    display_lanes = display_lanes.copy()
    display_lanes["display_order"] = range(len(display_lanes))
    if "track" not in tenures.columns:
        tenures["track"] = "organization"
    x_for_lane = dict(zip(display_lanes["lane_id"], display_lanes["display_order"]))
    if not lanes.empty:
        for branch in lanes[lanes["lane_type"] == "branch"].itertuples(index=False):
            parent_x = x_for_lane.get(branch.parent_lane_id)
            if parent_x is None:
                raise ValueError(f"组织支线 {branch.lane_id} 的主列不存在：{branch.parent_lane_id}")
            x_for_lane[branch.lane_id] = parent_x + float(branch.branch_offset)
    lane_for_org = dict(zip(organizations["org_id"], organizations["lane_id"]))
    parent_lane_for_lane = (
        dict(zip(lanes["lane_id"], lanes["parent_lane_id"])) if not lanes.empty else {}
    )
    x_for_org = {
        org_id: x_for_lane[lane_id] for org_id, lane_id in lane_for_org.items()
    }
    lane_type_by_id = dict(zip(display_lanes["lane_id"], display_lanes["lane_type"]))
    if not lanes.empty:
        lane_type_by_id.update(zip(lanes["lane_id"], lanes["lane_type"]))
    lane_type_for_org = {
        org_id: lane_type_by_id[lane_id] for org_id, lane_id in lane_for_org.items()
    }
    chart_height = max(1500, min(2400, 850 + len(events) * 13))
    chart_width = max(1450, len(display_lanes) * 125 + 330)
    x_range_width = (
        display_lanes["display_order"].max()
        - display_lanes["display_order"].min()
        + 1.2
    )
    x_pixels_per_unit = (chart_width - 430) / max(x_range_width, 1)
    all_dates = list(tenures["start_date"]) + list(tenures["end_date"])
    all_dates += list(events["event_date"])
    if not backgrounds.empty:
        all_dates += list(backgrounds["event_date"])
        if "end_date" in backgrounds.columns:
            all_dates += list(backgrounds["end_date"].dropna())
    if not stages.empty:
        all_dates += list(stages["start_date"]) + list(stages["end_date"])
    y_span_days = max((max(all_dates) - min(all_dates)).days, 1)
    y_pixels_per_day = (chart_height - 275) / y_span_days
    color_for_org = dict(zip(organizations["org_id"], organizations["color"]))
    name_for_org = dict(zip(organizations["org_id"], organizations["name_zh"]))
    branch_note_for_org = dict(
        zip(
            organizations["org_id"],
            organizations.get("branch_note", pd.Series("", index=organizations.index)),
        )
    )
    name_for_person = dict(zip(people["person_id"], people["name_zh"]))
    full_name_for_person = {
        row.person_id: (
            f"{row.name_en}（{row.name_zh_full}）"
            if getattr(row, "name_zh_full", "")
            else f"{row.name_en}（{row.name_zh}）"
        )
        for row in people.itertuples(index=False)
    }
    if "display_order" in people.columns:
        people["display_order"] = pd.to_numeric(people["display_order"], errors="coerce")
        people = people.sort_values(["display_order", "person_id"], na_position="last")
    person_ids = people["person_id"].tolist()
    person_color_for = (
        dict(zip(people["person_id"], people["color"]))
        if "color" in people.columns
        else {}
    )
    person_symbol_for = (
        dict(zip(people["person_id"], people["marker_symbol"]))
        if "marker_symbol" in people.columns
        else {}
    )

    def local_offset(record: object) -> float:
        value = getattr(record, "x_offset", "")
        return float(value) if str(value).strip() else 0.0

    def person_x(record: object) -> float:
        # People share the organization axis; role offsets (for example party
        # versus government office) remain small and independent of headcount.
        return x_for_org[getattr(record, "org_id")] + local_offset(record)

    fig = go.Figure()

    # Party lanes make the organizational columns visually stable.
    lane_hit_x: list[float | None] = []
    lane_hit_y: list[pd.Timestamp | None] = []
    lane_hit_ids: list[str | None] = []
    for lane in display_lanes.itertuples(index=False):
        fig.add_vrect(
            x0=lane.display_order - 0.42,
            x1=lane.display_order + 0.42,
            fillcolor=lane.color,
            opacity=0.055,
            line_width=0,
            layer="below",
        )
        if lane.lane_id != "lane_background":
            lane_hit_x.extend([
                lane.display_order - 0.42, lane.display_order + 0.42,
                lane.display_order + 0.42, lane.display_order - 0.42,
                lane.display_order - 0.42, None,
            ])
            lane_hit_y.extend([
                min(all_dates), min(all_dates), max(all_dates),
                max(all_dates), min(all_dates), None,
            ])
            lane_hit_ids.extend([lane.lane_id] * 5 + [None])
    if lane_hit_x:
        # One transparent filled trace provides full-column click targets,
        # behind all visible data. Visible person/relation traces keep priority.
        fig.add_trace(
            go.Scatter(
                x=lane_hit_x,
                y=lane_hit_y,
                customdata=lane_hit_ids,
                mode="none",
                fill="toself",
                fillcolor="rgba(0,0,0,0.001)",
                line={"width": 0},
                hoveron="fills",
                hovertemplate="<extra></extra>",
                name="选择组织列",
                showlegend=False,
                meta={"organization_lane_hit_area": True},
            )
        )

    # Stage labels divide multiple successor organizations drawn in one lane.
    # Boundaries are deliberately limited to that lane rather than spanning
    # the whole chart.
    if not stages.empty:
        focus_stage_shapes: list[dict[str, object]] = []
        focus_stage_annotations: list[dict[str, object]] = []
        for stage in stages.itertuples(index=False):
            lane_x = x_for_org[stage.org_id]
            x = lane_x + local_offset(stage)
            stage_lane_id = lane_for_org[stage.org_id]
            stage_lane_ids = [stage_lane_id]
            parent_lane_id = parent_lane_for_lane.get(stage_lane_id, "")
            if parent_lane_id:
                stage_lane_ids.append(parent_lane_id)
            stage_person_ids = [
                value.strip()
                for value in str(getattr(stage, "related_person_ids", "")).split(";")
                if value.strip()
            ]
            if str(stage.show_boundary).lower() == "yes":
                focus_stage_shapes.append(
                    {
                        "index": len(fig.layout.shapes or []),
                        "related_person_ids": stage_person_ids,
                        "organization_lane_ids": stage_lane_ids,
                    }
                )
                fig.add_shape(
                    type="line",
                    x0=lane_x - 0.42,
                    x1=lane_x + 0.42,
                    y0=stage.start_date,
                    y1=stage.start_date,
                    line={"color": "#555", "width": 2, "dash": "dash"},
                    opacity=0.20,
                    layer="above",
                )
            midpoint = stage.start_date + (stage.end_date - stage.start_date) / 2
            focus_stage_annotations.append(
                {
                    "index": len(fig.layout.annotations or []),
                    "related_person_ids": stage_person_ids,
                    "organization_lane_ids": stage_lane_ids,
                }
            )
            fig.add_annotation(
                x=x,
                y=midpoint,
                text=f"<b>{escape(stage.label)}</b>",
                showarrow=False,
                bgcolor="rgba(255,255,255,0.82)",
                bordercolor="rgba(85,85,85,0.35)",
                borderwidth=1,
                borderpad=3,
                opacity=0.20,
                font={"size": 13, "color": "#333"},
            )
        fig.update_layout(
            meta={
                "focus_stage_shapes": focus_stage_shapes,
                "focus_stage_annotations": focus_stage_annotations,
            }
        )

    # Short-lived, single-person organizations are shown as branch nodes
    # beside their parent lane. They keep their own facts and hover text but
    # do not consume a full party column.
    branch_annotations: list[dict[str, object]] = []
    if not lanes.empty:
        for branch in lanes[lanes["lane_type"] == "branch"].itertuples(index=False):
            branch_orgs = organizations[organizations["lane_id"] == branch.lane_id]["org_id"]
            branch_tenures = tenures[tenures["org_id"].isin(branch_orgs)]
            if branch_tenures.empty:
                continue
            midpoint = branch_tenures["start_date"].min() + (
                branch_tenures["end_date"].max() - branch_tenures["start_date"].min()
            ) / 2
            branch_people = sorted(set(branch_tenures["person_id"]))
            branch_annotations.append(
                {
                    "index": len(fig.layout.annotations or []),
                    "related_person_ids": branch_people,
                    "organization_lane_ids": [branch.lane_id, branch.parent_lane_id],
                }
            )
            fig.add_annotation(
                x=x_for_lane[branch.lane_id],
                y=midpoint,
                text=f"<b>支线</b><br>{escape(branch.short_name)}",
                showarrow=False,
                bgcolor="rgba(255,255,255,0.88)",
                bordercolor="rgba(122,81,149,0.45)",
                borderwidth=1,
                borderpad=2,
                opacity=0.20,
                font={"size": 11, "color": "#6b477d"},
            )
    fig.update_layout(
        meta={
            **(fig.layout.meta or {}),
            "focus_branch_annotations": branch_annotations,
        }
    )

    # Contextual political events use their own lane and do not imply a
    # personal tenure or party affiliation.
    if not backgrounds.empty:
        background_text = backgrounds["title"]
        if "show_label" in backgrounds.columns:
            background_text = background_text.where(
                backgrounds["show_label"].str.lower() != "no", ""
            )
        background_text_position: str | pd.Series = "middle right"
        if "label_position" in backgrounds.columns:
            background_text_position = backgrounds["label_position"].replace(
                "", "middle right"
            )
        backgrounds["hover_text"] = backgrounds.apply(build_background_hover, axis=1)
        if "end_date" in backgrounds.columns:
            period_x: list[float | None] = []
            period_y: list[str | None] = []
            period_text: list[str | None] = []
            for background in backgrounds[backgrounds["end_date"].notna()].itertuples(
                index=False
            ):
                x = x_for_org[background.org_id]
                period_x.extend([x, x, None])
                period_y.extend([background.event_date, background.end_date, None])
                period_text.extend(
                    [background.hover_text, background.hover_text, None]
                )
            if period_x:
                fig.add_trace(
                    go.Scatter(
                        x=period_x,
                        y=period_y,
                        mode="lines",
                        line={"color": "#4D4D4D", "width": 8},
                        text=period_text,
                        hovertemplate="%{text}",
                        name="政治背景时期",
                        legendgroup="political-background-period",
                        showlegend=False,
                        opacity=0.16,
                    )
                )
        fig.add_trace(
            go.Scatter(
                x=[x_for_org[value] for value in backgrounds["org_id"]],
                y=backgrounds["event_date"],
                mode="markers+text",
                marker={"symbol": "square", "size": 15, "color": "#4D4D4D"},
                text=background_text,
                textposition=background_text_position,
                customdata=backgrounds[["hover_text"]].to_numpy(),
                hovertemplate="%{customdata[0]}",
                name="政治背景",
                opacity=0.16,
            )
        )

    # One vertical segment represents one person's tenure in one organization.
    for tenure in tenures.itertuples(index=False):
        person_name = name_for_person[tenure.person_id]
        org_name = name_for_org[tenure.org_id]
        org_note = branch_note_for_org[tenure.org_id]
        x = person_x(tenure)
        lane_type = lane_type_for_org.get(tenure.org_id, "main")
        line_color = person_color_for.get(
            tenure.person_id, color_for_org[tenure.org_id]
        )
        precision_label = {
            "day": "日",
            "month": "月",
            "year": "年",
            "mixed": "混合",
            "uncertain": "时间仅为图示定位",
        }.get(tenure.date_precision, tenure.date_precision)
        org_context = f"<br>组织识别：{escape(org_note)}" if org_note else ""
        if tenure.track == "public_office":
            category = "党外任职" if tenure.person_id == "raimajhi" else "政府任职"
            # Government offices use the party lane for positioning only.
            hover_heading = f"<b>{escape(person_name)}</b><br><b>{category}</b>"
        else:
            hover_heading = (
                f"<b>{escape(person_name)}</b><br><b>党内任职</b>"
                f"<br>{escape(org_name)}{org_context}"
            )
        hover = (
            f"{hover_heading}"
            f"<br>职务：{escape(tenure.role)}"
            f"<br>起：{format_tenure_date(tenure.start_date, tenure.date_precision)}"
            f"<br>止：{format_tenure_date(tenure.end_date, tenure.date_precision)}"
            f"<br>精度：{precision_label}"
            f"<br>{wrap_hover(tenure.notes)}<extra></extra>"
        )
        fig.add_trace(
            go.Scatter(
                x=[x, x],
                y=[tenure.start_date, tenure.end_date],
                mode="lines",
                line={"color": line_color, "width": 3 if lane_type == "branch" else 4, "dash": "solid"},
                text=[hover, hover],
                hovertemplate="%{text}",
                name=full_name_for_person.get(tenure.person_id, person_name),
                legendgroup=tenure.person_id,
                showlegend=False,
                opacity=0.20,
                meta={"person_id": tenure.person_id},
            )
        )

    # Connect consecutive tenures of the same person to show organizational movement.
    for (person_id, _track), group in tenures.sort_values("start_date").groupby(
        ["person_id", "track"]
    ):
        rows = list(group.itertuples(index=False))
        transition_x: list[float | None] = []
        transition_y: list[pd.Timestamp | None] = []
        transition_text: list[str | None] = []
        for previous, current in zip(rows, rows[1:]):
            if previous.org_id == current.org_id:
                continue
            if (current.start_date - previous.end_date).days > 366:
                continue
            hover = (
                f"<b>{full_name_for_person.get(person_id, name_for_person[person_id])}</b>"
                "<br>组织转移："
                f"{name_for_org[previous.org_id]} → {name_for_org[current.org_id]}"
                "<extra></extra>"
            )
            transition_x.extend([person_x(previous), person_x(current), None])
            transition_y.extend([previous.end_date, current.start_date, None])
            transition_text.extend([hover, hover, None])
        if transition_x:
            transition_color = person_color_for.get(person_id, "#555")
            fig.add_trace(
                go.Scatter(
                    x=transition_x,
                    y=transition_y,
                    mode="lines",
                    line={"color": transition_color, "width": 2, "dash": "solid"},
                    text=transition_text,
                    hovertemplate="%{text}",
                    showlegend=False,
                    opacity=0.20,
                    meta={"person_id": person_id},
                )
            )

    # Organization split/merge relations are drawn independently from personal moves.
    relation_labels = {
        "split": "分裂",
        "merge": "合并",
        "renamed": "改名",
        "formalized": "正式另立",
    }
    for relation in relations.itertuples(index=False):
        related_person_ids = [
            value.strip()
            for value in str(getattr(relation, "related_person_ids", "")).split(";")
            if value.strip()
        ]
        source_note = branch_note_for_org[relation.source_org_id]
        target_note = branch_note_for_org[relation.target_org_id]
        branch_context = "".join(
            f"<br>{side}分支：{escape(note)}"
            for side, note in (("起点", source_note), ("终点", target_note))
            if note
        )
        source_x = x_for_org[relation.source_org_id]
        target_x = x_for_org[relation.target_org_id]
        if source_x == target_x:
            continue
        fig.add_trace(
            go.Scatter(
                x=[source_x, target_x],
                y=[relation.event_date, relation.event_date],
                mode="lines",
                line={"color": "#7A5195", "width": 3, "dash": "dash"},
                hovertemplate=(
                    f"<b>{relation_labels.get(relation.relation_type, relation.relation_type)}</b>"
                    f"<br>{name_for_org[relation.source_org_id]} → "
                    f"{name_for_org[relation.target_org_id]}"
                    f"{branch_context}"
                    f"<br>{relation.description}"
                    "<extra></extra>"
                ),
                name="组织分合",
                legendgroup="organization-relations",
                showlegend=False,
                opacity=0.20,
                meta={
                    "related_person_ids": related_person_ids,
                    "organization_lane_ids": sorted(
                        {
                            lane_for_org[relation.source_org_id],
                            lane_for_org[relation.target_org_id],
                        }
                    ),
                },
            )
        )

    # Events remain separate evidence-bearing points instead of being folded into tenures.
    if not events.empty:
        events["hover_text"] = events.apply(
            lambda row: build_event_hover(
                row, full_name_for_person.get(row["person_id"], name_for_person[row["person_id"]])
            ),
            axis=1,
        )
        base_event_x = [
            person_x(row) for row in events.itertuples(index=False)
        ]
        event_x, event_label_positions = spread_event_nodes(
            events,
            base_event_x,
            x_pixels_per_unit,
            y_pixels_per_day,
        )
        events["_plot_x"] = event_x
        events["_plot_text_position"] = event_label_positions
        event_text = events["title"]
        if "show_label" in events.columns:
            event_text = event_text.where(events["show_label"].str.lower() != "no", "")
        for person_id, person_events in events.groupby("person_id", sort=False):
            labels = event_text.loc[person_events.index]
            positions = events.loc[person_events.index, "_plot_text_position"]
            fig.add_trace(
                go.Scatter(
                    x=person_events["_plot_x"],
                    y=person_events["event_date"],
                    mode="markers+text",
                    marker={
                        "symbol": person_symbol_for.get(person_id, "circle"),
                        "size": 13,
                        "color": person_color_for.get(person_id, "#F28E2B"),
                    },
                    text=[
                        f"<b>{full_name_for_person.get(row.person_id, name_for_person[row.person_id])}</b><br>{label}"
                        if str(getattr(row, "first_appearance", "")).lower() == "yes"
                        else label
                        for row, label in zip(person_events.itertuples(index=False), labels)
                    ],
                    textposition=positions,
                    customdata=person_events[["hover_text"]].to_numpy(),
                    hovertemplate="%{customdata[0]}",
                    name=full_name_for_person.get(person_id, name_for_person[person_id]),
                    legendgroup=person_id,
                    showlegend=False,
                    opacity=0.20,
                    meta={"person_id": person_id},
                )
            )

        # The source places both facts at the 1957 second congress: Adhikari
        # was absent for treatment, and Rayamajhi was elected general secretary.
        congress_events = events.set_index("event_id")
        if {"event_adhikari_china", "event_1957_gs"}.issubset(congress_events.index):
            absent = congress_events.loc["event_adhikari_china"]
            elected = congress_events.loc["event_1957_gs"]
            x0 = absent["_plot_x"]
            x1 = elected["_plot_x"]
            congress_date = max(absent["event_date"], elected["event_date"])
            fig.add_annotation(
                x=x1,
                y=congress_date,
                ax=x0,
                ay=congress_date,
                xref="x",
                yref="y",
                axref="x",
                ayref="y",
                text="",
                showarrow=True,
                arrowhead=3,
                arrowsize=1,
                arrowwidth=1.5,
                arrowcolor="#555",
                hovertext="1957年尼共二大：阿迪卡里因病缺席，腊伊玛吉当选总书记",
                captureevents=True,
            )

    fig.update_layout(
        title={"text": title, "x": 0.5},
        template="plotly_white",
        height=chart_height,
        width=chart_width,
        autosize=False,
        margin={"l": 100, "r": 330, "t": 195, "b": 80},
        hovermode="closest",
        hoverlabel={
            "align": "left",
            "bgcolor": "white",
            "font": {"size": 14, "family": "Noto Sans CJK SC, Microsoft YaHei, sans-serif"},
        },
        showlegend=False,
        xaxis={
            "title": "党派／组织",
            "tickmode": "array",
            "tickvals": display_lanes["display_order"].tolist(),
            "ticktext": [
                escape(row.short_name)
                + (
                    f"<br><span style='font-size:11px;color:#64748b'>〔{escape(row.branch_note)}〕</span>"
                    if getattr(row, "branch_note", "") else ""
                )
                for row in display_lanes.itertuples(index=False)
            ],
            "tickangle": -50,
            "range": [display_lanes["display_order"].min() - 0.6, display_lanes["display_order"].max() + 0.6],
            "side": "top",
            "showgrid": True,
            "gridcolor": "#D9D9D9",
        },
        yaxis={
            "title": "时间（上早下晚）",
            "type": "date",
            "autorange": "reversed",
            "showgrid": True,
            "gridcolor": "#EAEAEA",
        },
    )
    lane_people: dict[str, list[str]] = {}
    for org_id, lane_id in lane_for_org.items():
        members = set(tenures.loc[tenures["org_id"] == org_id, "person_id"])
        if not events.empty:
            members.update(events.loc[events["org_id"] == org_id, "person_id"])
        lane_people.setdefault(lane_id, []).extend(members)
    lane_people = {lane_id: sorted(set(ids)) for lane_id, ids in lane_people.items()}
    lane_options = [
        {"id": row.lane_id, "name": row.short_name, "kind": "main"}
        for row in display_lanes.itertuples(index=False)
        if row.lane_id != "lane_background"
    ]
    if not lanes.empty:
        lane_options.extend(
            {"id": row.lane_id, "name": f"{row.short_name}〔支线〕", "kind": "branch"}
            for row in lanes[lanes["lane_type"] == "branch"].itertuples(index=False)
        )
    fig.update_layout(
        meta={
            **(fig.layout.meta or {}),
            "organization_lane_people": lane_people,
            "organization_lane_options": lane_options,
            "organization_lane_axis_ids": display_lanes["lane_id"].tolist(),
        }
    )
    return fig


def build_focus_post_script(people: pd.DataFrame) -> str:
    """Attach an offline focus/search/compare rail and person-wide highlighting."""
    entries = [
        {
            "id": row.person_id,
            "name": f"{row.name_zh}（{row.name_en}）",
            "color": getattr(row, "color", "#555555") or "#555555",
        }
        for row in people.itertuples(index=False)
    ]
    entries_json = json.dumps(entries, ensure_ascii=False)
    return r"""
(function() {
  const gd = document.getElementById('{plot_id}');
  const people = __PEOPLE_JSON__;
  const traceIndices = gd.data.map((trace, i) =>
    trace.meta && (trace.meta.person_id || Array.isArray(trace.meta.related_person_ids) || Array.isArray(trace.meta.organization_lane_ids)) ? i : -1
  ).filter(i => i >= 0);
  const defaultSelection = ['prachanda'];
  const selected = defaultSelection.slice();
  let hovered = null;
  let selectedLane = null;
  let compareMode = false;
  let lastOpacitySignature = traceIndices.map(i => gd.data[i].opacity == null ? 1 : gd.data[i].opacity).join(',');
  let lastStageSignature = '';
  const stageMeta = gd.layout.meta || {};
  const lanePeople = stageMeta.organization_lane_people || {};
  const laneOptions = stageMeta.organization_lane_options || [];
  const axisLaneIds = stageMeta.organization_lane_axis_ids || [];
  const initialXRange = Array.isArray(gd.layout.xaxis.range) ? gd.layout.xaxis.range.slice() : null;
  const initialYRange = Array.isArray(gd.layout.yaxis.range) ? gd.layout.yaxis.range.slice() : null;

  const rail = document.createElement('aside');
  rail.id = 'person-focus-rail';
  rail.innerHTML = `
    <h3>人物聚焦</h3>
    <label for="organization-focus-select">选择组织列</label>
    <select id="organization-focus-select"><option value="">不选择组织列</option></select>
    <label for="person-focus-search">搜索并聚焦</label>
    <input id="person-focus-search" type="search" list="person-focus-options" placeholder="输入人物姓名…" autocomplete="off">
    <datalist id="person-focus-options"></datalist>
    <div class="focus-buttons">
      <button id="focus-reset" type="button">全部人物</button>
      <button id="compare-toggle" type="button" aria-pressed="false">比较模式：关</button>
    </div>
    <div id="focus-status" role="status">默认聚焦：普拉昌达</div>
    <hr>
    <h4>快捷操作</h4>
    <ul>
      <li>悬停节点或人物线：临时高亮</li>
      <li>单击节点或人物线：锁定／取消</li>
      <li>Shift＋单击：加入对比，最多 3 人</li>
      <li>开启比较模式后，单击可增删对比人物</li>
      <li>按 Esc：恢复默认聚焦普拉昌达和初始视图</li>
      <li>点“全部人物”：取消人物聚焦</li>
      <li>点击组织列名或列内空白色带，或使用下拉框：聚焦该列人物</li>
    </ul>
    <small>组织成员为 60%，选中人物为 100%，其他人物为 20%。点到人物或关系线时仍由其自身交互响应。</small>
  `;
  const style = document.createElement('style');
  style.textContent = `
    #person-focus-rail { position: fixed; z-index: 1000; top: 112px; right: 14px; width: 252px; max-height: calc(100vh - 132px); overflow-y: auto; box-sizing: border-box; padding: 16px; border: 1px solid #d4d9df; border-radius: 10px; background: rgba(255,255,255,.97); box-shadow: 0 3px 16px rgba(0,0,0,.12); color: #263238; font: 14px/1.45 Arial, sans-serif; }
    #person-focus-rail h3 { margin: 0 0 12px; font-size: 18px; } #person-focus-rail h4 { margin: 12px 0 4px; font-size: 14px; }
    #person-focus-rail label { display: block; margin-bottom: 5px; font-weight: 600; }
    #person-focus-search { width: 100%; box-sizing: border-box; padding: 8px; border: 1px solid #b9c2ca; border-radius: 6px; font-size: 14px; }
    #organization-focus-select { width: 100%; box-sizing: border-box; margin: 0 0 10px; padding: 8px; border: 1px solid #b9c2ca; border-radius: 6px; background: white; font-size: 14px; }
    #person-focus-rail .focus-buttons { display: flex; gap: 6px; margin-top: 8px; }
    #person-focus-rail button { flex: 1; padding: 7px 5px; border: 1px solid #aeb8c2; border-radius: 6px; background: #f7f9fb; cursor: pointer; color: #263238; }
    #person-focus-rail button:hover, #person-focus-rail button[aria-pressed="true"] { background: #e4eef8; border-color: #4c78a8; }
    #focus-status { margin-top: 10px; padding: 7px; border-radius: 5px; background: #f0f3f5; font-size: 12px; }
    #person-focus-rail ul { margin: 5px 0 12px; padding-left: 18px; } #person-focus-rail li { margin: 4px 0; }
    #person-focus-rail small { display: block; color: #59636e; }
    #temporal_network .xaxislayer-above .xtick { cursor: pointer; }
    @media (max-width: 900px) { #person-focus-rail { top: auto; right: 8px; bottom: 8px; width: 230px; max-height: 55vh; } }
  `;
  document.head.appendChild(style);
  document.body.appendChild(rail);
  const search = rail.querySelector('#person-focus-search');
  const options = rail.querySelector('#person-focus-options');
  const status = rail.querySelector('#focus-status');
  const compareButton = rail.querySelector('#compare-toggle');
  const laneSelect = rail.querySelector('#organization-focus-select');
  for (const p of people) {
    const option = document.createElement('option'); option.value = p.name; options.appendChild(option);
  }
  for (const lane of laneOptions) {
    const option = document.createElement('option');
    option.value = lane.id;
    option.textContent = lane.name;
    laneSelect.appendChild(option);
  }

  function personFromName(value) { const p = people.find(item => item.name === value || item.id === value); return p ? p.id : null; }
  function opacityForPerson(id) {
    if (selected.includes(id) || hovered === id) return 1;
    if (selectedLane && (lanePeople[selectedLane] || []).includes(id)) return 0.6;
    return 0.2;
  }
  function opacityForRelated(ids) {
    if (!ids || !ids.length) return 0.2;
    if (ids.some(id => selected.includes(id) || hovered === id)) return 1;
    if (selectedLane && ids.some(id => (lanePeople[selectedLane] || []).includes(id))) return 0.6;
    return 0.2;
  }
  function traceOpacity(i) {
    const meta = gd.data[i].meta || {};
    if (meta.person_id) return opacityForPerson(meta.person_id);
    if (Array.isArray(meta.related_person_ids) &&
        meta.related_person_ids.some(id => selected.includes(id) || hovered === id)) return 1;
    if (selectedLane && Array.isArray(meta.organization_lane_ids) &&
        meta.organization_lane_ids.includes(selectedLane)) return 0.6;
    if (Array.isArray(meta.related_person_ids)) return opacityForRelated(meta.related_person_ids);
    return 1;
  }
  function update() {
    const opacity = traceIndices.map(traceOpacity);
    const signature = opacity.join(',');
    if (signature !== lastOpacitySignature) {
      lastOpacitySignature = signature;
      Plotly.restyle(gd, {opacity}, traceIndices);
    }
    const stageOpacity = item => {
      const ids = item.related_person_ids || [];
      if (ids.some(id => selected.includes(id) || hovered === id)) return 1;
      if (selectedLane && (item.organization_lane_ids || []).includes(selectedLane)) return 0.6;
      return opacityForRelated(ids);
    };
    const stageShapeOpacities = (stageMeta.focus_stage_shapes || []).map(stageOpacity);
    const stageAnnotationOpacities = (stageMeta.focus_stage_annotations || []).map(stageOpacity);
    const branchAnnotationOpacities = (stageMeta.focus_branch_annotations || []).map(stageOpacity);
    const stageSignature = stageShapeOpacities.concat(stageAnnotationOpacities, branchAnnotationOpacities).join(',');
    if (stageSignature !== lastStageSignature) {
      lastStageSignature = stageSignature;
      const updates = {};
      (stageMeta.focus_stage_shapes || []).forEach((item, at) => {
        updates[`shapes[${item.index}].opacity`] = stageShapeOpacities[at];
      });
      (stageMeta.focus_stage_annotations || []).forEach((item, at) => {
        updates[`annotations[${item.index}].opacity`] = stageAnnotationOpacities[at];
      });
      (stageMeta.focus_branch_annotations || []).forEach((item, at) => {
        updates[`annotations[${item.index}].opacity`] = branchAnnotationOpacities[at];
      });
      if (Object.keys(updates).length) Plotly.relayout(gd, updates);
    }
    if (selected.length) {
      status.textContent = '人物 100%：' + selected.map(id => people.find(p => p.id === id).name).join('；') +
        (selectedLane ? '；组织 60%：' + (laneOptions.find(l => l.id === selectedLane) || {}).name : '');
    } else if (hovered) {
      status.textContent = '人物 100%：' + people.find(p => p.id === hovered).name +
        (selectedLane ? '；组织 60%：' + (laneOptions.find(l => l.id === selectedLane) || {}).name : '');
    } else if (selectedLane) {
      status.textContent = '组织 60%：' + (laneOptions.find(l => l.id === selectedLane) || {}).name;
    } else {
      status.textContent = '当前：全部人物（20%）';
    }
  }
  function setSelectedLane(id) {
    selectedLane = id || null;
    laneSelect.value = selectedLane || '';
    update();
  }
  function togglePerson(id, shift) {
    if (!id) return;
    if (compareMode || shift) {
      const at = selected.indexOf(id);
      if (at >= 0) selected.splice(at, 1);
      else if (selected.length < 3) selected.push(id);
      else status.textContent = '对比最多选择 3 人，请先取消一人。';
    } else {
      if (selected.length === 1 && selected[0] === id) selected.splice(0, 1);
      else { selected.splice(0, selected.length, id); }
    }
    update();
  }
  function resetViewAndControls(nextSelection, clearLane = true) {
    selected.splice(0, selected.length, ...nextSelection);
    hovered = null;
    compareMode = false;
    if (clearLane) {
      selectedLane = null;
      laneSelect.value = '';
    }
    search.value = '';
    compareButton.textContent = '比较模式：关';
    compareButton.setAttribute('aria-pressed', 'false');
    gd.__focusShiftClick = false;
    if (Plotly.Fx && typeof Plotly.Fx.unhover === 'function') Plotly.Fx.unhover(gd);
    update();
    const axisReset = {};
    if (initialXRange) axisReset['xaxis.range'] = initialXRange.slice();
    if (initialYRange) axisReset['yaxis.range'] = initialYRange.slice();
    if (Object.keys(axisReset).length) Plotly.relayout(gd, axisReset);
    window.scrollTo(0, 0);
  }
  function resetToDefault() { resetViewAndControls(defaultSelection); }
  function showAllPeople() {
    resetViewAndControls([], false);
  }
  search.addEventListener('change', () => {
    const id = personFromName(search.value);
    if (id) { selected.splice(0, selected.length, id); update(); }
  });
  laneSelect.addEventListener('change', () => setSelectedLane(laneSelect.value));
  rail.querySelector('#focus-reset').addEventListener('click', showAllPeople);
  compareButton.addEventListener('click', () => {
    compareMode = !compareMode;
    compareButton.textContent = '比较模式：' + (compareMode ? '开' : '关');
    compareButton.setAttribute('aria-pressed', String(compareMode));
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') { event.preventDefault(); resetToDefault(); }
  });
  gd.addEventListener('click', event => { gd.__focusShiftClick = event.shiftKey; }, true);
  let dataClickHandled = false;
  let pointerStart = null;
  gd.addEventListener('pointerdown', event => {
    dataClickHandled = false;
    pointerStart = {id: event.pointerId, x: event.clientX, y: event.clientY};
  }, true);
  function laneAtClick(event) {
    const full = gd._fullLayout;
    const axis = full && full.xaxis;
    if (!axis || !Array.isArray(axis.range)) return null;
    const dragArea = gd.querySelector('.nsewdrag');
    let rect = dragArea && dragArea.getBoundingClientRect();
    if (!rect || !rect.width || !rect.height) {
      const size = full._size;
      const graph = gd.getBoundingClientRect();
      if (!size || !full.width || !full.height) return null;
      const scaleX = graph.width / full.width;
      const scaleY = graph.height / full.height;
      rect = {
        left: graph.left + size.l * scaleX,
        top: graph.top + size.t * scaleY,
        width: size.w * scaleX,
        height: size.h * scaleY,
      };
    }
    if (event.clientX < rect.left || event.clientX > rect.left + rect.width ||
        event.clientY < rect.top || event.clientY > rect.top + rect.height) return null;
    const fraction = (event.clientX - rect.left) / rect.width;
    const x = Number(axis.range[0]) + fraction * (Number(axis.range[1]) - Number(axis.range[0]));
    const column = Math.round(x);
    if (Math.abs(x - column) > 0.42) return null;
    const laneId = axisLaneIds[column];
    return laneOptions.some(lane => lane.id === laneId && lane.kind === 'main') ? laneId : null;
  }
  // Plotly creates a temporary dragcover outside gd after pointerdown. Capture
  // pointerup on document so a click on the plot is not lost to that overlay.
  document.addEventListener('pointerup', event => {
    const start = pointerStart;
    pointerStart = null;
    if (!start || start.id !== event.pointerId ||
        Math.hypot(event.clientX - start.x, event.clientY - start.y) > 5) return;
    if (event.target && event.target.closest &&
        event.target.closest('.xaxislayer-above .xtick, .modebar')) return;
    const laneId = laneAtClick(event);
    if (!laneId) return;
    window.setTimeout(() => {
      if (!dataClickHandled) setSelectedLane(selectedLane === laneId ? null : laneId);
    }, 40);
  }, true);
  document.addEventListener('pointercancel', () => { pointerStart = null; }, true);
  gd.addEventListener('click', event => {
    const tick = event.target && event.target.closest ? event.target.closest('.xaxislayer-above .xtick') : null;
    if (!tick) return;
    const ticks = Array.from(gd.querySelectorAll('.xaxislayer-above .xtick'));
    const index = ticks.indexOf(tick);
    const laneId = axisLaneIds[index];
    if (laneId && laneOptions.some(item => item.id === laneId)) setSelectedLane(selectedLane === laneId ? null : laneId);
  });
  gd.on('plotly_hover', eventData => {
    const point = eventData.points && eventData.points[0];
    const trace = point && gd.data[point.curveNumber];
    hovered = trace && trace.meta ? trace.meta.person_id || null : null;
    update();
  });
  gd.on('plotly_unhover', () => { hovered = null; update(); });
  gd.on('plotly_click', eventData => {
    const points = eventData.points || [];
    const personPoint = points.find(point => {
      const trace = gd.data[point.curveNumber];
      return trace && trace.meta && trace.meta.person_id;
    });
    const relationPoint = points.find(point => {
      const trace = gd.data[point.curveNumber];
      return trace && trace.meta && Array.isArray(trace.meta.related_person_ids);
    });
    if (personPoint) {
      dataClickHandled = true;
      const trace = gd.data[personPoint.curveNumber];
      togglePerson(trace.meta.person_id, Boolean(gd.__focusShiftClick));
    } else if (relationPoint) {
      dataClickHandled = true;
    }
    gd.__focusShiftClick = false;
  });
  update();
})();
""".replace("__PEOPLE_JSON__", entries_json)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    local_data = PROJECT_ROOT / "materials/local/datasets/raimajhi-life"
    default_data = local_data if local_data.is_dir() else PROJECT_ROOT / "examples/raimajhi-life"
    parser.add_argument("--data-dir", type=Path, default=default_data)
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "output/nepal-history-network.html")
    parser.add_argument("--title", default="尼泊尔政治人物与组织关系时序图（1946—2012）")
    parser.add_argument("--cdn", action="store_true", help="在线网页从 Plotly CDN 加载脚本；默认将脚本嵌入 HTML 以供离线使用")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data_dir = project_path(args.data_dir)
    output_path = project_path(args.output)
    frames = load_data(data_dir)
    validate_references(frames)
    figure = build_figure(frames, args.title)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.write_html(
        output_path,
        include_plotlyjs="cdn" if args.cdn else True,
        full_html=True,
        div_id="temporal_network",
        post_script=build_focus_post_script(frames["people"]),
    )
    html = output_path.read_text(encoding="utf-8")
    output_path.write_text(re.sub(r"(?m)[ \t]+$", "", html), encoding="utf-8")
    print(f"已生成：{output_path}")


if __name__ == "__main__":
    main()
