from dash import html, dcc
from utils import TH

def card(mode="dark", extra=None):
    t = TH(mode)
    s = {"backgroundColor": t["panel"], "borderRadius": "12px",
         "border": f"1px solid {t['border']}", "padding": "16px", "marginBottom": "16px",
         "backdropFilter": "blur(12px)", "boxShadow": "0 8px 32px rgba(0, 0, 0, 0.2)",
         "transition": "all 0.3s ease"}
    if extra: s.update(extra)
    return s

def btn(bg="#1E2028", color="#00D4FF"):
    return {"backgroundColor": bg, "color": color, "border": f"1px solid {color}",
            "borderRadius": "8px", "padding": "8px 16px", "cursor": "pointer",
            "fontSize": "13px", "fontWeight": "600", "whiteSpace": "nowrap", "transition": "all 0.2s ease"}

def inp(w="130px"):
    return {"backgroundColor": "rgba(0,0,0,0.2)", "color": "var(--text-primary)", "border": "1px solid var(--border-color)",
            "borderRadius": "6px", "padding": "8px 12px", "fontSize": "13px", "width": w}

def G(fig, mode, full=False, h=None, **kwargs):
    s = {**card(mode), **({"gridColumn":"1/-1"} if full else {})}
    kw = {"config":{"displayModeBar":True,
                    "toImageButtonOptions":{"format":"png","scale":2}}}
    if h: kw["style"] = {"height":f"{h}px"}
    kw.update(kwargs)
    return html.Div(style=s, children=[dcc.Graph(figure=fig, **kw)])

def upload_box(i, is_electron=False):
    return html.Div(style={'display': 'flex', 'flexDirection': 'column', 'gap': '6px'}, children=[
        dcc.Upload(id={'type': 'up-box', 'index': i}, children=html.Div(id={'type': 'up-label', 'index': i}, children=[
            html.Div('📁', style={'fontSize': '18px'}), 
            html.Div(f'Driver {i}', style={'fontSize': '11px', 'marginTop': '4px', 'color': 'var(--text-muted)'})
        ], style={'textAlign': 'center', 'padding': '12px'}), multiple=True, style={'border': '1px dashed var(--border-color)', 'borderRadius': '8px', 'backgroundColor': 'rgba(0,0,0,0.15)', 'cursor': 'pointer'}),
        
        # Native Browse for Electron inside the box
        html.Button('📂 Browse Native', id={'type': 'electron-box-browse', 'index': i}, className='btn-premium', 
                    style={'fontSize': '10px', 'padding': '4px', 'display': 'block' if is_electron else 'none'}),
        dcc.Store(id={'type': 'box-path-store', 'index': i}, data=None),
        
        dcc.Input(id=f'nm{i}', value='', placeholder=f'Driver {i}', type='text', style={'backgroundColor': 'rgba(0,0,0,0.2)', 'color': 'var(--text-primary)', 'border': '1px solid var(--border-color)', 'borderRadius': '6px', 'padding': '6px 10px', 'fontSize': '12px', 'width': '100%'})
    ])
