"""
╔══════════════════════════════════════════════════════════════════╗
║   iRacing Tire Analysis Module  —  v1.0                          ║
║   Surface + Carcass | Operating Window | Degradation | Grip Map  ║
╚══════════════════════════════════════════════════════════════════╝

Usage:
    from core.tire_analysis import TireAnalyzer
    ta  = TireAnalyzer(df)
    fig = ta.fig_surface_temps(mode)
    fig = ta.fig_operating_window(mode)
    fig = ta.fig_degradation(mode)
    fig = ta.fig_grip_map(mode)
    fig = ta.fig_fade_analysis(mode)
    df  = ta.corner_summary()
"""

import numpy as np
import pandas as pd
from scipy.ndimage import gaussian_filter1d
from scipy.stats   import linregress

import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots


# ════════════════════════════════════════════════════════════════════════════
# SABITLER
# ════════════════════════════════════════════════════════════════════════════

SURFACE_NORM = {
    "FL": {"L":"TireTemp_FL_L","M":"TireTemp_FL_M","R":"TireTemp_FL_R"},
    "FR": {"L":"TireTemp_FR_L","M":"TireTemp_FR_M","R":"TireTemp_FR_R"},
    "RL": {"L":"TireTemp_RL_L","M":"TireTemp_RL_M","R":"TireTemp_RL_R"},
    "RR": {"L":"TireTemp_RR_L","M":"TireTemp_RR_M","R":"TireTemp_RR_R"},
}
SURFACE_NORM_C = {
    "FL": {"L":"TireTemp_FL_L_C","M":"TireTemp_FL_M_C","R":"TireTemp_FL_R_C"},
    "FR": {"L":"TireTemp_FR_L_C","M":"TireTemp_FR_M_C","R":"TireTemp_FR_R_C"},
    "RL": {"L":"TireTemp_RL_L_C","M":"TireTemp_RL_M_C","R":"TireTemp_RL_R_C"},
    "RR": {"L":"TireTemp_RR_L_C","M":"TireTemp_RR_M_C","R":"TireTemp_RR_R_C"},
}
SURFACE_RAW = {
    "FL": {"L":"LFtempL","M":"LFtempM","R":"LFtempR"},
    "FR": {"L":"RFtempL","M":"RFtempM","R":"RFtempR"},
    "RL": {"L":"LRtempL","M":"LRtempM","R":"LRtempR"},
    "RR": {"L":"RRtempL","M":"RRtempM","R":"RRtempR"},
}
SURFACE_RAW_CORE = {
    "FL": {"L":"LFtempCL","M":"LFtempCM","R":"LFtempCR"},
    "FR": {"L":"RFtempCL","M":"RFtempCM","R":"RFtempCR"},
    "RL": {"L":"LRtempCL","M":"LRtempCM","R":"LRtempCR"},
    "RR": {"L":"RRtempCL","M":"RRtempCM","R":"RRtempCR"},
}
SURFACE_WEAR = {
    "FL": {"L":"TireWear_FL_L","M":"TireWear_FL_M","R":"TireWear_FL_R"},
    "FR": {"L":"TireWear_FR_L","M":"TireWear_FR_M","R":"TireWear_FR_R"},
    "RL": {"L":"TireWear_RL_L","M":"TireWear_RL_M","R":"TireWear_RL_R"},
    "RR": {"L":"TireWear_RR_L","M":"TireWear_RR_M","R":"TireWear_RR_R"},
}
CARCASS_CHANNELS = {
    "FL":"LFtempCarcass","FR":"RFtempCarcass",
    "RL":"LRtempCarcass","RR":"RRtempCarcass",
}
PRESSURE_CHANNELS = {
    "FL":"TirePress_FL","FR":"TirePress_FR",
    "RL":"TirePress_RL","RR":"TirePress_RR",
}
from utils import CORNER_COLORS, CORNER_LABELS, THEMES, TH as _TH, apply_theme as _apply, no_data_figure as _no_data

OPTIMAL_RANGES = {
    "default":(75,105),"gt3":(80,105),"formula":(85,115),"oval":(70,95),
    "wet":(35,70), # iRacing standard wet range
}


# ════════════════════════════════════════════════════════════════════════════
# TireAnalyzer
# ════════════════════════════════════════════════════════════════════════════

class TireAnalyzer:

    def __init__(self, df: pd.DataFrame,
                 car_class: str = "default",
                 driver_name: str = None,
                 opt_range: tuple = None,
                 tire_type: str = None,
                 unit: str = "metric"):
        """
        tire_type: "Dry", "Wet", or None (auto-detect)
        unit: "metric" (Celsius) or "imperial" (Fahrenheit)
        """
        self.df      = df.copy()
        self.driver  = driver_name or (df["Driver"].iloc[0] if "Driver" in df.columns else "Driver")
        self.unit    = unit
        
        # Determine Tire Type
        self.tire_type = tire_type
        if not self.tire_type:
            # Auto-detect from telemetry data (0=Dry, 1=Wet)
            type_cols = [c for c in ["TireType_FL", "TireType_FR", "TireType_RL", "TireType_RR"] if c in df.columns]
            if type_cols:
                # If any tire is wet (1), consider the set wet
                is_wet = (df[type_cols].iloc[0] == 1).any()
                self.tire_type = "Wet" if is_wet else "Dry"
            else:
                self.tire_type = "Dry" # Default per user request

        # Set Optimal Range
        if opt_range:
            self.opt_lo, self.opt_hi = opt_range
        else:
            self.opt_lo, self.opt_hi = OPTIMAL_RANGES.get(car_class, OPTIMAL_RANGES["default"])

        # IMPORTANT: Convert thresholds to the current unit System (C -> F if needed)
        self.opt_lo = self._convert_temp(self.opt_lo)
        self.opt_hi = self._convert_temp(self.opt_hi)

        # self._detect_laps() # Removed redundant logic
        self._build_surface()
        self._build_carcass()
        self._build_pressure()
        self._build_wear()
        self._compute_lap_stats()

    # ── helpers ──────────────────────────────────────────────────────────────
    def _convert_temp(self, val):
        if self.unit == "imperial":
            return val * 1.8 + 32
        return val

    def _unit_str(self):
        return "°F" if self.unit == "imperial" else "°C"

    # ── preparation ────────────────────────────────────────────────────────────
    # self._detect_laps() is handled externally or not needed here as df already has LapNumber from loader

    def _build_surface(self):
        df = self.df
        self.surface = {}
        for corner in ["FL","FR","RL","RR"]:
            # Priority: Normalized Surface > Normalized Carcass > Raw Surface > Raw Carcass Core
            for mapping in [SURFACE_NORM[corner], SURFACE_NORM_C[corner], SURFACE_RAW[corner], SURFACE_RAW_CORE[corner]]:
                avail = {k:v for k,v in mapping.items()
                         if v in df.columns and df[v].mean()>15}
                if avail:
                    self.surface[corner] = avail
                    break

    def _build_carcass(self):
        df = self.df
        self.carcass = {c:col for c,col in CARCASS_CHANNELS.items()
                        if col in df.columns and df[col].mean()>20}
        
        # If no explicit carcass, try taking the middle core temperature
        if not self.carcass:
            for corner in ["FL","FR","RL","RR"]:
                col = SURFACE_RAW_CORE[corner]["M"]
                if col in df.columns and df[col].mean() > 20:
                    self.carcass[corner] = col

    def _build_pressure(self):
        df = self.df
        self.pressure = {c:col for c,col in PRESSURE_CHANNELS.items()
                         if col in df.columns and df[col].mean()>0}

    def _build_wear(self):
        df = self.df
        self.wear = {}
        for corner in ["FL","FR","RL","RR"]:
            mapping = SURFACE_WEAR[corner]
            avail = {k:v for k,v in mapping.items() if v in df.columns and not df[v].isna().all()}
            if avail:
                self.wear[corner] = avail

    def calculate_optimal_cold_pressures(self, target_hot_psi=None):
        if not hasattr(self, "pressure") or not self.pressure:
            return None
            
        from core.lap_classifier import filter_flying_laps
        flying = filter_flying_laps(self.df)
        if flying.empty: flying = self.df
        
        current_hot = {}
        for c, col in self.pressure.items():
            mean_val = flying[col].mean()
            # If it's over 100, it's likely kPa, so convert to PSI
            if mean_val > 100:
                mean_val = mean_val * 0.145038
            current_hot[c] = mean_val
            
        if not current_hot: return None
            
        target = target_hot_psi if target_hot_psi else 24.0 # Default iRacing target
        
        adjustments = {
            corner: round(target - current_hot[corner], 1)
            for corner in ["FL", "FR", "RL", "RR"]
        }
        return {
            "current_hot": {k: round(v, 1) for k,v in current_hot.items()},
            "target_hot": target,
            "adjustments": adjustments
        }

    def _compute_lap_stats(self):
        df = self.df
        rows = []
        for lap in sorted(df["LapNumber"].unique()):
            ld  = df[df["LapNumber"]==lap]
            row = {"LapNumber":lap}

            all_t = [ld[v].mean() for corner in self.surface.values()
                     for v in corner.values() if v in ld.columns]
            row["AvgSurfaceTemp"]  = np.mean(all_t) if all_t else np.nan
            carc = [ld[c].mean() for c in self.carcass.values() if c in ld.columns]
            row["AvgCarcassTemp"]  = np.mean(carc) if carc else np.nan
            press = [ld[c].mean() for c in self.pressure.values() if c in ld.columns]
            row["AvgPressure"]     = np.mean(press) if press else np.nan
            if "LatAccel" in ld.columns and "Speed" in ld.columns:
                row["GripProxy"]   = (ld["LatAccel"].abs()/(ld["Speed"]+1e-9)).mean()*100
            else:
                row["GripProxy"]   = np.nan
            row["LapSamples"] = len(ld)
            rows.append(row)
        self.lap_stats = pd.DataFrame(rows)

    def has_real_tire_data(self): return bool(self.surface)

    def summary(self):
        print(f"\n{'─'*50}\n  Tire Analysis — {self.driver} ({self.tire_type})")
        print(f"  Surface: {list(self.surface.keys())}")
        print(f"  Carcass: {list(self.carcass.keys())}")
        print(f"  Pressure: {list(self.pressure.keys())}")
        print(f"  Wear Data: {len(self.wear)} corners with data")
        print(f"  Window: {self.opt_lo}–{self.opt_hi}°C\n{'─'*50}")

    # ════════════════════════════════════════════════════════════════════════
    # GRAPH 1 — Surface + Carcass
    # ════════════════════════════════════════════════════════════════════════
    def fig_surface_temps(self, mode="dark") -> go.Figure:
        df = self.df
        if not self.surface and not self.carcass:
            return _no_data("No tire temp data available (IBT required)", mode)

        corners = ["FL","FR","RL","RR"]
        fig = make_subplots(rows=2,cols=2,
            subplot_titles=[f"{c} — {CORNER_LABELS[c]}" for c in corners],
            vertical_spacing=0.12,horizontal_spacing=0.08)
        pos = {"FL":(1,1),"FR":(1,2),"RL":(2,1),"RR":(2,2)}

        for corner in corners:
            r,c = pos[corner]
            color = CORNER_COLORS[corner]

            if corner in self.surface:
                labels = {"L":"Inner","M":"Middle","R":"Outer"}
                dashes = {"L":"dash","M":"solid","R":"dot"}
                for key, col in self.surface[corner].items():
                    fig.add_trace(go.Scatter(
                        x=df["LapDistPct"],y=df[col],mode="lines",
                        name=f"{corner} {labels[key]}",
                        line=dict(color=color,width=1.5,dash=dashes[key]),
                        legendgroup=corner,showlegend=(key=="M"),
                    ),row=r,col=c)

            if corner in self.carcass:
                fig.add_trace(go.Scatter(
                    x=df["LapDistPct"],y=df[self.carcass[corner]],
                    mode="lines",name=f"{corner} Carcass",
                    line=dict(color=color,width=2.5,dash="longdash"),
                    legendgroup=corner,showlegend=True,
                ),row=r,col=c)

            fig.add_hrect(y0=self.opt_lo,y1=self.opt_hi,
                          fillcolor="rgba(0,212,170,0.07)",line_width=0,row=r,col=c)
            fig.add_hline(y=self.opt_lo,line_color="#00D4AA",
                          line_dash="dot",line_width=1,row=r,col=c)
            fig.add_hline(y=self.opt_hi,line_color="#FF3B5C",
                          line_dash="dot",line_width=1,row=r,col=c)

        fig.update_layout(hovermode="x unified")
        unit_label = self._unit_str()
        _apply(fig,f"🌡️ Surface & Carcass Temperatures ({self.tire_type}) — {self.driver} ({unit_label})",mode)
        return fig

    # ════════════════════════════════════════════════════════════════════════
    # GRAPH 2 — Operating Window
    # ════════════════════════════════════════════════════════════════════════
    def fig_operating_window(self, mode="dark") -> go.Figure:
        df = self.df
        if not self.surface:
            return _no_data("Surface temperature channel not available",mode)

        corners = [c for c in ["FL","FR","RL","RR"] if c in self.surface]
        fig = make_subplots(rows=1,cols=2,
            subplot_titles=["Avg Temp: I/M/O",
                            "Time in Window (%)"],
            horizontal_spacing=0.1)

        bar_colors = {"L":"#A855F7","M":"#00D4FF","R":"#FF8C00"}
        labels     = {"L":"Inner","M":"Middle","R":"Outer"}
        unit_label = self._unit_str()
        
        for corner in corners:
            for key,col in self.surface[corner].items():
                if col not in df.columns: continue
                val = self._convert_temp(df[col].mean())
                fig.add_trace(go.Bar(
                    x=[f"{corner} {labels[key]}"],y=[round(val,1)],
                    marker_color=bar_colors[key],
                    text=[f"{val:.1f}{unit_label}"],textposition="outside",
                    showlegend=False,
                ),row=1,col=1)

        fig.add_hline(y=self.opt_lo,line_color="#00D4AA",line_dash="dot",row=1,col=1)
        fig.add_hline(y=self.opt_hi,line_color="#FF3B5C",line_dash="dot",row=1,col=1)
        fig.add_hrect(y0=self.opt_lo,y1=self.opt_hi,
                      fillcolor="rgba(0,212,170,0.07)",line_width=0,row=1,col=1)

        shown = set()
        for corner in corners:
            if "M" not in self.surface[corner]: continue
            col = self.surface[corner]["M"]
            if col not in df.columns: continue
            mid = df[col].apply(self._convert_temp)
            inw   = ((mid>=self.opt_lo)&(mid<=self.opt_hi)).mean()*100
            above = (mid>self.opt_hi).mean()*100
            below = (mid<self.opt_lo).mean()*100

            def _bar(label,val,color):
                return go.Bar(x=[corner],y=[val],name=label,marker_color=color,
                              text=[f"{val:.0f}%"],textposition="inside",
                              showlegend=label not in shown,legendgroup=label)
            for lbl,val,col2 in [("✅ In Window",inw,"#00D4AA"),
                                  ("🔴 Too Hot",above,"#FF3B5C"),
                                  ("🔵 Too Cold",below,"#4A5060")]:
                fig.add_trace(_bar(lbl,val,col2),row=1,col=2)
                shown.add(lbl)

        fig.update_layout(barmode="stack",hovermode="x unified")
        fig.update_yaxes(title_text=unit_label,row=1,col=1)
        fig.update_yaxes(title_text="Time (%)",row=1,col=2)
        _apply(fig,f"🎯 Operating Window ({self.tire_type}) — {self.opt_lo:.1f}–{self.opt_hi:.1f}{unit_label}",mode)
        return fig

    # ════════════════════════════════════════════════════════════════════════
    # GRAFIK 3 — Bozunma Trendi
    # ════════════════════════════════════════════════════════════════════════
    def fig_degradation(self, mode="dark") -> go.Figure:
        ls = self.lap_stats
        if ls.empty or ls["AvgSurfaceTemp"].isna().all():
            return _no_data("No lap-based degradation data",mode)

        unit_label = self._unit_str()
        metrics = [
            ("AvgSurfaceTemp","#FF8C00",f"Avg Surface Temp ({unit_label})"),
            ("AvgPressure",   "#00D4FF","Avg Tire Pressure (kPa)"),
            ("GripProxy",     "#00D4AA","Grip Proxy"),
        ]
        fig = make_subplots(rows=3,cols=1,shared_xaxes=True,
            subplot_titles=[m[2] for m in metrics],
            vertical_spacing=0.08)

        for idx,(col,color,label) in enumerate(metrics,start=1):
            valid = ls.dropna(subset=[col]).copy()
            if valid.empty: continue
            
            if col == "AvgSurfaceTemp":
                valid[col] = valid[col].apply(self._convert_temp)
            
            fig.add_trace(go.Scatter(
                x=valid["LapNumber"],y=valid[col],
                mode="lines+markers",name=label,
                line=dict(color=color,width=2),marker=dict(size=6),
            ),row=idx,col=1)

            if len(valid)>=3:
                slope,intercept,r,_,_ = linregress(valid["LapNumber"],valid[col])
                x_r = np.array([valid["LapNumber"].min(),valid["LapNumber"].max()])
                direction = "▲" if slope>0 else "▼"
                fig.add_trace(go.Scatter(
                    x=x_r,y=slope*x_r+intercept,mode="lines",
                    name=f"{direction} Trend ({slope:+.3f}/lap)",
                    line=dict(color=color,width=1.5,dash="dot"),
                ),row=idx,col=1)

        fig.add_hrect(y0=self._convert_temp(self.opt_lo),y1=self._convert_temp(self.opt_hi),
                      fillcolor="rgba(0,212,170,0.07)",line_width=0,row=1,col=1)
        fig.update_xaxes(title_text="Lap",row=3,col=1)
        fig.update_layout(hovermode="x unified")
        _apply(fig,f"📉 Tire Degradation Trend — {self.driver} ({unit_label})",mode)
        return fig

    # ════════════════════════════════════════════════════════════════════════
    # GRAPH 4 — GPS Grip Map
    # ════════════════════════════════════════════════════════════════════════
    def fig_grip_map(self, mode="dark") -> go.Figure:
        df = self.df
        if "Lat" not in df.columns or "LatAccel" not in df.columns:
            return _no_data("GPS or LatAccel data not available",mode)

        lat_s = gaussian_filter1d(df["Lat"].values,2)
        lon_s = gaussian_filter1d(df["Lon"].values,2)
        
        # Hızın çok düşük olduğu (pit, kaza vb.) anlarda aşırı yüksek G force çıkmasını önlemek için filtrele
        grip = np.where(df["Speed"] > 5.0, df["LatAccel"].abs() / (df["Speed"]) * 100, 0)
        grip_s = gaussian_filter1d(grip, 3)

        # Plotly renk skalasının bir tane aşırı uç (kaza/spin) değer yüzünden tamamen kırmızıya dönmesini engelle
        g_max_clip = np.percentile(grip_s, 95)
        grip_s = np.clip(grip_s, 0, g_max_clip)

        g_min,g_max = grip_s.min(),grip_s.max()+1e-9
        fig = go.Figure()

        # Pist hattı
        fig.add_trace(go.Scattergl(x=lon_s,y=lat_s,mode="lines",
                                    line=dict(color="#1E2028",width=6),
                                    showlegend=False,hoverinfo="skip"))

        # Tek Trace ile Renkli Grip Map (Performans Optimizasyonu)
        custom_data = np.column_stack((df['LapDistPct'], grip_s, df['Speed'] * 3.6))
        fig.add_trace(go.Scattergl(
            x=lon_s, y=lat_s, mode="markers",
            customdata=custom_data,
            marker=dict(
                size=4,
                color=grip_s,
                colorscale=[[0, "rgb(255,55,50)"], [1, "rgb(0,255,50)"]], # Kırmızı (Düşük) -> Yeşil (Yüksek)
            ),
            hovertemplate="Dist: %{customdata[0]:.3f}<br>Grip: %{customdata[1]:.2f}<br>Speed: %{customdata[2]:.1f} km/h<extra></extra>",
            showlegend=False
        ))

        # Düşük grip uyarısı
        low_thr = np.percentile(grip_s,15)
        low_mask = grip_s<low_thr
        if low_mask.any():
            fig.add_trace(go.Scattergl(
                x=lon_s[low_mask],y=lat_s[low_mask],mode="markers",
                marker=dict(size=6,color="#FF3B5C",symbol="circle-open",line_width=1.5),
                name="⚠️ Düşük Grip",
            ))

        fig.update_yaxes(scaleanchor="x",scaleratio=1,
                         showticklabels=False,showgrid=False,zeroline=False)
        fig.update_xaxes(showticklabels=False,showgrid=False,zeroline=False)
        fig.update_layout(showlegend=True)
        _apply(fig,f"🗺️ GPS Grip Map — {self.driver}  (🔴=low  🟢=high)",mode)
        return fig

    # ════════════════════════════════════════════════════════════════════════
    # GRAPH 5 — Thermal Fade
    # ════════════════════════════════════════════════════════════════════════
    def fig_fade_analysis(self, mode="dark") -> go.Figure:
        unit_label = self._unit_str()
        df = self.df
        if not self.surface or "LatAccel" not in df.columns:
            return _no_data("Tire + LatAccel data required for fade analysis",mode)

        temp_cols = [col for c in self.surface.values()
                     for col in c.values() if col in df.columns]
        if not temp_cols:
            return _no_data("Surface temperature channel not found",mode)

        df = df.copy()
        df["_t"] = df[temp_cols].mean(axis=1)
        grip      = df["LatAccel"].abs()/(df["Speed"]+1e-9)*100

        t_min, t_max = df["_t"].min(), df["_t"].max()
        if pd.isna(t_min) or pd.isna(t_max) or t_max - t_min < 0.1:
            return _no_data("Insufficient temperature variance for thermal fade analysis", mode)

        bins = np.linspace(t_min, t_max, 30)
        df["_bin"] = pd.cut(df["_t"], bins=bins, duplicates='drop')
        binned = df.groupby("_bin",observed=False).agg(
            avg_temp=("_t","mean"),
            grip=("LatAccel",lambda x:(x.abs()/(df.loc[x.index,"Speed"]+1e-9)*100).mean()),
        ).dropna()

        fig = go.Figure()
        sample = df.sample(min(3000,len(df)),random_state=42)
        fig.add_trace(go.Scattergl(
            x=sample["_t"],y=grip[sample.index],mode="markers",
            marker=dict(size=2,color="#2A3040",opacity=0.4),
            name="Raw data",showlegend=True,
        ))
        fig.add_trace(go.Scatter(
            x=binned["avg_temp"],y=binned["grip"],
            mode="lines+markers",name="Bin average",
            line=dict(color="#00D4FF",width=2.5),marker=dict(size=6),
        ))
        fig.add_vrect(x0=self.opt_lo,x1=self.opt_hi,
                      fillcolor="rgba(0,212,170,0.10)",line_width=0,
                      annotation_text="Ideal Window",
                      annotation_position="top left",
                      annotation_font_color="#00D4AA")
        fig.add_vline(x=self.opt_lo,line_color="#00D4AA",line_dash="dot",line_width=1)
        fig.add_vline(x=self.opt_hi,line_color="#FF3B5C",line_dash="dot",line_width=1)

        if not binned.empty:
            peak = binned["grip"].idxmax()
            if peak is not None:
                fig.add_annotation(
                    x=self._convert_temp(binned.loc[peak,"avg_temp"]),y=binned.loc[peak,"grip"],
                    text=f"Peak: {self._convert_temp(binned.loc[peak,'avg_temp']):.0f}{unit_label}",
                    showarrow=True,arrowhead=2,
                    font=dict(color="#FFD600",size=11),arrowcolor="#FFD600",
                )

        fig.update_layout(xaxis_title=f"Avg Tire Temp ({unit_label})",
                          yaxis_title="Grip Proxy",hovermode="x unified")
        _apply(fig,f"🔥 Thermal Fade Analysis — {self.driver}",mode)
        return fig

    # ════════════════════════════════════════════════════════════════════════
    # GRAPH 6 — Tire Wear
    # ════════════════════════════════════════════════════════════════════════
    def fig_wear(self, mode="dark") -> go.Figure:
        if not hasattr(self, "wear") or not self.wear:
            return _no_data("No tire wear channels available", mode)
            
        df = self.df
        corners = ["FL", "FR", "RL", "RR"]
        fig = make_subplots(rows=1, cols=4, subplot_titles=[f"{c} — {CORNER_LABELS[c]}" for c in corners])
        
        for idx, corner in enumerate(corners, start=1):
            if corner not in self.wear: continue
            cols_d = self.wear[corner]
            
            # Use the min value of wear because it degrades over time and generally 1.0 is full, 0.0 is empty.
            # But sometimes it's saved as 100% or 1%. Let's normalize it to %.
            def _get_w(col):
                if col in df.columns:
                    val = df[col].dropna().min()
                    if val < 2.0: return val * 100 # likely stored as 0.0-1.0
                    return val
                return np.nan
                
            w_l = _get_w(cols_d.get("L"))
            w_m = _get_w(cols_d.get("M"))
            w_r = _get_w(cols_d.get("R"))
            
            vals = [w_l, w_m, w_r]
            labels = ["Inner", "Middle", "Outer"]
            colors = ["#A855F7", "#00D4FF", "#FF8C00"]
            
            for v, l, c in zip(vals, labels, colors):
                if pd.isna(v): continue
                # Highlight critical wear (< 50% or some threshold)
                marker_c = "#EF4444" if v < 50 else c
                fig.add_trace(go.Bar(
                    x=[l], y=[v],
                    marker_color=marker_c,
                    text=[f"{v:.1f}%"], textposition="outside",
                    showlegend=False,
                ), row=1, col=idx)
            
            fig.update_yaxes(range=[0, 105], row=1, col=idx)
            fig.add_hline(y=50, line_color="#EF4444", line_dash="dot", row=1, col=idx)

        fig.update_layout(hovermode="x unified", barmode="group")
        _apply(fig, f"🛞 Remaining Tire Wear — {self.driver} (%)", mode)
        return fig

    # ════════════════════════════════════════════════════════════════════════
    # TABLE — Corner Summary
    # ════════════════════════════════════════════════════════════════════════
    def corner_summary(self) -> pd.DataFrame:
        df = self.df
        rows = []
        unit_label = self._unit_str()
        for corner in ["FL","FR","RL","RR"]:
            if corner not in self.surface:
                rows.append({"Corner":corner,"Inner":"—","Middle":"—","Outer":"—",
                              "Δ(I-O)":"—","Window%":"—", "Wear%":"—",
                              "Camber Advice":"IBT required"})
                continue
            cols_d = self.surface[corner]
            ti = df[cols_d["L"]].mean() if "L" in cols_d and cols_d["L"] in df.columns else None
            tm = df[cols_d["M"]].mean() if "M" in cols_d and cols_d["M"] in df.columns else None
            to = df[cols_d["R"]].mean() if "R" in cols_d and cols_d["R"] in df.columns else None
            
            wear_val = "—"
            if hasattr(self, "wear") and corner in self.wear:
                wcols = self.wear[corner]
                w_vals = [df[wcols[k]].dropna().min() for k in ["L","M","R"] if k in wcols and wcols[k] in df.columns]
                if w_vals:
                    # avg or min remaining wear
                    min_w = min(w_vals)
                    if min_w < 2.0: min_w *= 100
                    wear_val = f"{min_w:.1f}%"
                    
            delta = round(ti-to,1) if (ti and to) else None
            pct   = None
            if tm is not None:
                mid = df[cols_d["M"]]
                pct = round(((mid>=self.opt_lo)&(mid<=self.opt_hi)).mean()*100,1)
            if delta is None: advice = "No data"
            elif delta>12:    advice = f"Increase neg camber +{delta*0.04:.2f}°"
            elif delta<-12:   advice = f"Decrease neg camber {abs(delta)*0.04:.2f}°"
            else:             advice = "Balanced"
            rows.append({"Corner":corner,
                         f"Inner ({unit_label})":  f"{self._convert_temp(ti):.1f}" if ti else "—",
                         f"Middle ({unit_label})": f"{self._convert_temp(tm):.1f}" if tm else "—",
                         f"Outer ({unit_label})":  f"{self._convert_temp(to):.1f}" if to else "—",
                         "Δ(I-O)":      f"{delta:.1f}" if delta else "—",
                         "Window%":     f"{pct:.1f}" if pct else "—",
                         "Wear%":       wear_val,
                         "Camber Advice": advice})
        return pd.DataFrame(rows)
