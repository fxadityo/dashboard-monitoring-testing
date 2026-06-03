from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from generate_dashboard import DATA_DIR, SHEET_NAME, load_all_projects


st.set_page_config(
    page_title="Dashboard Monitoring UAT",
    page_icon="QA",
    layout="wide",
)


def format_percent(value: float) -> str:
    return f"{value:.1f}%"


def summarize_data(df: pd.DataFrame) -> dict:
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
        "latest_source_modified": sorted(df["Source Modified"].unique())[-1] if len(df) else "-",
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


def make_task_completion_summary(summary: dict) -> pd.DataFrame:
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


def render_kpis(summary: dict) -> None:
    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Progress Task",
        format_percent(summary["progress"]),
        f"{summary['task_done']} / {summary['total_task']} task",
    )
    col2.metric(
        "Scenario Done",
        summary["done_scenario"],
        f"{summary['open_scenario']} belum Done",
    )
    col3.metric(
        "Total Scenario",
        summary["total_scenario"],
        f"{summary['total_project']} project",
    )
    col4.metric("Data Terakhir", summary["latest_source_modified"])


def render_charts(df: pd.DataFrame, summary: dict) -> None:
    col1, col2 = st.columns(2)

    with col1:
        render_pie_chart(
            "Pie Chart - Progress Task",
            make_task_completion_summary(summary),
        )

    with col2:
        render_pie_chart(
            "Pie Chart - Distribusi Status",
            make_count_summary(df, "Status"),
        )

    col3, col4 = st.columns(2)

    with col3:
        render_pie_chart(
            "Pie Chart - Total Task per PIC",
            make_group_summary(df, "PIC", "Total Task"),
        )

    with col4:
        render_pie_chart(
            "Pie Chart - Scenario per Project",
            make_count_summary(df, "Project"),
        )


def render_detail_table(df: pd.DataFrame) -> None:
    detail_columns = [
        "Project",
        "No",
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

    st.subheader("Detail Scenario UAT")
    st.dataframe(display_df, use_container_width=True, hide_index=True)


def main() -> None:
    st.title("Dashboard Monitoring UAT")
    st.caption(f"Source: `{DATA_DIR}` | Sheet: `{SHEET_NAME}`")

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
