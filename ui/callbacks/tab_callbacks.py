"""Sekme geçişi ve sekme içi etkileşim callback'leri."""
from app_context import *  # noqa: F401,F403
from app_context import app, _DATA  # noqa: F401
from utils.logger import get_logger

log = get_logger(__name__)
from app_context import _render_ai_engineer, _render_brakes, _render_channel_gps, _render_database, _render_dynamics, _render_fuel, _render_overlay, _render_overview, _render_sectors, _render_setup_advisor, _render_setup_delta, _render_setup_log, _render_tire_tab  # noqa: F401

@app.callback(Output('tab-content', 'children', allow_duplicate=True), Input('tabs', 'value'), Input('unit-store', 'data'), State('theme-store', 'data'), State('session-id-store', 'data'), State('color-store', 'data'), prevent_initial_call=True)
def switch_tab(tab, unit, mode, session_id, colors):
    """Sekme içeriğini render eder; sekme çökerse hatayı loglar ve okunur bir mesaj gösterir."""
    try:
        return _switch_tab_impl(tab, unit, mode, session_id, colors)
    except Exception as e:
        log.exception("Tab '%s' render failed", tab)
        return html.Div([
            html.Div(f"⚠️ The '{tab}' tab could not be rendered.", style={'fontWeight': '700', 'marginBottom': '6px'}),
            html.Div("The loaded file may be missing channels this tab needs "
                     "(for example Brake, Throttle or GPS).", style={'fontSize': '13px'}),
            html.Div(f"{type(e).__name__}: {e}", style={'fontSize': '12px', 'opacity': 0.7, 'marginTop': '8px'}),
        ], style={'color': '#F59E0B', 'padding': '20px'})


def _switch_tab_impl(tab, unit, mode, session_id, colors):
    dfs = _DATA.get('dfs', [])
    metas = _DATA.get('metas', [])
    tas = _DATA.get('tas', [])
    _DATA['mode'] = mode
    if (tab == 'database'):
        return _render_database(mode)
    if (tab == 'setup'):
        return _render_setup_log(dfs, metas, mode, session_id)
    if (tab == 'setup_advisor'):
        return _render_setup_advisor(dfs, metas, mode, unit)
    if (tab == 'setup_delta'):
        return _render_setup_delta(mode)
    if ((not dfs) and session_id):
        log.debug(f'Memory empty, auto-restoring session #{session_id}')
        (df_r, meta_r) = db_load_session_data(session_id)
        if (df_r is not None):
            (dfs, metas) = ([df_r], [meta_r])
            tas_r = []
            if TIRE_OK:
                preset = TYRE_PRESETS.get('slick_medium', TYRE_PRESETS['slick_medium'])
                try:
                    tas_r = [TireAnalyzer(df_r, opt_range=preset['surface'], unit=unit)]
                except Exception:
                    pass
            _DATA.update({'dfs': dfs, 'metas': metas, 'tas': tas_r, 'mode': mode})
            tas = tas_r
    if (not dfs):
        return html.Div('⚠️ No telemetry loaded. Upload .ibt or .csv files, then click Analyse.', style={'color': '#4A5060', 'padding': '20px', 'textAlign': 'center', 'fontSize': '14px'})
    if (tab == 'overview'):
        return _render_overview(dfs, metas, mode, unit=unit, colors=colors)
    if (tab == 'sectors'):
        return _render_sectors(dfs, mode)
    if (tab == 'channel_gps'):
        return _render_channel_gps(dfs, mode)
    if (tab == 'overlay'):
        return _render_overlay(dfs, mode)
    if (tab == 'brakes'):
        return _render_brakes(dfs, mode)
    if (tab == 'dynamics'):
        from ui.tabs.dynamics import _render_dynamics
        return _render_dynamics(dfs, mode)
    if (tab == 'driving_style'):
        from ui.tabs.driving_style import _render_driving_style
        return _render_driving_style(dfs, mode)
    if (tab == 'tire'):
        return _render_tire_tab(dfs, mode, unit=unit)
    if (tab == 'fuel'):
        return _render_fuel(dfs, metas, mode)
    if (tab == 'ai_engineer'):
        return _render_ai_engineer(dfs, mode)
    return html.Div('Unknown tab.')

@app.callback(Output('fuel-pit-window-out', 'children'), Input('fuel-tank-input', 'value'), Input('fuel-laps-left-input', 'value'), State('theme-store', 'data'), prevent_initial_call=True)
def update_fuel_pit_window(tank, laps_left, mode):
    return pit_window_children(_DATA.get('dfs', []), tank, laps_left, mode or 'dark')

@app.callback(Output('tab-content', 'children', allow_duplicate=True), Input('channel-gps-dd', 'value'), State('theme-store', 'data'), prevent_initial_call=True)
def update_channel_gps(channel, mode):
    dfs = _DATA.get('dfs', [])
    if ((not dfs) or (not channel)):
        return no_update
    return _render_channel_gps(dfs, mode, channel)

@app.callback(
    Output("overview-map-graph", "figure"),
    Input("overview-lap-table", "selected_rows"),
    State("overview-lap-table", "data"),
    State("theme-store", "data"),
    State("unit-store", "data"),
    prevent_initial_call=True
)
def update_overview_map(selected_rows, table_data, mode, unit):
    dfs = _DATA.get("dfs", [])
    if not dfs: return no_update

    from plotting.gps_maps import fig_gps_speed
    
    if not selected_rows or not table_data:
        return fig_gps_speed(dfs, mode, unit)
        
    try:
        idx = selected_rows[0]
        row = table_data[idx]
        driver = row.get("Driver")
        lap_num = row.get("LapNumber")
        
        filtered_dfs = []
        for df in dfs:
            if df["Driver"].iloc[0] == driver:
                # Find the single lap or just use it all if error
                lap_df = df[df["LapNumber"] == lap_num].copy()
                if not lap_df.empty:
                    filtered_dfs.append(lap_df)
                else:
                    filtered_dfs.append(df)
            else:
                pass # only show selected driver
                
        if not filtered_dfs:
            return fig_gps_speed(dfs, mode, unit)
            
        fig = fig_gps_speed(filtered_dfs, mode, unit)
        fig.layout.title.text = f"📍 GPS Speed Map — {driver} (Lap {lap_num})"
        return fig
    except Exception as e:
        log.error(f"Overview map error: {e}")
        return no_update

@app.callback(Output('tab-content', 'children', allow_duplicate=True), Input('overlay-channels-dd', 'value'), Input('overlay-laps-dd', 'value'), State('theme-store', 'data'), prevent_initial_call=True)
def update_overlay(channels, selected_laps, mode):
    dfs = _DATA.get('dfs', [])
    if (not dfs):
        return no_update
    return _render_overlay(dfs, mode, channels, selected_laps=selected_laps)

@app.callback(Output('tab-content', 'children', allow_duplicate=True), Input('tire-type-dd', 'value'), State('theme-store', 'data'), State('unit-store', 'data'), prevent_initial_call=True)
def update_tire_type(tire_type, mode, unit):
    dfs = _DATA.get('dfs', [])
    if (not dfs):
        return no_update
    return _render_tire_tab(dfs, mode, tire_type=tire_type, unit=unit)

@app.callback(
    Output('sectors-mini-sector-graph', 'figure'), 
    Output('sectors-corner-comparison', 'figure'),
    Output('sectors-mini-sector-table-container', 'children'),
    Input('sectors-mini-sector-ref-mode', 'value'), 
    State('theme-store', 'data'), 
    prevent_initial_call=True
)
def update_sectors_sector_map(ref_mode, mode):
    from ui.tabs.sectors import _build_segment_table
    dfs = _DATA.get('dfs', [])
    if (not dfs):
        return (no_update, no_update, no_update)
    
    table_content = _build_segment_table(dfs, ref_mode, mode)
    return (
        fig_mini_sector_map(dfs, mode=mode, ref_mode=ref_mode), 
        fig_corner_comparison(dfs, mode=mode, ref_mode=ref_mode),
        table_content
    )

@app.callback(Output('brakes-multi-comparison-graph', 'figure'), Input('brakes-turn-selector', 'value'), State('theme-store', 'data'), prevent_initial_call=True)
def update_brake_comparison_graph(turn_label, mode):
    dfs = _DATA.get('dfs', [])
    if (not dfs):
        return no_update
    return fig_multi_brake_comparison(dfs, turn_label=turn_label, mode=mode)
