import dash
from dash import html, dcc, dash_table
from ui.components import card, btn, inp, G
from utils import TH, apply_theme
import numpy as np

# Placeholders for plotting functions that will be imported in app.py or here


def _render_database(mode):
    t  = TH(mode); C_ = card(mode)
    sessions = db_load_sessions()

    if sessions.empty:
        return html.Div(className="fade-in", children=[
            html.Div(style={**C_,"padding":"24px"}, children=[
                html.Div("🗄️ Session Database", className="section-title", style={"color":t["gold"]}),
                html.P("No sessions saved yet. Load a file and click '💾 Save Session'.",
                       className="section-description"),
            ])
        ])

    has_data = []
    for _, row in sessions.iterrows():
        dp = row.get("data_path", "")
        has_data.append(bool(dp and Path(dp).exists()))
    sessions["restorable"] = ["✅" if h else "—" for h in has_data]

    display_cols = ["id","date","driver","track","car","best_lap_str",
                    "n_laps","compound","weather","restorable","notes"]
    display_cols = [c for c in display_cols if c in sessions.columns]

    manage_rows = []
    for _, row in sessions.iterrows():
        dp = row.get("data_path", "")
        sid = row["id"]
        exists = bool(dp and Path(dp).exists())
        
        manage_rows.append(html.Div(style={"display":"flex","gap":"12px","alignItems":"center",
                                           "padding":"8px 12px","backgroundColor":"rgba(0,0,0,0.2)",
                                           "borderRadius":"8px","marginBottom":"8px"}, children=[
            html.Div(f"#{sid} - {row['driver']} - {row['track']}", 
                     style={"flex":"1","fontSize":"13px","color":t["text"]}),
            
            html.Button("🔄 Load", id={"type": "restore-btn", "index": sid},
                        className="btn-premium", 
                        disabled=not exists,
                        style={"color":"#10B981","borderColor":"#10B981","fontSize":"11px",
                               "padding":"4px 12px","width":"auto","opacity": 1 if exists else 0.3}),
            
            html.Button("🗑️ Delete", id={"type": "delete-btn", "index": sid},
                        className="btn-premium",
                        style={"color":"#EF4444","borderColor":"#EF4444","fontSize":"11px",
                               "padding":"4px 12px","width":"auto"}),
        ]))

    return html.Div(className="fade-in", children=[
        html.Div(style={**C_,"padding":"18px 22px"}, children=[
            html.Div("🗄️ Session Database", className="section-title", style={"color":t["gold"]}),
            html.P(f"{len(sessions)} session(s) stored in {DB_PATH}",
                   className="section-description"),
            dash_table.DataTable(
                id="db-session-table",
                data=sessions[display_cols].to_dict("records"),
                columns=[{"name":c.replace("_"," ").title(),"id":c}
                         for c in display_cols],
                style_header={"backgroundColor":"rgba(0,0,0,0.3)","color":t["gold"],
                               "fontFamily":"var(--font-mono)","fontSize":"10px",
                               "fontWeight":"bold","textTransform":"uppercase","letterSpacing":"0.5px"},
                style_cell={"backgroundColor":t["panel"],"color":t["text"],
                            "fontFamily":"var(--font-mono)","fontSize":"12px",
                            "border":f"1px solid {t['border']}","padding":"8px 12px",
                            "textAlign":"center"},
                sort_action="native", filter_action="native",
                export_format="csv", page_size=20,
            ),
        ]),
        html.Div(style={**C_,"padding":"18px 22px"}, children=[
            html.Div("🛠️ Manage Sessions", className="section-title", style={"color":t["accent"]}),
            html.P("Load saved telemetry data or delete old sessions from local database.",
                   className="section-description"),
            html.Div(style={"display":"flex","flexDirection":"column","gap":"4px"},
                     children=manage_rows if manage_rows else [
                         html.P("No sessions found to manage.",
                                className="section-description")
                     ]),
            html.Div(id="restore-status", style={"color":t["good"],"fontSize":"13px","marginTop":"12px","fontWeight":"600"}),
        ]),
    ])