"""Paylaşılan uygulama bağlamı: importlar, bayraklar, yardımcılar, _DATA ve Dash `app` nesnesi.
Callback modülleri `from app_context import *` ve gerekirse `from app_context import _DATA` kullanır."""
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
from ui.tabs.fuel import _render_fuel, pit_window_children

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
