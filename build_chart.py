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
    if row["person_id"] == "raimajhi":
        event_type = row["event_type"]
        if event_type == "public_office":
            category = "党外任职"
        elif event_type in {"context", "retirement"}:
            category = "党外任职相关事件"
        elif event_type == "death":
            category = "生平事件"
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


def build_figure(frames: dict[str, pd.DataFrame], title: str) -> go.Figure:
    organizations = frames["organizations"].copy()
    people = frames["people"].copy()
    tenures = frames["tenures"].copy()
    events = frames["events"].copy()
    events = events.sort_values(["event_date", "person_id"])
    relations = frames["organization_relations"].copy()
    backgrounds = frames.get("background_events", pd.DataFrame()).copy()
    stages = frames.get("organization_stages", pd.DataFrame()).copy()

    organizations["display_order"] = organizations["display_order"].astype(int)
    organizations = organizations.sort_values("display_order")
    if "track" not in tenures.columns:
        tenures["track"] = "organization"
    x_for_org = dict(zip(organizations["org_id"], organizations["display_order"]))
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
    for org in organizations.itertuples(index=False):
        fig.add_vrect(
            x0=org.display_order - 0.42,
            x1=org.display_order + 0.42,
            fillcolor=org.color,
            opacity=0.055,
            line_width=0,
            layer="below",
        )

    # Stage labels divide multiple successor organizations drawn in one lane.
    # Boundaries are deliberately limited to that lane rather than spanning
    # the whole chart.
    if not stages.empty:
        focus_stage_shape_indices: list[int] = []
        focus_stage_annotation_indices: list[int] = []
        focus_stage_person_ids: set[str] = set()
        for stage in stages.itertuples(index=False):
            lane_x = x_for_org[stage.org_id]
            x = lane_x + local_offset(stage)
            stage_person_ids = [
                value.strip()
                for value in str(getattr(stage, "related_person_ids", "")).split(";")
                if value.strip()
            ]
            focus_stage_person_ids.update(stage_person_ids)
            if str(stage.show_boundary).lower() == "yes":
                focus_stage_shape_indices.append(len(fig.layout.shapes or []))
                fig.add_shape(
                    type="line",
                    x0=lane_x - 0.42,
                    x1=lane_x + 0.42,
                    y0=stage.start_date,
                    y1=stage.start_date,
                    line={"color": "#555", "width": 2, "dash": "dash"},
                    opacity=0.24,
                    layer="above",
                )
            midpoint = stage.start_date + (stage.end_date - stage.start_date) / 2
            focus_stage_annotation_indices.append(len(fig.layout.annotations or []))
            fig.add_annotation(
                x=x,
                y=midpoint,
                text=f"<b>{escape(stage.label)}</b>",
                showarrow=False,
                bgcolor="rgba(255,255,255,0.82)",
                bordercolor="rgba(85,85,85,0.35)",
                borderwidth=1,
                borderpad=3,
                opacity=0.24,
                font={"size": 13, "color": "#333"},
            )
        fig.update_layout(
            meta={
                "focus_stage_shape_indices": focus_stage_shape_indices,
                "focus_stage_annotation_indices": focus_stage_annotation_indices,
                "focus_stage_person_ids": sorted(focus_stage_person_ids),
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
        dash = "dash" if tenure.status in {"disputed", "uncertain"} else "solid"
        if "line_style" in tenures.columns and tenure.line_style:
            dash = tenure.line_style
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
        if tenure.person_id == "raimajhi":
            category = "党外任职" if tenure.track == "public_office" else "党内任职"
            # Public offices share the drawing column but are not party offices.
            affiliation = "" if tenure.track == "public_office" else f"<br>{escape(org_name)}{org_context}"
            hover_heading = f"<b>{escape(person_name)}</b><br><b>{category}</b>{affiliation}"
        else:
            hover_heading = f"<b>{escape(person_name)}</b><br>{escape(org_name)}{org_context}"
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
                mode="lines+markers",
                line={"color": line_color, "width": 4, "dash": dash},
                marker={
                    "size": 9,
                    "color": line_color,
                    "symbol": person_symbol_for.get(tenure.person_id, "circle"),
                },
                text=[hover, hover],
                hovertemplate="%{text}",
                name=full_name_for_person.get(tenure.person_id, person_name),
                legendgroup=tenure.person_id,
                showlegend=False,
                opacity=0.24,
                meta={"person_id": tenure.person_id},
            )
        )

    # Connect consecutive tenures of the same person to show organizational movement.
    for (person_id, _track), group in tenures.sort_values("start_date").groupby(
        ["person_id", "track"]
    ):
        rows = list(group.itertuples(index=False))
        for previous, current in zip(rows, rows[1:]):
            if previous.org_id == current.org_id:
                continue
            if (current.start_date - previous.end_date).days > 366:
                continue
            transition_color = person_color_for.get(person_id, "#555")
            fig.add_trace(
                go.Scatter(
                    x=[person_x(previous), person_x(current)],
                    y=[previous.end_date, current.start_date],
                    mode="lines",
                    line={"color": transition_color, "width": 2, "dash": "dot"},
                    hovertemplate=(
                    f"<b>{full_name_for_person.get(person_id, name_for_person[person_id])}</b>"
                    "<br>组织转移："
                        f"{name_for_org[previous.org_id]} → {name_for_org[current.org_id]}"
                        "<extra></extra>"
                    ),
                    showlegend=False,
                    opacity=0.24,
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
        fig.add_trace(
            go.Scatter(
                x=[x_for_org[relation.source_org_id], x_for_org[relation.target_org_id]],
                y=[relation.event_date, relation.event_date],
                mode="lines+markers",
                line={"color": "#7A5195", "width": 3, "dash": "dash"},
                marker={"symbol": "diamond", "size": 10, "color": "#7A5195"},
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
                opacity=0.24,
                meta={"related_person_ids": related_person_ids},
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
        event_text = events["title"]
        if "show_label" in events.columns:
            event_text = event_text.where(events["show_label"].str.lower() != "no", "")
        event_text_position: str | pd.Series = "middle right"
        if "label_position" in events.columns:
            event_text_position = events["label_position"].replace("", "middle right")
        for person_id, person_events in events.groupby("person_id", sort=False):
            labels = event_text.loc[person_events.index]
            positions = event_text_position.loc[person_events.index] if isinstance(event_text_position, pd.Series) else event_text_position
            fig.add_trace(
                go.Scatter(
                    x=[person_x(row) for row in person_events.itertuples(index=False)],
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
                    opacity=0.24,
                    meta={"person_id": person_id},
                )
            )

        # The source places both facts at the 1957 second congress: Adhikari
        # was absent for treatment, and Rayamajhi was elected general secretary.
        congress_events = events.set_index("event_id")
        if {"event_adhikari_china", "event_1957_gs"}.issubset(congress_events.index):
            absent = congress_events.loc["event_adhikari_china"]
            elected = congress_events.loc["event_1957_gs"]
            x0 = x_for_org[absent["org_id"]] + float(absent["x_offset"] or 0.0)
            x1 = x_for_org[elected["org_id"]] + float(elected["x_offset"] or 0.0)
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

    chart_height = max(1500, min(2400, 850 + len(events) * 13))
    chart_width = max(1450, len(organizations) * 125 + 330)

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
            "tickvals": organizations["display_order"].tolist(),
            "ticktext": [
                escape(row.short_name)
                + (
                    f"<br><span style='font-size:11px;color:#64748b'>〔{escape(row.branch_note)}〕</span>"
                    if getattr(row, "branch_note", "") else ""
                )
                for row in organizations.itertuples(index=False)
            ],
            "tickangle": -50,
            "range": [organizations["display_order"].min() - 0.6, organizations["display_order"].max() + 0.6],
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
    trace.meta && (trace.meta.person_id || Array.isArray(trace.meta.related_person_ids)) ? i : -1
  ).filter(i => i >= 0);
  const defaultSelection = ['prachanda'];
  const selected = defaultSelection.slice();
  let hovered = null;
  let compareMode = false;
  let lastOpacitySignature = traceIndices.map(i => gd.data[i].opacity == null ? 1 : gd.data[i].opacity).join(',');
  let lastStageOpacity = 0.24;
  const stageMeta = gd.layout.meta || {};
  const initialXRange = Array.isArray(gd.layout.xaxis.range) ? gd.layout.xaxis.range.slice() : null;
  const initialYRange = Array.isArray(gd.layout.yaxis.range) ? gd.layout.yaxis.range.slice() : null;

  const rail = document.createElement('aside');
  rail.id = 'person-focus-rail';
  rail.innerHTML = `
    <h3>人物聚焦</h3>
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
    </ul>
    <small>人物轨迹按组织列共用位置显示；被选人物的事件与任职会同步高亮。</small>
  `;
  const style = document.createElement('style');
  style.textContent = `
    #person-focus-rail { position: fixed; z-index: 1000; top: 112px; right: 14px; width: 252px; max-height: calc(100vh - 132px); overflow-y: auto; box-sizing: border-box; padding: 16px; border: 1px solid #d4d9df; border-radius: 10px; background: rgba(255,255,255,.97); box-shadow: 0 3px 16px rgba(0,0,0,.12); color: #263238; font: 14px/1.45 Arial, sans-serif; }
    #person-focus-rail h3 { margin: 0 0 12px; font-size: 18px; } #person-focus-rail h4 { margin: 12px 0 4px; font-size: 14px; }
    #person-focus-rail label { display: block; margin-bottom: 5px; font-weight: 600; }
    #person-focus-search { width: 100%; box-sizing: border-box; padding: 8px; border: 1px solid #b9c2ca; border-radius: 6px; font-size: 14px; }
    #person-focus-rail .focus-buttons { display: flex; gap: 6px; margin-top: 8px; }
    #person-focus-rail button { flex: 1; padding: 7px 5px; border: 1px solid #aeb8c2; border-radius: 6px; background: #f7f9fb; cursor: pointer; color: #263238; }
    #person-focus-rail button:hover, #person-focus-rail button[aria-pressed="true"] { background: #e4eef8; border-color: #4c78a8; }
    #focus-status { margin-top: 10px; padding: 7px; border-radius: 5px; background: #f0f3f5; font-size: 12px; }
    #person-focus-rail ul { margin: 5px 0 12px; padding-left: 18px; } #person-focus-rail li { margin: 4px 0; }
    #person-focus-rail small { display: block; color: #59636e; }
    @media (max-width: 900px) { #person-focus-rail { top: auto; right: 8px; bottom: 8px; width: 230px; max-height: 55vh; } }
  `;
  document.head.appendChild(style);
  document.body.appendChild(rail);
  const search = rail.querySelector('#person-focus-search');
  const options = rail.querySelector('#person-focus-options');
  const status = rail.querySelector('#focus-status');
  const compareButton = rail.querySelector('#compare-toggle');
  for (const p of people) {
    const option = document.createElement('option'); option.value = p.name; options.appendChild(option);
  }

  function personFromName(value) { const p = people.find(item => item.name === value || item.id === value); return p ? p.id : null; }
  function traceOpacity(i) {
    const meta = gd.data[i].meta || {};
    const focus = selected.length ? selected : (hovered ? [hovered] : []);
    if (meta.person_id) return focus.length ? (focus.includes(meta.person_id) ? 1 : 0.07) : 0.24;
    if (Array.isArray(meta.related_person_ids)) {
      if (!focus.length) return 0.24;
      return focus.some(id => meta.related_person_ids.includes(id)) ? 1 : 0.07;
    }
    return 1;
  }
  function update() {
    const focus = selected.length ? selected : (hovered ? [hovered] : []);
    const opacity = traceIndices.map(traceOpacity);
    const signature = opacity.join(',');
    if (signature !== lastOpacitySignature) {
      lastOpacitySignature = signature;
      Plotly.restyle(gd, {opacity}, traceIndices);
    }
    const stageOpacity = !focus.length ? 0.24 :
      (focus.some(id => (stageMeta.focus_stage_person_ids || []).includes(id)) ? 1 : 0.07);
    if (stageOpacity !== lastStageOpacity) {
      lastStageOpacity = stageOpacity;
      const updates = {};
      for (const i of stageMeta.focus_stage_shape_indices || []) updates[`shapes[${i}].opacity`] = stageOpacity;
      for (const i of stageMeta.focus_stage_annotation_indices || []) updates[`annotations[${i}].opacity`] = stageOpacity;
      if (Object.keys(updates).length) Plotly.relayout(gd, updates);
    }
    if (selected.length) {
      status.textContent = '已锁定：' + selected.map(id => people.find(p => p.id === id).name).join('；');
    } else if (hovered) {
      status.textContent = '预览：' + people.find(p => p.id === hovered).name;
    } else {
      status.textContent = '当前：全部人物（淡显）';
    }
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
  function resetViewAndControls(nextSelection) {
    selected.splice(0, selected.length, ...nextSelection);
    hovered = null;
    compareMode = false;
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
    resetViewAndControls([]);
  }
  search.addEventListener('change', () => {
    const id = personFromName(search.value);
    if (id) { selected.splice(0, selected.length, id); update(); }
  });
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
  gd.on('plotly_hover', eventData => {
    const point = eventData.points && eventData.points[0];
    const trace = point && gd.data[point.curveNumber];
    hovered = trace && trace.meta ? trace.meta.person_id || null : null;
    update();
  });
  gd.on('plotly_unhover', () => { hovered = null; update(); });
  gd.on('plotly_click', eventData => {
    const point = eventData.points && eventData.points[0];
    const trace = point && gd.data[point.curveNumber];
    togglePerson(trace && trace.meta ? trace.meta.person_id : null, Boolean(gd.__focusShiftClick));
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
    parser.add_argument("--title", default="尼泊尔政治人物与组织关系时序图（1949—2012）")
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
