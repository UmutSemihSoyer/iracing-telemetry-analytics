from dash import dcc, html
from ui.components import upload_box
from utils import TYRE_PRESETS

def create_layout(is_electron: bool) -> html.Div:
    """
    Constructs the main application layout.
    """
    return html.Div(id='root', className='app-container', children=[
        dcc.Store(id='theme-store', data='dark', storage_type='local'), 
        dcc.Store(id='annotation-store', data=[], storage_type='local'), 
        dcc.Store(id='session-id-store', data=None, storage_type='local'),
        dcc.Store(id='unit-store', data='metric', storage_type='local'), 
        dcc.Store(id='color-store', data={'best':'#5eead4','outlap':'#93c5fd','inlap':'#fdba74','invalid':'#fca5a5','safety':'#fde68a','reset':'#c4b5fd'}, storage_type='local'), 
        dcc.Download(id='dl-zip'), dcc.Download(id='dl-pdf'), 
        
        html.Div(className='sidebar', children=[
            html.Div(className='sidebar-header', children=[
                html.Span('iRacing Telemetry', className='brand-title'), 
                html.Span('v9.1 Professional', className='brand-subtitle')
            ]), 
            html.Div(style={'flex': '1', 'padding': '12px 0', 'overflowY': 'auto'}, children=[
                dcc.Tabs(id='tabs', value='overview', vertical=True, parent_style={'flexDirection': 'column', 'display': 'flex'}, style={'border': 'none', 'display': 'flex', 'flexDirection': 'column'}, children=[
                    dcc.Tab(label='📊 Overview', value='overview', className='nav-tab', selected_className='nav-tab-active'), 
                    dcc.Tab(label='🗺️ Sector Map', value='sectors', className='nav-tab', selected_className='nav-tab-active'), 
                    dcc.Tab(label='📡 Channel GPS', value='channel_gps', className='nav-tab', selected_className='nav-tab-active'), 
                    dcc.Tab(label='📈 Overlay', value='overlay', className='nav-tab', selected_className='nav-tab-active'), 
                    dcc.Tab(label='🛑 Brakes', value='brakes', className='nav-tab', selected_className='nav-tab-active'), 
                    dcc.Tab(label='🏎️ Dynamics', value='dynamics', className='nav-tab', selected_className='nav-tab-active'), 
                    dcc.Tab(label='🎯 Driving Style', value='driving_style', className='nav-tab', selected_className='nav-tab-active'), 
                    dcc.Tab(label='🌡️ Tire ', value='tire', className='nav-tab', selected_className='nav-tab-active'), 
                    dcc.Tab(label='🧠 AI Engineer', value='ai_engineer', className='nav-tab', selected_className='nav-tab-active'), 
                    dcc.Tab(label='🔧 Setup Log', value='setup', className='nav-tab', selected_className='nav-tab-active'), 
                    dcc.Tab(label='🧰 Setup Advisor', value='setup_advisor', className='nav-tab', selected_className='nav-tab-active'), 
                    dcc.Tab(label='⚖️ Setup Delta', value='setup_delta', className='nav-tab', selected_className='nav-tab-active'), 
                    dcc.Tab(label='🗄️ Database', value='database', className='nav-tab', selected_className='nav-tab-active')
                ])
            ]), 
            html.Div(style={'padding': '16px 24px', 'display': 'flex', 'flexDirection': 'column', 'gap': '10px', 'maxHeight': '50vh', 'overflowY': 'auto', 'flexShrink': '0'}, children=[
                html.Button('☀ Light / Dark', id='theme-btn', className='btn-premium'), 
                html.Button('💾 Save Session', id='save-db-btn', className='btn-premium', style={'color': '#10B981', 'borderColor': '#10B981'}), 
                html.Button('📸 Snapshot', id='snap-btn', className='btn-premium', style={'display': 'none', 'color': '#A855F7', 'borderColor': '#A855F7'}), 
                dcc.Loading(html.Button('⬇ PDF Report', id='pdf-btn', className='btn-premium', style={'width': '100%', 'color': '#EF4444', 'borderColor': '#EF4444'}), type='circle', color='#EF4444'), 
                html.Details(style={'marginTop':'8px'}, children=[
                    html.Summary('🎨 Table Colors', style={'fontSize':'11px','color':'var(--text-muted)','cursor':'pointer','fontWeight':'600','letterSpacing':'0.5px'}), 
                    html.Div(className='color-settings-panel', children=[
                        html.Div(className='color-swatch', children=[html.Label('Best Lap'), dcc.Input(id='clr-best', type='color', value='#5eead4', style={'width':'28px','height':'22px','padding':'0','border':'1px solid var(--border-color)','borderRadius':'4px','cursor':'pointer'})]), 
                        html.Div(className='color-swatch', children=[html.Label('Outlap'), dcc.Input(id='clr-outlap', type='color', value='#93c5fd', style={'width':'28px','height':'22px','padding':'0','border':'1px solid var(--border-color)','borderRadius':'4px','cursor':'pointer'})]), 
                        html.Div(className='color-swatch', children=[html.Label('Inlap'), dcc.Input(id='clr-inlap', type='color', value='#fdba74', style={'width':'28px','height':'22px','padding':'0','border':'1px solid var(--border-color)','borderRadius':'4px','cursor':'pointer'})]), 
                        html.Div(className='color-swatch', children=[html.Label('Invalid'), dcc.Input(id='clr-invalid', type='color', value='#fca5a5', style={'width':'28px','height':'22px','padding':'0','border':'1px solid var(--border-color)','borderRadius':'4px','cursor':'pointer'})]), 
                        html.Div(className='color-swatch', children=[html.Label('Safety Car'), dcc.Input(id='clr-safety', type='color', value='#fde68a', style={'width':'28px','height':'22px','padding':'0','border':'1px solid var(--border-color)','borderRadius':'4px','cursor':'pointer'})]), 
                        html.Div(className='color-swatch', children=[html.Label('Reset'), dcc.Input(id='clr-reset', type='color', value='#c4b5fd', style={'width':'28px','height':'22px','padding':'0','border':'1px solid var(--border-color)','borderRadius':'4px','cursor':'pointer'})])
                    ])
                ])
            ])
        ]), 
        
        html.Div(className='main-scroll-area', children=[
            html.Div(className='content-padding', children=[
                html.Div(className='glass-panel', style={'padding': '20px'}, children=[
                    html.Div(style={'display': 'flex', 'gap': '12px', 'marginBottom': '12px', 'alignItems': 'flex-end'}, children=[
                        html.Div([
                            html.Label('📂 Telemetry Source', style={'fontSize': '12px', 'color': 'var(--text-muted)', 'display': 'block', 'marginBottom': '6px'}), 
                            html.Div(style={'display': 'flex', 'gap': '8px'}, children=[
                                dcc.Input(id='folder-input', placeholder='Paste path or browse files...', type='text', style={'backgroundColor': 'rgba(0,0,0,0.2)', 'color': 'var(--text-primary)', 'border': '1px solid var(--border-color)', 'borderRadius': '6px', 'padding': '8px 12px', 'fontSize': '13px', 'width': '620px'}), 
                                html.Button('📄 Files', id='electron-browse-files-btn', className='btn-premium', style={'display': 'block' if is_electron else 'none', 'backgroundColor': 'rgba(255,255,255,0.1)'}),
                                html.Button('🔍 Scan', id='scan-btn', className='btn-premium')
                            ])
                        ]), 
                        html.Div(id='folder-status', style={'fontSize': '12px', 'color': 'var(--text-muted)', 'alignSelf': 'center', 'marginLeft': '12px'})
                    ]), 
                    
                    html.Div(id='electron-drop-zone', style={
                        'display': 'flex' if is_electron else 'none',
                        'flexDirection': 'column', 'alignItems': 'center', 'justifyContent': 'center',
                        'padding': '20px', 'border': '2px dashed var(--border-color)', 'borderRadius': '12px',
                        'backgroundColor': 'rgba(0,0,0,0.1)', 'marginBottom': '16px', 'cursor': 'pointer',
                        'transition': 'all 0.3s ease'
                    }, children=[
                        html.Div('📥', style={'fontSize': '24px', 'marginBottom': '8px'}),
                        html.Div('Drag & Drop IBT files here', style={'fontSize': '13px', 'fontWeight': '600', 'color': 'var(--text-primary)'}),
                        html.Div('Files will be parsed directly from your disk', style={'fontSize': '11px', 'color': 'var(--text-muted)'})
                    ]),
                    dcc.Input(id='electron-file-paths-hidden-trigger', style={'display': 'none'}),
                    dcc.Store(id='electron-file-paths', data=[]),
                    
                    html.Div(id='ibt-selector-area'), 
                    
                    html.Details(open=True, children=[
                        html.Summary('Multi-Driver Manual Upload', style={'fontSize': '12px', 'color': 'var(--text-muted)', 'cursor': 'pointer', 'marginBottom': '14px', 'marginTop': '10px'}), 
                        html.Div(style={'display': 'grid', 'gridTemplateColumns': 'repeat(6,1fr)', 'gap': '12px'}, children=[upload_box(i, is_electron) for i in range(1, 7)])
                    ]), 
                    
                    html.Div(style={'display': 'flex', 'gap': '12px', 'flexWrap': 'wrap', 'alignItems': 'flex-end', 'marginTop': '16px'}, children=[
                        html.Div([
                            html.Label('Compound', style={'fontSize': '12px', 'color': 'var(--text-muted)', 'display': 'block', 'marginBottom': '4px'}), 
                            dcc.Dropdown(id='compound-dd', options=[{'label': v['name'], 'value': k} for (k, v) in TYRE_PRESETS.items()], value='slick_medium', clearable=False, style={'width': '160px', 'backgroundColor': '#1E2028', 'color': '#C9CDD6', 'border': 'none', 'fontSize': '13px'})
                        ]), 
                        html.Div([
                            html.Label('Load Mode (Endurance)', style={'fontSize': '12px', 'color': 'var(--text-muted)', 'display': 'block', 'marginBottom': '4px'}), 
                            dcc.Dropdown(id='downsample-dd', options=[{'label': 'Sprint (Full detail)', 'value': 1}, {'label': 'Endurance (3-6h)', 'value': 5}, {'label': 'Ultra Lazy (12h+)', 'value': 20}], value=1, clearable=False, style={'width': '180px', 'backgroundColor': '#1E2028', 'color': '#C9CDD6', 'border': 'none', 'fontSize': '13px'})
                        ]), 
                        dcc.Loading(
                            html.Button('🚀 Analyse', id='go-btn', className='btn-premium', style={'background': 'var(--accent)', 'color': 'var(--bg-color)', 'fontSize': '14px', 'padding': '10px 24px', 'marginLeft': 'auto', 'fontWeight': 'bold'}), 
                            type='circle', color='var(--accent)'
                        )
                    ]), 
                    html.Div(id='upload-status', style={'color': 'var(--accent)', 'fontSize': '13px', 'marginTop': '12px', 'fontWeight': '600'})
                ]), 
                
                html.Div(id='tab-content'), 
                html.Div(id='status', style={'textAlign': 'center', 'color': 'var(--text-muted)', 'padding': '40px', 'fontSize': '15px'}, children='☝️ Select a telemetry folder, then click Analyse.')
            ])
        ])
    ])
