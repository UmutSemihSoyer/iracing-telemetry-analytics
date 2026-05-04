from dash import Input, Output, State, html, no_update, MATCH
import json

def register_upload_callbacks(app):
    
    app.clientside_callback(
        """
        async function(n_clicks) {
            if (n_clicks > 0 && window.electronAPI) {
                const paths = await window.electronAPI.openFolderDialog();
                if (paths && paths.length > 0) {
                    return paths[0];
                }
            }
            return window.dash_clientside.no_update;
        }
        """,
        Output('folder-input', 'value'),
        Input('electron-browse-folder-btn', 'n_clicks'),
        prevent_initial_call=True
    )

    app.clientside_callback(
        """
        async function(n_clicks) {
            if (n_clicks > 0 && window.electronAPI) {
                const paths = await window.electronAPI.openFileDialog();
                return paths || [];
            }
            return window.dash_clientside.no_update;
        }
        """,
        Output('electron-file-paths', 'data'),
        Input('electron-browse-files-btn', 'n_clicks'),
        prevent_initial_call=True
    )

    # Handle Drop Zone
    app.clientside_callback(
        """
        function(id) {
            const zone = document.getElementById('electron-drop-zone');
            if (!zone) return window.dash_clientside.no_update;

            zone.addEventListener('dragover', (e) => {
                e.preventDefault();
                e.stopPropagation();
                zone.style.borderColor = 'var(--accent)';
                zone.style.backgroundColor = 'rgba(255,255,255,0.05)';
            });

            zone.addEventListener('dragleave', (e) => {
                e.preventDefault();
                e.stopPropagation();
                zone.style.borderColor = 'var(--border-color)';
                zone.style.backgroundColor = 'rgba(0,0,0,0.1)';
            });

            zone.addEventListener('drop', (e) => {
                e.preventDefault();
                e.stopPropagation();
                zone.style.borderColor = 'var(--border-color)';
                zone.style.backgroundColor = 'rgba(0,0,0,0.1)';

                if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
                    const paths = Array.from(e.dataTransfer.files)
                        .map(f => f.path)
                        .filter(p => p && p.toLowerCase().endsWith('.ibt'));
                    
                    if (paths.length > 0) {
                        const store = document.getElementById('electron-file-paths-hidden-trigger');
                        if (store) {
                            // React-safe value setting
                            const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
                            setter.call(store, JSON.stringify(paths));
                            store.dispatchEvent(new Event('input', { bubbles: true }));
                        }
                    }
                }
            });
            
            return window.dash_clientside.no_update;
        }
        """,
        Output('electron-drop-zone', 'id'),
        Input('electron-drop-zone', 'id')
    )

    app.clientside_callback(
        """
        async function(id) {
            if (window.electronAPI) {
                const path = await window.electronAPI.getDefaultTelemetryPath();
                return path;
            }
            return window.dash_clientside.no_update;
        }
        """,
        Output('folder-input', 'value', allow_duplicate=True),
        Input('root', 'id'),
        prevent_initial_call=True
    )

    app.clientside_callback(
        """
        async function(n_clicks) {
            if (n_clicks > 0 && window.electronAPI) {
                const paths = await window.electronAPI.openFileDialog();
                return paths || [];
            }
            return window.dash_clientside.no_update;
        }
        """,
        Output({'type': 'box-path-store', 'index': MATCH}, 'data'),
        Input({'type': 'electron-box-browse', 'index': MATCH}, 'n_clicks'),
        prevent_initial_call=True
    )

    @app.callback(
        Output({'type': 'up-label', 'index': MATCH}, 'children'),
        Input({'type': 'box-path-store', 'index': MATCH}, 'data'),
        Input({'type': 'up-box', 'index': MATCH}, 'contents'),
        State({'type': 'up-label', 'index': MATCH}, 'id'),
        prevent_initial_call=True
    )
    def update_box_label(native_paths, upload_contents, box_id):
        count = 0
        if native_paths:
            count = len(native_paths)
        elif upload_contents:
            count = len(upload_contents) if isinstance(upload_contents, list) else 1
            
        if count == 0: return no_update
        
        return [
            html.Div('✅', style={'fontSize': '18px', 'color': '#10B981'}),
            html.Div(f'{count} file(s) ready', style={'fontSize': '10px', 'marginTop': '4px', 'color': '#10B981'})
        ]
