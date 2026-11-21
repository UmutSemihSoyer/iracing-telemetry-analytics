"""Oturum kaydet/geri yükle/sil, setup ve setup delta callback'leri."""
from app_context import *  # noqa: F401,F403
from app_context import app, _DATA  # noqa: F401
from app_context import _render_database  # noqa: F401

@app.callback(Output('session-id-store', 'data'), Output('upload-status', 'children', allow_duplicate=True), Input('save-db-btn', 'n_clicks'), State('compound-dd', 'value'), prevent_initial_call=True)
def save_to_db(_, compound):
    dfs = _DATA.get('dfs', [])
    metas = _DATA.get('metas', [])
    if (not dfs):
        return (no_update, 'No data loaded.')
    ids = []
    for (df, meta) in zip(dfs, metas):
        lt = lap_times(df)
        sid = db_save_session(meta, lt, compound=compound, telemetry_df=df)
        ids.append(sid)
    return ((ids[0] if ids else None), f'[OK] Saved {len(ids)} session(s) + telemetry to database.')

@app.callback(Output('session-id-store', 'data', allow_duplicate=True), Output('tab-content', 'children', allow_duplicate=True), Output('upload-status', 'children', allow_duplicate=True), Output('tabs', 'value', allow_duplicate=True), Input({'type': 'restore-btn', 'index': dash.ALL}, 'n_clicks'), State('theme-store', 'data'), prevent_initial_call=True)
def restore_session(n_clicks, mode):
    if ((not n_clicks) or (not any((x for x in n_clicks if x)))):
        return (no_update, no_update, no_update, no_update)
    triggered = ctx.triggered_id
    if ((not triggered) or (not isinstance(triggered, dict))):
        return (no_update, no_update, no_update, no_update)
    session_id = triggered['index']
    (df, meta) = db_load_session_data(session_id)
    if (df is None):
        return (no_update, no_update, f'[FAIL] Could not load session #{session_id}.', no_update)
    dfs = [df]
    metas = [meta]
    tas = []
    if TIRE_OK:
        preset = TYRE_PRESETS.get('slick_medium', TYRE_PRESETS['slick_medium'])
        try:
            tas.append(TireAnalyzer(df, opt_range=preset['surface']))
        except Exception:
            pass
    _DATA.update({'dfs': dfs, 'metas': metas, 'tas': tas, 'mode': mode})
    total = len(df)
    driver = meta.get('driver_name', '?')
    track = meta.get('track', '?')
    status = f'🔄 Restored session #{session_id}: {driver} @ {track} — {total:,} rows'
    return (session_id, no_update, status, 'overview')

@app.callback(Output('tab-content', 'children', allow_duplicate=True), Output('upload-status', 'children', allow_duplicate=True), Input({'type': 'delete-btn', 'index': dash.ALL}, 'n_clicks'), State('theme-store', 'data'), prevent_initial_call=True)
def delete_session(n_clicks, mode):
    if ((not n_clicks) or (not any((x for x in n_clicks if x)))):
        return (no_update, no_update)
    triggered = ctx.triggered_id
    if ((not triggered) or (not isinstance(triggered, dict))):
        return (no_update, no_update)
    session_id = triggered['index']
    db_delete_session(session_id)
    return (_render_database(mode), f'🗑️ Session #{session_id} deleted from services.database.')

@app.callback(Output('setup-save-status', 'children'), Input('setup-save-btn', 'n_clicks'), State('session-id-store', 'data'), State('s-fw', 'value'), State('s-rw', 'value'), State('s-fl-spr', 'value'), State('s-fr-spr', 'value'), State('s-rl-spr', 'value'), State('s-rr-spr', 'value'), State('s-fl-cam', 'value'), State('s-fr-cam', 'value'), State('s-fl-toe', 'value'), State('s-fr-toe', 'value'), State('s-fl-rh', 'value'), State('s-fr-rh', 'value'), State('s-fl-cp', 'value'), State('s-fr-cp', 'value'), State('s-rl-cp', 'value'), State('s-rr-cp', 'value'), State('s-bb', 'value'), State('s-de', 'value'), State('s-dm', 'value'), State('s-dx', 'value'), State('s-notes', 'value'), State('compound-dd', 'value'), prevent_initial_call=True)
def save_setup(_, session_id, fw, rw, fl_s, fr_s, rl_s, rr_s, fl_c, fr_c, fl_t, fr_t, fl_r, fr_r, fl_p, fr_p, rl_p, rr_p, bb, de, dm, dx, notes, compound):
    if (not session_id):
        return '[FAIL] Save session to DB first.'
    setup = dict(front_wing=fw, rear_wing=rw, fl_spring=fl_s, fr_spring=fr_s, rl_spring=rl_s, rr_spring=rr_s, fl_camber=fl_c, fr_camber=fr_c, fl_toe=fl_t, fr_toe=fr_t, fl_ride_h=fl_r, fr_ride_h=fr_r, fl_cold_p=fl_p, fr_cold_p=fr_p, rl_cold_p=rl_p, rr_cold_p=rr_p, compound=compound, brake_bias=bb, diff_entry=de, diff_mid=dm, diff_exit=dx, notes=notes)
    db_save_setup(session_id, setup)
    return '[OK] Setup saved to database.'

@app.callback(
    Output("rating-save-status", "children"),
    Input("save-rating-btn", "n_clicks"),
    State("setup-rating-radio", "value"),
    State("session-id-store", "data"),
    prevent_initial_call=True
)
def save_setup_rating(n_clicks, rating, session_id):
    if not n_clicks or not rating or not session_id:
        return ""
    try:
        from services.database import db_save_rating
        db_save_rating(session_id, int(rating))
        return "✅ Saved"
    except Exception as e:
        return f"❌ Error: {e}"

def _setup_input(label, id_, default=None):
    return html.Div([html.Label(label, style={'fontSize': '11px', 'color': 'var(--text-muted)', 'display': 'block', 'marginBottom': '4px', 'fontWeight': '600'}), dcc.Input(id=id_, value=default, type='number', style={'backgroundColor': 'rgba(0,0,0,0.2)', 'color': 'var(--text-primary)', 'border': '1px solid var(--border-color)', 'borderRadius': '8px', 'padding': '8px 12px', 'fontSize': '13px', 'width': '100px'})])

@app.callback(Output('setup-delta-content', 'children'), Input('sd-session-a', 'value'), Input('sd-session-b', 'value'), State('theme-store', 'data'), State('unit-store', 'data'), prevent_initial_call=False)
def update_setup_delta(id_a, id_b, mode, unit_store):
    if ((not id_a) or (not id_b)):
        return ''
    t = TH(mode)
    C_ = card(mode)
    sess_a_all = db_load_sessions()
    sess_a = (sess_a_all[(sess_a_all['id'] == id_a)] if (not sess_a_all.empty) else pd.DataFrame())
    sess_b_all = db_load_sessions()
    sess_b = (sess_b_all[(sess_b_all['id'] == id_b)] if (not sess_b_all.empty) else pd.DataFrame())
    set_a = db_load_setup(id_a)
    set_b = db_load_setup(id_b)
    if ((not set_a) or (not set_b)):
        return html.Div('Setup data missing for one of the sessions.', style={'color': t['subtext'], 'padding': '16px'})
    time_a = (sess_a.iloc[0]['best_lap_s'] if (not sess_a.empty) else 0)
    time_b = (sess_b.iloc[0]['best_lap_s'] if (not sess_b.empty) else 0)
    delta_s = (time_b - time_a)
    delta_color = ('#10B981' if (delta_s < 0) else '#EF4444')
    delta_str = (f'{delta_s:+.3f}s' if ((time_a > 0) and (time_b > 0)) else 'N/A')

    # Performance Correlation Logic
    max_a = (sess_a.iloc[0]['max_speed'] if (not sess_a.empty and 'max_speed' in sess_a.columns) else 0)
    max_b = (sess_b.iloc[0]['max_speed'] if (not sess_b.empty and 'max_speed' in sess_b.columns) else 0)
    spd_mult = 3.6 if (unit_store == 'metric') else 2.23694
    unit_nm = ('km/h' if (unit_store == 'metric') else 'mph')
    
    spd_delta = (max_b - max_a) * spd_mult
    spd_color = ('#10B981' if (spd_delta > 0.5) else '#EF4444')
    if (abs(spd_delta) < 0.5): spd_color = t['subtext']

    # Automated Engineering Verdict
    verdict = "Compare two setups to see performance corellation."
    icon = "📊"
    v_col = t['accent']
    
    rw_a = set_a.get('rear_wing', 0) or 0
    rw_b = set_b.get('rear_wing', 0) or 0
    rw_diff = rw_b - rw_a
    
    if abs(rw_diff) > 0.001:
        if rw_diff < 0 and spd_delta > 1.0:
            verdict = f"Aero Efficiency: Removing wing gained {spd_delta:.1f} {unit_nm} on straights."
            icon = "🚀"
        elif rw_diff > 0 and spd_delta < -1.0:
            verdict = f"Drag Impact: Increasing wing cost {abs(spd_delta):.1f} {unit_nm} in top speed."
            icon = "📉"
        
        if delta_s < -0.05:
            verdict += " Overall lap time improved."
            v_col = t['good']
        elif delta_s > 0.05:
            verdict += " However, overall lap time was slower."
            v_col = t['warn']
    cats = {'Aero': ['front_wing', 'rear_wing'], 'Springs': ['fl_spring', 'fr_spring', 'rl_spring', 'rr_spring'], 'Camber': ['fl_camber', 'fr_camber', 'rl_camber', 'rr_camber'], 'Toe': ['fl_toe', 'fr_toe', 'rl_toe', 'rr_toe'], 'Ride Height': ['fl_ride_h', 'fr_ride_h', 'rl_ride_h', 'rr_ride_h'], 'Cold Pressure': ['fl_cold_p', 'fr_cold_p', 'rl_cold_p', 'rr_cold_p'], 'Diff': ['diff_entry', 'diff_mid', 'diff_exit'], 'Brakes': ['brake_bias']}
    rows = []
    for (cat, keys) in cats.items():
        rows.append(html.Tr([html.Th(cat, colSpan=4, style={'backgroundColor': 'rgba(0,212,255,0.08)', 'color': t['accent'], 'padding': '8px 12px', 'textAlign': 'left', 'fontWeight': '700', 'fontSize': '12px', 'borderBottom': f"1px solid {t['border']}"})]))
        for k in keys:
            v_a = set_a.get(k, 0)
            if (v_a is None):
                v_a = 0
            v_b = set_b.get(k, 0)
            if (v_b is None):
                v_b = 0
            try:
                diff = (float(v_b) - float(v_a))
            except (TypeError, ValueError):
                diff = 0
            if (abs(diff) > 0.001):
                col = ('#10B981' if (diff > 0) else '#EF4444')
                diff_str = f'{diff:+.2f}'
            else:
                col = t.get('subtext', '#888')
                diff_str = '='
            val_a_str = (f'{v_a:.2f}' if isinstance(v_a, float) else str(v_a))
            val_b_str = (f'{v_b:.2f}' if isinstance(v_b, float) else str(v_b))
            rows.append(html.Tr([html.Td(k.replace('_', ' ').title(), style={'padding': '6px 12px', 'borderBottom': f"1px solid {t['border']}", 'color': t['text'], 'fontSize': '12px'}), html.Td(val_a_str, style={'padding': '6px 12px', 'borderBottom': f"1px solid {t['border']}", 'color': t['subtext'], 'fontFamily': 'var(--font-mono)', 'fontSize': '12px'}), html.Td(val_b_str, style={'padding': '6px 12px', 'borderBottom': f"1px solid {t['border']}", 'color': t['text'], 'fontFamily': 'var(--font-mono)', 'fontSize': '12px'}), html.Td(diff_str, style={'padding': '6px 12px', 'borderBottom': f"1px solid {t['border']}", 'color': col, 'fontWeight': '700', 'fontFamily': 'var(--font-mono)', 'fontSize': '12px'})]))
    header = html.Div(style={'display': 'flex', 'gap': '16px', 'marginBottom': '16px'}, children=[
        html.Div(style={**C_, 'flex': '1', 'padding': '18px 22px'}, children=[
            html.Div('Lap Time Delta', className='metric-label'),
            html.Div(delta_str, style={'fontSize': '28px', 'fontWeight': '800', 'color': delta_color, 'fontFamily': 'var(--font-mono)'})
        ]),
        html.Div(style={**C_, 'flex': '1', 'padding': '18px 22px'}, children=[
            html.Div(f'Top Speed Delta ({unit_nm})', className='metric-label'),
            html.Div(f"{spd_delta:+.1f}", style={'fontSize': '28px', 'fontWeight': '800', 'color': spd_color, 'fontFamily': 'var(--font-mono)'})
        ]),
        html.Div(style={**C_, 'flex': '2', 'padding': '18px 22px', 'borderLeft': f"4px solid {v_col}"}, children=[
            html.Div('Performance Insight', className='metric-label', style={'color': v_col}),
            html.Div([html.Span(icon, style={'marginRight': '8px'}), html.Span(verdict)], style={'fontSize': '14px', 'fontWeight': '600', 'color': t['text'], 'marginTop': '4px'})
        ]),
    ])
    table = html.Table(style={'width': '100%', 'borderCollapse': 'collapse', 'fontSize': '12px'}, children=[html.Thead(html.Tr([html.Th('Parameter', style={'padding': '10px 12px', 'textAlign': 'left', 'color': t['subtext'], 'fontSize': '10px', 'textTransform': 'uppercase', 'letterSpacing': '0.5px'}), html.Th('Setup A', style={'padding': '10px 12px', 'textAlign': 'left', 'color': t['subtext'], 'fontSize': '10px', 'textTransform': 'uppercase', 'letterSpacing': '0.5px'}), html.Th('Setup B', style={'padding': '10px 12px', 'textAlign': 'left', 'color': t['subtext'], 'fontSize': '10px', 'textTransform': 'uppercase', 'letterSpacing': '0.5px'}), html.Th('Delta', style={'padding': '10px 12px', 'textAlign': 'left', 'color': t['subtext'], 'fontSize': '10px', 'textTransform': 'uppercase', 'letterSpacing': '0.5px'})])), html.Tbody(rows)])
    return html.Div([header, html.Div(table, style={**C_, 'padding': '8px'})])
