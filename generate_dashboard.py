from __future__ import annotations

import json
from datetime import datetime
from html import escape
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_FILE = OUTPUT_DIR / "uat_dashboard.html"
SHEET_NAME = "Dashboard Progress"
SOURCE_MODIFIED_DISPLAY_FORMAT = "%d/%m/%Y %H:%M"
SOURCE_MODIFIED_SORT_COLUMN = "Source Modified Sort"


MAIN_COLUMNS = ["No", "Scenario ID", "Total Task", "Task Done", "Status", "PIC", "Notes"]


def find_excel_files(data_dir: Path) -> list[Path]:
    """Ambil semua file Excel yang bukan temporary file Excel."""
    return sorted(
        file
        for file in data_dir.glob("*.xlsx")
        if not file.name.startswith("~$")
    )


def project_name_from_file(file_path: Path) -> str:
    """Ubah nama file menjadi nama project yang enak dibaca."""
    name = file_path.stem

    if " - " in name:
        parts = name.split(" - ")
        if len(parts) >= 3:
            return " - ".join(parts[1:])

    return name


def read_dashboard_sheet(file_path: Path) -> pd.DataFrame:
    """Baca sheet Dashboard Progress dari satu workbook."""
    return pd.read_excel(file_path, sheet_name=SHEET_NAME)


def clean_dashboard_data(raw_df: pd.DataFrame, file_path: Path) -> pd.DataFrame:
    """Rapikan data utama skenario UAT dari sheet Dashboard Progress."""
    missing_columns = [column for column in MAIN_COLUMNS if column not in raw_df.columns]
    if missing_columns:
        missing = ", ".join(missing_columns)
        raise ValueError(f"{file_path.name}: kolom wajib tidak ditemukan: {missing}")

    df = raw_df[MAIN_COLUMNS].copy()
    df = df.dropna(subset=["Scenario ID"])

    source_modified_at = datetime.fromtimestamp(file_path.stat().st_mtime)
    df["Project"] = project_name_from_file(file_path)
    df["Source File"] = file_path.name
    df["Source Modified"] = source_modified_at.strftime(SOURCE_MODIFIED_DISPLAY_FORMAT)
    df[SOURCE_MODIFIED_SORT_COLUMN] = source_modified_at.isoformat(timespec="minutes")

    df["No"] = pd.to_numeric(df["No"], errors="coerce").fillna(0).astype(int)
    df["Total Task"] = pd.to_numeric(df["Total Task"], errors="coerce").fillna(0).astype(int)
    df["Task Done"] = pd.to_numeric(df["Task Done"], errors="coerce").fillna(0).astype(int)
    df["Status"] = df["Status"].fillna("No Status").astype(str).str.strip()
    df["PIC"] = df["PIC"].fillna("Unassigned").astype(str).str.strip()
    df["Notes"] = df["Notes"].fillna("").astype(str).str.strip()

    df["Progress"] = df.apply(calculate_row_progress, axis=1)
    return df


def calculate_row_progress(row: pd.Series) -> float:
    if row["Total Task"] <= 0:
        return 0.0
    return round((row["Task Done"] / row["Total Task"]) * 100, 2)


def load_all_projects() -> pd.DataFrame:
    """Baca semua workbook Excel di folder data dan gabungkan menjadi satu tabel."""
    excel_files = find_excel_files(DATA_DIR)
    if not excel_files:
        raise FileNotFoundError(f"Tidak ada file .xlsx di folder {DATA_DIR}")

    frames = []
    for file_path in excel_files:
        raw_df = read_dashboard_sheet(file_path)
        frames.append(clean_dashboard_data(raw_df, file_path))

    return pd.concat(frames, ignore_index=True)


def get_latest_source_modified(df: pd.DataFrame) -> str:
    if df.empty:
        return "-"

    if SOURCE_MODIFIED_SORT_COLUMN in df.columns:
        latest_index = df[SOURCE_MODIFIED_SORT_COLUMN].idxmax()
        return str(df.loc[latest_index, "Source Modified"])

    return sorted(df["Source Modified"].unique())[-1]


def make_summary(df: pd.DataFrame) -> dict:
    total_scenarios = int(len(df))
    total_tasks = int(df["Total Task"].sum())
    task_done = int(df["Task Done"].sum())
    done_scenarios = int((df["Status"].str.lower() == "done").sum())
    progress = round((task_done / total_tasks) * 100, 2) if total_tasks else 0.0

    return {
        "total_projects": int(df["Project"].nunique()),
        "total_scenarios": total_scenarios,
        "done_scenarios": done_scenarios,
        "open_scenarios": total_scenarios - done_scenarios,
        "total_tasks": total_tasks,
        "task_done": task_done,
        "task_open": total_tasks - task_done,
        "progress": progress,
        "latest_source_modified": get_latest_source_modified(df),
    }


def make_group_summary(df: pd.DataFrame, group_column: str) -> list[dict]:
    grouped = (
        df.groupby(group_column, dropna=False)
        .agg(
            scenarios=("Scenario ID", "count"),
            total_task=("Total Task", "sum"),
            task_done=("Task Done", "sum"),
        )
        .reset_index()
        .sort_values([group_column])
    )

    grouped["progress"] = grouped.apply(
        lambda row: round((row["task_done"] / row["total_task"]) * 100, 2)
        if row["total_task"]
        else 0.0,
        axis=1,
    )

    return grouped.to_dict(orient="records")


def make_dashboard_payload(df: pd.DataFrame) -> dict:
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

    return {
        "summary": make_summary(df),
        "projects": sorted(df["Project"].unique().tolist()),
        "pics": sorted(df["PIC"].unique().tolist()),
        "statuses": sorted(df["Status"].unique().tolist()),
        "project_summary": make_group_summary(df, "Project"),
        "pic_summary": make_group_summary(df, "PIC"),
        "status_summary": make_group_summary(df, "Status"),
        "rows": df[detail_columns].to_dict(orient="records"),
    }


def render_html(payload: dict) -> str:
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    data_json = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    title = "Dashboard Monitoring UAT - Tim Adityo"

    return f"""<!doctype html>
<html lang="id">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <style>
    :root {{
      --bg: #f5f7f8;
      --panel: #ffffff;
      --text: #172026;
      --muted: #65737e;
      --line: #dce3e7;
      --green: #12805c;
      --blue: #2264a7;
      --amber: #b66a00;
      --red: #b42318;
      --ink: #27323a;
    }}

    * {{
      box-sizing: border-box;
    }}

    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: Arial, Helvetica, sans-serif;
      line-height: 1.4;
    }}

    header {{
      background: #172026;
      color: #ffffff;
      padding: 24px 28px;
    }}

    header h1 {{
      margin: 0 0 8px;
      font-size: 28px;
      font-weight: 700;
      letter-spacing: 0;
    }}

    header p {{
      margin: 0;
      color: #d7dee2;
      max-width: 980px;
      font-size: 14px;
    }}

    main {{
      max-width: 1320px;
      margin: 0 auto;
      padding: 22px;
    }}

    .toolbar {{
      display: grid;
      grid-template-columns: repeat(4, minmax(160px, 1fr));
      gap: 12px;
      align-items: end;
      margin-bottom: 18px;
    }}

    label {{
      display: grid;
      gap: 6px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
      text-transform: uppercase;
    }}

    select,
    input {{
      min-height: 40px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #ffffff;
      color: var(--text);
      padding: 8px 10px;
      font-size: 14px;
      width: 100%;
    }}

    .kpi-grid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(160px, 1fr));
      gap: 12px;
      margin-bottom: 18px;
    }}

    .kpi {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
      min-height: 108px;
    }}

    .kpi .label {{
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
      text-transform: uppercase;
    }}

    .kpi .value {{
      margin-top: 10px;
      color: var(--ink);
      font-size: 30px;
      font-weight: 700;
    }}

    .kpi .note {{
      margin-top: 4px;
      color: var(--muted);
      font-size: 13px;
    }}

    .grid {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 14px;
      margin-bottom: 18px;
    }}

    .section {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 18px;
      min-width: 0;
    }}

    .section h2 {{
      margin: 0 0 12px;
      font-size: 18px;
      letter-spacing: 0;
    }}

    .progress-wrap {{
      display: grid;
      grid-template-columns: 160px 1fr 64px;
      gap: 10px;
      align-items: center;
      margin: 10px 0;
      font-size: 13px;
    }}

    .bar {{
      height: 12px;
      background: #e8eef1;
      border-radius: 999px;
      overflow: hidden;
    }}

    .bar span {{
      display: block;
      height: 100%;
      width: 0%;
      background: var(--green);
    }}

    .donut-row {{
      display: grid;
      grid-template-columns: 160px 1fr;
      gap: 18px;
      align-items: center;
    }}

    .donut {{
      width: 148px;
      height: 148px;
      border-radius: 50%;
      background: conic-gradient(var(--green) 0deg, var(--green) 0deg, #e8eef1 0deg);
      display: grid;
      place-items: center;
      position: relative;
    }}

    .donut::after {{
      content: "";
      position: absolute;
      width: 96px;
      height: 96px;
      border-radius: 50%;
      background: #ffffff;
    }}

    .donut strong {{
      position: relative;
      z-index: 1;
      font-size: 24px;
    }}

    .status-list {{
      display: grid;
      gap: 8px;
      color: var(--muted);
      font-size: 14px;
    }}

    .table-section {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
    }}

    .table-head {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: center;
      padding: 16px 18px;
      border-bottom: 1px solid var(--line);
    }}

    .table-head h2 {{
      margin: 0;
      font-size: 18px;
    }}

    .table-wrap {{
      overflow-x: auto;
    }}

    table {{
      width: 100%;
      border-collapse: collapse;
      min-width: 960px;
      font-size: 13px;
    }}

    th,
    td {{
      border-bottom: 1px solid var(--line);
      padding: 10px 12px;
      text-align: left;
      vertical-align: top;
    }}

    th {{
      background: #f0f4f6;
      color: #42515b;
      font-size: 12px;
      text-transform: uppercase;
      white-space: nowrap;
    }}

    td.number {{
      text-align: right;
      white-space: nowrap;
    }}

    .badge {{
      display: inline-block;
      border-radius: 999px;
      padding: 4px 8px;
      background: #e8f4ef;
      color: var(--green);
      font-weight: 700;
      font-size: 12px;
      white-space: nowrap;
    }}

    .notes {{
      max-width: 420px;
      white-space: pre-wrap;
    }}

    .source {{
      color: var(--muted);
      font-size: 12px;
    }}

    footer {{
      color: var(--muted);
      font-size: 12px;
      padding: 16px 0 4px;
    }}

    @media (max-width: 920px) {{
      main {{
        padding: 14px;
      }}

      .toolbar,
      .kpi-grid,
      .grid {{
        grid-template-columns: 1fr;
      }}

      .progress-wrap {{
        grid-template-columns: 112px 1fr 56px;
      }}

      .donut-row {{
        grid-template-columns: 1fr;
      }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>Dashboard Monitoring UAT</h1>
    <p>Ringkasan progress UAT per project untuk PMO dan User. Data diambil dari folder <strong>data</strong>, sheet <strong>Dashboard Progress</strong>, lalu dihitung ulang dari tabel skenario utama.</p>
  </header>

  <main>
    <section class="toolbar" aria-label="Filter dashboard">
      <label>
        Project
        <select id="projectFilter"></select>
      </label>
      <label>
        PIC
        <select id="picFilter"></select>
      </label>
      <label>
        Status
        <select id="statusFilter"></select>
      </label>
      <label>
        Cari Scenario / Notes
        <input id="searchFilter" type="search" placeholder="Ketik kata kunci">
      </label>
    </section>

    <section class="kpi-grid">
      <article class="kpi">
        <div class="label">Progress Task</div>
        <div class="value" id="kpiProgress">0%</div>
        <div class="note" id="kpiTaskNote">0 dari 0 task selesai</div>
      </article>
      <article class="kpi">
        <div class="label">Scenario Done</div>
        <div class="value" id="kpiDone">0</div>
        <div class="note" id="kpiDoneNote">0 scenario belum done</div>
      </article>
      <article class="kpi">
        <div class="label">Total Scenario</div>
        <div class="value" id="kpiScenario">0</div>
        <div class="note" id="kpiProjectNote">0 project aktif</div>
      </article>
      <article class="kpi">
        <div class="label">Data Terakhir</div>
        <div class="value" id="kpiFreshness">-</div>
        <div class="note">Berdasarkan waktu modifikasi file Excel</div>
      </article>
    </section>

    <section class="grid">
      <article class="section">
        <h2>Overall Completion</h2>
        <div class="donut-row">
          <div class="donut" id="overallDonut"><strong id="donutText">0%</strong></div>
          <div class="status-list" id="overallNarrative"></div>
        </div>
      </article>

      <article class="section">
        <h2>Progress per PIC</h2>
        <div id="picChart"></div>
      </article>
    </section>

    <section class="grid">
      <article class="section">
        <h2>Progress per Project</h2>
        <div id="projectChart"></div>
      </article>

      <article class="section">
        <h2>Distribusi Status</h2>
        <div id="statusChart"></div>
      </article>
    </section>

    <section class="table-section">
      <div class="table-head">
        <h2>Detail Scenario UAT</h2>
        <span class="source" id="tableCount">0 data</span>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Project</th>
              <th>No</th>
              <th>Scenario</th>
              <th>Total Task</th>
              <th>Task Done</th>
              <th>Progress</th>
              <th>Status</th>
              <th>PIC</th>
              <th>Notes</th>
            </tr>
          </thead>
          <tbody id="detailTable"></tbody>
        </table>
      </div>
    </section>

    <footer>
      Dibuat: {escape(generated_at)}. Source: semua workbook .xlsx di folder data dengan sheet Dashboard Progress.
    </footer>
  </main>

  <script>
    const dashboardData = {data_json};

    const filters = {{
      project: document.getElementById("projectFilter"),
      pic: document.getElementById("picFilter"),
      status: document.getElementById("statusFilter"),
      search: document.getElementById("searchFilter")
    }};

    function formatPercent(value) {{
      return `${{Number(value || 0).toFixed(1)}}%`;
    }}

    function fillSelect(select, values, allLabel) {{
      select.innerHTML = "";
      const allOption = document.createElement("option");
      allOption.value = "";
      allOption.textContent = allLabel;
      select.appendChild(allOption);

      values.forEach((value) => {{
        const option = document.createElement("option");
        option.value = value;
        option.textContent = value;
        select.appendChild(option);
      }});
    }}

    function getFilteredRows() {{
      const project = filters.project.value;
      const pic = filters.pic.value;
      const status = filters.status.value;
      const search = filters.search.value.trim().toLowerCase();

      return dashboardData.rows.filter((row) => {{
        const text = `${{row["Scenario ID"]}} ${{row.Notes}} ${{row.Project}}`.toLowerCase();
        return (!project || row.Project === project)
          && (!pic || row.PIC === pic)
          && (!status || row.Status === status)
          && (!search || text.includes(search));
      }});
    }}

    function summarizeRows(rows) {{
      const totalTask = rows.reduce((sum, row) => sum + Number(row["Total Task"] || 0), 0);
      const taskDone = rows.reduce((sum, row) => sum + Number(row["Task Done"] || 0), 0);
      const doneScenario = rows.filter((row) => String(row.Status).toLowerCase() === "done").length;
      const projects = new Set(rows.map((row) => row.Project));
      const latestSource = rows.map((row) => row["Source Modified"]).sort().at(-1) || "-";

      return {{
        totalTask,
        taskDone,
        taskOpen: totalTask - taskDone,
        progress: totalTask ? (taskDone / totalTask) * 100 : 0,
        totalScenario: rows.length,
        doneScenario,
        openScenario: rows.length - doneScenario,
        totalProject: projects.size,
        latestSource
      }};
    }}

    function groupRows(rows, groupName) {{
      const groups = new Map();

      rows.forEach((row) => {{
        const key = row[groupName] || "N/A";
        if (!groups.has(key)) {{
          groups.set(key, {{ name: key, scenarios: 0, totalTask: 0, taskDone: 0 }});
        }}
        const item = groups.get(key);
        item.scenarios += 1;
        item.totalTask += Number(row["Total Task"] || 0);
        item.taskDone += Number(row["Task Done"] || 0);
      }});

      return Array.from(groups.values())
        .map((item) => ({{
          ...item,
          progress: item.totalTask ? (item.taskDone / item.totalTask) * 100 : 0
        }}))
        .sort((a, b) => a.name.localeCompare(b.name));
    }}

    function renderBarChart(elementId, rows, labelMode = "task") {{
      const element = document.getElementById(elementId);
      element.innerHTML = "";

      if (!rows.length) {{
        element.textContent = "Tidak ada data sesuai filter.";
        return;
      }}

      rows.forEach((row) => {{
        const wrap = document.createElement("div");
        wrap.className = "progress-wrap";

        const label = document.createElement("div");
        label.textContent = row.name;

        const bar = document.createElement("div");
        bar.className = "bar";
        const fill = document.createElement("span");
        fill.style.width = `${{Math.max(0, Math.min(row.progress, 100))}}%`;
        bar.appendChild(fill);

        const value = document.createElement("div");
        value.className = "number";
        value.textContent = labelMode === "status"
          ? `${{row.scenarios}} scenario`
          : formatPercent(row.progress);

        wrap.append(label, bar, value);
        element.appendChild(wrap);
      }});
    }}

    function renderKpis(summary) {{
      document.getElementById("kpiProgress").textContent = formatPercent(summary.progress);
      document.getElementById("kpiTaskNote").textContent = `${{summary.taskDone}} dari ${{summary.totalTask}} task selesai`;
      document.getElementById("kpiDone").textContent = summary.doneScenario;
      document.getElementById("kpiDoneNote").textContent = `${{summary.openScenario}} scenario belum done`;
      document.getElementById("kpiScenario").textContent = summary.totalScenario;
      document.getElementById("kpiProjectNote").textContent = `${{summary.totalProject}} project aktif`;
      document.getElementById("kpiFreshness").textContent = summary.latestSource;

      const degree = Math.max(0, Math.min(summary.progress, 100)) * 3.6;
      const donut = document.getElementById("overallDonut");
      donut.style.background = `conic-gradient(var(--green) 0deg, var(--green) ${{degree}}deg, #e8eef1 ${{degree}}deg)`;
      document.getElementById("donutText").textContent = formatPercent(summary.progress);

      document.getElementById("overallNarrative").innerHTML = `
        <div><strong>${{summary.taskDone}}</strong> task selesai dari <strong>${{summary.totalTask}}</strong> total task.</div>
        <div><strong>${{summary.doneScenario}}</strong> scenario berstatus Done dari <strong>${{summary.totalScenario}}</strong> scenario.</div>
        <div><strong>${{summary.taskOpen}}</strong> task masih terbuka pada filter saat ini.</div>
      `;
    }}

    function renderTable(rows) {{
      const tbody = document.getElementById("detailTable");
      tbody.innerHTML = "";

      rows.forEach((row) => {{
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td>${{escapeHtml(row.Project)}}</td>
          <td class="number">${{row.No}}</td>
          <td>${{escapeHtml(row["Scenario ID"])}}</td>
          <td class="number">${{row["Total Task"]}}</td>
          <td class="number">${{row["Task Done"]}}</td>
          <td class="number">${{formatPercent(row.Progress)}}</td>
          <td><span class="badge">${{escapeHtml(row.Status)}}</span></td>
          <td>${{escapeHtml(row.PIC)}}</td>
          <td class="notes">${{escapeHtml(row.Notes)}}</td>
        `;
        tbody.appendChild(tr);
      }});

      document.getElementById("tableCount").textContent = `${{rows.length}} data`;
    }}

    function escapeHtml(value) {{
      return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
    }}

    function updateDashboard() {{
      const rows = getFilteredRows();
      const summary = summarizeRows(rows);

      renderKpis(summary);
      renderBarChart("picChart", groupRows(rows, "PIC"));
      renderBarChart("projectChart", groupRows(rows, "Project"));
      renderBarChart("statusChart", groupRows(rows, "Status"), "status");
      renderTable(rows);
    }}

    fillSelect(filters.project, dashboardData.projects, "Semua Project");
    fillSelect(filters.pic, dashboardData.pics, "Semua PIC");
    fillSelect(filters.status, dashboardData.statuses, "Semua Status");

    Object.values(filters).forEach((filter) => {{
      filter.addEventListener("input", updateDashboard);
    }});

    updateDashboard();
  </script>
</body>
</html>
"""


def save_dashboard(html: str, output_file: Path) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(html, encoding="utf-8")


def main() -> None:
    df = load_all_projects()
    payload = make_dashboard_payload(df)
    html = render_html(payload)
    save_dashboard(html, OUTPUT_FILE)

    summary = payload["summary"]
    print(f"Dashboard berhasil dibuat: {OUTPUT_FILE}")
    print(f"Project: {summary['total_projects']}")
    print(f"Scenario: {summary['total_scenarios']}")
    print(f"Task: {summary['task_done']} / {summary['total_tasks']}")
    print(f"Progress: {summary['progress']}%")


if __name__ == "__main__":
    main()
