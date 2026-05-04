"""
Shared utilities for iRacing Telemetry Analytics
=================================================
Central place for themes, palettes, and common UI helpers.
All modules should import from here to avoid duplication.
"""

# ════════════════════════════════════════════════════════════════════════════
# COLOR PALETTE & CONSTANTS
# ════════════════════════════════════════════════════════════════════════════

PALETTE = ["#00D4FF","#FF8C00","#00D4AA","#FF3B5C","#A855F7",
           "#FFD600","#F97316","#84CC16","#EC4899","#14B8A6"]

CORNER_COLORS = {"FL":"#00D4FF","FR":"#FF8C00","RL":"#00D4AA","RR":"#FF3B5C"}
CORNER_LABELS = {"FL":"Front Left","FR":"Front Right","RL":"Rear Left","RR":"Rear Right"}

TYRE_PRESETS = {
    "slick_medium": {"name":"Slick Medium","surface":(75,105),"carcass":(60,90),"pressure":(172,193)},
    "slick_soft":   {"name":"Slick Soft",  "surface":(80,110),"carcass":(65,95),"pressure":(172,186)},
    "slick_hard":   {"name":"Slick Hard",  "surface":(70,100),"carcass":(55,85),"pressure":(179,200)},
    "rain_full":    {"name":"Full Wet",    "surface":(50,80), "carcass":(40,70),"pressure":(152,172)},
    "formula":      {"name":"Formula",     "surface":(85,115),"carcass":(70,100),"pressure":(138,165)},
}


# ════════════════════════════════════════════════════════════════════════════
# THEMES  (dark + light)
# ════════════════════════════════════════════════════════════════════════════

THEMES = {
    "dark":  dict(bg="#0B0F19",panel="rgba(22,28,45,0.7)",border="rgba(255,255,255,0.08)",
                  text="#F8FAFC",subtext="#94A3B8",plot_bg="rgba(0,0,0,0)",
                  paper_bg="rgba(0,0,0,0)",grid="rgba(255,255,255,0.05)",zero="rgba(255,255,255,0.1)",
                  accent="#00D4FF",gold="#FBBF24",good="#10B981",
                  warn="#F59E0B",bad="#EF4444"),
    "light": dict(bg="#F8FAFC",panel="rgba(255,255,255,0.8)",border="rgba(0,0,0,0.1)",
                  text="#0F172A",subtext="#64748B",plot_bg="rgba(0,0,0,0)",
                  paper_bg="rgba(0,0,0,0)",grid="rgba(0,0,0,0.05)",zero="rgba(0,0,0,0.1)",
                  accent="#2563EB",gold="#D97706",good="#059669",
                  warn="#D97706",bad="#DC2626"),
}


def TH(mode="dark"):
    """Return theme dict for given mode."""
    return THEMES.get(mode, THEMES["dark"])


def apply_theme(fig, title, mode="dark"):
    """Apply consistent theme to a Plotly figure."""
    t = TH(mode)
    fig.update_layout(
        title=dict(text=title, font=dict(size=14, color=t["text"], family="system-ui, sans-serif")),
        plot_bgcolor=t["plot_bg"], paper_bgcolor=t["paper_bg"],
        font=dict(family="ui-monospace, Consolas, monospace",
                  color=t["text"], size=11),
        margin=dict(l=40, r=20, t=50, b=32),
        hoverlabel=dict(
            bgcolor=t["bg"],
            bordercolor=t["border"],
            font=dict(color=t["text"], family="ui-monospace, Consolas, monospace")
        )
    )
    fig.update_xaxes(gridcolor=t["grid"], zerolinecolor=t["zero"], gridwidth=1)
    fig.update_yaxes(gridcolor=t["grid"], zerolinecolor=t["zero"], gridwidth=1)
    return fig


def no_data_figure(msg, mode="dark"):
    """Return an empty figure with a centered message."""
    import plotly.graph_objects as go
    fig = go.Figure()
    fig.add_annotation(text=msg, xref="paper", yref="paper", x=0.5, y=0.5,
                       showarrow=False,
                       font=dict(color=TH(mode)["subtext"], size=13))
    apply_theme(fig, msg, mode)
    return fig

def infer_hz(df):
    if "SessionTime" in df.columns:
        diffs = df["SessionTime"].diff().dropna()
        if not diffs.empty: return round(1.0 / diffs.median())
    elif "Time" in df.columns:
        diffs = df["Time"].diff().dropna()
        if not diffs.empty: return round(1.0 / diffs.median())
    return 60.0
