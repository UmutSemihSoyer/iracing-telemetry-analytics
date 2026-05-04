import dash
from dash import html, dcc, dash_table
from ui.components import card, btn, inp, G
from utils import TH, apply_theme
import numpy as np
import pandas as pd
from services.telemetry_service import lap_times, predict_fuel_strategy
from utils import PALETTE
from plotting.gps_maps import fig_gps_speed
from plotting.overlays import fig_lap_compare
from plotting.gps_maps import get_plottable_channels
from core.corner_detector import calculate_optimal_lap_time
from utils import infer_hz

# Placeholders for plotting functions that will be imported in app.py or here


def _render_overview(dfs, metas, mode, unit="metric", colors=None):
    t  = TH(mode); C_ = card(mode)
    if colors is None:
        colors = {'best':'#5eead4','outlap':'#93c5fd','inlap':'#fdba74','invalid':'#fca5a5','safety':'#fde68a','reset':'#c4b5fd'}
    combined = pd.concat(dfs, ignore_index=True)
    lt       = lap_times(combined, flying_only=False)
    primary  = dfs[0]

    # Unit conversion
    spd_mult = 3.6 if unit == "metric" else 2.23694
    unit_name = "km/h" if unit == "metric" else "mph"

    driver_cards = []
    for i,(df,meta) in enumerate(zip(dfs,metas)):
        color=PALETTE[i%len(PALETTE)]
        d_lt_flying = lap_times(df, flying_only=True)
        best_t = d_lt_flying.iloc[0]["Time_str"] if not d_lt_flying.empty else "?"
        best_s = d_lt_flying.iloc[0]["Time_s"] if not d_lt_flying.empty else 0.0
        
        # Calculate Optimal Lap
        hz = infer_hz(df)
        opt_s, opt_str = calculate_optimal_lap_time(df, hz)
        potential = best_s - opt_s if (best_s > 0 and opt_s > 0) else 0.0
        
        avg_fuel = 0.0
        recent_fuel = 0.0
        fuel_rem = 0.0
        stint_count = 1
        if "FuelLevel" in df.columns:
            strategy = predict_fuel_strategy(df)
            if strategy:
                avg_fuel = strategy["avg_per_lap"]
                recent_fuel = strategy["recent_avg"]
                fuel_rem = strategy["remaining"]
                stint_count = strategy["stint_count"]
            
        est_laps = f"{fuel_rem/recent_fuel - 0.5:.1f}" if recent_fuel > 0 else "—"
        if est_laps != "—" and float(est_laps) < 0: est_laps = "0.0"
        n_flying = len(d_lt_flying)

        def _metric(label, value, val_color=t["accent"]):
            return html.Div(style={"textAlign":"center","minWidth":"70px"}, children=[
                html.Div(label, className="metric-label"),
                html.Div(value, style={"fontSize":"15px","fontWeight":"700",
                         "fontFamily":"var(--font-mono)","color":val_color}),
            ])

        metrics = [
            _metric("Best Lap", best_t, t["gold"]),
            _metric("Optimal Lap", opt_str, "#A855F7"),
            _metric("Potential", f"-{potential:.3f}s" if potential > 0.001 else "—", t["good"] if potential > 0.1 else t["subtext"]),
            _metric("Max Speed", f"{df['Speed'].max()*spd_mult:.1f} {unit_name}"),
            _metric("Laps", str(n_flying)),
        ]
        if "FuelLevel" in df.columns:
            metrics.append(_metric("Stint", str(stint_count), "#A855F7"))
            metrics.append(_metric("Fuel/Lap", f"{recent_fuel:.2f}L", t["warn"]))
            metrics.append(_metric("Laps Left", est_laps, t["good"] if est_laps != "—" else t["subtext"]))

        driver_cards.append(html.Div(style={
            "background": f"linear-gradient(135deg, {t['panel']}, rgba(0,0,0,0.3))",
            "borderRadius": "12px",
            "border": f"1px solid {color}40",
            "borderLeft": f"4px solid {color}",
            "padding": "18px 20px", "flex": "1",
            "backdropFilter": "blur(12px)",
            "transition": "all 0.3s ease",
        }, children=[
            html.Div(style={"display":"flex","justifyContent":"space-between","alignItems":"center",
                            "marginBottom":"12px"}, children=[
                html.Div([
                    html.Div(f"🏎️ {df['Driver'].iloc[0]}",
                             style={"color":color,"fontWeight":"700","fontSize":"15px"}),
                    html.Div(f"{meta.get('car_name','?')} · {meta.get('track','?')}",
                             style={"color":t["subtext"],"fontSize":"11px","marginTop":"4px"}),
                ]),
            ]),
            html.Div(style={"display":"flex","gap":"20px","flexWrap":"wrap","justifyContent":"space-around"},
                     children=metrics),
        ]))

    # ── Weather / Conditions bar ──
    meta0 = metas[0] if metas else {}
    air_t = meta0.get("air_temp", "?")
    trk_t = meta0.get("track_temp", "?")
    weather = meta0.get("weather", "?")
    series = meta0.get("series", "?")
    
    # Try to extract wind info from meta
    wind_speed = meta0.get("wind_speed", "")
    wind_dir = meta0.get("wind_dir", "")
    humidity = meta0.get("humidity", "")
    
    conditions_items = []
    if weather and weather != "?":
        conditions_items.append(html.Span(f"☁️ {weather}", style={"marginRight": "18px"}))
    if air_t and air_t != "?":
        conditions_items.append(html.Span(f"🌡️ Air: {air_t}°C", style={"marginRight": "18px"}))
    if trk_t and trk_t != "?":
        conditions_items.append(html.Span(f"🛣️ Track: {trk_t}°C", style={"marginRight": "18px"}))
    if humidity:
        conditions_items.append(html.Span(f"💧 Humidity: {humidity}%", style={"marginRight": "18px"}))
    if wind_speed:
        wind_str = f"💨 Wind: {wind_speed} m/s"
        if wind_dir:
            wind_str += f" ({wind_dir}°)"
        conditions_items.append(html.Span(wind_str, style={"marginRight": "18px"}))
    if series and series != "?":
        conditions_items.append(html.Span(f"🏁 {series}", style={"marginRight": "18px"}))

    conditions_bar = html.Div()
    if conditions_items:
        conditions_bar = html.Div(style={
            **C_, "padding": "10px 20px", "marginBottom": "16px",
            "display": "flex", "alignItems": "center", "flexWrap": "wrap", "gap": "4px",
        }, children=[
            html.Span("📋 Session Conditions: ", style={
                "fontWeight": "700", "color": t["accent"], "fontSize": "12px", "marginRight": "12px",
            }),
            html.Div(style={"display": "flex", "flexWrap": "wrap", "gap": "4px",
                           "color": t["subtext"], "fontSize": "12px", "fontFamily": "var(--font-mono)"},
                    children=conditions_items),
        ])

    return html.Div(className="fade-in", children=[
        html.Div(style={"display":"flex","gap":"16px","marginBottom":"20px"},
                 children=driver_cards),
        conditions_bar,
        html.Div(style={**C_,"padding":"16px 20px"}, children=[
            html.Div("🏆 Lap Times (🔍 Click a row to view the lap on the map)", className="section-title", style={"color":t["gold"]}),
            dash_table.DataTable(
                id="overview-lap-table",
                row_selectable="single",
                data=lt.drop(columns=["Time_s"],errors="ignore").to_dict("records"),
                columns=[{"name":c,"id":c} for c in lt.columns if c!="Time_s"],
                style_header={"backgroundColor":"rgba(0,0,0,0.3)","color":t["gold"],
                               "fontFamily":"var(--font-mono)",
                               "fontSize":"10px","fontWeight":"bold","textTransform":"uppercase",
                               "letterSpacing":"0.5px"},
                style_cell={"backgroundColor":t["panel"],"color":t["text"],
                            "fontFamily":"'Crimson Text', 'Times New Roman', Georgia, serif","fontSize":"13px",
                            "border":f"1px solid {t['border']}",
                            "padding":"8px 12px","textAlign":"center"},
                style_data_conditional=[
                    {"if":{"filter_query":"{Rank} = 1"},
                     "backgroundColor":f"{colors['best']}14","color":colors["best"],"fontWeight":"bold"},
                    {"if":{"filter_query":'{LapType} = "Outlap"'},
                     "backgroundColor":f"{colors['outlap']}10","color":colors["outlap"],"fontStyle":"italic"},
                    {"if":{"filter_query":'{LapType} = "Inlap"'},
                     "backgroundColor":f"{colors['inlap']}10","color":colors["inlap"],"fontStyle":"italic"},
                    {"if":{"filter_query":'{LapType} = "DNF"'},
                     "backgroundColor":f"{colors['invalid']}10","color":colors["invalid"],"textDecoration":"line-through"},
                    {"if":{"filter_query":'{LapType} = "Unknown"'},
                     "color":t["subtext"],"fontStyle":"italic"},
                    {"if":{"filter_query":'{LapType} = "Safety Car"'},
                     "backgroundColor":f"{colors['safety']}14","color":colors["safety"]},
                    {"if":{"filter_query":'{LapType} = "Invalid"'},
                     "backgroundColor":f"{colors['invalid']}14","color":colors["invalid"],"textDecoration":"line-through"},
                    {"if":{"filter_query":'{LapType} = "Active Reset"'},
                     "backgroundColor":f"{colors['reset']}10","color":colors["reset"],"fontStyle":"italic"},
                    # Driving style highlights (if more than 5% coast or 2% overlap, warn)
                    {"if":{"filter_query":'{Coasting (%)} >= "5.0%"'},
                     "color":colors["inlap"],"fontWeight":"bold"},
                    {"if":{"filter_query":'{Coasting (%)} >= "10.0%"'},
                     "color":colors["invalid"],"fontWeight":"bold"},
                    {"if":{"filter_query":'{Overlap (%)} >= "2.0%"'},
                     "color":colors["invalid"]},
                ],
                sort_action="native",page_size=12)]),
        
        # GPS/Lap Comparison Grid (Now single column/full width)
        html.Div(style={"marginTop":"16px"}, children=[
            G(fig_gps_speed(dfs,mode,unit=unit), mode, full=True, id="overview-map-graph"),
            html.Div(style={"marginTop":"16px"}, children=[
                G(fig_lap_compare(dfs,mode,unit), mode,full=True)
            ]),
        ]),
    ])