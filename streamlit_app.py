from __future__ import annotations

from typing import Any

import altair as alt
import pandas as pd
import streamlit as st

from generate_dashboard import get_latest_source_modified, load_all_projects


st.set_page_config(
    page_title="Dashboard Monitoring UAT - Tim Adityo",
    page_icon="QA",
    layout="wide",
)


def format_percent(value: float) -> str:
    return f"{value:.1f}%"


def apply_dashboard_style() -> None:
    st.markdown(
        """
        <style>
        [data-testid="stMetric"] {
            min-width: 0;
        }

        [data-testid="stMetricLabel"] p {
            font-size: 1rem;
            line-height: 1.25;
            white-space: nowrap;
        }

        [data-testid="stMetricValue"] {
            overflow: visible;
        }

        [data-testid="stMetricValue"] > div {
            font-size: clamp(1.9rem, 2.15vw, 2.45rem);
            line-height: 1.15;
            overflow: visible;
            text-overflow: clip;
            white-space: nowrap;
        }

        [data-testid="stMetricDelta"] {
            font-size: 0.9rem;
            line-height: 1.2;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def summarize_data(df: pd.DataFrame) -> dict[str, Any]:
    total_task = int(df["Total Task"].sum())
    task_done = int(df["Task Done"].sum())
    total_scenario = int(len(df))
    done_scenario = int((df["Status"].str.lower() == "done").sum())
    progress = (task_done / total_task) * 100 if total_task else 0

    return {
        "total_project": int(df["Project"].nunique()),
        "total_scenario": total_scenario,
        "done_scenario": done_scenario,
        "open_scenario": total_scenario - done_scenario,
        "total_task": total_task,
        "task_done": task_done,
        "task_open": total_task - task_done,
        "progress": progress,
        "latest_source_modified": get_latest_source_modified(df),
    }


def apply_filters(df: pd.DataFrame) -> pd.DataFrame:
    st.sidebar.header("Filter")

    selected_project = st.sidebar.multiselect(
        "Project",
        options=sorted(df["Project"].unique()),
        default=sorted(df["Project"].unique()),
    )
    selected_pic = st.sidebar.multiselect(
        "PIC",
        options=sorted(df["PIC"].unique()),
        default=sorted(df["PIC"].unique()),
    )
    selected_status = st.sidebar.multiselect(
        "Status",
        options=sorted(df["Status"].unique()),
        default=sorted(df["Status"].unique()),
    )
    keyword = st.sidebar.text_input("Cari Scenario / Notes")

    if st.sidebar.button("Refresh Data", use_container_width=True):
        st.rerun()

    filtered = df[
        df["Project"].isin(selected_project)
        & df["PIC"].isin(selected_pic)
        & df["Status"].isin(selected_status)
    ].copy()

    if keyword.strip():
        keyword_lower = keyword.strip().lower()
        filtered = filtered[
            filtered["Scenario ID"].str.lower().str.contains(keyword_lower, na=False)
            | filtered["Notes"].str.lower().str.contains(keyword_lower, na=False)
            | filtered["Project"].str.lower().str.contains(keyword_lower, na=False)
        ]

    return filtered


def make_group_summary(df: pd.DataFrame, group_column: str, value_column: str) -> pd.DataFrame:
    return (
        df.groupby(group_column, dropna=False)
        .agg(Value=(value_column, "sum"))
        .reset_index()
        .rename(columns={group_column: "Category"})
        .sort_values("Category")
    )


def make_count_summary(df: pd.DataFrame, group_column: str) -> pd.DataFrame:
    return (
        df.groupby(group_column, dropna=False)
        .size()
        .reset_index(name="Value")
        .rename(columns={group_column: "Category"})
        .sort_values("Category")
    )


def make_task_completion_summary(summary: dict[str, Any]) -> pd.DataFrame:
    rows = [
        {"Category": "Task Done", "Value": summary["task_done"]},
        {"Category": "Task Open", "Value": summary["task_open"]},
    ]
    result = pd.DataFrame(rows)
    return result[result["Value"] > 0]


def render_pie_chart(title: str, chart_df: pd.DataFrame) -> None:
    st.subheader(title)

    if chart_df.empty or chart_df["Value"].sum() <= 0:
        st.info("Tidak ada data untuk chart ini.")
        return

    chart = (
        alt.Chart(chart_df)
        .mark_arc(innerRadius=55, outerRadius=120)
        .encode(
            theta=alt.Theta("Value:Q", title="Total"),
            color=alt.Color("Category:N", title="Kategori"),
            tooltip=[
                alt.Tooltip("Category:N", title="Kategori"),
                alt.Tooltip("Value:Q", title="Total", format=",.0f"),
            ],
        )
        .properties(height=320)
    )

    st.altair_chart(chart, use_container_width=True)
    st.dataframe(chart_df, use_container_width=True, hide_index=True)


def render_kpis(summary: dict[str, Any]) -> None:
    col1, col2, col3, col4 = st.columns([1, 1, 1, 1.25], gap="large")

    col1.metric(
        "Task Progress",
        format_percent(summary["progress"]),
        f"{summary['task_done']} / {summary['total_task']} Tasks",
    )
    col2.metric(
        "Scenarios Done",
        summary["done_scenario"],
        f"{summary['open_scenario']} Not Completed",
    )
    col3.metric(
        "Total Scenarios",
        summary["total_scenario"],
        f"{summary['total_project']} Projects",
    )
    col4.metric("Last Modified", summary["latest_source_modified"])


def render_charts(df: pd.DataFrame, summary: dict[str, Any]) -> None:
    col1, col2 = st.columns(2)

    with col1:
        render_pie_chart(
            "Task Progress Overview",
            make_task_completion_summary(summary),
        )

    with col2:
        render_pie_chart(
            "Scenario Status Breakdown",
            make_count_summary(df, "Status"),
        )

    col3, col4 = st.columns(2)

    with col3:
        render_pie_chart(
            "Workload by Owner (PIC)",
            make_group_summary(df, "PIC", "Total Task"),
        )

    with col4:
        render_pie_chart(
            "Scenario Coverage by Project",
            make_count_summary(df, "Project"),
        )


def render_detail_table(df: pd.DataFrame) -> None:
    detail_columns = [
        "No",
        "Project",
        "Scenario ID",
        "Total Task",
        "Task Done",
        "Progress",
        "Status",
        "PIC",
        "Notes",
        "Source File",
        "Source Modified",
    ]

    display_df = df[detail_columns].copy()
    display_df["Progress"] = display_df["Progress"].map(format_percent)

    st.subheader("UAT Scenario Insights")
    st.dataframe(display_df, use_container_width=True, hide_index=True)


def main() -> None:
    apply_dashboard_style()
    st.title("Dashboard Monitoring UAT - Tim Adityo")

    try:
        df = load_all_projects()
    except Exception as exc:
        st.error(f"Gagal membaca data Excel: {exc}")
        st.stop()

    filtered_df = apply_filters(df)

    if filtered_df.empty:
        st.warning("Tidak ada data sesuai filter.")
        st.stop()

    summary = summarize_data(filtered_df)
    render_kpis(summary)

    st.divider()
    render_charts(filtered_df, summary)

    st.divider()
    render_detail_table(filtered_df)


if __name__ == "__main__":
    main()
