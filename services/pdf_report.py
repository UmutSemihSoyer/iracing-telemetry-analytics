"""
iRacing PDF Report Generator — v1.0
Plotly->PNG | Executive Summary | Sector Delta | Setup Detail

Installation: pip install reportlab kaleido plotly
Usage:
    from services.pdf_report import build_pdf
    pdf_bytes = build_pdf(dfs, metas, tire_analyzers=[ta])
"""
import io, datetime, threading
import numpy as np
import pandas as pd

from reportlab.lib.pagesizes  import A4
from reportlab.lib.styles      import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units       import cm
from reportlab.lib             import colors as rl_colors
from reportlab.platypus        import (SimpleDocTemplate, Paragraph, Spacer,
                                       Table, TableStyle, PageBreak,
                                       HRFlowable, Image as RLImage, KeepTogether)
from reportlab.lib.enums       import TA_CENTER

try:
    import plotly.io as pio
    KALEIDO_OK = True
except Exception:
    KALEIDO_OK = False

try:
    from core.tire_analysis import TireAnalyzer
    TIRE_OK = True
except ImportError:
    TIRE_OK = False

try:
    from services.ai_feedback import generate_feedback
    AI_OK = True
except ImportError:
    AI_OK = False

try:
    from services.setup_advisor import analyze_setup, setup_score, category_grades
    SETUP_ADVISOR_OK = True
except ImportError:
    SETUP_ADVISOR_OK = False

# ════════════════════════════════════════════════════════════════════════════
# COLORS
# ════════════════════════════════════════════════════════════════════════════
C = dict(
    accent    = rl_colors.HexColor("#00D4FF"),
    gold      = rl_colors.HexColor("#FFD600"),
    good      = rl_colors.HexColor("#00D4AA"),
    warn      = rl_colors.HexColor("#FF8C00"),
    bad       = rl_colors.HexColor("#DC2626"),
    text      = rl_colors.HexColor("#1A1D26"),
    subtext   = rl_colors.HexColor("#6B7280"),
    border    = rl_colors.HexColor("#DDE1EA"),
    row_even  = rl_colors.HexColor("#F4F5F7"),
    row_odd   = rl_colors.HexColor("#FFFFFF"),
    hdr_bg    = rl_colors.HexColor("#1A1D26"),
    hdr_fg    = rl_colors.HexColor("#00D4FF"),
    green_bg  = rl_colors.HexColor("#1A3A1A"),
    red_bg    = rl_colors.HexColor("#3A1A1A"),
)

# ════════════════════════════════════════════════════════════════════════════
# STYLES
# ════════════════════════════════════════════════════════════════════════════
def _st():
    d = {}
    d["title"]   = ParagraphStyle("t",  fontSize=26, textColor=C["accent"],
                                   alignment=TA_CENTER, fontName="Helvetica-Bold",
                                   spaceAfter=4, leading=32)
    d["sub"]     = ParagraphStyle("sb", fontSize=11, textColor=C["subtext"],
                                   alignment=TA_CENTER, fontName="Helvetica", spaceAfter=18)
    d["section"] = ParagraphStyle("s",  fontSize=14, textColor=C["gold"],
                                   fontName="Helvetica-Bold", spaceBefore=14, spaceAfter=5)
    d["ssec"]    = ParagraphStyle("ss", fontSize=11, textColor=C["accent"],
                                   fontName="Helvetica-Bold", spaceBefore=8, spaceAfter=4)
    d["body"]    = ParagraphStyle("b",  fontSize=9,  textColor=C["text"],
                                   fontName="Helvetica", spaceAfter=3, leading=13)
    d["bullet"]  = ParagraphStyle("bl", fontSize=9,  textColor=C["text"],
                                   fontName="Helvetica", leftIndent=12,
                                   spaceAfter=3, leading=13, bulletIndent=4)
    d["small"]   = ParagraphStyle("sm", fontSize=7.5, textColor=C["subtext"],
                                   fontName="Helvetica", spaceAfter=2)
    d["footer"]  = ParagraphStyle("f",  fontSize=7,  textColor=C["subtext"],
                                   fontName="Helvetica", alignment=TA_CENTER)
    return d

def _hr():
    return HRFlowable(width="100%", thickness=0.5, color=C["border"], spaceAfter=5)

def _tbl_style(header=True):
    cmds = [
        ("FONTNAME",      (0,0),(-1,-1), "Helvetica"),
        ("FONTSIZE",      (0,0),(-1,-1), 8),
        ("TOPPADDING",    (0,0),(-1,-1), 4),
        ("BOTTOMPADDING", (0,0),(-1,-1), 4),
        ("LEFTPADDING",   (0,0),(-1,-1), 6),
        ("RIGHTPADDING",  (0,0),(-1,-1), 6),
        ("BOX",           (0,0),(-1,-1), 0.4, C["border"]),
        ("INNERGRID",     (0,0),(-1,-1), 0.25, C["border"]),
        ("ROWBACKGROUNDS",(0, 1 if header else 0),(-1,-1),
         [C["row_odd"], C["row_even"]]),
        ("ALIGN",         (0,0),(-1,-1), "CENTER"),
        ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
        ("TEXTCOLOR",     (0, 1 if header else 0),(-1,-1), C["text"]),
    ]
    if header:
        cmds += [
            ("BACKGROUND", (0,0),(-1,0), C["hdr_bg"]),
            ("TEXTCOLOR",  (0,0),(-1,0), C["hdr_fg"]),
            ("FONTNAME",   (0,0),(-1,0), "Helvetica-Bold"),
            ("FONTSIZE",   (0,0),(-1,0), 8.5),
        ]
    return TableStyle(cmds)

# ════════════════════════════════════════════════════════════════════════════
# PLOTLY -> PNG
# ════════════════════════════════════════════════════════════════════════════
def _fig2img(fig, wcm=17, hcm=9, timeout=15):
    if not KALEIDO_OK or fig is None:
        return None
    
    # Run pio.to_image in a separate thread with a timeout
    # to prevent Kaleido hangs from blocking the entire app.
    res = {"img": None, "err": None}
    def worker():
        try:
            png = pio.to_image(fig, format="png",
                               width=int(wcm*37.8), height=int(hcm*37.8), scale=2)
            res["img"] = RLImage(io.BytesIO(png), width=wcm*cm, height=hcm*cm)
        except Exception as e:
            res["err"] = str(e)

    t = threading.Thread(target=worker)
    t.daemon = True
    t.start()
    t.join(timeout)

    if t.is_alive():
        print(f" (TIMEOUT after {timeout}s)")
        return None
    if res["err"]:
        print(f" (ERROR: {res['err']})")
    return res["img"]

def _fig_block(story, fig, title, st, wcm=17, hcm=9):
    img = _fig2img(fig, wcm, hcm)
    if img is None:
        story.append(Paragraph(f"[{title} - chart could not be rendered]", st["small"]))
        return
    story.append(KeepTogether([Paragraph(title, st["ssec"]), img, Spacer(1,0.3*cm)]))

# ════════════════════════════════════════════════════════════════════════════
# HELPERS
# ════════════════════════════════════════════════════════════════════════════
def _lap_times(df, hz=60.0):
    if "LapLastTime" in df.columns:
        lt = df.groupby(["Driver","LapNumber"])["LapLastTime"].max().reset_index()
        lt = lt[lt["LapLastTime"]>0].rename(columns={"LapLastTime":"Time_s"})
    else:
        c = df.groupby(["Driver","LapNumber"]).size().reset_index(name="N")
        c["Time_s"] = c["N"]/hz
        lt = c[["Driver","LapNumber","Time_s"]]
    lt = lt.sort_values("Time_s").reset_index(drop=True)
    def _safe_fmt(s):
        if pd.isna(s) or np.isinf(s) or s <= 0: return "--:--.---"
        return f"{int(s//60)}:{s%60:06.3f}"
    lt["Time_str"] = lt["Time_s"].apply(_safe_fmt)
    best = lt["Time_s"].iloc[0]
    lt["Rank"] = range(1, len(lt)+1)
    lt["Gap"]  = lt["Time_s"].apply(lambda s: "REF" if s==best else f"+{s-best:.3f}s")
    return lt

def _sector_delta(dfs, n=10):
    bins  = np.linspace(0,1,n+1)
    label = [f"S{i:02d}" for i in range(1,n+1)]
    rows  = []
    for df in dfs:
        driver = df["Driver"].iloc[0]
        tmp = df.copy()
        tmp["_s"] = pd.cut(tmp["LapDistPct"], bins=bins, labels=label)
        grp = tmp.groupby(["LapNumber","_s"], observed=False)["Speed"].mean()
        lap_totals = grp.groupby("LapNumber").sum()
        if lap_totals.empty: continue
        best_lap = lap_totals.idxmin()
        ref = grp[best_lap]
        for lap in tmp["LapNumber"].unique():
            cur = grp.get(lap, pd.Series(dtype=float))
            for sec in label:
                cv = cur.get(sec, np.nan); rv = ref.get(sec, np.nan)
                delta = round(cv-rv, 2) if not(np.isnan(cv) or np.isnan(rv)) else 0
                rows.append({"Driver":driver,"LapNumber":lap,"Sector":sec,"Delta":delta})
    return pd.DataFrame(rows)

def _setup_advice(dfs):
    advice = []
    df = dfs[0]
    TEMP_MAP = {
        "FL":["TireTemp_FL_L","TireTemp_FL_M","TireTemp_FL_R"],
        "FR":["TireTemp_FR_L","TireTemp_FR_M","TireTemp_FR_R"],
        "RL":["TireTemp_RL_L","TireTemp_RL_M","TireTemp_RL_R"],
        "RR":["TireTemp_RR_L","TireTemp_RR_M","TireTemp_RR_R"],
    }
    for corner, cols in TEMP_MAP.items():
        avail = [c for c in cols if c in df.columns and df[c].mean()>30]
        if len(avail)==3:
            ti,tm,to = [df[c].mean() for c in avail]
            d = ti - to
            if   d > 15:  advice.append(("HIGH", corner, f"Inner too hot (delta={d:.1f}C). Increase neg camber +{d*0.04:.2f}."))
            elif d < -15: advice.append(("HIGH", corner, f"Outer too hot (delta={abs(d):.1f}C). Decrease neg camber {abs(d)*0.04:.2f}."))
            else:         advice.append(("OK",   corner, f"Thermal distribution balanced (delta={abs(d):.1f}C)."))
    SUSP = {"FL":"Suspension_FL","FR":"Suspension_FR","RL":"Suspension_RL","RR":"Suspension_RR"}
    vals = {c:df[col].abs().mean()*1000 for c,col in SUSP.items()
            if col in df.columns and df[col].abs().max()>0.001}
    if vals:
        avg = np.mean(list(vals.values()))
        if   avg > 25: advice.append(("HIGH","Spring",f"High deflection ({avg:.1f}mm). Stiffen springs."))
        elif avg <  8: advice.append(("MED", "Spring",f"Low deflection ({avg:.1f}mm). Try softer springs."))
        else:          advice.append(("OK",  "Spring",f"Suspension travel normal ({avg:.1f}mm)."))
    if not advice:
        advice.append(("INFO","General","IBT required for detailed setup advice."))
    return advice

# ════════════════════════════════════════════════════════════════════════════
# MAIN FUNCTION
# ════════════════════════════════════════════════════════════════════════════
def build_pdf(dfs, metas, tire_analyzers=None, extra_figs=None, session_date=""):
    """
    Parameters
    ----------
    dfs            : list[DataFrame]
    metas          : list[dict]
    tire_analyzers : list[TireAnalyzer]  (optional)
    extra_figs     : dict{"title": fig} (optional)
    session_date   : str

    Returns: bytes (PDF)
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                             leftMargin=2*cm, rightMargin=2*cm,
                             topMargin=2.5*cm, bottomMargin=2*cm,
                             title="iRacing Telemetry Report v9.1")
    st       = _st()
    story    = []
    combined = pd.concat(dfs, ignore_index=True)

    # ═══ KAPAK ═══════════════════════════════════════════════════════════
    story += [
        Spacer(1, 1.5*cm),
        Paragraph("iRacing Telemetry Report", st["title"]),
        Paragraph("v9.1  Professional Edition", st["sub"]),
        Paragraph(session_date or datetime.datetime.now().strftime("%d %B %Y  |  %H:%M"), st["sub"]),
        _hr(), Spacer(1, 0.5*cm),
    ]

    # Driver summary table
    story.append(Paragraph("Driver Summary", st["section"]))
    drv_data = [["Driver","Car","Track","Series","Best Lap","Laps"]]
    for df, meta in zip(dfs, metas):
        lt = _lap_times(df)
        drv_data.append([
            df["Driver"].iloc[0],
            meta.get("car_name","?"),
            meta.get("track","?"),
            meta.get("series","?"),
            lt.iloc[0]["Time_str"] if not lt.empty else "?",
            str(df["LapNumber"].nunique() if "LapNumber" in df.columns else "?"),
        ])
    tbl = Table(drv_data, repeatRows=1,
                colWidths=[3.5*cm,3.5*cm,3*cm,2.5*cm,2.5*cm,1.5*cm])
    tbl.setStyle(_tbl_style())
    story.append(tbl)
    story.append(Spacer(1, 0.4*cm))

    # Executive summary
    story.append(Paragraph("Executive Summary", st["section"]))
    lt_all = _lap_times(combined)
    if not lt_all.empty:
        br = lt_all.iloc[0]
        for txt in [
            f"<b>Overall Best Lap:</b>  {br['Driver']}  —  {br['Time_str']}  (Lap {int(br['LapNumber'])})",
            f"<b>Total Drivers:</b>  {len(dfs)}",
            f"<b>Total Laps Logged:</b>  {len(lt_all)}",
        ]:
            story.append(Paragraph(f"• {txt}", st["bullet"]))

    for df in dfs:
        driver = df["Driver"].iloc[0]
        coast  = (df["Driver_State"]=="Coasting").mean()*100 if "Driver_State" in df.columns else 0
        story.append(Spacer(1, 0.15*cm))
        story.append(Paragraph(
            f"<b>{driver}</b>  |  Max speed: <b>{df['Speed'].max()*3.6:.1f} km/h</b>  "
            f"|  Coasting: <b>{coast:.1f}%</b>",
            st["body"]))
            
        # AI Feedback / Rules Injection
        if AI_OK:
            ai_items = generate_feedback(df)
            if ai_items:
                criticals = [i for i in ai_items if i.get("priority") == "critical"]
                c_txt = " | ".join([f"{c['title']}" for c in criticals])
                if criticals:
                    story.append(Paragraph(f"<i>Critical Issues:</i> <font color='#DC2626'>{c_txt}</font>", st["small"]))


    story.append(PageBreak())

    # ═══ LAP TIMES & SECTOR DELTA ════════════════════════════════
    story.append(Paragraph("Lap Times", st["section"]))
    lt_data = [["Rank","Driver","Lap","Time","Gap"]] + \
               lt_all[["Rank","Driver","LapNumber","Time_str","Gap"]].values.tolist()
    lt_tbl  = Table(lt_data, repeatRows=1,
                    colWidths=[1.5*cm,5*cm,2*cm,4.5*cm,4*cm])
    lt_tbl.setStyle(_tbl_style())
    for i, row in enumerate(lt_data[1:], 1):
        if row[-1] == "REF":
            lt_tbl.setStyle(TableStyle([
                ("BACKGROUND",(0,i),(-1,i), rl_colors.HexColor("#1A2A1A")),
                ("TEXTCOLOR", (0,i),(-1,i), C["good"]),
                ("FONTNAME",  (0,i),(-1,i), "Helvetica-Bold"),
            ]))
    story.append(lt_tbl)
    story.append(Spacer(1, 0.5*cm))

    # Sector delta
    story.append(Paragraph("Sector Delta  (+ = slower,  - = faster)", st["section"]))
    story.append(Paragraph(
        "Sector speed differences relative to each driver's own fastest lap.",
        st["body"]))
    story.append(Spacer(1, 0.2*cm))

    delta_df = _sector_delta(dfs, n=10)
    if not delta_df.empty:
        sectors = sorted(delta_df["Sector"].unique())
        for df in dfs:
            driver = df["Driver"].iloc[0]
            d_sub  = delta_df[delta_df["Driver"]==driver]
            pivot  = d_sub.pivot_table(index="LapNumber", columns="Sector",
                                        values="Delta", aggfunc="mean")\
                          .reindex(columns=sectors).round(2)
            story.append(Paragraph(driver, st["ssec"]))
            hdr2  = ["Lap"] + list(pivot.columns)
            rows_ = [[str(int(l))] + [str(v) for v in row]
                     for l, row in zip(pivot.index, pivot.values)]
            d_tbl = Table([hdr2]+rows_, repeatRows=1,
                          colWidths=[1.5*cm]+[1.6*cm]*len(sectors))
            d_tbl.setStyle(_tbl_style())
            for ri, row in enumerate(rows_, 1):
                for ci, val in enumerate(row[1:], 1):
                    try:
                        v  = float(val)
                        bg = C["red_bg"] if v>5 else (C["green_bg"] if v<-5 else None)
                        if bg:
                            d_tbl.setStyle(TableStyle([("BACKGROUND",(ci,ri),(ci,ri),bg)]))
                    except Exception:
                        pass
            story.append(d_tbl)
            story.append(Spacer(1, 0.3*cm))

    story.append(PageBreak())

    # ═══ SETUP ADVISOR ════════════════════════════════════════════════
    story.append(Paragraph("Setup Advisor — Telemetry-Based Recommendations", st["section"]))
    story.append(Paragraph(
        "Automatically generated from telemetry analysis. "
        "14 rules evaluate tire pressures, temperatures, aero balance, brakes, suspension, and differential.",
        st["body"]))
    story.append(Spacer(1, 0.2*cm))

    if SETUP_ADVISOR_OK:
        # Get setup data from meta
        setup_data = {}
        if metas:
            setup_data = metas[0].get("auto_setup", {})

        recs = analyze_setup(combined, setup_data)
        score = setup_score(recs)
        grades = category_grades(recs)

        # Score + Grades header
        grade_str = "  |  ".join([f"{cat}: {g}" for cat, g in grades.items()])
        # Use safe ASCII alternatives for reportlab
        grade_str_safe = grade_str.replace("⚠️", "[!]").replace("✅", "[OK]").replace("🔴", "[!!]").replace("ℹ️", "[i]")
        story.append(Paragraph(
            f"<b>Setup Score: {score}/100</b>  |  {grade_str_safe}", st["body"]))
        story.append(Spacer(1, 0.2*cm))

        # Build recommendation table
        sev_label = {"critical": "CRITICAL", "warning": "WARNING", "info": "INFO", "good": "OK"}
        sev_color = {"critical": C["bad"], "warning": C["warn"], "info": C["accent"], "good": C["good"]}

        adv_data = [["Severity", "Category", "Issue", "Recommendation"]]
        for r in recs:
            sev = sev_label.get(r["severity"], r["severity"].upper())
            delta_str = ""
            if r["suggested_delta"] and r["suggested_delta"] not in ("OK", "Monitor", ""):
                param = r["parameter"].replace("_", " ").title() if r["parameter"] else ""
                delta_str = f"{param}: {r['suggested_delta']}"

            adv_data.append([
                sev,
                r["category"],
                Paragraph(r["title"], st["body"]),
                Paragraph(f"{r['detail']}<br/><b>{delta_str}</b>" if delta_str else r["detail"], st["body"]),
            ])

        adv_tbl = Table(adv_data, repeatRows=1, colWidths=[2.2*cm, 2.2*cm, 5*cm, 7.6*cm])
        adv_tbl.setStyle(_tbl_style())
        for i, r in enumerate(recs, 1):
            color = sev_color.get(r["severity"], C["text"])
            adv_tbl.setStyle(TableStyle([
                ("TEXTCOLOR", (0, i), (1, i), color),
                ("FONTNAME", (0, i), (0, i), "Helvetica-Bold"),
            ]))
        story.append(adv_tbl)
    else:
        # Fallback to old advice
        prio_color = {"HIGH":C["bad"],"MED":C["warn"],"OK":C["good"],"INFO":C["subtext"]}
        advice   = _setup_advice(dfs)
        adv_data = [["Priority","Category","Advice"]] + [[p,cat,msg] for p,cat,msg in advice]
        adv_tbl  = Table(adv_data, repeatRows=1, colWidths=[2.5*cm,3*cm,11.5*cm])
        adv_tbl.setStyle(_tbl_style())
        for i,(p,_,_) in enumerate(advice, 1):
            adv_tbl.setStyle(TableStyle([
                ("TEXTCOLOR",(0,i),(1,i), prio_color.get(p, C["text"])),
                ("FONTNAME", (0,i),(1,i), "Helvetica-Bold"),
            ]))
        story.append(adv_tbl)
    story.append(Spacer(1, 0.4*cm))

    # Corner summary (TireAnalyzer)
    if tire_analyzers:
        story.append(Paragraph("Tire Corner Temperature Summary", st["section"]))
        for ta in tire_analyzers:
            story.append(Paragraph(ta.driver, st["ssec"]))
            cs = ta.corner_summary()
            if not cs.empty:
                cs_data = [list(cs.columns)] + [list(r) for r in cs.values]
                cs_tbl  = Table(cs_data, repeatRows=1,
                                colWidths=[1.4*cm, 1.8*cm, 1.8*cm, 1.8*cm, 1.6*cm, 1.8*cm, 1.8*cm, 5.0*cm])
                cs_tbl.setStyle(_tbl_style())
                story.append(cs_tbl)
                story.append(Spacer(1, 0.3*cm))

    story.append(PageBreak())

    # ═══ AI ENGINEER FEEDBACK ══════════════════════════════════════════
    if AI_OK:
        story.append(Paragraph("🧠 AI Engineer Sürüş Analizi", st["section"]))
        story.append(Paragraph(
            "Telemetri verilerinizden türetilen yapay zeka destekli sürüş geliştirme ipuçları ve segment değerlendirmeleri.",
            st["body"]))
        story.append(Spacer(1, 0.3*cm))
        
        for df in dfs:
            driver = df["Driver"].iloc[0] if "Driver" in df.columns else "Driver"
            story.append(Paragraph(f"Pilot: {driver}", st["ssec"]))
            try:
                feedback_items = generate_feedback(df)
            except Exception as _e:
                print(f"AI error: {_e}")
                feedback_items = []
            
            prio_color_ai = {"critical": C["bad"], "improvement": C["warn"], "good": C["good"], "warning": C["warn"], "info": C["subtext"]}
            ai_data = [["Durum", "Bölge/Viraj", "AI Analizi ve Öneri"]]
            
            for item in feedback_items:
                # remove emojis for reportlab standard fonts since emoji rendering often fails in Helvetica unless using UTF-8 TTF
                ico = item.get("icon", "")
                pri_str = item.get("priority", "info").capitalize()
                tit = item.get("title", "")
                det = item.get("detail", "")
                pri = item.get("priority", "info")
                ai_data.append([f"{pri_str}", tit, Paragraph(det, st["body"])])
                
            if len(ai_data) > 1:
                ai_tbl = Table(ai_data, repeatRows=1, colWidths=[2.5*cm, 3.5*cm, 11*cm])
                ai_tbl.setStyle(_tbl_style())
                for i_row, item in enumerate(feedback_items, 1):
                    pri = item.get("priority", "info")
                    ai_tbl.setStyle(TableStyle([
                        ("TEXTCOLOR", (0, i_row), (0, i_row), prio_color_ai.get(pri, C["text"])),
                        ("FONTNAME",  (0, i_row), (0, i_row), "Helvetica-Bold"),
                    ]))
                story.append(ai_tbl)
            else:
                story.append(Paragraph("Yeterli veri oluşturulamadı veya analiz tamamen kusursuz.", st["body"]))
            story.append(Spacer(1, 0.5*cm))

    story.append(PageBreak())

    # ═══ CHARTS ════════════════════════════════════════════════════════
    story.append(Paragraph("Chart Analysis", st["section"]))
    if not KALEIDO_OK:
        story.append(Paragraph(
            "Kaleido required for image embedding: pip install kaleido",
            st["body"]))
    else:
        if tire_analyzers:
            story.append(Paragraph("Tire Analysis", st["section"]))
            for ta in tire_analyzers:
                story.append(Paragraph(ta.driver, st["ssec"]))
                _fig_block(story, ta.fig_surface_temps("light"),
                           "Surface and Carcass Temperatures", st, 17, 11)
                _fig_block(story, ta.fig_operating_window("light"),
                           "Operating Window", st, 17, 8)
                _fig_block(story, ta.fig_degradation("light"),
                           "Degradation Trend (lap-based)", st, 17, 11)
                _fig_block(story, ta.fig_grip_map("light"),
                           "GPS Grip Map", st, 14, 10)
                _fig_block(story, ta.fig_wear("light"),
                           "Remaining Tire Wear", st, 17, 8)
                _fig_block(story, ta.fig_fade_analysis("light"),
                           "Thermal Fade Analysis", st, 17, 8)
                story.append(PageBreak())

        if extra_figs:
            story.append(Paragraph("Additional Analysis", st["section"]))
            for title, fig in extra_figs.items():
                _fig_block(story, fig, title, st, 17, 9)

    # ═══ BASIC STATISTICS ════════════════════════════════════════════
    story.append(Paragraph("Basic Statistics", st["section"]))
    metrics = [
        ("Max Speed (km/h)",   lambda d: f"{d['Speed'].max()*3.6:.1f}"),
        ("Avg Speed (km/h)",   lambda d: f"{d['Speed'].mean()*3.6:.1f}"),
        ("Max Brake (%)",     lambda d: f"{d['Brake'].max()*100:.0f}"),
        ("Avg Throttle (%)",  lambda d: f"{d['Throttle'].mean()*100:.0f}"),
        ("Coasting (%)",      lambda d: f"{(d['Driver_State']=='Coasting').mean()*100:.1f}" if "Driver_State" in d.columns else "-"),
        ("Overlap (%)",       lambda d: f"{(d['Driver_State']=='Overlap').mean()*100:.1f}" if "Driver_State" in d.columns else "-"),
        ("Avg RPM",           lambda d: f"{d['RPM'].mean():.0f}"          if "RPM" in d.columns else "-"),
        ("Max LatAccel (G)",  lambda d: f"{d['LatAccel'].abs().max():.2f}" if "LatAccel" in d.columns else "-"),
    ]
    stat_hdr  = ["Metric"] + [df["Driver"].iloc[0] for df in dfs] + ["Best"]
    stat_data = [stat_hdr]
    for label, fn in metrics:
        vals = []
        for df in dfs:
            try:    vals.append(fn(df))
            except: vals.append("-")
        try:
            num_vals = [float(v) for v in vals]
            winner   = dfs[num_vals.index(max(num_vals))]["Driver"].iloc[0]
        except Exception:
            winner = "-"
        stat_data.append([label] + vals + [winner])

    stat_tbl = Table(stat_data, repeatRows=1,
                     colWidths=[4.5*cm]+[3.5*cm]*len(dfs)+[3*cm])
    stat_tbl.setStyle(_tbl_style())
    story.append(stat_tbl)

    # Footer
    story += [
        Spacer(1, 1*cm), _hr(),
        Paragraph(
            f"iRacing Telemetry Analytics v9.1  "
            f"|  {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}",
            st["footer"])
    ]

    doc.build(story)
    return buf.getvalue()


# ════════════════════════════════════════════════════════════════════════════
# CLI TEST
# ════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    n = 3600
    np.random.seed(42)
    dummy = pd.DataFrame({
        "Speed":       np.abs(np.sin(np.linspace(0,6*np.pi,n))*50+50),
        "LapDistPct":  np.tile(np.linspace(0,0.999,n//3),3),
        "Throttle":    np.clip(np.random.rand(n),0,1),
        "Brake":       np.clip(np.random.rand(n)*0.3,0,1),
        "RPM":         np.random.uniform(4000,8000,n),
        "Gear":        np.random.randint(1,7,n),
        "LatAccel":    np.random.normal(0,2,n),
        "LongAccel":   np.random.normal(0,1.5,n),
        "Driver":      "TestDriver",
        "Driver_State":np.random.choice(["Throttle","Braking","Coasting"],n),
        "LapNumber":   np.repeat([1,2,3],n//3),
    })
    meta = {"driver_name":"TestDriver","track":"Laguna Seca",
            "car_name":"GTE","series":"iRacing","weather":"Dry",
            "track_temp":35,"air_temp":28}
    print("Building PDF report...")
    pdf = build_pdf([dummy],[meta])
    with open("test_report.pdf","wb") as f:
        f.write(pdf)
    print(f"test_report.pdf  ({len(pdf)//1024} KB)")
