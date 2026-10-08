from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.files.base import ContentFile
from io import BytesIO
from .models import MedicalReport
from .forms import ExaminationForm
from .models import XRayImage, DetectionResult, ClassificationResult, AbnormalityCategory
from .ai_pipeline import run_full_pipeline
from django.http import HttpResponse
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from .forms import PatientRegistrationForm, DoctorRegistrationForm
from .models import Patient, Doctor, XRayExamination


def home(request):
    return render(request, "core/home.html")


# ── Registration ────────────────────────────────────────────────

def patient_register(request):
    if request.method == "POST":
        form = PatientRegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Registration successful. Please log in.")
            return redirect("login")
    else:
        form = PatientRegistrationForm()
    return render(request, "core/patient_register.html", {"form": form})


def doctor_register(request):
    if request.method == "POST":
        form = DoctorRegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                "Registration submitted. An admin must approve your account before you can log in."
            )
            return redirect("login")
    else:
        form = DoctorRegistrationForm()
    return render(request, "core/doctor_register.html", {"form": form})


# ── Login / Logout ──────────────────────────────────────────────
# A single login page for all roles — after authenticating, we check
# which profile the user has (superuser / Doctor / Patient) and send
# them to the matching dashboard. This matches the assignment's three
# separate modules while keeping one simple entry point for the user.

def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)

        if user is None:
            messages.error(request, "Invalid username or password.")
            return render(request, "core/login.html")

        if user.is_superuser:
            auth_login(request, user)
            return redirect("/admin/")

        doctor = Doctor.objects.filter(user=user).first()
        if doctor:
            if not doctor.is_approved:
                messages.error(request, "Your account is pending admin approval.")
                return render(request, "core/login.html")
            auth_login(request, user)
            return redirect("doctor_dashboard")

        patient = Patient.objects.filter(user=user).first()
        if patient:
            auth_login(request, user)
            return redirect("patient_dashboard")

        messages.error(request, "No profile found for this account.")
        return render(request, "core/login.html")

    return render(request, "core/login.html")


def logout_view(request):
    auth_logout(request)
    return redirect("home")


@login_required
def patient_dashboard(request):
    patient = get_object_or_404(Patient, user=request.user)
    examinations = patient.examinations.order_by("-created_at")
    total = examinations.count()
    verified = examinations.filter(status="verified").count()
    return render(request, "core/patient_dashboard.html", {
        "patient": patient,
        "examinations": examinations,
        "total_count": total,
        "verified_count": verified,
        "pending_count": total - verified,
    })


@login_required
def doctor_dashboard(request):
    doctor = get_object_or_404(Doctor, user=request.user)
    examinations = doctor.examinations.order_by("-created_at")
    total = examinations.count()
    verified = examinations.filter(status="verified").count()
    return render(request, "core/doctor_dashboard.html", {
        "doctor": doctor,
        "examinations": examinations,
        "total_count": total,
        "verified_count": verified,
        "pending_count": total - verified,
    })


@login_required
def new_examination(request):
    patient = get_object_or_404(Patient, user=request.user)
 
    if request.method == "POST":
        form = ExaminationForm(request.POST, request.FILES)
        if form.is_valid():
            # 1. Create the examination record
            examination = XRayExamination.objects.create(
                patient=patient,
                doctor=form.cleaned_data["doctor"],
                hospital_clinic=form.cleaned_data["hospital_clinic"],
                examination_date=form.cleaned_data["examination_date"],
                symptoms=form.cleaned_data["symptoms"],
                status="submitted",
            )
 
            # 2. Save the uploaded image
            xray_image = XRayImage.objects.create(
                examination=examination,
                original_image=form.cleaned_data["xray_image"],
            )
 
            # 3. Run the AI pipeline on the saved file
            pipeline_result = run_full_pipeline(xray_image.original_image.path)
 
            # 4. Save each detection + its classification to the database
            for det in pipeline_result["detections"]:
                detection_category, _ = AbnormalityCategory.objects.get_or_create(
                    name=det["class_name"]
                )
                detection = DetectionResult.objects.create(
                    xray_image=xray_image,
                    abnormality_category=detection_category,
                    confidence_score=det["confidence"],
                    box_x1=det["box"][0],
                    box_y1=det["box"][1],
                    box_x2=det["box"][2],
                    box_y2=det["box"][3],
                )
                classification_category, _ = AbnormalityCategory.objects.get_or_create(
                    name=det["classification_class"]
                )
                ClassificationResult.objects.create(
                    detection=detection,
                    predicted_category=classification_category,
                    confidence_score=det["classification_confidence"],
                )
 
            # 5. Save the annotated image
            buffer = BytesIO()
            pipeline_result["annotated_image"].save(buffer, format="JPEG")
            xray_image.annotated_image.save(
                f"annotated_{examination.id}.jpg",
                ContentFile(buffer.getvalue()),
                save=True,
            )
 
            # 6. Update status now that AI analysis is done
            examination.status = "ai_processed"
            examination.save()
 
            messages.success(request, "X-ray submitted and AI analysis complete.")
            return redirect("examination_detail", exam_id=examination.id)
    else:
        form = ExaminationForm()
 
    return render(request, "core/examination_new.html", {"form": form})
 
 
@login_required
def examination_detail(request, exam_id):
    examination = get_object_or_404(XRayExamination, id=exam_id)
 
    # Basic access control: only the patient who owns this exam or the
    # assigned doctor can view it.
    is_owner_patient = hasattr(request.user, "patient") and examination.patient.user == request.user
    is_assigned_doctor = hasattr(request.user, "doctor") and examination.doctor and examination.doctor.user == request.user
 
    if not (is_owner_patient or is_assigned_doctor or request.user.is_superuser):
        messages.error(request, "You do not have permission to view this examination.")
        return redirect("home")
 
    xray_image = getattr(examination, "xray_image", None)
    detections = xray_image.detections.select_related(
        "abnormality_category", "classification__predicted_category"
    ) if xray_image else []
 
    report = getattr(examination, "report", None)
 
    return render(request, "core/examination_detail.html", {
        "examination": examination,
        "xray_image": xray_image,
        "detections": detections,
        "report": report,
        "is_assigned_doctor": is_assigned_doctor,
    })

@login_required
def examination_review(request, exam_id):
    examination = get_object_or_404(XRayExamination, id=exam_id)
 
    # Only the assigned doctor may submit a review
    if not (hasattr(request.user, "doctor") and examination.doctor and examination.doctor.user == request.user):
        messages.error(request, "You are not authorized to review this examination.")
        return redirect("examination_detail", exam_id=exam_id)
 
    if request.method == "POST":
        report, _ = MedicalReport.objects.get_or_create(examination=examination)
        report.clinical_observation = request.POST.get("clinical_observation", "")
        report.final_interpretation = request.POST.get("final_interpretation", "")
        report.additional_notes = request.POST.get("additional_notes", "")
 
        action = request.POST.get("action")
        if action == "verify":
            report.status = "verified"
            import django.utils.timezone as timezone
            report.reviewed_at = timezone.now()
            examination.status = "verified"
            examination.save()
            messages.success(request, "Report verified and finalized.")
        else:
            examination.status = "doctor_reviewed"
            examination.save()
            messages.success(request, "Draft saved.")
 
        report.save()
 
    return redirect("examination_detail", exam_id=exam_id)

@login_required
def download_report_pdf(request, exam_id):
    examination = get_object_or_404(XRayExamination, id=exam_id)
 
    # Same access control as the detail page
    is_owner_patient = hasattr(request.user, "patient") and examination.patient.user == request.user
    is_assigned_doctor = hasattr(request.user, "doctor") and examination.doctor and examination.doctor.user == request.user
    if not (is_owner_patient or is_assigned_doctor or request.user.is_superuser):
        messages.error(request, "You do not have permission to view this report.")
        return redirect("home")
 
    report = getattr(examination, "report", None)
    if not report or report.status != "verified":
        messages.error(request, "This report has not been verified yet.")
        return redirect("examination_detail", exam_id=exam_id)
 
    xray_image = getattr(examination, "xray_image", None)
    detections = xray_image.detections.select_related(
        "abnormality_category", "classification__predicted_category"
    ) if xray_image else []
 
    # ── Build the PDF ──
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="medical_report_exam_{examination.id}.pdf"'
 
    doc = SimpleDocTemplate(response, pagesize=A4, topMargin=20 * mm, bottomMargin=20 * mm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("TitleCustom", parent=styles["Title"], fontSize=16)
    heading_style = ParagraphStyle("HeadingCustom", parent=styles["Heading2"], spaceBefore=12, spaceAfter=6)
    body_style = styles["BodyText"]
 
    elements = []
 
    # Title
    elements.append(Paragraph("AI-Assisted Chest X-Ray Medical Report", title_style))
    elements.append(Paragraph("This report combines AI-generated findings with a licensed doctor's clinical review.", body_style))
    elements.append(Spacer(1, 10))
 
    # Patient / exam info table
    info_data = [
        ["Patient", str(examination.patient)],
        ["Age / Gender", f"{examination.patient.age} / {examination.patient.get_gender_display()}"],
        ["Examination Date", str(examination.examination_date)],
        ["Hospital / Clinic", examination.hospital_clinic],
        ["Reviewing Doctor", str(examination.doctor) if examination.doctor else "—"],
        ["Report Status", report.get_status_display()],
    ]
    info_table = Table(info_data, colWidths=[50 * mm, 110 * mm])
    info_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 14))
 
    # Annotated X-ray image
    if xray_image and xray_image.annotated_image:
        elements.append(Paragraph("Annotated X-Ray", heading_style))
        elements.append(RLImage(xray_image.annotated_image.path, width=140 * mm, height=140 * mm, kind="proportional"))
        elements.append(Spacer(1, 10))
 
    # AI findings table
    elements.append(Paragraph("AI Detection & Classification Findings", heading_style))
    if detections:
        table_data = [["Detected Region", "Detection Conf.", "CNN Classification", "Classification Conf."]]
        for det in detections:
            classification = getattr(det, "classification", None)
            table_data.append([
                det.abnormality_category.name,
                f"{det.confidence_score:.1%}",
                classification.predicted_category.name if classification else "—",
                f"{classification.confidence_score:.1%}" if classification else "—",
            ])
        findings_table = Table(table_data, colWidths=[55 * mm, 30 * mm, 50 * mm, 25 * mm])
        findings_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0d6efd")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        elements.append(findings_table)
    else:
        elements.append(Paragraph("No abnormalities detected by the AI model.", body_style))
    elements.append(Spacer(1, 14))
 
    # Doctor's clinical review
    elements.append(Paragraph("Doctor's Clinical Observation", heading_style))
    elements.append(Paragraph(report.clinical_observation or "—", body_style))
 
    elements.append(Paragraph("Final Interpretation", heading_style))
    elements.append(Paragraph(report.final_interpretation or "—", body_style))
 
    if report.additional_notes:
        elements.append(Paragraph("Additional Notes", heading_style))
        elements.append(Paragraph(report.additional_notes, body_style))
 
    elements.append(Spacer(1, 16))
    elements.append(Paragraph(
        "<i>This is an AI-assisted analysis. The final clinical interpretation above has been "
        "provided and verified by a qualified doctor/radiologist.</i>",
        body_style
    ))
 
    doc.build(elements)
    return response
 