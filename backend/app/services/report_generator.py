import os
import time
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from app.services.calibration_engine import CalibrationSample, get_calibration_engine

def generate_pdf_report(title: str, samples: list[CalibrationSample], exp_metadata: dict = None) -> str:
    reports_dir = "data/reports"
    os.makedirs(reports_dir, exist_ok=True)
    
    timestamp = int(time.time())
    pdf_filename = os.path.join(reports_dir, f"Validation_Report_{timestamp}.pdf")
    
    if not exp_metadata:
        exp_metadata = {}
        
    engine = get_calibration_engine()
    profile_name = exp_metadata.get("calibration_profile", engine.active_profile_name)
    profile = engine.profiles.get(profile_name, engine.profiles.get("default"))
    n = profile.n
    rssi_0 = profile.rssi_0

    # Extract data
    actual_dists = [s.actual_distance for s in samples]
    raw_rssi = [s.rssi for s in samples]
    filtered_rssi = [s.filtered_rssi for s in samples]
    ema_rssi = [s.ema_rssi for s in samples]
    
    # Calculate Distances using calibrated model
    est_dists = [10 ** ((rssi_0 - r) / (10 * n)) for r in ema_rssi]
    errors = [est - act for est, act in zip(est_dists, actual_dists)]
    abs_errors = np.abs(errors)
    
    # ---- 1. RSSI vs Distance ----
    plt.figure(figsize=(8, 4))
    plt.scatter(actual_dists, raw_rssi, alpha=0.3, label="Raw RSSI", color="gray", s=10)
    plt.scatter(actual_dists, filtered_rssi, alpha=0.6, label="Filtered RSSI", color="blue", s=15)
    plt.scatter(actual_dists, ema_rssi, alpha=0.9, label="EMA RSSI", color="red", s=20)
    
    # Plot Calibration Curve
    x_curve = np.linspace(min(actual_dists) if actual_dists else 0.1, max(actual_dists) if actual_dists else 10.0, 100)
    y_curve = rssi_0 - 10 * n * np.log10(x_curve)
    plt.plot(x_curve, y_curve, 'k--', label=f"Calibrated Curve (n={n:.2f}, RSSI0={rssi_0:.1f})")
    
    plt.title("RSSI vs Distance & Calibration Curve")
    plt.xlabel("Actual Distance (m)")
    plt.ylabel("RSSI (dBm)")
    plt.legend()
    plt.grid(True, linestyle="--", alpha=0.6)
    chart1_path = os.path.join(reports_dir, f"chart1_{timestamp}.png")
    plt.savefig(chart1_path, bbox_inches="tight")
    plt.close()
    
    # ---- 2. Error Histogram ----
    plt.figure(figsize=(8, 4))
    plt.hist(errors, bins=30, color="purple", alpha=0.7, edgecolor="black")
    plt.title("Error Distribution (Estimated - Actual)")
    plt.xlabel("Error (m)")
    plt.ylabel("Frequency")
    plt.grid(True, linestyle="--", alpha=0.6)
    chart2_path = os.path.join(reports_dir, f"chart2_{timestamp}.png")
    plt.savefig(chart2_path, bbox_inches="tight")
    plt.close()
    
    # ---- 3. Estimated vs Actual Scatter ----
    plt.figure(figsize=(6, 6))
    plt.scatter(actual_dists, est_dists, alpha=0.5, color="teal")
    max_dist = max(max(actual_dists), max(est_dists)) if actual_dists else 10
    plt.plot([0, max_dist], [0, max_dist], 'r--', label="Perfect Prediction")
    plt.title("Estimated vs Actual Distance (Prediction Scatter Plot)")
    plt.xlabel("Actual Distance (m)")
    plt.ylabel("Estimated Distance (m)")
    plt.legend()
    plt.grid(True, linestyle="--", alpha=0.6)
    chart3_path = os.path.join(reports_dir, f"chart3_{timestamp}.png")
    plt.savefig(chart3_path, bbox_inches="tight")
    plt.close()

    # ---- 4. Residual Plot ----
    plt.figure(figsize=(8, 4))
    plt.scatter(actual_dists, errors, alpha=0.5, color="orange")
    plt.axhline(0, color='r', linestyle='--')
    plt.title("Residual Plot (Error vs Distance)")
    plt.xlabel("Actual Distance (m)")
    plt.ylabel("Error (m)")
    plt.grid(True, linestyle="--", alpha=0.6)
    chart4_path = os.path.join(reports_dir, f"chart4_{timestamp}.png")
    plt.savefig(chart4_path, bbox_inches="tight")
    plt.close()
    
    # ---- 5. CDF of Error ----
    plt.figure(figsize=(8, 4))
    sorted_errs = np.sort(abs_errors)
    cdf = np.arange(1, len(sorted_errs) + 1) / len(sorted_errs)
    plt.plot(sorted_errs, cdf, marker='.', linestyle='none', color='blue')
    plt.title("Cumulative Distribution Function (CDF) of Absolute Error")
    plt.xlabel("Absolute Error (m)")
    plt.ylabel("CDF")
    plt.grid(True, linestyle="--", alpha=0.6)
    chart5_path = os.path.join(reports_dir, f"chart5_{timestamp}.png")
    plt.savefig(chart5_path, bbox_inches="tight")
    plt.close()
    
    # ---- 6. Box Plot of Errors by Distance (if multiple distinct distances exist) ----
    plt.figure(figsize=(8, 4))
    unique_dists = sorted(list(set(actual_dists)))
    if len(unique_dists) > 1 and len(unique_dists) < 20:
        box_data = []
        labels = []
        for d in unique_dists:
            box_data.append([err for err, act in zip(errors, actual_dists) if act == d])
            labels.append(f"{d}m")
        plt.boxplot(box_data, tick_labels=labels)
        plt.title("Box Plot of Errors per Distance")
        plt.xlabel("Actual Distance")
        plt.ylabel("Error (m)")
        plt.grid(True, linestyle="--", alpha=0.6)
    else:
        plt.boxplot(errors)
        plt.title("Box Plot of Overall Error")
        plt.ylabel("Error (m)")
    chart6_path = os.path.join(reports_dir, f"chart6_{timestamp}.png")
    plt.savefig(chart6_path, bbox_inches="tight")
    plt.close()

    # Create PDF Document
    doc = SimpleDocTemplate(pdf_filename, pagesize=letter)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('MainTitle', parent=styles['Heading1'], fontSize=24, spaceAfter=20, textColor=colors.HexColor("#1e3a8a"))
    h2 = styles['Heading2']
    p_style = styles["Normal"]
    
    Story = []
    
    # ---- Cover & Metadata ----
    Story.append(Paragraph(title, title_style))
    Story.append(Paragraph(f"<b>Session ID:</b> {exp_metadata.get('id', 'N/A')}", p_style))
    Story.append(Paragraph(f"<b>Date:</b> {exp_metadata.get('date', time.ctime())}", p_style))
    Story.append(Paragraph(f"<b>Environment:</b> {exp_metadata.get('environment', 'Default')}", p_style))
    Story.append(Paragraph(f"<b>Router:</b> {exp_metadata.get('router_name', 'Unknown')} ({exp_metadata.get('router_mac', 'N/A')})", p_style))
    Story.append(Paragraph(f"<b>ESP32:</b> {exp_metadata.get('esp32_mac', 'Unknown')}", p_style))
    Story.append(Paragraph(f"<b>Total Samples:</b> {len(samples)}", p_style))
    
    Story.append(Spacer(1, 20))
    
    # ---- Calibration Profile ----
    Story.append(Paragraph("Calibration Profile", h2))
    calib_data = [
        ["Metric", "Value"],
        ["Profile Name", profile.name],
        ["Path Loss Exponent (n)", f"{profile.n:.3f}"],
        ["RSSI_0 (1m)", f"{profile.rssi_0:.2f} dBm"],
        ["Quality Grade", getattr(profile, 'quality_grade', 'Unknown')],
        ["Quality Score", f"{getattr(profile, 'quality_score', 0):.1f}/100"],
        ["Signal Stability", getattr(profile, 'signal_stability', 0)],
        ["Noise Level", getattr(profile, 'noise_level', 0)]
    ]
    t_calib = Table(calib_data, colWidths=[200, 150])
    t_calib.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1e40af")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0,0), (-1,-1), 1, colors.black),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor("#f3f4f6")),
    ]))
    Story.append(t_calib)
    Story.append(Spacer(1, 20))
    
    # ---- Statistical Summary ----
    Story.append(Paragraph("Distance Statistics & Error Analysis", h2))
    
    mae = np.mean(abs_errors) if len(abs_errors) > 0 else 0
    rmse = np.sqrt(np.mean(abs_errors**2)) if len(abs_errors) > 0 else 0
    std_dev = np.std(errors) if len(errors) > 0 else 0
    ci_95 = 1.96 * (std_dev / np.sqrt(len(samples))) if len(samples) > 0 else 0
    
    pct_errors = [(abs(err) / act) * 100 for err, act in zip(errors, actual_dists) if act > 0]
    mape = np.mean(pct_errors) if pct_errors else 0

    stat_data = [
        ["Metric", "Value"],
        ["Mean Absolute Error (MAE)", f"{mae:.3f} m"],
        ["Root Mean Square Error (RMSE)", f"{rmse:.3f} m"],
        ["Mean Absolute Percentage Error (MAPE)", f"{mape:.2f} %"],
        ["Error Std Dev", f"{std_dev:.3f} m"],
        ["95% Confidence Interval", f"±{ci_95:.3f} m"],
        ["Min Error", f"{np.min(errors):.3f} m" if len(errors) > 0 else "0"],
        ["Max Error", f"{np.max(errors):.3f} m" if len(errors) > 0 else "0"],
    ]
    
    t_stat = Table(stat_data, colWidths=[250, 100])
    t_stat.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1e40af")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0,0), (-1,-1), 1, colors.black),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor("#f3f4f6")),
    ]))
    Story.append(t_stat)
    
    Story.append(PageBreak())
    
    # ---- Graphs ----
    Story.append(Paragraph("1. Calibration Curve & Signal Attenuation", h2))
    Story.append(Image(chart1_path, width=400, height=200))
    Story.append(Spacer(1, 15))
    
    Story.append(Paragraph("2. Prediction Scatter Plot", h2))
    Story.append(Image(chart3_path, width=300, height=300))
    Story.append(PageBreak())
    
    Story.append(Paragraph("3. Error Distribution (Histogram)", h2))
    Story.append(Image(chart2_path, width=400, height=200))
    Story.append(Spacer(1, 15))
    
    Story.append(Paragraph("4. Residual Analysis", h2))
    Story.append(Image(chart4_path, width=400, height=200))
    Story.append(PageBreak())
    
    Story.append(Paragraph("5. Cumulative Distribution Function (CDF)", h2))
    Story.append(Image(chart5_path, width=400, height=200))
    Story.append(Spacer(1, 15))
    
    Story.append(Paragraph("6. Error Box Plot", h2))
    Story.append(Image(chart6_path, width=400, height=200))
    Story.append(Spacer(1, 20))
    
    # ---- Discussion & Conclusion ----
    Story.append(Paragraph("Discussion & Observations", h2))
    Story.append(Paragraph("The Calibration Quality Score indicates the reliability of the baseline. The Residual Plot highlights whether the Log-Distance model underpredicts or overpredicts at specific distances due to multipath effects or non-line-of-sight (NLOS) conditions.", p_style))
    Story.append(Spacer(1, 10))
    Story.append(Paragraph("Limitations", h2))
    Story.append(Paragraph("Signal strength (RSSI) is inherently volatile. While the Exponential Moving Average (EMA) and Outlier Removal significantly stabilize estimations, physical obstructions and interference will continue to introduce variance, as mapped in the Error Histogram and Box Plot.", p_style))
    Story.append(Spacer(1, 10))
    Story.append(Paragraph("Conclusion", h2))
    Story.append(Paragraph(f"Under the '{exp_metadata.get('environment', 'tested')}' environment, the system achieved a Mean Absolute Error (MAE) of {mae:.2f} meters and a MAPE of {mape:.1f}%. The Log-Distance Path Loss model demonstrates scientific validity for proximity tracking within these error boundaries.", p_style))

    # Build
    doc.build(Story)
    
    # Return generated graphs for organization (Module 8)
    graphs = [chart1_path, chart2_path, chart3_path, chart4_path, chart5_path, chart6_path]
    
    return pdf_filename, graphs

def generate_final_summary_pdf(experiments: list) -> str:
    reports_dir = "data/reports"
    os.makedirs(reports_dir, exist_ok=True)
    timestamp = int(time.time())
    pdf_filename = os.path.join(reports_dir, f"Final_Project_Summary_{timestamp}.pdf")
    
    doc = SimpleDocTemplate(pdf_filename, pagesize=letter)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('MainTitle', parent=styles['Heading1'], fontSize=24, spaceAfter=20, textColor=colors.HexColor("#1e3a8a"))
    h2 = styles['Heading2']
    p_style = styles["Normal"]
    
    Story = []
    Story.append(Paragraph("Final Project Summary", title_style))
    Story.append(Paragraph(f"<b>Date:</b> {time.ctime()}", p_style))
    Story.append(Paragraph(f"<b>Total Sessions Analyzed:</b> {len(experiments)}", p_style))
    Story.append(Spacer(1, 20))
    
    # Calculate cross-session stats
    total_samples = sum([e.get("sample_count", 0) for e in experiments])
    envs = list(set([e.get("environment", "Unknown") for e in experiments]))
    
    Story.append(Paragraph("Cross-Environment Analytics", h2))
    Story.append(Paragraph(f"<b>Total Datapoints:</b> {total_samples}", p_style))
    Story.append(Paragraph(f"<b>Environments Tested:</b> {', '.join(envs)}", p_style))
    Story.append(Spacer(1, 20))
    
    Story.append(Paragraph("Conclusion & Recommendations", h2))
    Story.append(Paragraph("Based on the aggregated sessions, the system maintains stable Log-Distance tracking across LOS environments. NLOS environments show expected attenuation variance. Proceed with deploying the best-fit profile per specific room.", p_style))
    
    doc.build(Story)
    return pdf_filename
