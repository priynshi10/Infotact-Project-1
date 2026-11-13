"""
AetherHound Technical Project Report PDF Generator.
Compiles a publication-grade, corporate PDF report using ReportLab,
embedding executive headers, tables, code snippets, and experimental figures.
"""

import os
import sys
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak, KeepTogether, HRFlowable
)
from reportlab.pdfgen import canvas

# Ensure UTF-8 output
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

class NumberedCanvas(canvas.Canvas):
    """Two-pass canvas for dynamic total page count."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        if self._pageNumber > 1:
            self.saveState()
            self.setFont("Helvetica", 9)
            self.setFillColor(colors.HexColor("#64748B"))
            # Header
            self.drawString(54, 750, "INFOTACT SOLUTIONS  |  AETHERHOUND TECHNICAL PROJECT REPORT")
            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.5)
            self.line(54, 742, 558, 742)
            # Footer
            self.line(54, 45, 558, 45)
            self.drawString(54, 32, "Confidential - Cyber Security Domain (Ref: ITS/CS/1193)")
            self.drawRightString(558, 32, f"Page {self._pageNumber} of {page_count}")
            self.restoreState()

def generate_pdf():
    pdf_path = "PROJECT_REPORT.pdf"
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )

    styles = getSampleStyleSheet()

    # Custom typography
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=24,
        leading=28,
        textColor=colors.HexColor("#0F172A"),
        spaceAfter=12
    )

    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=13,
        leading=17,
        textColor=colors.HexColor("#0284C7"),
        spaceAfter=18
    )

    h1_style = ParagraphStyle(
        'H1',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=15,
        leading=19,
        textColor=colors.HexColor("#0F172A"),
        spaceBefore=14,
        spaceAfter=8,
        keepWithNext=True
    )

    h2_style = ParagraphStyle(
        'H2',
        parent=styles['Heading3'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#0369A1"),
        spaceBefore=10,
        spaceAfter=6,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        'Body',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14.5,
        textColor=colors.HexColor("#334155"),
        spaceAfter=8
    )

    abstract_style = ParagraphStyle(
        'Abstract',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=9.5,
        leading=14,
        textColor=colors.HexColor("#1E293B")
    )

    story = []

    # ==========================================
    # COVER / TITLE BLOCK
    # ==========================================
    story.append(Paragraph("INFOTACT SOLUTIONS", ParagraphStyle('Company', fontName='Helvetica-Bold', fontSize=12, textColor=colors.HexColor("#0284C7"), spaceAfter=4)))
    story.append(Paragraph("TECHNICAL PROJECT REPORT — CYBER SECURITY DIVISION", ParagraphStyle('SubCompany', fontName='Helvetica-Bold', fontSize=9, textColor=colors.HexColor("#64748B"), spaceAfter=14)))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#0284C7"), spaceBefore=0, spaceAfter=16))

    story.append(Paragraph("AetherHound: Air-Gapped RF & Acoustic Covert Channel Detector", title_style))
    story.append(Paragraph("Autonomous Physical-Layer Signals Intelligence (SIGINT) & Deep Spectral Autoencoder Anomaly Detection", subtitle_style))

    # Metadata Table
    meta_data = [
        [Paragraph("<b>Candidate Name:</b>", body_style), Paragraph("Bharanidharan D", body_style), Paragraph("<b>Reference No.:</b>", body_style), Paragraph("ITS/CS/1193", body_style)],
        [Paragraph("<b>Internship Role:</b>", body_style), Paragraph("Security Admin Associate L1. Intern", body_style), Paragraph("<b>Domain:</b>", body_style), Paragraph("Cyber Security", body_style)],
        [Paragraph("<b>Start Date:</b>", body_style), Paragraph("11/05/2026", body_style), Paragraph("<b>End Date:</b>", body_style), Paragraph("12/05/2026", body_style)],
        [Paragraph("<b>Organization:</b>", body_style), Paragraph("Infotact Solutions, Bengaluru", body_style), Paragraph("<b>Evaluation:</b>", body_style), Paragraph("Month 1 Final Review", body_style)]
    ]
    t_meta = Table(meta_data, colWidths=[1.4*inch, 2.2*inch, 1.4*inch, 2.0*inch])
    t_meta.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F8FAFC")),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(t_meta)
    story.append(Spacer(1, 16))

    # Abstract Box
    abs_title = Paragraph("<b>EXECUTIVE ABSTRACT</b>", ParagraphStyle('AbsH', fontName='Helvetica-Bold', fontSize=10, textColor=colors.HexColor("#0369A1"), spaceAfter=6))
    abs_text = Paragraph(
        "In highly classified defense installations, air-gapped financial databases, and critical national infrastructure, compute clusters are physically severed from all conventional data networks to eliminate external cyber attack vectors. Despite this isolation, advanced persistent threats (APTs) have developed physical-layer side-channel exfiltration vectors—specifically manipulating internal chassis CPU fan speed pulse-width modulation (Fansmitter) or memory bus clock switching (RAMBO) to radiate acoustic Morse code and electromagnetic radio frequencies across the physical air-gap to nearby adversary receivers. "
        "This report presents <b>AetherHound</b>, an autonomous, hyper-local edge appliance and signals intelligence (SIGINT) defense architecture designed to defeat physical-layer covert channel exfiltration. Operating entirely on offline, air-gapped embedded edge hardware without external network or cloud dependencies, AetherHound combines a multichannel acoustic/ultrasonic microphone array with a Software Defined Radio (SDR). "
        "A real-time DSP pipeline processes spectral waterfalls, while an unsupervised deep convolutional-recurrent spectral autoencoder neural network learns baseline structural harmonics and detects artificial covert channels through reconstruction loss spikes and adaptive statistical thresholding. A multi-sensor indoor log-distance path loss spatial triangulation engine isolates the infected server rack with &gt;85% confidence, paired with an automated demodulation engine that reconstructs leaked payloads. Experimental evaluation demonstrated a Receiver Operating Characteristic Area Under the Curve (ROC-AUC) of <b>0.9167</b>, Precision-Recall AUC of <b>0.9430</b>, <b>98.95%</b> precision, and an <b>0.8%</b> false positive rate.",
        abstract_style
    )
    t_abs = Table([[abs_title], [abs_text]], colWidths=[7.0*inch])
    t_abs.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F0F9FF")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#BAE6FD")),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('LEFTPADDING', (0,0), (-1,-1), 12),
        ('RIGHTPADDING', (0,0), (-1,-1), 12),
    ]))
    story.append(t_abs)
    story.append(Spacer(1, 16))

    # ==========================================
    # SECTION 1: INTRODUCTION & PROBLEM FORMULATION
    # ==========================================
    story.append(Paragraph("1. Introduction & Threat Formulation", h1_style))
    story.append(Paragraph(
        "Air-gapped compute systems are deployed in defense, intelligence, and financial environments where physical isolation is assumed to guarantee absolute network security. However, sophisticated adversaries bridge this boundary via compromised maintenance USB flash drives (e.g. Stuxnet) or insider access. Once established, malware cannot establish outbound TCP/IP connections. Adversaries instead exploit physical emissions (TEMPEST side channels) to bridge the air-gap:",
        body_style
    ))
    story.append(Paragraph("<b>• Acoustic PWM Exfiltration (Fansmitter):</b> Malware regulates CPU fan speed PWM duty cycles or schedules intensive math loops to modulate cooling fan RPM. This generates acoustic tones in the 1000 Hz to 3000 Hz band, radiating Morse code or FSK to external recording devices up to 8 meters away.", body_style))
    story.append(Paragraph("<b>• Electromagnetic Memory Bus Leakage (RAMBO):</b> Malware alternates high-throughput RAM memory bus read/write cycles (using AVX streaming stores). The high-frequency switching of DDR data and address lines generates electromagnetic RF emanations in the 24 MHz to 40 MHz band decodable by nearby Software Defined Radios (SDR).", body_style))
    story.append(Paragraph("Conventional firewalls and NIDS are completely blind to physical emissions. Server rooms are acoustically hostile with multiple cooling fans (800-4500 RPM) and HVAC turbulence, requiring advanced DSP and unsupervised machine learning to isolate faint covert channels.", body_style))

    # ==========================================
    # SECTION 2: ARCHITECTURE & DSP PIPELINE
    # ==========================================
    story.append(Paragraph("2. System Architecture & Digital Signal Processing", h1_style))
    story.append(Paragraph(
        "AetherHound operates as a hyper-local physical firewall deployed directly within the server room. It runs on an industrial Raspberry Pi 5 or embedded ARM appliance connected to a 4-channel microphone array and an SDR (HackRF One / RTL-SDR).",
        body_style
    ))

    story.append(Paragraph("Mathematical Formulations of the DSP Pipeline:", h2_style))
    story.append(Paragraph("<b>1. Short-Time Fourier Transform (STFT):</b> Signals are windowed using 1024-point Hann frames with 75% overlap (hop length 256):", body_style))
    story.append(Paragraph("<i>X(m, k) = &Sigma; x[mH + n] &middot; w[n] &middot; e<sup>-j 2&pi; k n / N</sup></i> (yielding 46.875 Hz bin resolution).", body_style))
    story.append(Paragraph("<b>2. Filtering & Interference Rejection:</b> A 4th-order zero-phase Butterworth bandpass filter suppresses frequencies outside 200 Hz – 20 kHz. Cascaded IIR notch filters (Q=30) eliminate 50 Hz, 60 Hz, 100 Hz, and 120 Hz electrical power grid hum.", body_style))
    story.append(Paragraph("<b>3. Max-Pooled Downsampling:</b> Slicing 513 FFT bins down to 64 neural input bins using max-pooling across 8-bin blocks ensures that narrowband covert carrier spikes are preserved at 100% signal strength without averaging attenuation.", body_style))

    # ==========================================
    # SECTION 3: DEEP AUTOENCODER ANOMALY DETECTION
    # ==========================================
    story.append(Paragraph("3. Unsupervised Deep Neural Autoencoder", h1_style))
    story.append(Paragraph(
        "Supervised classification is unfeasible because adversaries can change frequencies or modulation rates. AetherHound employs an Unsupervised Deep Convolutional-Recurrent Autoencoder trained strictly on clean server-room hum. The model compresses 2D spectrogram patches (40 time slices &times; 64 frequency bins) into a 32-dimensional latent bottleneck through 3 Conv2d layers with Batch Normalization and LeakyReLU(0.2).",
        body_style
    ))
    story.append(Paragraph(
        "When an artificial covert carrier tone appears, the model cannot reconstruct the unseen narrowband harmonic structure, causing an anomaly loss spike evaluated as: "
        "<br/>&nbsp;&nbsp;&nbsp;&nbsp;<b>&Epsilon;<sub>anomaly</sub> = MSE(X, X_hat) + 1.5 &middot; max( |X - X_hat|<sup>2</sup> )</b>"
        "<br/>Dynamic thresholding applies: <b>&tau; = &mu;<sub>baseline</sub> + 2.5 &middot; &sigma;<sub>baseline</sub></b> (99% confidence interval).",
        body_style
    ))

    story.append(PageBreak())

    # ==========================================
    # SECTION 4: EXPERIMENTAL RESULTS & FIGURES
    # ==========================================
    story.append(Paragraph("4. Experimental Results & Quantitative Evaluation", h1_style))
    story.append(Paragraph(
        "The complete system was evaluated across 250 test spectrogram patches (125 baseline normal hum frames and 125 covert malware attack frames across multiple fan PWM frequencies and server rack locations).",
        body_style
    ))

    # Benchmark Results Table
    bench_data = [
        [Paragraph("<b>Evaluation Metric</b>", body_style), Paragraph("<b>AetherHound Value</b>", body_style), Paragraph("<b>Target Benchmark</b>", body_style), Paragraph("<b>Assessment</b>", body_style)],
        [Paragraph("ROC Area Under Curve (ROC-AUC)", body_style), Paragraph("<b>0.9167</b>", body_style), Paragraph("&gt; 0.8500", body_style), Paragraph("Exceeded", body_style)],
        [Paragraph("Precision-Recall AUC (PR-AUC)", body_style), Paragraph("<b>0.9430</b>", body_style), Paragraph("&gt; 0.8500", body_style), Paragraph("Exceeded", body_style)],
        [Paragraph("Classification Accuracy", body_style), Paragraph("<b>87.20%</b>", body_style), Paragraph("&gt; 80.00%", body_style), Paragraph("Exceeded", body_style)],
        [Paragraph("Detection Precision", body_style), Paragraph("<b>98.95%</b>", body_style), Paragraph("&gt; 90.00%", body_style), Paragraph("Exceeded", body_style)],
        [Paragraph("Detection Recall (Sensitivity)", body_style), Paragraph("<b>75.20%</b>", body_style), Paragraph("&gt; 70.00%", body_style), Paragraph("Exceeded", body_style)],
        [Paragraph("F1-Score", body_style), Paragraph("<b>0.8545</b>", body_style), Paragraph("&gt; 0.8000", body_style), Paragraph("Exceeded", body_style)],
        [Paragraph("False Positive Rate (FPR)", body_style), Paragraph("<b>0.80%</b>", body_style), Paragraph("&lt; 3.00%", body_style), Paragraph("Exceeded", body_style)],
        [Paragraph("DSP Processing Latency", body_style), Paragraph("<b>0.82 ms</b>", body_style), Paragraph("&lt; 10.0 ms", body_style), Paragraph("Sub-millisecond", body_style)],
        [Paragraph("Neural Inference Latency", body_style), Paragraph("<b>1.40 ms</b>", body_style), Paragraph("&lt; 20.0 ms", body_style), Paragraph("Real-Time CPU", body_style)],
    ]
    t_bench = Table(bench_data, colWidths=[2.6*inch, 1.4*inch, 1.5*inch, 1.5*inch])
    t_bench.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0284C7")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#F8FAFC")]),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(t_bench)
    story.append(Spacer(1, 14))

    # Embed Evaluation Plots
    plots = [
        ("evaluation_results/roc_curve.png", "Figure 1: Receiver Operating Characteristic (ROC) Curve (AUC = 0.9167)"),
        ("evaluation_results/reconstruction_loss_distribution.png", "Figure 2: Reconstruction Error Distribution: Baseline Normal Hum vs Covert Malware Attack"),
        ("evaluation_results/spectrogram_anomaly_detection.png", "Figure 3: Spectrogram Transformation: Baseline Hum, Injected Fansmitter Tone, and Residual Heatmap"),
        ("evaluation_results/confusion_matrix.png", "Figure 4: Confusion Matrix (94 TP, 124 TN, 1 FP, 31 FN)")
    ]

    for p_path, p_caption in plots:
        if os.path.exists(p_path):
            story.append(Paragraph(f"<b>{p_caption}</b>", h2_style))
            # Scale image nicely
            story.append(Image(p_path, width=6.2*inch, height=2.8*inch))
            story.append(Spacer(1, 10))

    story.append(PageBreak())

    # ==========================================
    # SECTION 5: TRIANGULATION & CAPTURE VALIDATION
    # ==========================================
    story.append(Paragraph("5. Spatial Localization & Capture Validation", h1_style))
    story.append(Paragraph(
        "AetherHound implements an indoor Log-Distance Path Loss RSSI model: "
        "<br/>&nbsp;&nbsp;&nbsp;&nbsp;<b>RSSI(d) = P<sub>0</sub> - 10 &middot; n &middot; log<sub>10</sub>(d / d<sub>0</sub>)</b> (with path loss exponent n = 2.2). "
        "During live demonstration, mock malware injected at Rack-Delta (4.0m, 5.0m) was successfully isolated and pinpointed with &gt;85% spatial confidence. "
        "The demodulator engine reconstructed the leaked canary flag <b>FLAG{AIR_GAP_1337}</b>, fulfilling the Mid-Project and Final Review capture validation audits.",
        body_style
    ))

    # ==========================================
    # SECTION 6: MILESTONE COMPLIANCE & CONCLUSION
    # ==========================================
    story.append(Paragraph("6. 4-Week Milestone Completion & Conclusion", h1_style))
    story.append(Paragraph(
        "All four week-wise implementations stipulated in the Project Execution Handbook were completed with 100% compliance: "
        "Week 1 (Sensors & Mock Malware), Week 2 (DSP & 30+ FPS CLI, Mid Review Audit), Week 3 (Deep Autoencoder & Triangulation), and Week 4 (C-Optimization, Demodulation, 16/16 Unit Tests, Technical Report & Presentation Deck).",
        body_style
    ))
    story.append(Paragraph(
        "<b>Conclusion:</b> AetherHound provides an innovative, hyper-local, physical-layer security solution for air-gapped systems, closing the critical vulnerability window where conventional firewalls fail.",
        body_style
    ))
    story.append(Spacer(1, 16))

    # Sign-off Table
    sign_data = [
        [Paragraph("<b>Submitted By:</b>", body_style), Paragraph("<b>Reviewed By:</b>", body_style)],
        [Paragraph("Bharanidharan D<br/>Security Admin Associate L1. Intern<br/>Infotact Solutions", body_style),
         Paragraph("Infotact Solutions Technical Review Committee<br/>Electronic City, Bengaluru, Karnataka", body_style)]
    ]
    t_sign = Table(sign_data, colWidths=[3.5*inch, 3.5*inch])
    t_sign.setStyle(TableStyle([
        ('LINEABOVE', (0,0), (-1,0), 1, colors.HexColor("#0284C7")),
        ('TOPPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(t_sign)

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"[OK] PDF Report successfully compiled: {pdf_path}")

if __name__ == "__main__":
    generate_pdf()
