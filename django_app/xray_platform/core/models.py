from django.db import models
from django.contrib.auth.models import User


# ── Role profiles ──────────────────────────────────────────────
# We extend Django's built-in User (which handles login/password)
# with one-to-one "profile" tables for each role. This keeps auth
# generic while letting each role carry its own extra fields.

class Doctor(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    medical_registration_number = models.CharField(max_length=50, unique=True)
    mobile_number = models.CharField(max_length=15)
    specialization = models.CharField(max_length=100)
    hospital_clinic = models.CharField(max_length=150)
    city = models.CharField(max_length=100)
    office_address = models.TextField()
    is_approved = models.BooleanField(default=False)  # admin must approve before doctor can log in
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
       name = self.user.get_full_name() or self.user.username
       if name.lower().startswith(("dr.", "dr ")):
          return name
       return f"Dr. {name}"


class Patient(models.Model):
    GENDER_CHOICES = [("M", "Male"), ("F", "Female"), ("O", "Other")]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    age = models.PositiveIntegerField()
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)
    mobile_number = models.CharField(max_length=15)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.user.get_full_name() or self.user.username


# ── Abnormality categories (matches your trained models' classes) ──

class AbnormalityCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Abnormality categories"


# ── Examination workflow ───────────────────────────────────────

class XRayExamination(models.Model):
    STATUS_CHOICES = [
        ("submitted", "Submitted"),
        ("ai_processed", "AI Analysis Complete"),
        ("doctor_reviewed", "Doctor Reviewed"),
        ("verified", "Verified"),
    ]

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="examinations")
    doctor = models.ForeignKey(Doctor, on_delete=models.SET_NULL, null=True, related_name="examinations")
    hospital_clinic = models.CharField(max_length=150)
    examination_date = models.DateField()
    symptoms = models.TextField(blank=True, help_text="Optional clinical information from patient")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="submitted")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Exam #{self.id} — {self.patient}"


class XRayImage(models.Model):
    examination = models.OneToOneField(XRayExamination, on_delete=models.CASCADE, related_name="xray_image")
    original_image = models.ImageField(upload_to="xrays/original/")
    annotated_image = models.ImageField(upload_to="xrays/annotated/", blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"X-ray for Exam #{self.examination_id}"


# ── AI pipeline results ────────────────────────────────────────
# One DetectionResult per YOLO box. Each box then gets its own
# ClassificationResult from the CNN — this mirrors the actual
# pipeline (detect region -> crop -> classify that one region).

class DetectionResult(models.Model):
    xray_image = models.ForeignKey(XRayImage, on_delete=models.CASCADE, related_name="detections")
    abnormality_category = models.ForeignKey(AbnormalityCategory, on_delete=models.PROTECT)
    confidence_score = models.FloatField(help_text="YOLO detection confidence, 0-1")
    # Bounding box, stored as pixel coordinates on the original image
    box_x1 = models.IntegerField()
    box_y1 = models.IntegerField()
    box_x2 = models.IntegerField()
    box_y2 = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.abnormality_category} ({self.confidence_score:.2f})"


class ClassificationResult(models.Model):
    detection = models.OneToOneField(DetectionResult, on_delete=models.CASCADE, related_name="classification")
    predicted_category = models.ForeignKey(AbnormalityCategory, on_delete=models.PROTECT)
    confidence_score = models.FloatField(help_text="CNN classification confidence, 0-1")

    def __str__(self):
        return f"{self.predicted_category} ({self.confidence_score:.2f})"


# ── Doctor review & final report ───────────────────────────────

class MedicalReport(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending Review"),
        ("verified", "Verified"),
    ]

    examination = models.OneToOneField(XRayExamination, on_delete=models.CASCADE, related_name="report")
    clinical_observation = models.TextField(blank=True)
    final_interpretation = models.TextField(blank=True)
    additional_notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    reviewed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Report for Exam #{self.examination_id} ({self.status})"