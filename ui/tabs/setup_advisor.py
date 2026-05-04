"""
Setup Advisor Tab — Dashboard UI for setup recommendations.

Renders:
  - Score card (out of 100)
  - Category quick-status badges
  - Current setup summary (from IBT)
  - Sorted recommendation cards
"""

from dash import html, dcc
from ui.components import card, G
from utils import TH


def _render_setup_advisor(dfs, metas, mode, unit="metric"):
    """Main render function for the Setup Advisor tab."""
    t = TH(mode)
    C_ = card(mode)

    # ── Extract setup from IBT metadata ──
    setup_data = {}
    if metas:
        setup_data = metas[0].get("auto_setup", {})

    # ── Run analysis ──
    recommendations = []
    score = 0
    cat_grades = {}

    try:
        from services.setup_advisor import analyze_setup, setup_score, category_grades
        if dfs:
            recommendations = analyze_setup(dfs[0], setup_data)
            score = setup_score(recommendations)
            cat_grades = category_grades(recommendations)
    except Exception as e:
        import traceback; traceback.print_exc()
        recommendations = [{
            "category": "General", "severity": "warning", "icon": "⚠️",
            "title": "Analysis Error",
            "detail": f"Could not run setup analysis: {e}",
            "parameter": "", "direction": "check", "suggested_delta": "",
        }]
        score = 0

    # ── Score color ──
    if score >= 80:
        score_color = "#10B981"
        score_label = "Excellent"
    elif score >= 60:
        score_color = "#FBBF24"
        score_label = "Needs Tuning"
    elif score >= 40:
        score_color = "#FF8C00"
        score_label = "Significant Issues"
    else:
        score_color = "#EF4444"
        score_label = "Major Problems"

    # ── Build layout ──
    children = []

    # ── Header ──
    children.append(html.Div(style={
        "display": "flex", "gap": "16px", "marginBottom": "20px",
    }, children=[
        # Score card
        html.Div(style={
            **C_, "padding": "24px", "minWidth": "160px",
            "textAlign": "center", "position": "relative",
            "borderLeft": f"4px solid {score_color}",
        }, children=[
            html.Div("SETUP SCORE", style={
                "fontSize": "10px", "color": t["subtext"],
                "textTransform": "uppercase", "letterSpacing": "1px",
                "fontWeight": "700", "marginBottom": "8px",
            }),
            html.Div(f"{score}", style={
                "fontSize": "48px", "fontWeight": "800",
                "color": score_color, "fontFamily": "var(--font-mono)",
                "lineHeight": "1",
            }),
            html.Div("/100", style={
                "fontSize": "14px", "color": t["subtext"],
                "fontWeight": "600", "marginTop": "2px",
            }),
            html.Div(score_label, style={
                "fontSize": "11px", "color": score_color,
                "fontWeight": "700", "marginTop": "8px",
                "textTransform": "uppercase", "letterSpacing": "0.5px",
            }),
        ]),

        # Category grades
        html.Div(style={
            **C_, "padding": "20px 24px", "flex": "1",
        }, children=[
            html.Div("Category Status", style={
                "fontSize": "10px", "color": t["subtext"],
                "textTransform": "uppercase", "letterSpacing": "1px",
                "fontWeight": "700", "marginBottom": "12px",
            }),
            html.Div(style={
                "display": "flex", "flexWrap": "wrap", "gap": "10px",
            }, children=[
                _badge(cat, grade, t) for cat, grade in cat_grades.items()
            ] if cat_grades else [
                html.Div("No data available", style={
                    "color": t["subtext"], "fontSize": "12px",
                }),
            ]),
        ]),

        # Quick setup info
        html.Div(style={
            **C_, "padding": "20px 24px", "minWidth": "200px",
        }, children=[
            html.Div("Current Setup", style={
                "fontSize": "10px", "color": t["subtext"],
                "textTransform": "uppercase", "letterSpacing": "1px",
                "fontWeight": "700", "marginBottom": "12px",
            }),
            *_quick_setup_items(setup_data, t),
        ]),
    ]))

    # ── Recommendations ──
    children.append(html.Div(style={
        "display": "flex", "alignItems": "center", "gap": "10px",
        "marginBottom": "14px",
    }, children=[
        html.Span("🧰", style={"fontSize": "18px"}),
        html.Span("Setup Recommendations", style={
            "fontSize": "15px", "fontWeight": "700",
            "color": t["text"],
        }),
        html.Span(f"({len(recommendations)} items)", style={
            "fontSize": "12px", "color": t["subtext"],
        }),
    ]))

    # Group by severity
    severity_groups = {
        "critical": ("🔴 Critical Issues", "#EF4444"),
        "warning": ("🟠 Warnings", "#FF8C00"),
        "info": ("🔵 Suggestions", "#00D4FF"),
        "good": ("🟢 Looking Good", "#10B981"),
    }

    for sev_key, (sev_label, sev_color) in severity_groups.items():
        sev_items = [r for r in recommendations if r["severity"] == sev_key]
        if not sev_items:
            continue

        children.append(html.Div(sev_label, style={
            "fontSize": "12px", "fontWeight": "700", "color": sev_color,
            "marginTop": "16px", "marginBottom": "8px",
            "textTransform": "uppercase", "letterSpacing": "0.5px",
        }))

        for rec in sev_items:
            children.append(_rec_card(rec, t, C_, sev_color))

    # ── Anomaly Detection Section ──
    anomaly_children = _build_anomaly_section(dfs, t, C_)
    if anomaly_children:
        children.append(html.Hr(style={
            "border": "none", "borderTop": f"1px solid {t['border']}",
            "margin": "24px 0 16px 0",
        }))
        children.extend(anomaly_children)

    return html.Div(className="fade-in", children=[
        html.Div(style={**C_, "padding": "24px"}, children=[
            html.Div(style={
                "display": "flex", "alignItems": "center", "gap": "10px",
                "marginBottom": "16px",
            }, children=[
                html.Div("🧰 Setup Advisor", className="section-title",
                         style={"color": t["gold"], "margin": "0"}),
                html.Span("— Based on your telemetry data", style={
                    "fontSize": "12px", "color": t["subtext"],
                }),
            ]),
            html.P(
                "Analyzes your driving telemetry to recommend setup changes. "
                "Load an IBT file with setup data for best results.",
                className="section-description",
            ),
            
            # ── Feedback UI ──
            html.Div(style={
                "display": "flex", "alignItems": "center", "gap": "12px",
                "padding": "12px 16px", "backgroundColor": "rgba(0,0,0,0.2)",
                "borderRadius": "8px", "border": f"1px solid {t['border']}",
                "marginBottom": "24px"
            }, children=[
                html.Span("How was this setup on track?", style={
                    "fontSize": "13px", "fontWeight": "600", "color": t["text"]
                }),
                dcc.RadioItems(
                    id='setup-rating-radio',
                    options=[
                        {'label': ' ⭐', 'value': 1},
                        {'label': ' ⭐⭐', 'value': 2},
                        {'label': ' ⭐⭐⭐', 'value': 3},
                        {'label': ' ⭐⭐⭐⭐', 'value': 4},
                        {'label': ' ⭐⭐⭐⭐⭐', 'value': 5},
                    ],
                    value=0,
                    inline=True,
                    inputStyle={"marginRight": "4px", "marginLeft": "12px"},
                    style={"color": t["gold"], "fontSize": "13px"}
                ),
                html.Button("Save Rating", id="save-rating-btn", className="btn-premium", style={
                    "padding": "4px 12px", "fontSize": "11px", "marginLeft": "auto",
                    "backgroundColor": "transparent", "border": f"1px solid {t['accent']}",
                    "color": t["accent"]
                }),
                html.Div(id="rating-save-status", style={"fontSize": "11px", "color": "#10B981"})
            ]),
            
            *children,
        ]),
    ])


# ════════════════════════════════════════════════════════════════════════════
# UI HELPERS
# ════════════════════════════════════════════════════════════════════════════

def _badge(category, grade, t):
    """Category badge with grade icon."""
    return html.Div(style={
        "display": "flex", "alignItems": "center", "gap": "6px",
        "backgroundColor": "rgba(0,0,0,0.2)",
        "border": "1px solid var(--border-color)",
        "borderRadius": "8px", "padding": "6px 12px",
    }, children=[
        html.Span(grade, style={"fontSize": "14px"}),
        html.Span(category, style={
            "fontSize": "11px", "color": t["text"],
            "fontWeight": "600",
        }),
    ])


def _quick_setup_items(setup, t):
    """Quick-glance setup values."""
    items = []
    quick_keys = [
        ("Wing", "wing_setting", ""),
        ("Brake Bias", "brake_bias", "%"),
        ("Diff Preload", "diff_preload", "Nm"),
        ("ABS", "abs_setting", ""),
        ("TC", "tc_setting", ""),
    ]
    for label, key, unit in quick_keys:
        val = setup.get(key)
        if val is None or val == "" or val == "None":
            continue
        items.append(html.Div(style={
            "display": "flex", "justifyContent": "space-between",
            "alignItems": "center", "marginBottom": "4px",
        }, children=[
            html.Span(label, style={
                "fontSize": "11px", "color": t["subtext"],
            }),
            html.Span(f"{val}{' ' + unit if unit else ''}", style={
                "fontSize": "12px", "color": t["accent"],
                "fontWeight": "600", "fontFamily": "var(--font-mono)",
            }),
        ]))

    if not items:
        items.append(html.Div("No setup data in IBT", style={
            "fontSize": "11px", "color": t["subtext"],
            "fontStyle": "italic",
        }))

    return items


def _rec_card(rec, t, C_, accent_color):
    """Single recommendation card."""
    # Direction arrow
    dir_map = {"increase": "▲", "decrease": "▼", "check": "•"}
    dir_icon = dir_map.get(rec["direction"], "•")
    dir_color = "#10B981" if rec["direction"] == "increase" else (
        "#EF4444" if rec["direction"] == "decrease" else t["subtext"]
    )

    right_panel = []
    if rec["parameter"] and rec["suggested_delta"] and rec["suggested_delta"] not in ("", "OK", "Monitor"):
        right_panel = [
            html.Div(style={
                "textAlign": "right", "minWidth": "120px",
                "borderLeft": f"1px solid {t['border']}",
                "paddingLeft": "16px", "marginLeft": "16px",
            }, children=[
                html.Div(rec["parameter"].replace("_", " ").title(), style={
                    "fontSize": "9px", "color": t["subtext"],
                    "textTransform": "uppercase", "letterSpacing": "0.5px",
                    "marginBottom": "4px",
                }),
                html.Div(style={
                    "display": "flex", "alignItems": "center",
                    "justifyContent": "flex-end", "gap": "4px",
                }, children=[
                    html.Span(dir_icon, style={
                        "fontSize": "14px", "color": dir_color,
                        "fontWeight": "800",
                    }),
                    html.Span(rec["suggested_delta"], style={
                        "fontSize": "14px", "fontWeight": "700",
                        "color": dir_color, "fontFamily": "var(--font-mono)",
                    }),
                ]),
            ]),
        ]

    return html.Div(style={
        "display": "flex", "alignItems": "flex-start",
        "gap": "12px", "padding": "14px 18px",
        "backgroundColor": "rgba(0,0,0,0.15)",
        "border": f"1px solid {t['border']}",
        "borderLeft": f"3px solid {accent_color}",
        "borderRadius": "10px", "marginBottom": "8px",
        "transition": "all 0.2s ease",
    }, children=[
        # Icon
        html.Div(rec["icon"], style={
            "fontSize": "20px", "minWidth": "28px",
            "textAlign": "center", "paddingTop": "2px",
        }),
        # Content
        html.Div(style={"flex": "1"}, children=[
            html.Div(rec["title"], style={
                "fontSize": "13px", "fontWeight": "700",
                "color": t["text"], "marginBottom": "4px",
            }),
            html.Div(rec["detail"], style={
                "fontSize": "12px", "color": t["subtext"],
                "lineHeight": "1.5",
            }),
        ]),
        # Delta panel
        *right_panel,
    ])


# ════════════════════════════════════════════════════════════════════════════
# ANOMALY DETECTION SECTION
# ════════════════════════════════════════════════════════════════════════════

def _build_anomaly_section(dfs, t, C_):
    """Build anomaly detection UI cards from historical comparison."""
    if not dfs:
        return []

    try:
        from core.telemetry_metrics import extract_session_metrics
        from core.anomaly_detector import detect_anomalies
        from services.database import db_load_all_metrics
    except ImportError:
        return []

    try:
        current_metrics = extract_session_metrics(dfs[0])
        historical = db_load_all_metrics()
        anomalies = detect_anomalies(current_metrics, historical)
    except Exception as e:
        print(f"Anomaly detection error: {e}")
        return []

    if not anomalies:
        return []

    children = []

    # Section header
    children.append(html.Div(style={
        "display": "flex", "alignItems": "center", "gap": "10px",
        "marginBottom": "14px",
    }, children=[
        html.Span("🔮", style={"fontSize": "18px"}),
        html.Span("Session Anomaly Detection", style={
            "fontSize": "15px", "fontWeight": "700",
            "color": t["text"],
        }),
        html.Span(f"(vs. {len(historical)} historical sessions)", style={
            "fontSize": "12px", "color": t["subtext"],
        }),
    ]))

    # Anomaly cards
    for a in anomalies:
        sev = a.get("severity", "normal")
        is_bad = a.get("is_bad", False)

        if sev == "anomaly":
            border_color = "#EF4444" if is_bad else "#10B981"
        elif sev == "notable":
            border_color = "#FF8C00"
        elif sev == "info":
            border_color = "#00D4FF"
        else:
            border_color = t["border"]

        # Z-score bar visualization
        z = a.get("z_score", 0)
        z_bar = []
        if abs(z) > 0:
            bar_width = min(abs(z) * 20, 100)
            bar_color = "#EF4444" if is_bad else "#10B981"
            z_bar = [html.Div(style={
                "marginTop": "6px", "display": "flex",
                "alignItems": "center", "gap": "8px",
            }, children=[
                html.Div(style={
                    "flex": "1", "height": "4px",
                    "backgroundColor": "rgba(255,255,255,0.1)",
                    "borderRadius": "2px", "overflow": "hidden",
                }, children=[
                    html.Div(style={
                        "width": f"{bar_width}%", "height": "100%",
                        "backgroundColor": bar_color,
                        "borderRadius": "2px",
                        "transition": "width 0.5s ease",
                    }),
                ]),
                html.Span(f"z={z:.1f}", style={
                    "fontSize": "10px", "color": t["subtext"],
                    "fontFamily": "var(--font-mono)",
                }),
            ])]

        children.append(html.Div(style={
            "display": "flex", "alignItems": "flex-start",
            "gap": "12px", "padding": "12px 16px",
            "backgroundColor": "rgba(0,0,0,0.15)",
            "border": f"1px solid {t['border']}",
            "borderLeft": f"3px solid {border_color}",
            "borderRadius": "10px", "marginBottom": "6px",
        }, children=[
            html.Div(a.get("icon", "•"), style={
                "fontSize": "18px", "minWidth": "24px", "textAlign": "center",
            }),
            html.Div(style={"flex": "1"}, children=[
                html.Div(a.get("label", ""), style={
                    "fontSize": "12px", "fontWeight": "700",
                    "color": t["text"], "marginBottom": "2px",
                }),
                html.Div(a.get("message", ""), style={
                    "fontSize": "11px", "color": t["subtext"],
                    "lineHeight": "1.4",
                }),
                *z_bar,
            ]),
        ]))

    return children
