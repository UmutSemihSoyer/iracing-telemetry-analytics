"""Snapshot ve PDF dışa aktarma callback'leri."""
from app_context import *  # noqa: F401,F403
from app_context import app, _DATA  # noqa: F401

from utils.logger import get_logger
log = get_logger(__name__)

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
        log.error(f'PDF export failed: {e}')
        return (no_update, '⬇ PDF')
