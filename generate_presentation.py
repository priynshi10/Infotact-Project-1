"""
AetherHound Executive Presentation Generator.
Generates a polished 12-slide PowerPoint presentation (.pptx)
for the Mid-Project Review and Final Project Review presentations.
"""

import os
import sys
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE

# Ensure UTF-8 output
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def build_presentation():
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)  # 16:9 widescreen layout

    blank_layout = prs.slide_layouts[6]

    # Color Palette: Cyber SIGINT Tactical Theme
    COLOR_BG = RGBColor(15, 23, 42)        # Deep Navy / Slate (#0F172A)
    COLOR_CARD = RGBColor(30, 41, 59)      # Slate Card (#1E293B)
    COLOR_CYAN = RGBColor(6, 182, 212)     # Cyan Accent (#06B6D4)
    COLOR_GREEN = RGBColor(34, 197, 94)    # Neon Green (#22C55E)
    COLOR_RED = RGBColor(239, 68, 68)      # Alert Red (#EF4444)
    COLOR_WHITE = RGBColor(248, 250, 252)  # Bright White (#F8FAFC)
    COLOR_MUTED = RGBColor(148, 163, 184)  # Slate Muted (#94A3B8)

    def set_slide_background(slide):
        bg = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(13.333), Inches(7.5))
        bg.fill.solid()
        bg.fill.fore_color.rgb = COLOR_BG
        bg.line.color.rgb = COLOR_BG
        return bg

    def add_header(slide, title_text, category_text="INFOTACT SOLUTIONS | CYBER SECURITY INTERNSHIP"):
        cat_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.4), Inches(11.7), Inches(0.4))
        tf_cat = cat_box.text_frame
        tf_cat.word_wrap = True
        p_cat = tf_cat.paragraphs[0]
        p_cat.text = category_text.upper()
        p_cat.font.size = Pt(11)
        p_cat.font.bold = True
        p_cat.font.color.rgb = COLOR_CYAN

        title_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.75), Inches(11.7), Inches(0.8))
        tf_title = title_box.text_frame
        tf_title.word_wrap = True
        p_title = tf_title.paragraphs[0]
        p_title.text = title_text
        p_title.font.size = Pt(26)
        p_title.font.bold = True
        p_title.font.color.rgb = COLOR_WHITE

    # ==========================================
    # SLIDE 1: TITLE SLIDE
    # ==========================================
    s1 = prs.slides.add_slide(blank_layout)
    set_slide_background(s1)

    tbox = s1.shapes.add_textbox(Inches(1.0), Inches(1.8), Inches(11.333), Inches(3.8))
    tf1 = tbox.text_frame
    tf1.word_wrap = True

    p0 = tf1.paragraphs[0]
    p0.text = "INFOTACT SOLUTIONS - CYBER SECURITY DIVISION"
    p0.font.size = Pt(14)
    p0.font.bold = True
    p0.font.color.rgb = COLOR_CYAN
    p0.space_after = Pt(15)

    p1 = tf1.add_paragraph()
    p1.text = "AETHERHOUND: AIR-GAPPED RF & ACOUSTIC COVERT CHANNEL DETECTOR"
    p1.font.size = Pt(32)
    p1.font.bold = True
    p1.font.color.rgb = COLOR_WHITE
    p1.space_after = Pt(15)

    p2 = tf1.add_paragraph()
    p2.text = "Physical-Layer Signals Intelligence (SIGINT) & Deep Unsupervised Neural Anomaly Detection"
    p2.font.size = Pt(18)
    p2.font.color.rgb = COLOR_GREEN
    p2.space_after = Pt(30)

    p3 = tf1.add_paragraph()
    p3.text = "Intern Name: Bharanidharan D  |  Role: Security Admin Associate L1. Intern  |  Ref: ITS/CS/1193\nDomain: Cyber Security  |  Project Duration: 1 Month  |  Date: October 2026"
    p3.font.size = Pt(13)
    p3.font.color.rgb = COLOR_MUTED

    # ==========================================
    # SLIDE 2: PROBLEM STATEMENT
    # ==========================================
    s2 = prs.slides.add_slide(blank_layout)
    set_slide_background(s2)
    add_header(s2, "Problem Statement: The Air-Gap Security Illusion")

    c1 = s2.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(1.8), Inches(5.6), Inches(5.0))
    c1.fill.solid()
    c1.fill.fore_color.rgb = COLOR_CARD
    c1.line.color.rgb = COLOR_RED
    tf_c1 = c1.text_frame
    tf_c1.word_wrap = True
    p = tf_c1.paragraphs[0]
    p.text = "The Threat: Physical Side-Channel Exfiltration"
    p.font.size = Pt(18)
    p.font.bold = True
    p.font.color.rgb = COLOR_RED
    p.space_after = Pt(12)

    bullets1 = [
        "Air-Gapped Systems (military, nuclear, HSMs) lack network interfaces (Ethernet, Wi-Fi, Bluetooth).",
        "Adversaries breach isolation using malware introduced via infected maintenance media or supply chain attacks.",
        "Malware manipulates physical server actuators to leak data across the air-gap:",
        "  • Acoustic PWM: Modulating CPU fan RPM in Morse code or FSK (Fansmitter).",
        "  • Acoustic Actuator: Stepping HDD read/write heads (DiskFiltration).",
        "  • RF Memory Bus: Modulating RAM bus access to radiate HF/VHF radio signals (RAMBO)."
    ]
    for b in bullets1:
        p = tf_c1.add_paragraph()
        p.text = b
        p.font.size = Pt(13)
        p.font.color.rgb = COLOR_WHITE
        p.space_after = Pt(6)

    c2 = s2.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(6.8), Inches(1.8), Inches(5.6), Inches(5.0))
    c2.fill.solid()
    c2.fill.fore_color.rgb = COLOR_CARD
    c2.line.color.rgb = COLOR_CYAN
    tf_c2 = c2.text_frame
    tf_c2.word_wrap = True
    p = tf_c2.paragraphs[0]
    p.text = "The Defense Deficit"
    p.font.size = Pt(18)
    p.font.bold = True
    p.font.color.rgb = COLOR_CYAN
    p.space_after = Pt(12)

    bullets2 = [
        "Traditional Firewalls & NIDS inspect packet syntax (IP, TCP, UDP). They are completely blind to physical emissions.",
        "Server Rooms are Acoustically Hostile: Multi-blade fan harmonics (800-4500 RPM) and HVAC turbulence drown out covert signals.",
        "Low Bandwidth Exfiltration (1-15 bps) operates at negative or near-zero SNR, easily missed by simple thresholding.",
        "Need: An autonomous, air-gapped SIGINT appliance that learns the baseline hum and detects micro-acoustic & RF anomalies without cloud dependencies."
    ]
    for b in bullets2:
        p = tf_c2.add_paragraph()
        p.text = b
        p.font.size = Pt(13)
        p.font.color.rgb = COLOR_WHITE
        p.space_after = Pt(8)

    # ==========================================
    # SLIDE 3: NOVEL IDEA - AETHERHOUND
    # ==========================================
    s3 = prs.slides.add_slide(blank_layout)
    set_slide_background(s3)
    add_header(s3, "The Novel Solution: AetherHound SIGINT Appliance")

    col_w = Inches(3.6)
    cards_data = [
        ("Hyper-Local Sensor Array", COLOR_CYAN, [
            "Deploys directly in server room perimeter.",
            "Combines 4-channel microphone array (48/96 kHz) with Software Defined Radio (HackRF/RTL-SDR).",
            "Zero cloud connectivity; zero web APIs; fully air-gapped edge appliance."
        ]),
        ("Unsupervised ML Baseline", COLOR_GREEN, [
            "Trains Deep Convolutional Autoencoder solely on normal server room hum.",
            "Learns complex multi-blade fan harmonics and structural vibration physics.",
            "Covert channels spike reconstruction error due to artificial spectral structures."
        ]),
        ("Spatial Pinpointing & Decoding", COLOR_RED, [
            "Uses Log-Distance Path Loss & TDoA multilateration.",
            "Pinpoints the exact infected server rack (e.g. Rack-Delta) in real time.",
            "Demodulates intercepted Morse code / FSK to recover exfiltrated canary strings."
        ])
    ]

    for i, (title, color, items) in enumerate(cards_data):
        cx = Inches(0.8 + i * 4.0)
        c = s3.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, cx, Inches(1.8), col_w, Inches(5.0))
        c.fill.solid()
        c.fill.fore_color.rgb = COLOR_CARD
        c.line.color.rgb = color
        tf = c.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = title
        p.font.size = Pt(17)
        p.font.bold = True
        p.font.color.rgb = color
        p.space_after = Pt(14)

        for item in items:
            p = tf.add_paragraph()
            p.text = f"• {item}"
            p.font.size = Pt(13)
            p.font.color.rgb = COLOR_WHITE
            p.space_after = Pt(10)

    # ==========================================
    # SLIDE 4: SYSTEM ARCHITECTURE
    # ==========================================
    s4 = prs.slides.add_slide(blank_layout)
    set_slide_background(s4)
    add_header(s4, "End-to-End System Architecture")

    steps = [
        ("1. Ingestion Layer", "Microphone Array & HackRF SDR (IQ @ 2.4 MSPS, Audio @ 48 kHz)", COLOR_CYAN),
        ("2. Digital Signal Processing", "4th-order Butterworth Bandpass, 50/60Hz Notch, STFT, Welch PSD", COLOR_GREEN),
        ("3. Deep Neural Inference", "PyTorch Conv2D Autoencoder calculates reconstruction loss & dynamic threshold", COLOR_CYAN),
        ("4. Spatial Triangulation", "Log-Distance Path Loss RSSI matches sensor readings to rack coordinates", COLOR_GREEN),
        ("5. Demodulator & Alerting", "Demodulates Morse/FSK payload, flashes RED CLI alert, triggers buzzer", COLOR_RED)
    ]

    for i, (stitle, sdesc, scolor) in enumerate(steps):
        sy = Inches(1.8 + i * 1.0)
        box = s4.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), sy, Inches(11.7), Inches(0.8))
        box.fill.solid()
        box.fill.fore_color.rgb = COLOR_CARD
        box.line.color.rgb = scolor
        tf = box.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = f"{stitle}:  "
        p.font.size = Pt(15)
        p.font.bold = True
        p.font.color.rgb = scolor
        run = p.add_run()
        run.text = sdesc
        run.font.size = Pt(13)
        run.font.bold = False
        run.font.color.rgb = COLOR_WHITE

    # ==========================================
    # SLIDE 5: HARDWARE & SENSOR DESIGN
    # ==========================================
    s5 = prs.slides.add_slide(blank_layout)
    set_slide_background(s5)
    add_header(s5, "Edge Hardware Layer & Sensor Array Specifications")

    hw_specs = [
        ("Edge Compute Host", "Industrial Raspberry Pi 5 / 4B", "Quad-Core ARM Cortex-A76 @ 2.4 GHz, 8 GB LPDDR4X, zero-cloud headless deployment"),
        ("Acoustic Sensor", "ReSpeaker 4-Mic Circular Array v2.0", "4-element microphone array, 48 kHz / 96 kHz ultrasonic, XMOS XVF3000 voice processor"),
        ("Software Defined Radio", "Great Scott Gadgets HackRF One", "1 MHz – 6 GHz RF range, 2.4 MSPS standard capture, calibrated for 24.5 MHz RAM bus"),
        ("Alternative SDR", "RTL-SDR Blog V4", "Low-cost R828D tuner with TCXO (0.5 PPM) and HF direct sampling for memory leakage"),
        ("Physical Alert Peripheral", "Active Piezo Buzzer", "Connected to GPIO Pin 18 (PWM), pulses audible alarm upon verified covert intrusion"),
        ("Tactical Display", "Direct HDMI / Local TTY Console", "Runs native Curses / Rich terminal UI at 30+ FPS without web components or X11")
    ]

    for i, (name, model, details) in enumerate(hw_specs):
        col = i % 2
        row = i // 2
        bx = Inches(0.8 + col * 5.9)
        by = Inches(1.8 + row * 1.7)

        c = s5.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, bx, by, Inches(5.6), Inches(1.5))
        c.fill.solid()
        c.fill.fore_color.rgb = COLOR_CARD
        c.line.color.rgb = COLOR_CYAN
        tf = c.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = f"{name}: {model}"
        p.font.size = Pt(14)
        p.font.bold = True
        p.font.color.rgb = COLOR_CYAN
        p.space_after = Pt(4)
        p2 = tf.add_paragraph()
        p2.text = details
        p2.font.size = Pt(11)
        p2.font.color.rgb = COLOR_WHITE

    # ==========================================
    # SLIDE 6: DSP PIPELINE & SPECTRAL ANALYSIS
    # ==========================================
    s6 = prs.slides.add_slide(blank_layout)
    set_slide_background(s6)
    add_header(s6, "Digital Signal Processing (DSP) Pipeline")

    c1 = s6.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(1.8), Inches(5.6), Inches(5.0))
    c1.fill.solid()
    c1.fill.fore_color.rgb = COLOR_CARD
    c1.line.color.rgb = COLOR_GREEN
    tf_c1 = c1.text_frame
    tf_c1.word_wrap = True
    p = tf_c1.paragraphs[0]
    p.text = "Mathematical Flowgraph & Filters"
    p.font.size = Pt(18)
    p.font.bold = True
    p.font.color.rgb = COLOR_GREEN
    p.space_after = Pt(10)

    dsp_items = [
        "DC Offset Removal: Eliminates sensor bias and SDR LO leakage.",
        "Notch Rejection: Cascaded IIR notch filters at 50 Hz, 60 Hz, 100 Hz, 120 Hz suppress AC power grid interference.",
        "Butterworth Bandpass: 4th-order zero-phase filtering across 200 Hz – 20 kHz.",
        "STFT Spectrogram: 1024-point FFT with Hann windowing and 75% overlap (46.875 Hz bin resolution).",
        "Max-Pool Decimation: Downsamples 513 spectral bins to 64 bins via max-pooling, ensuring narrowband carriers are never averaged out."
    ]
    for it in dsp_items:
        p = tf_c1.add_paragraph()
        p.text = f"• {it}"
        p.font.size = Pt(12)
        p.font.color.rgb = COLOR_WHITE
        p.space_after = Pt(6)

    c2 = s6.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(6.8), Inches(1.8), Inches(5.6), Inches(5.0))
    c2.fill.solid()
    c2.fill.fore_color.rgb = COLOR_CARD
    c2.line.color.rgb = COLOR_CYAN
    tf_c2 = c2.text_frame
    tf_c2.word_wrap = True
    p = tf_c2.paragraphs[0]
    p.text = "Vectorized SIMD & Latency Performance"
    p.font.size = Pt(18)
    p.font.bold = True
    p.font.color.rgb = COLOR_CYAN
    p.space_after = Pt(10)

    perf_items = [
        "Memory Layout: C-contiguous aligned buffers prevent heap allocation during streaming.",
        "Spectral Kurtosis: Measures non-Gaussian impulsiveness to detect transient data bursts.",
        "Spectral Entropy: Normalized Shannon entropy flags carrier collapses from ~0.85 down to ~0.3.",
        "Benchmarked Performance: Sub-millisecond execution (<1 ms per 2048-sample slice).",
        "Rendering Speed: Sustained 30+ frames per second console update on headless ARM hardware."
    ]
    for it in perf_items:
        p = tf_c2.add_paragraph()
        p.text = f"• {it}"
        p.font.size = Pt(12)
        p.font.color.rgb = COLOR_WHITE
        p.space_after = Pt(6)

    # ==========================================
    # SLIDE 7: DEEP AUTOENCODER MODEL
    # ==========================================
    s7 = prs.slides.add_slide(blank_layout)
    set_slide_background(s7)
    add_header(s7, "Unsupervised PyTorch Spectral Autoencoder")

    c1 = s7.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(1.8), Inches(5.6), Inches(5.0))
    c1.fill.solid()
    c1.fill.fore_color.rgb = COLOR_CARD
    c1.line.color.rgb = COLOR_CYAN
    tf_c1 = c1.text_frame
    tf_c1.word_wrap = True
    p = tf_c1.paragraphs[0]
    p.text = "Neural Network Architecture"
    p.font.size = Pt(18)
    p.font.bold = True
    p.font.color.rgb = COLOR_CYAN
    p.space_after = Pt(10)

    ae_items = [
        "Input: 2D Spectrogram Patch (1, 40, 64) -> 40 time slices x 64 frequency bins.",
        "Encoder: 3 Conv2d layers (16, 32, 64 filters) with Batch Normalization & LeakyReLU(0.2).",
        "Latent Bottleneck: Flattened to 32 dimensions, forcing the model to learn only stationary blade hum.",
        "Decoder: Symmetrical ConvTranspose2d architecture with Sigmoid output in [0, 1].",
        "Total Parameters: 190,229 trainable weights. Fast CPU inference in 1.4 ms."
    ]
    for it in ae_items:
        p = tf_c1.add_paragraph()
        p.text = f"• {it}"
        p.font.size = Pt(12)
        p.font.color.rgb = COLOR_WHITE
        p.space_after = Pt(6)

    c2 = s7.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(6.8), Inches(1.8), Inches(5.6), Inches(5.0))
    c2.fill.solid()
    c2.fill.fore_color.rgb = COLOR_CARD
    c2.line.color.rgb = COLOR_GREEN
    tf_c2 = c2.text_frame
    tf_c2.word_wrap = True
    p = tf_c2.paragraphs[0]
    p.text = "Loss Formulation & Adaptive Threshold"
    p.font.size = Pt(18)
    p.font.bold = True
    p.font.color.rgb = COLOR_GREEN
    p.space_after = Pt(10)

    loss_items = [
        "Combined Loss Function: MSE + Spectral Frequency Gradient Loss:\n  Loss = MSE(X, X_hat) + 0.3 * MSE(grad_orig, grad_recon)",
        "Anomaly Detection Metric: Incorporates Peak Residual:\n  Error = MSE + 1.5 * max(residual)",
        "Adaptive Dynamic Threshold:\n  Tau = Mean_baseline + 2.5 * Std_baseline",
        "Welford's Online Accumulator: Slowly tracks ambient thermal drift without false-alarming on seasonal room changes."
    ]
    for it in loss_items:
        p = tf_c2.add_paragraph()
        p.text = f"• {it}"
        p.font.size = Pt(12)
        p.font.color.rgb = COLOR_WHITE
        p.space_after = Pt(6)

    # ==========================================
    # SLIDE 8: MOCK MALWARE & CAPTURE VALIDATION
    # ==========================================
    s8 = prs.slides.add_slide(blank_layout)
    set_slide_background(s8)
    add_header(s8, "Mock Malware Proof-of-Concept & Mid-Review Audit")

    c1 = s8.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(1.8), Inches(5.6), Inches(5.0))
    c1.fill.solid()
    c1.fill.fore_color.rgb = COLOR_CARD
    c1.line.color.rgb = COLOR_RED
    tf_c1 = c1.text_frame
    tf_c1.word_wrap = True
    p = tf_c1.paragraphs[0]
    p.text = "Offensive Simulation Suite"
    p.font.size = Pt(18)
    p.font.bold = True
    p.font.color.rgb = COLOR_RED
    p.space_after = Pt(10)

    mal_items = [
        "Fansmitter Mock Malware (fansmitter.py): Benign script controlling CPU load to induce fan PWM acoustic frequency shifts.",
        "Morse Code Encoding: Encodes plaintext canary messages (e.g. 'FLAG{1337}') into short/long acoustic tones.",
        "RAMBO RF Malware (rambo_rf.py): Benign memory bus burst modulation generating electromagnetic pulses at 24.5 MHz.",
        "Safety Clamps: Configured with dry-run simulation mode to prevent physical CPU thermal stress or hardware damage."
    ]
    for it in mal_items:
        p = tf_c1.add_paragraph()
        p.text = f"• {it}"
        p.font.size = Pt(12)
        p.font.color.rgb = COLOR_WHITE
        p.space_after = Pt(6)

    c2 = s8.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(6.8), Inches(1.8), Inches(5.6), Inches(5.0))
    c2.fill.solid()
    c2.fill.fore_color.rgb = COLOR_CARD
    c2.line.color.rgb = COLOR_GREEN
    tf_c2 = c2.text_frame
    tf_c2.word_wrap = True
    p = tf_c2.paragraphs[0]
    p.text = "Mid-Project Review: Capture Validation Audit"
    p.font.size = Pt(18)
    p.font.bold = True
    p.font.color.rgb = COLOR_GREEN
    p.space_after = Pt(10)

    audit_items = [
        "Requirement: Prove hardware & DSP isolates specific frequency spike caused by mock CPU fan malware.",
        "Target Malware Tone: 1950.0 Hz acoustic pulse injected at Rack-Delta.",
        "Measured Carrier Frequency: 1921.9 Hz – 1968.8 Hz (within 1-bin FFT resolution).",
        "Carrier SNR: 48.9 dB above background server noise.",
        "Baseline False Positives: 0 during 15 baseline audit frames.",
        "Audit Status: VERIFIED & PASSED (exfil_test_runner.py)."
    ]
    for it in audit_items:
        p = tf_c2.add_paragraph()
        p.text = f"• {it}"
        p.font.size = Pt(12)
        p.font.color.rgb = COLOR_WHITE
        p.space_after = Pt(6)

    # ==========================================
    # SLIDE 9: MODEL BENCHMARKS & EVALUATION
    # ==========================================
    s9 = prs.slides.add_slide(blank_layout)
    set_slide_background(s9)
    add_header(s9, "Experimental Results & Model Evaluation")

    metrics_cards = [
        ("ROC-AUC", "0.9167", "Area Under Receiver Operating Characteristic", COLOR_CYAN),
        ("PR-AUC", "0.9430", "Area Under Precision-Recall Curve", COLOR_GREEN),
        ("Precision", "98.95%", "Near-zero false alarms in noisy server room", COLOR_CYAN),
        ("Accuracy", "87.2%", "Overall classification accuracy", COLOR_GREEN),
        ("False Positive Rate", "0.8%", "Trained rejection of HVAC transients", COLOR_RED),
        ("Frame Latency", "1.4 ms", "Real-time edge CPU execution speed", COLOR_CYAN)
    ]

    for i, (name, val, desc, color) in enumerate(metrics_cards):
        col = i % 3
        row = i // 3
        bx = Inches(0.8 + col * 3.95)
        by = Inches(1.8 + row * 2.5)

        c = s9.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, bx, by, Inches(3.7), Inches(2.2))
        c.fill.solid()
        c.fill.fore_color.rgb = COLOR_CARD
        c.line.color.rgb = color
        tf = c.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = name
        p.font.size = Pt(15)
        p.font.bold = True
        p.font.color.rgb = COLOR_MUTED
        p.space_after = Pt(6)

        p2 = tf.add_paragraph()
        p2.text = val
        p2.font.size = Pt(28)
        p2.font.bold = True
        p2.font.color.rgb = color
        p2.space_after = Pt(6)

        p3 = tf.add_paragraph()
        p3.text = desc
        p3.font.size = Pt(11)
        p3.font.color.rgb = COLOR_WHITE

    # ==========================================
    # SLIDE 10: TRIANGULATION & DEMODULATION
    # ==========================================
    s10 = prs.slides.add_slide(blank_layout)
    set_slide_background(s10)
    add_header(s10, "Spatial Rack Pinpointing & Payload Demodulation")

    c1 = s10.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(1.8), Inches(5.6), Inches(5.0))
    c1.fill.solid()
    c1.fill.fore_color.rgb = COLOR_CARD
    c1.line.color.rgb = COLOR_CYAN
    tf_c1 = c1.text_frame
    tf_c1.word_wrap = True
    p = tf_c1.paragraphs[0]
    p.text = "Server Room Rack Pinpointing"
    p.font.size = Pt(18)
    p.font.bold = True
    p.font.color.rgb = COLOR_CYAN
    p.space_after = Pt(10)

    tri_items = [
        "4-Sensor Array Perimeter: Sensor-North, Sensor-South, Sensor-East, Sensor-West.",
        "Indoor Log-Distance Path Loss Model:\n  RSSI(d) = P0 - 10 * n * log10(d / d0)",
        "Centroid Estimation: Multi-sensor weighted energy centroid calculates emitter coordinate.",
        "Isolated Target Rack: Accurately isolates Rack-Delta (4.0m, 5.0m) with 85%+ spatial confidence.",
        "Terminal Rack Map: Displays live ASCII grid highlighting the compromised rack in flashing RED."
    ]
    for it in tri_items:
        p = tf_c1.add_paragraph()
        p.text = f"• {it}"
        p.font.size = Pt(12)
        p.font.color.rgb = COLOR_WHITE
        p.space_after = Pt(6)

    c2 = s10.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(6.8), Inches(1.8), Inches(5.6), Inches(5.0))
    c2.fill.solid()
    c2.fill.fore_color.rgb = COLOR_CARD
    c2.line.color.rgb = COLOR_GREEN
    tf_c2 = c2.text_frame
    tf_c2.word_wrap = True
    p = tf_c2.paragraphs[0]
    p.text = "Covert Payload Demodulation"
    p.font.size = Pt(18)
    p.font.bold = True
    p.font.color.rgb = COLOR_GREEN
    p.space_after = Pt(10)

    dem_items = [
        "Pulse Duration Extraction: Measures carrier on/off intervals (0.2s dot, 0.6s dash).",
        "Morse Code Decoder: Converts dot-dash sequences into ASCII characters in real time.",
        "Binary FSK Decoder: Reconstructs alternating frequency shifts into 8-bit binary bytes.",
        "Intercepted Canary Flag: Successfully decoded 'FLAG{AIR_GAP_1337}'.",
        "Structured Audit Logging: Incidents recorded with timestamp, frequency, rack ID, and SNR into logs/aetherhound_incidents.jsonl."
    ]
    for it in dem_items:
        p = tf_c2.add_paragraph()
        p.text = f"• {it}"
        p.font.size = Pt(12)
        p.font.color.rgb = COLOR_WHITE
        p.space_after = Pt(6)

    # ==========================================
    # SLIDE 11: 4-WEEK IMPLEMENTATION ROADMAP
    # ==========================================
    s11 = prs.slides.add_slide(blank_layout)
    set_slide_background(s11)
    add_header(s11, "4-Week Milestone Completion & Review Compliance")

    weeks_data = [
        ("Week 1: Hardware Setup & Mock Malware", "100% DONE", COLOR_GREEN, [
            "Configured audio/SDR abstraction layers.",
            "Built physical server room acoustic & RF emulator.",
            "Implemented benign Fansmitter & RAMBO mock malware."
        ]),
        ("Week 2: Signal Filtering & 30+ FPS CLI", "100% DONE", COLOR_GREEN, [
            "Built DSP flowgraph (Butterworth, notch, STFT, PSD).",
            "Developed hacker-style Rich terminal UI @ 30+ FPS.",
            "Mid-Project Review: Capture validation audit passed."
        ]),
        ("Week 3: Deep Autoencoder & Alerts", "100% DONE", COLOR_GREEN, [
            "Trained PyTorch Autoencoder on baseline server hum.",
            "Implemented dynamic thresholding & rack pinpointing.",
            "Configured red alert triggers & edge buzzer simulation."
        ]),
        ("Week 4: Optimization, Tests & Final Review", "100% DONE", COLOR_GREEN, [
            "Optimized C-level matrix DSP math (<1 ms latency).",
            "Passed 16/16 unit and integration tests.",
            "Final Project Review: Produced report, slides, and demo."
        ])
    ]

    for i, (wtitle, wstatus, wcolor, witems) in enumerate(weeks_data):
        wy = Inches(1.8 + i * 1.3)
        c = s11.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), wy, Inches(11.7), Inches(1.15))
        c.fill.solid()
        c.fill.fore_color.rgb = COLOR_CARD
        c.line.color.rgb = wcolor
        tf = c.text_frame
        tf.word_wrap = True

        p = tf.paragraphs[0]
        p.text = f"{wtitle}  —  "
        p.font.size = Pt(14)
        p.font.bold = True
        p.font.color.rgb = COLOR_WHITE
        run = p.add_run()
        run.text = f"[{wstatus}]"
        run.font.bold = True
        run.font.color.rgb = wcolor

        p2 = tf.add_paragraph()
        p2.text = " | ".join(witems)
        p2.font.size = Pt(11)
        p2.font.color.rgb = COLOR_MUTED

    # ==========================================
    # SLIDE 12: CONCLUSION & FUTURE SCOPE
    # ==========================================
    s12 = prs.slides.add_slide(blank_layout)
    set_slide_background(s12)
    add_header(s12, "Conclusion & Future Security Impact")

    c1 = s12.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(1.8), Inches(5.6), Inches(5.0))
    c1.fill.solid()
    c1.fill.fore_color.rgb = COLOR_CARD
    c1.line.color.rgb = COLOR_GREEN
    tf_c1 = c1.text_frame
    tf_c1.word_wrap = True
    p = tf_c1.paragraphs[0]
    p.text = "Key Project Achievements"
    p.font.size = Pt(18)
    p.font.bold = True
    p.font.color.rgb = COLOR_GREEN
    p.space_after = Pt(10)

    achieve_items = [
        "Defeats Advanced Air-Gap Exfiltration: Closes the physical gap where IT firewalls are blind.",
        "Unsupervised Resilience: Learns server hum dynamically; requires no prior malware signatures.",
        "Zero Cloud Dependency: Operates securely on hyper-local edge hardware with zero network exposure.",
        "Rapid Real-Time Alerting: Isolates anomalies within 1-2 frames (<100 ms) and pinpoints infected racks.",
        "Complete Compliance: Meets all 4-week milestones, Mid-Review and Final-Review standards from Infotact."
    ]
    for it in achieve_items:
        p = tf_c1.add_paragraph()
        p.text = f"• {it}"
        p.font.size = Pt(12)
        p.font.color.rgb = COLOR_WHITE
        p.space_after = Pt(8)

    c2 = s12.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(6.8), Inches(1.8), Inches(5.6), Inches(5.0))
    c2.fill.solid()
    c2.fill.fore_color.rgb = COLOR_CARD
    c2.line.color.rgb = COLOR_CYAN
    tf_c2 = c2.text_frame
    tf_c2.word_wrap = True
    p = tf_c2.paragraphs[0]
    p.text = "Future Roadmap & Industrialization"
    p.font.size = Pt(18)
    p.font.bold = True
    p.font.color.rgb = COLOR_CYAN
    p.space_after = Pt(10)

    future_items = [
        "Active Jamming Countermeasures: Deploy smart ultrasonic acoustic white noise transducers to jam covert fansmitters.",
        "Optical Covert Channels: Extend sensor suite to include high-speed photodiode arrays for HDD LED exfiltration (xLED).",
        "Hardware ASIC Acceleration: Port DSP matrix math to FPGA / Coral Edge TPU for sub-100 microsecond latency.",
        "Distributed Multi-Room Mesh: Interconnect air-gapped sensor nodes across data halls via secure optical fiber."
    ]
    for it in future_items:
        p = tf_c2.add_paragraph()
        p.text = f"• {it}"
        p.font.size = Pt(12)
        p.font.color.rgb = COLOR_WHITE
        p.space_after = Pt(8)

    out_file = os.path.join("presentation", "AetherHound_Presentation.pptx")
    prs.save(out_file)
    print(f"[OK] Presentation successfully generated: {out_file} (12 Widescreen Slides)")

if __name__ == "__main__":
    build_presentation()
