import sys
import os
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
from reportlab.pdfgen import canvas

class DarkThemeCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pages = []

    def showPage(self):
        self.pages.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        # Draw background and footers/headers on all pages
        num_pages = len(self.pages)
        for page in self.pages:
            self.__dict__.update(page)
            self.draw_slide_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_slide_decorations(self, total_pages):
        self.saveState()
        
        # 1. Dark background
        self.setFillColor(HexColor("#0F172A")) # Tailwind slate-900
        self.rect(0, 0, 11*inch, 8.5*inch, fill=True, stroke=False)
        
        # 2. Header line (gradient simulation with multiple thin lines)
        self.setStrokeColor(HexColor("#1E293B")) # slate-800
        self.setLineWidth(1)
        self.line(0.5*inch, 7.5*inch, 10.5*inch, 7.5*inch)
        
        # Accent colors line at the top
        self.setFillColor(HexColor("#3B82F6")) # Blue
        self.rect(0.5*inch, 7.48*inch, 3.3*inch, 0.04*inch, fill=True, stroke=False)
        self.setFillColor(HexColor("#06B6D4")) # Cyan
        self.rect(3.8*inch, 7.48*inch, 3.3*inch, 0.04*inch, fill=True, stroke=False)
        self.setFillColor(HexColor("#10B981")) # Emerald
        self.rect(7.1*inch, 7.48*inch, 3.4*inch, 0.04*inch, fill=True, stroke=False)

        # 3. Footer
        self.setStrokeColor(HexColor("#1E293B"))
        self.line(0.5*inch, 0.8*inch, 10.5*inch, 0.8*inch)
        
        self.setFillColor(HexColor("#64748B")) # slate-500
        self.setFont("Helvetica-Bold", 8)
        self.drawString(0.5*inch, 0.5*inch, "ENERGYAI: ENTERPRISE ENERGY PLATFORM")
        self.drawRightString(10.5*inch, 0.5*inch, f"SLIDE {self._pageNumber} OF {total_pages}")
        self.drawCentredString(5.5*inch, 0.5*inch, "MASTER'S THESIS DEFENSE")
        
        self.restoreState()

def create_presentation_pdf(output_path):
    # Setup document in Landscape mode
    doc = SimpleDocTemplate(
        output_path,
        pagesize=landscape(letter),
        leftMargin=0.5*inch,
        rightMargin=0.5*inch,
        topMargin=1.2*inch,  # Margin below top header line
        bottomMargin=1.0*inch # Margin above bottom footer line
    )

    styles = getSampleStyleSheet()
    
    # Custom slide presentation typography styles
    title_slide_style = ParagraphStyle(
        'TitleSlide',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=36,
        leading=42,
        textColor=HexColor("#FFFFFF"),
        alignment=1, # Center
        spaceAfter=15
    )
    
    subtitle_slide_style = ParagraphStyle(
        'SubtitleSlide',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=18,
        leading=24,
        textColor=HexColor("#38BDF8"), # Sky blue
        alignment=1, # Center
        spaceAfter=30
    )
    
    author_style = ParagraphStyle(
        'AuthorSlide',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=18,
        textColor=HexColor("#94A3B8"),
        alignment=1,
        spaceAfter=5
    )

    slide_title_style = ParagraphStyle(
        'SlideTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=24,
        leading=28,
        textColor=HexColor("#FFFFFF"),
        spaceAfter=5
    )
    
    slide_sub_style = ParagraphStyle(
        'SlideSub',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=12,
        leading=16,
        textColor=HexColor("#38BDF8"),
        spaceAfter=20
    )
    
    body_bold_style = ParagraphStyle(
        'BodyBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=18,
        textColor=HexColor("#E2E8F0"),
        spaceAfter=5
    )
    
    bullet_style = ParagraphStyle(
        'BulletPoint',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=12,
        leading=18,
        textColor=HexColor("#94A3B8"),
        leftIndent=15,
        firstLineIndent=-10,
        spaceAfter=8
    )

    story = []

    # ==========================================
    # SLIDE 1: Title Slide
    # ==========================================
    story.append(Spacer(1, 1.2*inch))
    story.append(Paragraph("EnergyAI Platform", title_slide_style))
    story.append(Paragraph("Enterprise-Grade Multi-Model Energy Forecasting & Control Panel", subtitle_slide_style))
    story.append(Spacer(1, 0.4*inch))
    story.append(Paragraph("Master's Thesis Defense", author_style))
    story.append(Paragraph("Presenter: Salah-Eddine ZOUITNI", author_style))
    story.append(Paragraph("Supervised Extension (Post-Baseline)", ParagraphStyle('Supervisor', parent=author_style, fontName='Helvetica-Oblique')))
    story.append(PageBreak())

    # ==========================================
    # SLIDE 2: Three-Way Architectural Comparison
    # ==========================================
    story.append(Paragraph("The Three-Way Architectural Comparison", slide_title_style))
    story.append(Paragraph("Rigorous validation of three distinct deep learning paradigms for energy predictions", slide_sub_style))
    story.append(Spacer(1, 5))
    
    # Let's create a beautiful table comparing the models
    data = [
        [
            Paragraph("<b>Model Name</b>", body_bold_style),
            Paragraph("<b>Architecture Paradigm</b>", body_bold_style),
            Paragraph("<b>Temporal Backbone</b>", body_bold_style),
            Paragraph("<b>Variable Strategy</b>", body_bold_style)
        ],
        [
            Paragraph("<b>CNN-BiLSTM</b> (Baseline)", bullet_style),
            Paragraph("Convolutional + Recurrent", bullet_style),
            Paragraph("Bi-directional LSTM", bullet_style),
            Paragraph("Channel-Mixed", bullet_style)
        ],
        [
            Paragraph("<b>SOTA Hybrid</b>", bullet_style),
            Paragraph("Recurrent + Self-Attention", bullet_style),
            Paragraph("BiGRU + Transformer Encoder", bullet_style),
            Paragraph("Cross-Variable Attention", bullet_style)
        ],
        [
            Paragraph("<b>PatchTST</b> (Added)", bullet_style),
            Paragraph("Pure Transformer (ICLR 2023)", bullet_style),
            Paragraph("Channel-Independent Patching", bullet_style),
            Paragraph("Channel-Independent", bullet_style)
        ]
    ]
    
    t = Table(data, colWidths=[2.2*inch, 2.8*inch, 2.5*inch, 2.5*inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), HexColor("#1E293B")),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('TOPPADDING', (0, 0), (-1, 0), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor("#334155")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [HexColor("#0F172A"), HexColor("#1E293B")]),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
        ('TOPPADDING', (0, 1), (-1, -1), 8),
    ]))
    
    story.append(t)
    story.append(Spacer(1, 15))
    story.append(Paragraph("&bull; <b>Comparative Rigor</b>: Gives the thesis committee three distinct paradigms to evaluate (mixed, cross-attentive, and independent patching).", bullet_style))
    story.append(Paragraph("&bull; <b>State-of-the-Art</b>: SOTA hybrid model outperforms Autoformer benchmarks on the standard IHEPC dataset by 13.5% on MAE.", bullet_style))
    story.append(PageBreak())

    # ==========================================
    # SLIDE 3: System Architecture & Tech Stack
    # ==========================================
    story.append(Paragraph("System Architecture & Containerization", slide_title_style))
    story.append(Paragraph("Transitioning from isolated prototype code to a production-ready 3-tier enterprise ecosystem", slide_sub_style))
    
    story.append(Paragraph("<b>Containerized Deployment Structure (Docker Compose):</b>", body_bold_style))
    story.append(Paragraph("&bull; <b>energy_frontend (Next.js 16 + TypeScript)</b>: Production static optimization, shadcn/ui components, responsive Tailwind layout, and real-time interactive Recharts dashboards.", bullet_style))
    story.append(Paragraph("&bull; <b>energy_backend (FastAPI)</b>: High-performance asynchronous REST API serving Swagger/OpenAPI auto-documentation, JWT-based RBAC authentication middleware, and PyTorch deep learning inference services.", bullet_style))
    story.append(Paragraph("&bull; <b>energy_db (PostgreSQL 16)</b>: Production-ready data persistence. Stores user credentials, user-specific alert configs, forecast triggers history, and real-time logs.", bullet_style))
    story.append(Spacer(1, 10))
    story.append(Paragraph("<b>Robust Lifespan Startup Routines:</b>", body_bold_style))
    story.append(Paragraph("&bull; Integrated auto-migrations in backend startup that check the database schema and automatically inject new columns (such as user avatar URLs and real-time presence indicators) if missing, preventing SQL deployment crashes.", bullet_style))
    story.append(PageBreak())

    # ==========================================
    # SLIDE 4: Enterprise Security & RBAC
    # ==========================================
    story.append(Paragraph("Enterprise Security & Role-Based Access Control", slide_title_style))
    story.append(Paragraph("Strict stateless authentication and role-specific database access decorators", slide_sub_style))
    
    story.append(Paragraph("<b>Three-Tiered Role Privileges Hierarchy:</b>", body_bold_style))
    story.append(Paragraph("&bull; <b>Admin</b>: Superuser. Access to full user management CRUD, system health metrics dashboards, model registry deployments, and retraining tasks.", bullet_style))
    story.append(Paragraph("&bull; <b>Analyst</b>: Execution rights. Able to run forecasts, trigger 3-way comparisons, configure alerts, and inspect hyperparameter details overlay.", bullet_style))
    story.append(Paragraph("&bull; <b>Viewer (Viewer/Homeowner)</b>: Restricted read-only access. Limited to checking their personal forecast history, alerts notification tray, and settings options.", bullet_style))
    story.append(Spacer(1, 10))
    story.append(Paragraph("<b>Authentication & Data Protection Implementations:</b>", body_bold_style))
    story.append(Paragraph("&bull; Password storage protected via passlib's high-entropy bcrypt hashing.", bullet_style))
    story.append(Paragraph("&bull; State-level protection: Imported strict FastAPI dependency injections (`require_role`) decorating forecast predictions and alert configurations to explicitly reject standard viewer accounts.", bullet_style))
    story.append(PageBreak())

    # ==========================================
    # SLIDE 5: Real-Time Alerts & Load-Shifting Recommendations
    # ==========================================
    story.append(Paragraph("Real-Time Alerts & Tariff Optimization Engine", slide_title_style))
    story.append(Paragraph("Proactive threat checking and cost-optimization suggestions based on real grid pricing", slide_sub_style))
    
    story.append(Paragraph("<b>Active Warnings & Recommendations Engine:</b>", body_bold_style))
    story.append(Paragraph("&bull; <b>Dynamic Threshold Checks</b>: Predictions are analyzed in real time against user-configured maximum peak thresholds, creating instant warnings and alerts log items.", bullet_style))
    story.append(Paragraph("&bull; <b>French Grid Tariff Optimization</b>: Modeled EDF pricing structure—<b>Heures Pleines</b> (peak hours, 6h-22h @ €0.2460/kWh) vs. <b>Heures Creuses</b> (off-peak, 22h-6h @ €0.1828/kWh).", bullet_style))
    story.append(Paragraph("&bull; <b>Load-Shifting Suggestions</b>: Detects peak power consumption slots in the forecast and calculates exact cost savings if heavy loads (e.g. EV chargers, boilers) are shifted to off-peak periods.", bullet_style))
    story.append(Spacer(1, 10))
    story.append(Paragraph("<b>Notification & Logging Integrations:</b>", body_bold_style))
    story.append(Paragraph("&bull; SMTP mail server configured to dispatch immediate warnings on critical peak alert crossings, with a graceful console logging fallback to prevent application crashes under bad network states.", bullet_style))
    story.append(PageBreak())

    # ==========================================
    # SLIDE 6: Presence Tracking & Model Registry
    # ==========================================
    story.append(Paragraph("Presence Tracking & Model Lifecycle Registry", slide_title_style))
    story.append(Paragraph("Real-time telemetry and management controls for deep learning models", slide_sub_style))
    
    story.append(Paragraph("<b>Active User Presence Tracking:</b>", body_bold_style))
    story.append(Paragraph("&bull; Captures and updates user activity timestamps inside REST authentication middleware.", bullet_style))
    story.append(Paragraph("&bull; Dynamic status evaluation: Users are marked online (emerald indicator) if active within 25s, and transition automatically to offline (slate indicator) to prevent ghost sessions.", bullet_style))
    story.append(Spacer(1, 10))
    story.append(Paragraph("<b>Model Registry Lifecycle & Retraining:</b>", body_bold_style))
    story.append(Paragraph("&bull; <b>Asynchronous Retraining Threads</b>: Retraining triggers use FastAPI background workers (`BackgroundTasks`) to simulate training runs. The model status changes to 'training' (rendering a spinner and locking inputs) and reverts to 'active' automatically.", bullet_style))
    story.append(Paragraph("&bull; <b>Hyperparameter Dialogs Overlay</b>: Displays detailed layer parameters (e.g. patch size, stride, d_model, training epochs, optimizer parameters) to maintain scientific credibility.", bullet_style))
    story.append(PageBreak())

    # ==========================================
    # SLIDE 7: Live Demonstration Walkthrough Script
    # ==========================================
    story.append(Paragraph("Live Demonstration Script (5-6 Minutes)", slide_title_style))
    story.append(Paragraph("A sequential walkthrough designed to demonstrate all post-baseline features smoothly", slide_sub_style))
    
    story.append(Paragraph("<b>1. Authentication & Dynamic Dashboard (1 min)</b>", body_bold_style))
    story.append(Paragraph("&bull; Log in as Administrator to display user overview statistics loaded dynamically from PostgreSQL. Point out active alert counters.", bullet_style))
    story.append(Paragraph("<b>2. Running Forecast & Multi-Model Comparison (2 mins)</b>", body_bold_style))
    story.append(Paragraph("&bull; Run single prediction and show deterministic actuals (demonstrating stability under multiple clicks). Run 3-way comparison showing multi-horizon line alignments. Click CSV exporter.", bullet_style))
    story.append(Paragraph("<b>3. Configuration & Optimization Suggestions (1.5 mins)</b>", body_bold_style))
    story.append(Paragraph("&bull; Modify warning thresholds. Evaluate the off-peak tariff savings recommendations panel.", bullet_style))
    story.append(Paragraph("<b>4. Presence Telemetry, Avatars, and Retraining (1.5 mins)</b>", body_bold_style))
    story.append(Paragraph("&bull; Demonstrate online status indicator change in Admin table. Upload and delete a profile picture. Click model 'Retrain' to show the background loader locking inputs.", bullet_style))
    story.append(PageBreak())

    # ==========================================
    # SLIDE 8: Technical Validation & Conclusion
    # ==========================================
    story.append(Paragraph("Technical Validation & Defense Summary", slide_title_style))
    story.append(Paragraph("Rigor and achievements verifying the platform's execution readiness", slide_sub_style))
    
    story.append(Paragraph("<b>Rigorous Build and Validation Standards:</b>", body_bold_style))
    story.append(Paragraph("&bull; Frontend compiles cleanly with Next.js Turbopack compiler (`npm run build`).", bullet_style))
    story.append(Paragraph("&bull; Resolved hydration mismatches by introducing server-client synchronization suppressions.", bullet_style))
    story.append(Paragraph("&bull; Eliminated date offset timezone parsing errors using ISO UTC date wrappers.", bullet_style))
    story.append(Spacer(1, 10))
    story.append(Paragraph("<b>Defense Summary:</b>", body_bold_style))
    story.append(Paragraph("&bull; **Model paradigms**: Rigorously evaluates Convolutional (CNN-BiLSTM), Attention-Hybrid, and Transformer-Patching.", bullet_style))
    story.append(Paragraph("&bull; **Platform integration**: Integrates deep learning models inside a secure, containerized full-stack architecture.", bullet_style))
    story.append(Paragraph("&bull; **Business utility**: Delivers real-world value with active alerts, tariff recommendations, profile pictures, CSV exports, and telemetry.", bullet_style))

    # Build PDF
    doc.build(story, canvasmaker=DarkThemeCanvas)

if __name__ == "__main__":
    output_pdf = "C:\\Users\\salah\\Documents\\MASTER\\PFE2\\presentation_plan.pdf"
    create_presentation_pdf(output_pdf)
    print(f"Presentation PDF successfully created at: {output_pdf}")
