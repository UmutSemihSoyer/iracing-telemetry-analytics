import dash
from dash import html, dcc, dash_table
from ui.components import card, btn, inp, G
from utils import TH, apply_theme
import numpy as np
from services.database import db_load_setup, db_load_sessions


def _setup_input(label, id_, default=None):
    return html.Div([
        html.Label(label, style={'fontSize': '11px', 'color': 'var(--text-muted)', 'display': 'block',
                                  'marginBottom': '4px', 'fontWeight': '600'}),
        dcc.Input(id=id_, value=default, type='number',
                  style={'backgroundColor': 'rgba(0,0,0,0.2)', 'color': 'var(--text-primary)',
                         'border': '1px solid var(--border-color)', 'borderRadius': '8px',
                         'padding': '8px 12px', 'fontSize': '13px', 'width': '100px'}),
    ])


def _setup_display(label, value, unit="", accent=False):
    """Read-only display card for a setup value."""
    color = "var(--accent)" if accent else "var(--text-primary)"
    return html.Div(style={
        "backgroundColor": "rgba(0,0,0,0.15)",
        "border": "1px solid var(--border-color)",
        "borderRadius": "10px",
        "padding": "10px 14px",
        "minWidth": "110px",
        "flex": "1",
    }, children=[
        html.Div(label, style={
            "fontSize": "10px", "color": "var(--text-muted)",
            "textTransform": "uppercase", "letterSpacing": "0.5px",
            "marginBottom": "4px", "fontWeight": "600"
        }),
        html.Div(style={"display": "flex", "alignItems": "baseline", "gap": "4px"}, children=[
            html.Span(str(value) if value not in (None, "", "None") else "—",
                       style={"fontSize": "16px", "fontWeight": "700", "color": color,
                              "fontFamily": "var(--font-mono)"}),
            html.Span(unit, style={"fontSize": "10px", "color": "var(--text-muted)"}) if unit else None,
        ]),
    ])


def _corner_grid(setup, key_template, label_template, unit=""):
    """Create a 2x2 grid for FL/FR/RL/RR values."""
    corners = [("fl", "FL"), ("fr", "FR"), ("rl", "RL"), ("rr", "RR")]
    items = []
    for prefix, lbl in corners:
        key = key_template.format(prefix=prefix)
        val = setup.get(key, "—")
        items.append(_setup_display(f"{lbl} {label_template}", val, unit))
    return html.Div(style={
        "display": "grid", "gridTemplateColumns": "1fr 1fr",
        "gap": "8px",
    }, children=items)


def _section_header(text, icon=""):
    return html.Div(style={
        "display": "flex", "alignItems": "center", "gap": "8px",
        "marginBottom": "10px", "marginTop": "20px",
        "borderBottom": "1px solid var(--border-color)",
        "paddingBottom": "8px",
    }, children=[
        html.Span(icon, style={"fontSize": "16px"}),
        html.Span(text, style={
            "color": "var(--accent)", "fontSize": "13px",
            "fontWeight": "700", "letterSpacing": "0.3px"
        }),
    ])


def _render_setup_log(dfs, metas, mode, session_id=None):
    t = TH(mode)
    C_ = card(mode)

    setup_data = {}
    source_label = ""

    # Priority 1: Load from services.database
    if session_id:
        try:
            setup_data = db_load_setup(session_id) or {}
            if setup_data:
                source_label = f"📂 Loaded from DB (Session #{session_id})"
        except Exception:
            pass

    # Priority 2: Auto-extract from IBT metadata
    if not setup_data and metas:
        m = metas[0]
        auto_s = m.get("auto_setup", {})
        if auto_s:
            setup_data = auto_s
            source_label = "🔄 Auto-extracted from IBT telemetry file"
        else:
            setup_data = {
                "compound": m.get("compound", "slick_medium"),
                "brake_bias": 52.0,
            }
            source_label = "⚠️ No setup data found in IBT"

    def v(key, default=""):
        val = setup_data.get(key)
        if val is None or val == "None":
            return default
        return val

    def row(*items):
        return html.Div(style={"display": "flex", "gap": "10px", "flexWrap": "wrap",
                                "marginBottom": "8px"}, children=list(items))

    # ── Has rich auto-setup data? ──
    has_auto = bool(setup_data.get("fl_spring") or setup_data.get("wing_setting") or setup_data.get("abs_setting"))

    children = []

    # Source indicator
    if source_label:
        children.append(html.Div(style={
            "padding": "8px 14px", "borderRadius": "8px",
            "backgroundColor": "rgba(0,212,255,0.08)",
            "border": "1px solid rgba(0,212,255,0.2)",
            "fontSize": "12px", "color": t["accent"],
            "marginBottom": "16px", "fontWeight": "600",
        }, children=source_label))

    if has_auto:
        # ═══════════════════════════════
        # RICH AUTO-EXTRACTED VIEW
        # ═══════════════════════════════

        # ── Tires & Aero ──
        children.append(_section_header("Tires & Aero", "🛞"))

        # Tire type
        children.append(row(
            _setup_display("Tire Type", v("tire_type", "Unknown"), accent=True),
            _setup_display("Wing Setting", v("wing_setting"), "°"),
            _setup_display("Front Downforce", v("front_downforce_pct"), "%"),
            _setup_display("Splitter Height", v("splitter_height"), "mm"),
        ))

        # Cold / Hot pressures
        children.append(html.Div("Cold Pressures (kPa)", style={
            "fontSize": "11px", "color": t["subtext"], "marginTop": "10px",
            "marginBottom": "6px", "fontWeight": "600",
        }))
        children.append(_corner_grid(setup_data, "{prefix}_cold_p", "Cold", "kPa"))

        children.append(html.Div("Hot Pressures (kPa)", style={
            "fontSize": "11px", "color": t["subtext"], "marginTop": "10px",
            "marginBottom": "6px", "fontWeight": "600",
        }))
        children.append(_corner_grid(setup_data, "{prefix}_hot_p", "Hot", "kPa"))

        # Last temps
        children.append(html.Div("Last Tire Temps (O/M/I)", style={
            "fontSize": "11px", "color": t["subtext"], "marginTop": "10px",
            "marginBottom": "6px", "fontWeight": "600",
        }))
        children.append(row(
            _setup_display("FL Temps", v("fl_last_temps")),
            _setup_display("FR Temps", v("fr_last_temps")),
            _setup_display("RL Temps", v("rl_last_temps")),
            _setup_display("RR Temps", v("rr_last_temps")),
        ))

        # Tread remaining
        children.append(html.Div("Tread Remaining", style={
            "fontSize": "11px", "color": t["subtext"], "marginTop": "10px",
            "marginBottom": "6px", "fontWeight": "600",
        }))
        children.append(row(
            _setup_display("FL Tread", v("fl_tread_remaining")),
            _setup_display("FR Tread", v("fr_tread_remaining")),
            _setup_display("RL Tread", v("rl_tread_remaining")),
            _setup_display("RR Tread", v("rr_tread_remaining")),
        ))

        # Ride height at speed
        children.append(row(
            _setup_display("Front RH @ Speed", v("front_rh_at_speed"), "mm"),
            _setup_display("Rear RH @ Speed", v("rear_rh_at_speed"), "mm"),
        ))

        # ── Suspension ──
        children.append(_section_header("Suspension", "🔩"))

        children.append(html.Div("Spring Rates (N/mm)", style={
            "fontSize": "11px", "color": t["subtext"], "marginBottom": "6px", "fontWeight": "600",
        }))
        children.append(_corner_grid(setup_data, "{prefix}_spring", "Spring", "N/mm"))

        children.append(html.Div("Ride Height (mm)", style={
            "fontSize": "11px", "color": t["subtext"], "marginTop": "10px",
            "marginBottom": "6px", "fontWeight": "600",
        }))
        children.append(_corner_grid(setup_data, "{prefix}_ride_h", "RH", "mm"))

        children.append(html.Div("Camber (°)", style={
            "fontSize": "11px", "color": t["subtext"], "marginTop": "10px",
            "marginBottom": "6px", "fontWeight": "600",
        }))
        children.append(_corner_grid(setup_data, "{prefix}_camber", "Camber", "°"))

        children.append(html.Div("Bump Rubber Gap (mm)", style={
            "fontSize": "11px", "color": t["subtext"], "marginTop": "10px",
            "marginBottom": "6px", "fontWeight": "600",
        }))
        children.append(_corner_grid(setup_data, "{prefix}_bump_rubber", "Bump", "mm"))

        children.append(html.Div("Corner Weights (N)", style={
            "fontSize": "11px", "color": t["subtext"], "marginTop": "10px",
            "marginBottom": "6px", "fontWeight": "600",
        }))
        children.append(_corner_grid(setup_data, "{prefix}_corner_weight", "Weight", "N"))

        # ARB & Toe
        children.append(row(
            _setup_display("Front ARB", v("arb_front")),
            _setup_display("Rear ARB", v("arb_rear")),
            _setup_display("Front Toe", v("front_toe")),
            _setup_display("Rear Toe", v("rear_toe")),
        ))

        # ── Dampers ──
        children.append(_section_header("Dampers", "🔧"))

        children.append(html.Div(style={
            "display": "grid", "gridTemplateColumns": "1fr 1fr",
            "gap": "12px",
        }, children=[
            # Front dampers
            html.Div(style={
                "backgroundColor": "rgba(0,0,0,0.1)",
                "borderRadius": "10px", "padding": "12px",
                "border": "1px solid var(--border-color)",
            }, children=[
                html.Div("Front Dampers", style={
                    "fontSize": "11px", "fontWeight": "700",
                    "color": t["accent"], "marginBottom": "8px",
                }),
                row(
                    _setup_display("Low Comp", v("front_lsc"), "clicks"),
                    _setup_display("High Comp", v("front_hsc"), "clicks"),
                ),
                row(
                    _setup_display("Low Reb", v("front_lsr"), "clicks"),
                    _setup_display("High Reb", v("front_hsr"), "clicks"),
                ),
            ]),
            # Rear dampers
            html.Div(style={
                "backgroundColor": "rgba(0,0,0,0.1)",
                "borderRadius": "10px", "padding": "12px",
                "border": "1px solid var(--border-color)",
            }, children=[
                html.Div("Rear Dampers", style={
                    "fontSize": "11px", "fontWeight": "700",
                    "color": t["accent"], "marginBottom": "8px",
                }),
                row(
                    _setup_display("Low Comp", v("rear_lsc"), "clicks"),
                    _setup_display("High Comp", v("rear_hsc"), "clicks"),
                ),
                row(
                    _setup_display("Low Reb", v("rear_lsr"), "clicks"),
                    _setup_display("High Reb", v("rear_hsr"), "clicks"),
                ),
            ]),
        ]))

        # ── Brakes & Differential ──
        children.append(_section_header("Brakes & Differential", "🛑"))

        children.append(row(
            _setup_display("Brake Bias", v("brake_bias"), "%", accent=True),
            _setup_display("Brake Pads", v("brake_pads")),
            _setup_display("Front Master Cyl", v("front_master_cyl"), "mm"),
            _setup_display("Rear Master Cyl", v("rear_master_cyl"), "mm"),
        ))

        children.append(row(
            _setup_display("Diff Preload", v("diff_preload"), "Nm"),
            _setup_display("Friction Faces", v("friction_faces")),
            _setup_display("Gear Stack", v("gear_stack")),
        ))

        # ── In-Car Adjustments ──
        children.append(_section_header("In-Car Adjustments", "🎛️"))

        children.append(row(
            _setup_display("ABS Setting", v("abs_setting"), "", accent=True),
            _setup_display("TC Setting", v("tc_setting"), "", accent=True),
            _setup_display("Throttle Shape", v("throttle_shape")),
        ))

        children.append(row(
            _setup_display("Front Weight Dist", v("fw_dist"), "%"),
            _setup_display("Cross Weight", v("cross_weight"), "%"),
            _setup_display("Fuel Level", v("fuel_level"), "L"),
        ))

    # ═══════════════════════════════
    # MANUAL ENTRY FORM (always shown, auto-filled if data available)
    # ═══════════════════════════════
    children.append(html.Details(
        open=not has_auto,  # Auto-open if no rich data
        style={"marginTop": "20px"},
        children=[
            html.Summary("✏️ Manual Setup Entry / Edit", style={
                "fontSize": "13px", "color": t["accent"],
                "cursor": "pointer", "fontWeight": "600",
                "marginBottom": "14px",
            }),
            html.Div(style={"marginTop": "10px"}, children=[
                _section_header_simple("Aerodynamics", t),
                row(_setup_input("Front Wing", "s-fw", v("front_wing")),
                    _setup_input("Rear Wing", "s-rw", v("rear_wing"))),

                _section_header_simple("Springs (N/mm)", t),
                row(_setup_input("FL Spring", "s-fl-spr", v("fl_spring")),
                    _setup_input("FR Spring", "s-fr-spr", v("fr_spring")),
                    _setup_input("RL Spring", "s-rl-spr", v("rl_spring")),
                    _setup_input("RR Spring", "s-rr-spr", v("rr_spring"))),

                _section_header_simple("Camber (°) / Toe (°)", t),
                row(_setup_input("FL Camber", "s-fl-cam", v("fl_camber")),
                    _setup_input("FR Camber", "s-fr-cam", v("fr_camber")),
                    _setup_input("FL Toe", "s-fl-toe", v("fl_toe")),
                    _setup_input("FR Toe", "s-fr-toe", v("fr_toe"))),

                _section_header_simple("Ride Height (mm)", t),
                row(_setup_input("FL Ride H", "s-fl-rh", v("fl_ride_h")),
                    _setup_input("FR Ride H", "s-fr-rh", v("fr_ride_h"))),

                _section_header_simple("Cold Tyre Pressure (kPa)", t),
                row(_setup_input("FL", "s-fl-cp", v("fl_cold_p")),
                    _setup_input("FR", "s-fr-cp", v("fr_cold_p")),
                    _setup_input("RL", "s-rl-cp", v("rl_cold_p")),
                    _setup_input("RR", "s-rr-cp", v("rr_cold_p"))),

                _section_header_simple("Brakes / Differential", t),
                row(_setup_input("Brake Bias %", "s-bb", v("brake_bias", 52)),
                    _setup_input("Diff Entry", "s-de", v("diff_entry")),
                    _setup_input("Diff Mid", "s-dm", v("diff_mid")),
                    _setup_input("Diff Exit", "s-dx", v("diff_exit"))),

                html.Div([
                    html.Label("Notes", style={"fontSize": "11px", "color": "var(--text-muted)", "display": "block",
                                               "marginBottom": "6px", "marginTop": "16px", "fontWeight": "600"}),
                    dcc.Textarea(id="s-notes", value=v("notes", ""),
                                 style={"backgroundColor": "rgba(0,0,0,0.2)", "color": "var(--text-primary)",
                                        "border": "1px solid var(--border-color)", "borderRadius": "8px",
                                        "padding": "10px", "fontSize": "13px", "width": "100%",
                                        "height": "80px", "fontFamily": "var(--font-mono)", "resize": "vertical"}),
                ]),

                html.Div(style={"display": "flex", "gap": "12px", "marginTop": "18px", "alignItems": "center"}, children=[
                    html.Button("💾 Save Setup to DB", id="setup-save-btn",
                                className="btn-premium", style={"color": "#10B981", "borderColor": "#10B981", "width": "auto"}),
                    html.Div(id="setup-save-status",
                             style={"color": t["good"], "fontSize": "13px",
                                    "alignSelf": "center", "fontWeight": "600"}),
                ]),
            ]),
        ]
    ))

    return html.Div(className="fade-in", children=[
        html.Div(style={**C_, "padding": "20px 24px"}, children=[
            html.Div("🔧 Car Setup — Auto Extracted", className="section-title", style={"color": t["gold"]}),
            *children,
        ])
    ])


def _section_header_simple(text, t):
    """Simple section header for the manual form."""
    return html.Div(text, style={
        "color": t["accent"], "fontSize": "13px", "fontWeight": "700",
        "marginBottom": "8px", "marginTop": "16px",
        "borderBottom": f"1px solid {t['border']}",
        "paddingBottom": "6px"
    })


def _render_setup_delta(mode):
    t = TH(mode); C_ = card(mode)
    try:
        sessions = db_load_sessions()
    except Exception as e:
        return html.Div(f"DB Error: {e}", style={"color": "#EF4444", "padding": "20px"})
        
    if sessions.empty or len(sessions) < 2:
        return html.Div(className="fade-in", children=[
            html.Div(style={**C_, "padding": "24px", "textAlign": "center"}, children=[
                html.Div("⚖️ Setup Delta Comparison", className="section-title",
                         style={"color": t["gold"], "justifyContent": "center"}),
                html.P("Need at least 2 saved sessions in the Database to compare setups.",
                       className="section-description"),
            ])
        ])
                        
    opts = []
    for _, row in sessions.iterrows():
        lbl = f"#{row['id']} - {row['driver']} - {row['car']} - {row['track']} ({row.get('best_lap_str','')})"
        opts.append({"label": lbl, "value": row["id"]})
        
    return html.Div(className="fade-in", children=[
        html.Div(style={**C_, "padding": "18px 22px"}, children=[
            html.Div("⚖️ Setup Delta Comparison", className="section-title", style={"color": t["gold"]}),
            html.P("Compare two setups side-by-side to see what changed and its impact on lap time.",
                   className="section-description"),
            html.Div(style={"display": "flex", "gap": "20px"}, children=[
                html.Div(style={"flex": "1"}, children=[
                    html.Label("🔵 Setup A (Baseline)", style={"color": t["subtext"], "fontSize": "12px",
                               "fontWeight": "600", "display": "block", "marginBottom": "6px"}),
                    dcc.Dropdown(id="sd-session-a", options=opts,
                                 value=opts[1]["value"] if len(opts)>1 else opts[0]["value"],
                                 style={"fontSize": "13px", "backgroundColor": "#1E2028", "color": "#C9CDD6", "border": "none"}),
                ]),
                html.Div(style={"flex": "1"}, children=[
                    html.Label("🟡 Setup B (Compare)", style={"color": t["subtext"], "fontSize": "12px",
                               "fontWeight": "600", "display": "block", "marginBottom": "6px"}),
                    dcc.Dropdown(id="sd-session-b", options=opts, value=opts[0]["value"],
                                 style={"fontSize": "13px", "backgroundColor": "#1E2028", "color": "#C9CDD6", "border": "none"}),
                ]),
            ]),
        ]),
        dcc.Loading(html.Div(id="setup-delta-content"), type="circle", color="var(--accent)")
    ])