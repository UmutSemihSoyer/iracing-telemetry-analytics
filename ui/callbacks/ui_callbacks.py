"""Tema, renk ve yükleme etiketi callback'leri."""
from app_context import *  # noqa: F401,F403
from app_context import app, _DATA  # noqa: F401

@app.callback(Output('theme-store', 'data'), Output('theme-btn', 'children'), Output('root', 'style'), Input('theme-btn', 'n_clicks'), State('theme-store', 'data'), prevent_initial_call=True)
def toggle_theme(_, cur):
    new = ('light' if (cur == 'dark') else 'dark')
    t = TH(new)
    return (new, ('🌙 Dark' if (new == 'light') else '☀ Light'), {'backgroundColor': t['bg'], 'color': t['text']})

@app.callback(Output('color-store', 'data'), [Input('clr-best', 'value'), Input('clr-outlap', 'value'), Input('clr-inlap', 'value'), Input('clr-invalid', 'value'), Input('clr-safety', 'value'), Input('clr-reset', 'value')], prevent_initial_call=True)
def update_colors(best, outlap, inlap, invalid, safety, reset):
    return {'best': best or '#5eead4', 'outlap': outlap or '#93c5fd', 'inlap': inlap or '#fdba74', 'invalid': invalid or '#fca5a5', 'safety': safety or '#fde68a', 'reset': reset or '#c4b5fd'}

def _make_upload_callback(i):

    @app.callback(Output(f'up-label-{i}', 'children'), Input(f'up{i}', 'contents'))
    def update_label(contents):
        if (not contents):
            return [html.Div('📁', style={'fontSize': '18px'}), html.Div(f'Driver {i}', style={'fontSize': '10px', 'marginTop': '2px'})]
        return [html.Div('✅', style={'fontSize': '18px'}), html.Div('File Ready', style={'fontSize': '10px', 'marginTop': '2px', 'color': '#00D4AA'})]

for i in range(1, 7):
    _make_upload_callback(i)

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
