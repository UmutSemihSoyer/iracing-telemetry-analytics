"""Dosya yükleme / klasör tarama / analiz çalıştırma callback'leri."""
from app_context import *  # noqa: F401,F403
from app_context import app, _DATA  # noqa: F401
from app_context import _render_overview  # noqa: F401
from services.team_loader import group_by_track, team_tracks, latest_per_driver  # noqa: F401

from utils.logger import get_logger
log = get_logger(__name__)

@app.callback(Output('electron-file-paths', 'data', allow_duplicate=True), Input('electron-file-paths-hidden-trigger', 'value'), prevent_initial_call=True)
def handle_electron_drop(json_paths):
    if not json_paths:
        return dash.no_update
    import json
    try:
        paths = json.loads(json_paths)
        return paths
    except (TypeError, ValueError):
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
    groups = team_tracks(group_by_track(ibts, folder))
    if groups:
        opts = [{'label': f"{trk}  ({len(drv)} drivers)", 'value': trk} for trk, drv in groups.items()]
        selector = html.Div([selector, html.Div(style={'marginTop': '10px'}, children=[
            html.Label('👥 Team compare — fullest file per driver on one track:',
                       style={'fontSize': '11px', 'color': t['subtext'], 'display': 'block', 'marginBottom': '4px'}),
            dcc.Dropdown(id='team-track-dd', options=opts, value=opts[0]['value'], clearable=False,
                         style={'backgroundColor': '#1E2028', 'color': '#C9CDD6', 'border': 'none', 'fontSize': '11px'}),
            html.Button('👥 Load team', id='load-team-btn', style={**btn('#1E2028', '#00D4FF'), 'marginTop': '6px'})])])
    return (f'✅ Found {len(ibts)} IBT files', selector)

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

@app.callback(Output('tab-content', 'children', allow_duplicate=True), Output('upload-status', 'children', allow_duplicate=True), Input('load-selected-btn', 'n_clicks'), State('ibt-file-dd', 'value'), State('compound-dd', 'value'), State('downsample-dd', 'value'), State('theme-store', 'data'), State('unit-store', 'data'), prevent_initial_call=True)
def load_selected_ibts(_, paths, compound, downsample, mode, unit):
    return _load_paths(paths, compound, downsample, mode, unit)


@app.callback(Output('tab-content', 'children', allow_duplicate=True), Output('upload-status', 'children', allow_duplicate=True), Input('load-team-btn', 'n_clicks'), State('team-track-dd', 'value'), State('folder-input', 'value'), State('compound-dd', 'value'), State('downsample-dd', 'value'), State('theme-store', 'data'), State('unit-store', 'data'), prevent_initial_call=True)
def load_team(_, track, folder, compound, downsample, mode, unit):
    if not track or not folder or not os.path.isdir(folder):
        return (no_update, 'Scan a team folder first.')
    paths = latest_per_driver(group_by_track(discover_ibts(folder), folder), track)
    return _load_paths(paths, compound, downsample, mode, unit)


def _load_paths(paths, compound, downsample, mode, unit):
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
            log.error(f'Load error {path}: {e}')
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
def run_analysis(_, contents, filenames, nm1, nm2, nm3, nm4, nm5, nm6, box_paths, compound, downsample, mode, unit):
    try:
        names = [nm1, nm2, nm3, nm4, nm5, nm6]
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
                        log.error(f"Error loading native file {p}: {e}")
            
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
                        log.error(f'Upload error: {e}')
                        
        if (not dfs):
            error_msg = f'[FAIL] {last_error}' if last_error else '[FAIL] No valid telemetry files could be loaded.'
            return (no_update, error_msg, {'textAlign': 'center', 'color': '#FF3B5C', 'padding': '20px'}, '', '🚀 Analyse')
        
        _DATA.update({'dfs': dfs, 'metas': metas, 'tas': tas, 'mode': mode})
        total = sum((len(d) for d in dfs))
        return (_render_overview(dfs, metas, mode, unit), '', {'display': 'none'}, f'✅ {len(dfs)} data source(s) — {total:,} rows', '🚀  Analyse')
    except Exception as e:
        import traceback
        err = traceback.format_exc()
        log.error(err)
        return (no_update, f"CRITICAL ERROR: {str(e)}\n\n{err}", {'color': 'red', 'whiteSpace': 'pre-wrap', 'textAlign': 'left', 'padding': '20px'}, '', '🚀 Analyse')
