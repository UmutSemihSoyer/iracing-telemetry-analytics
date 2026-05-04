import dash
from dash import dcc, html, Input, Output, State, dash_table, no_update, ctx, MATCH, ALL
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import datetime, traceback
from pathlib import Path

# Core / Data / Services
from services.database import *
from services.telemetry_service import *

# UI / Plotting
from ui.components import card, btn, inp, G
from plotting.gps_maps import *
from plotting.overlays import *
from plotting.brakes import *

# Tabs
from ui.tabs.overview import _render_overview
from ui.tabs.dynamics import _render_dynamics
from ui.tabs.sectors import _render_sectors
from ui.tabs.channel_gps import _render_channel_gps
from ui.tabs.overlay import _render_overlay
from ui.tabs.brakes import _render_brakes
from ui.tabs.ai import _render_ai_engineer
from ui.tabs.setup_log import _render_setup_log, _render_setup_delta
from ui.tabs.setup_advisor import _render_setup_advisor
from ui.tabs.database import _render_database
from ui.tabs.tire import _render_tire_tab

# Config
from config import DEFAULT_STACK_CHANNELS
from utils import THEMES, TH, TYRE_PRESETS, PALETTE, apply_theme, no_data_figure

'\niRacing Telemetry Analytics  v9.0  —  Professional Edition\n============================================================\nNEW:\n  • Mini-sector GPS map      — time loss painted on track\n  • Stacked telemetry overlay — multi-channel, multi-driver panels\n  • Brake pedal shape analysis — application rate, peak, release\n  • Any channel on GPS map   — dropdown selector\n  • Local SQLite database    — persistent session history\n  • Setup log                — record car setup per session\n  • Snapshot + annotation    — annotated PNG export\n  • Folder IBT discovery     — drag folder, auto-load all IBTs\n  • Vehicle Dynamics          — slip angle, understeer gradient\n  • Driving Style Metrics    — coasting, trail brake score, throttle smoothness\n\nRequirements:\n    pip install dash plotly pandas numpy scipy dash-bootstrap-components\n    pip install scikit-learn watchdog reportlab kaleido pyyaml pillow\n\nSame-folder files:\n    ibt_parser.py  |  tire_analysis.py  |  pdf_report.py\n    ai_feedback.py |  utils.py          |  corner_detector.py\n    data_loader.py |  lap_classifier.py |  database.py\n\nRun:\n    python app.py  →  http://127.0.0.1:8050\n'
import io, base64, json, datetime, os, glob, sqlite3, zipfile, tempfile, pickle, gzip
import numpy as np
import pandas as pd
from pathlib import Path
from scipy.ndimage import gaussian_filter1d
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import plotly.io as pio
import dash
from dash import dcc, html, Input, Output, State, dash_table, no_update, ctx, MATCH
import dash_bootstrap_components as dbc
try:
    from core.tire_analysis import TireAnalyzer
    TIRE_OK = True
except ImportError:
    TIRE_OK = False
try:
    from services.pdf_report import build_pdf
    PDF_OK = True
except ImportError:
    PDF_OK = False
try:
    from core.ibt_parser import IBTFile, ibt_to_dashboard_df
    IBT_OK = True
except ImportError:
    IBT_OK = False
try:
    from services.ai_feedback import generate_feedback
    AI_OK = True
except ImportError:
    AI_OK = False
try:
    from core.corner_detector import detect_corners, label_segments, build_segment_map, get_segment_summary, compute_corner_deltas
    CORNER_OK = True
except ImportError:
    CORNER_OK = False
try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_OK = True
except ImportError:
    PIL_OK = False
try:
    import kaleido
    KALEIDO_OK = True
except ImportError:
    KALEIDO_OK = False
# from utils import PALETTE, CORNER_COLORS, CORNER_LABELS as CORNER_LABEL, TYRE_PRESETS, THEMES, TH, apply_theme
DB_PATH = Path('iracing_sessions.db')
SAVED_DATA_DIR = Path('saved_sessions')
SAVED_DATA_DIR.mkdir(exist_ok=True)

def fig_brake_consistency(zones_df: pd.DataFrame, mode: str='dark') -> go.Figure:
    'Scatter: track position vs peak brake pressure — consistency view.'
    t = TH(mode)
    fig = make_subplots(rows=1, cols=2, subplot_titles=['Peak Brake vs Track Position', 'Application Rate vs Entry Speed'])
    if zones_df.empty:
        return apply_theme(fig, '🛑 Brake Analysis', mode)
    fig.add_trace(go.Scatter(x=zones_df['Track_Pos_%'], y=zones_df['Peak_Brake_%'], mode='markers+text', marker=dict(color=t['accent'], size=10, opacity=0.8, symbol='triangle-down'), text=[f'Z{z}' for z in zones_df['Zone']], textposition='top center', textfont=dict(size=8), name='Peak Brake'), row=1, col=1)
    fig.add_trace(go.Scatter(x=(zones_df['Entry_Speed'] * 3.6), y=zones_df['App_Rate'], mode='markers', marker=dict(size=12, color=zones_df['App_Rate'], colorscale='RdYlGn_r', showscale=True, colorbar=dict(title='App Rate', len=0.5, x=1.05)), text=[f'Z{z} Trail:{t:.0f}%' for (z, t) in zip(zones_df['Zone'], zones_df['Trail_Brake_%'])], hovertemplate='%{text}<extra></extra>', name='App Rate'), row=1, col=2)
    fig.update_xaxes(title_text='Track Position (%)', row=1, col=1)
    fig.update_yaxes(title_text='Peak Brake (%)', row=1, col=1)
    fig.update_xaxes(title_text='Entry Speed (km/h)', row=1, col=2)
    fig.update_yaxes(title_text='Application Rate', row=1, col=2)
    fig.update_layout(hovermode='closest')
    return apply_theme(fig, '🛑 Brake Consistency & Aggression', mode)

def fig_brake_trail_map(df: pd.DataFrame, mode: str='dark') -> go.Figure:
    'GPS map showing trail-braking depth (% of brake zone with steering).'
    t = TH(mode)
    fig = go.Figure()
    if (('Lat' not in df.columns) or ('Steer' not in df.columns)):
        fig.add_annotation(text='GPS + Steering channels required.', xref='paper', yref='paper', x=0.5, y=0.5, showarrow=False, font=dict(color=t['subtext']))
        return apply_theme(fig, '🗺️ Trail Braking Map', mode)
    d = best_lap_df(df).copy()
    lat_s = gaussian_filter1d(d['Lat'].values, 2)
    lon_s = gaussian_filter1d(d['Lon'].values, 2)
    trail = ((d['Brake'] > 0.1) & (d['Steer'].abs() > 0.08)).values.astype(float)
    trail_colorscale = [[0.0, 'rgb(100,100,80)'], [1.0, 'rgb(168,0,200)']]
    fig.add_trace(go.Scattergl(x=lon_s, y=lat_s, mode='markers', marker=dict(size=4, color=trail, colorscale=trail_colorscale, showscale=False), showlegend=False, hoverinfo='skip'))
    fig.update_yaxes(scaleanchor='x', scaleratio=1, showticklabels=False, showgrid=False, zeroline=False)
    fig.update_xaxes(showticklabels=False, showgrid=False, zeroline=False)
    return apply_theme(fig, '🗺️ Trail Braking Depth Map  (🟣 = trail braking)', mode)

def export_snapshots_zip(figs: dict, annotations: list, session_label: str='') -> bytes:
    '\n    Render each figure to PNG (requires kaleido),\n    add text annotations, bundle into a ZIP.\n    Falls back to HTML if kaleido unavailable.\n    '
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for (name, fig) in figs.items():
            safe_name = name.replace(' ', '_').replace('/', '_')
            try:
                if KALEIDO_OK:
                    img_bytes = pio.to_image(fig, format='png', width=1200, height=600, scale=1.5)
                    if (PIL_OK and annotations):
                        img = Image.open(io.BytesIO(img_bytes)).convert('RGBA')
                        draw = ImageDraw.Draw(img)
                        y_offset = 20
                        for ann in annotations:
                            draw.text((20, y_offset), f'📌 {ann}', fill=(255, 215, 0, 200))
                            y_offset += 24
                        out = io.BytesIO()
                        img.save(out, format='PNG')
                        zf.writestr(f'{safe_name}.png', out.getvalue())
                    else:
                        zf.writestr(f'{safe_name}.png', img_bytes)
                else:
                    html_str = pio.to_html(fig, full_html=True, include_plotlyjs=True)
                    zf.writestr(f'{safe_name}.html', html_str)
            except Exception as e:
                zf.writestr(f'{safe_name}_error.txt', str(e))
        if annotations:
            ann_text = f'''Session: {session_label}

Annotations:
'''
            ann_text += '\n'.join((f'• {a}' for a in annotations))
            zf.writestr('annotations.txt', ann_text)
    return buf.getvalue()
_DATA = {}
db_init()
IS_ELECTRON = os.environ.get('ELECTRON_RUN_AS_NODE', '') == '1'
app = dash.Dash(__name__, title='iRacing Telemetry v9.0', external_stylesheets=[dbc.themes.BOOTSTRAP], suppress_callback_exceptions=True)

from ui.layout import create_layout
app.layout = create_layout(IS_ELECTRON)

from ui.callbacks.upload_callbacks import register_upload_callbacks
register_upload_callbacks(app)

@app.callback(Output('theme-store', 'data'), Output('theme-btn', 'children'), Output('root', 'style'), Input('theme-btn', 'n_clicks'), State('theme-store', 'data'), prevent_initial_call=True)
def toggle_theme(_, cur):
    new = ('light' if (cur == 'dark') else 'dark')
    t = TH(new)
    return (new, ('🌙 Dark' if (new == 'light') else '☀ Light'), {'backgroundColor': t['bg'], 'color': t['text']})

def _make_ibt_selector(ibts, t):
    """Helper to create the IBT selection dropdown and load button."""
    if not ibts:
        return html.Div("No IBT files found.", style={'color': '#EF4444', 'fontSize': '11px'})
    
    options = [{'label': f"{Path(p).name}  ({datetime.datetime.fromtimestamp(os.path.getmtime(p)).strftime('%Y-%m-%d %H:%M')})", 'value': p} for p in ibts[:100]]
    
    return html.Div(style={'marginBottom': '10px'}, children=[
        html.Label(f'Found {len(ibts)} IBT file(s) — select to load:', style={'fontSize': '11px', 'color': t['subtext'], 'display': 'block', 'marginBottom': '4px'}), 
        dcc.Dropdown(id='ibt-file-dd', options=options, value=(options[0]['value'] if options else None), multi=True, style={'backgroundColor': '#1E2028', 'color': '#C9CDD6', 'border': 'none', 'fontSize': '11px'}), 
        html.Button('✅ Load Selected', id='load-selected-btn', style={**btn('#1E2028', '#00D4FF'), 'marginTop': '6px'})
    ])

@app.callback(Output('color-store', 'data'), [Input('clr-best', 'value'), Input('clr-outlap', 'value'), Input('clr-inlap', 'value'), Input('clr-invalid', 'value'), Input('clr-safety', 'value'), Input('clr-reset', 'value')], prevent_initial_call=True)
def update_colors(best, outlap, inlap, invalid, safety, reset):
    return {'best': best or '#5eead4', 'outlap': outlap or '#93c5fd', 'inlap': inlap or '#fdba74', 'invalid': invalid or '#fca5a5', 'safety': safety or '#fde68a', 'reset': reset or '#c4b5fd'}

@app.callback(Output('electron-file-paths', 'data', allow_duplicate=True), Input('electron-file-paths-hidden-trigger', 'value'), prevent_initial_call=True)
def handle_electron_drop(json_paths):
    if not json_paths:
        return dash.no_update
    import json
    try:
        paths = json.loads(json_paths)
        return paths
    except:
        return dash.no_update

@app.callback(
    Output('folder-status', 'children', allow_duplicate=True), 
    Output('ibt-selector-area', 'children', allow_duplicate=True), 
    Input('electron-file-paths', 'data'),
    State('theme-store', 'data'), 
    prevent_initial_call=True
)
def process_electron_paths(paths, mode):
    if not paths:
        return dash.no_update, dash.no_update
    t = TH(mode)
    selector = _make_ibt_selector(paths, t)
    return f'✅ {len(paths)} file(s) ready', selector

@app.callback(Output('folder-status', 'children'), Output('ibt-selector-area', 'children'), Input('scan-btn', 'n_clicks'), State('folder-input', 'value'), State('theme-store', 'data'), prevent_initial_call=True)
def scan_folder(_, folder, mode):
    t = TH(mode)
    if ((not folder) or (not os.path.isdir(folder))):
        return (f'[FAIL] Folder not found: {folder}', html.Div())
    ibts = discover_ibts(folder)
    if (not ibts):
        return (f'No IBT files found in {folder}', html.Div())
    
    selector = _make_ibt_selector(ibts, t)
    return (f'✅ Found {len(ibts)} IBT files', selector)

@app.callback(Output('tab-content', 'children', allow_duplicate=True), Output('upload-status', 'children', allow_duplicate=True), Input('load-selected-btn', 'n_clicks'), State('ibt-file-dd', 'value'), State('compound-dd', 'value'), State('downsample-dd', 'value'), State('theme-store', 'data'), State('unit-store', 'data'), prevent_initial_call=True)
def load_selected_ibts(_, paths, compound, downsample, mode, unit):
    if (not paths):
        return (no_update, 'No files selected.')
    if isinstance(paths, str):
        paths = [paths]
    (dfs, metas, tas) = ([], [], [])
    preset = TYRE_PRESETS.get(compound, TYRE_PRESETS['slick_medium'])
    last_error = None
    for path in paths[:6]:
        try:
            (df, meta) = load_ibt_from_path(path, downsample=downsample)
            if (df is None):
                continue
            dfs.append(df)
            metas.append(meta)
            if TIRE_OK:
                ta = TireAnalyzer(df, opt_range=preset['surface'])
                tas.append(ta)
        except Exception as e:
            import traceback; traceback.print_exc()
            last_error = str(e)
            print(f'Load error {path}: {e}')
    if (not dfs):
        error_msg = f'[FAIL] {last_error}' if last_error else '[FAIL] Could not load any files.'
        return (no_update, error_msg)
    _DATA.update({'dfs': dfs, 'metas': metas, 'tas': tas, 'mode': mode})
    total = sum((len(d) for d in dfs))
    status = f'✅ {len(dfs)} IBT(s) loaded — {total:,} rows'
    return (_render_overview(dfs, metas, mode, unit), status)

@app.callback(
    Output('tab-content', 'children'), 
    Output('status', 'children'), 
    Output('status', 'style'), 
    Output('upload-status', 'children'), 
    Output('go-btn', 'children'), 
    Input('go-btn', 'n_clicks'), 
    State({'type': 'up-box', 'index': ALL}, 'contents'), 
    State({'type': 'up-box', 'index': ALL}, 'filename'), 
    *[State(f'nm{i}', 'value') for i in range(1, 7)], 
    State({'type': 'box-path-store', 'index': ALL}, 'data'),
    State('compound-dd', 'value'), 
    State('downsample-dd', 'value'), 
    State('theme-store', 'data'), 
    State('unit-store', 'data'), 
    prevent_initial_call=True
)
def run_analysis(_, contents, filenames, names, box_paths, compound, downsample, mode, unit):
    (dfs, metas, tas) = ([], [], [])
    preset = TYRE_PRESETS.get(compound, TYRE_PRESETS['slick_medium'])
    last_error = None
    
    # Process both standard uploads and Electron box paths
    for i in range(6):
        nm = names[i] or f'Driver {i+1}'
        
        # Priority 1: Native paths from box-path-store (Electron)
        if i < len(box_paths) and box_paths[i]:
            for p in box_paths[i]:
                try:
                    (df, meta) = load_ibt_from_path(p, downsample=downsample)
                    if df is not None:
                        meta['driver_name'] = nm
                        dfs.append(df)
                        metas.append(meta)
                        if TIRE_OK:
                            tas.append(TireAnalyzer(df, opt_range=preset['surface']))
                except Exception as e:
                    last_error = str(e)
                    print(f"Error loading native file {p}: {e}")
        
        # Priority 2: Standard uploads (Web or Drag-and-drop into box)
        elif i < len(contents) and contents[i]:
            c_list = contents[i] if isinstance(contents[i], list) else [contents[i]]
            f_list = filenames[i] if isinstance(filenames[i], list) else [filenames[i]]
            for (ci, fi) in zip(c_list, f_list):
                try:
                    (df, meta) = load_file(ci, fi, nm, downsample=downsample)
                    dfs.append(df)
                    metas.append(meta)
                    if TIRE_OK:
                        tas.append(TireAnalyzer(df, opt_range=preset['surface']))
                except Exception as e:
                    last_error = str(e)
                    print(f'Upload error: {e}')
                    
    if (not dfs):
        error_msg = f'[FAIL] {last_error}' if last_error else '[FAIL] No valid telemetry files could be loaded.'
        return (no_update, error_msg, {'textAlign': 'center', 'color': '#FF3B5C', 'padding': '20px'}, '', '🚀 Analyse')
    
    _DATA.update({'dfs': dfs, 'metas': metas, 'tas': tas, 'mode': mode})
    total = sum((len(d) for d in dfs))
    return (_render_overview(dfs, metas, mode, unit), '', {'display': 'none'}, f'✅ {len(dfs)} data source(s) — {total:,} rows', '🚀  Analyse')

@app.callback(Output('tab-content', 'children', allow_duplicate=True), Input('tabs', 'value'), Input('unit-store', 'data'), State('theme-store', 'data'), State('session-id-store', 'data'), State('color-store', 'data'), prevent_initial_call=True)
def switch_tab(tab, unit, mode, session_id, colors):
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
        print(f'DEBUG: Memory empty, auto-restoring session #{session_id}')
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
    if (tab == 'ai_engineer'):
        return _render_ai_engineer(dfs, mode)
    return html.Div('Unknown tab.')

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
        print(f"Overview map error: {e}")
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

@app.callback(Output('dl-zip', 'data'), Input('snap-btn', 'n_clicks'), State('annotation-store', 'data'), State('theme-store', 'data'), State('unit-store', 'data'), prevent_initial_call=True)
def snapshot_export(_, annotations, mode, unit):
    dfs = _DATA.get('dfs', [])
    metas = _DATA.get('metas', [])
    if (not dfs):
        return no_update
    primary = dfs[0]
    figs = {
        'GPS_Speed': fig_gps_speed(dfs, mode, unit=unit), 
        'Lap_Comparison': fig_lap_compare(dfs, mode, unit=unit), 
        'Mini_Sector_Map': fig_mini_sector_map(dfs, mode=mode, unit=unit), 
        'Brake_Shapes': fig_brake_shapes(primary, mode, unit=unit)
    }
    session_label = f"{primary['Driver'].iloc[0]}  {metas[0].get('track', '?')}  {datetime.datetime.now().strftime('%Y-%m-%d')}"
    zip_bytes = export_snapshots_zip(figs, (annotations or []), session_label)
    return dict(base64=True, content=base64.b64encode(zip_bytes).decode(), filename=f"iracing_snapshots_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.zip", type='application/zip')

@app.callback(Output('dl-pdf', 'data'), Output('pdf-btn', 'children'), Input('pdf-btn', 'n_clicks'), State('theme-store', 'data'), prevent_initial_call=True)
def export_pdf(_, mode):
    dfs = _DATA.get('dfs', [])
    metas = _DATA.get('metas', [])
    tas = _DATA.get('tas', [])
    if ((not dfs) or (not PDF_OK)):
        return (no_update, no_update)
    try:
        pdf_bytes = build_pdf(dfs, metas, tire_analyzers=tas)
        return (dict(base64=True, content=base64.b64encode(pdf_bytes).decode(), filename='iracing_v9.pdf', type='application/pdf'), '⬇ PDF')
    except Exception as e:
        print(f'PDF: {e}')
        return (no_update, '⬇ PDF')

def _make_upload_callback(i):

    @app.callback(Output(f'up-label-{i}', 'children'), Input(f'up{i}', 'contents'))
    def update_label(contents):
        if (not contents):
            return [html.Div('📁', style={'fontSize': '18px'}), html.Div(f'Driver {i}', style={'fontSize': '10px', 'marginTop': '2px'})]
        return [html.Div('✅', style={'fontSize': '18px'}), html.Div('File Ready', style={'fontSize': '10px', 'marginTop': '2px', 'color': '#00D4AA'})]
for i in range(1, 7):
    _make_upload_callback(i)
import core.lap_classifier as lap_classifier
print(f"DEBUG: Using lap_classifier version: {getattr(lap_classifier, '__VERSION__', 'OLD')}")
print(f'DEBUG: lap_classifier path: {lap_classifier.__file__}')

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

def _setup_input(label, id_, default=None):
    return html.Div([html.Label(label, style={'fontSize': '11px', 'color': 'var(--text-muted)', 'display': 'block', 'marginBottom': '4px', 'fontWeight': '600'}), dcc.Input(id=id_, value=default, type='number', style={'backgroundColor': 'rgba(0,0,0,0.2)', 'color': 'var(--text-primary)', 'border': '1px solid var(--border-color)', 'borderRadius': '8px', 'padding': '8px 12px', 'fontSize': '13px', 'width': '100px'})])
DEFAULT_STACK_CHANNELS = ['Speed', 'Throttle', 'Brake', 'RPM', 'Gear', 'LatAccel']

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
            except:
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

def _make_upload_callback(i):

    @app.callback(Output(f'up-label-{i}', 'children', allow_duplicate=True), Input(f'up{i}', 'filename'), prevent_initial_call=True)
    def update_label(filename):
        if (not filename):
            return dash.no_update
        fname = (filename[0] if isinstance(filename, list) else filename)
        extra = (f' (+{(len(filename) - 1)})' if (isinstance(filename, list) and (len(filename) > 1)) else '')
        return [html.Div('✅', style={'fontSize': '18px'}), html.Div(f'{fname}{extra}', style={'fontSize': '11px', 'marginTop': '4px', 'color': '#10B981', 'wordBreak': 'break-all', 'padding': '0 4px'})]
for _i in range(1, 7):
    _make_upload_callback(_i)

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
if (__name__ == '__main__'):
    print('+--------------------------------------------------+')
    print('|  iRacing Telemetry Analytics  v9.0               |')
    print('|  Professional Edition                             |')
    print('+--------------------------------------------------+')
    print(f'''
  IBT parser:    {('[OK]' if IBT_OK else '[FAIL]  missing ibt_parser.py')}''')
    print('Tire Analyzer OK')
    print('PDF Report OK')
    print('Kaleido OK')
    print('Pillow OK')
    print(f'''
  Database:      {DB_PATH}''')
    print('\nURL:  http://127.0.0.1:8050\n')
    app.run(debug=False, port=8050)
