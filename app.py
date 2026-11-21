"""
iRacing Telemetry Analytics — giriş noktası.

Dash `app` nesnesi ve paylaşılan bağlam `app_context.py` içinde, callback'ler `ui/callbacks/` altında.
Çalıştırma:  python main.py   (ya da python app.py)
"""
from app_context import *  # noqa: F401,F403  (main.py: app, IBT_OK, DB_PATH)
from app_context import app, _DATA  # noqa: F401
from utils.logger import get_logger

log = get_logger(__name__)

from ui.layout import create_layout
app.layout = create_layout(IS_ELECTRON)

from ui.callbacks.upload_callbacks import register_upload_callbacks
register_upload_callbacks(app)

# Callback modülleri import edilince @app.callback dekoratörleri kayıt olur
import ui.callbacks.ui_callbacks       # noqa: E402,F401
import ui.callbacks.data_callbacks     # noqa: E402,F401
import ui.callbacks.tab_callbacks      # noqa: E402,F401
import ui.callbacks.session_callbacks  # noqa: E402,F401
import ui.callbacks.export_callbacks   # noqa: E402,F401

import core.lap_classifier as lap_classifier  # noqa: E402
log.debug("lap_classifier version: %s (%s)", getattr(lap_classifier, '__VERSION__', 'OLD'), lap_classifier.__file__)

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
