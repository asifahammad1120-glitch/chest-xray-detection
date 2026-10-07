from django.contrib import admin
from .models import (
    Doctor, Patient, AbnormalityCategory, XRayExamination,
    XRayImage, DetectionResult, ClassificationResult, MedicalReport
)


@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    list_display = ("user", "specialization", "hospital_clinic", "is_approved", "created_at")
    list_filter = ("is_approved", "specialization")
    search_fields = ("user__username", "user__first_name", "user__last_name", "medical_registration_number")
    actions = ["approve_doctors", "reject_doctors"]

    def approve_doctors(self, request, queryset):
        queryset.update(is_approved=True)
    approve_doctors.short_description = "Approve selected doctors"

    def reject_doctors(self, request, queryset):
        queryset.update(is_approved=False)
    reject_doctors.short_description = "Reject selected doctors"


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ("user", "age", "gender", "mobile_number", "created_at")
    search_fields = ("user__username", "user__first_name", "user__last_name")


@admin.register(AbnormalityCategory)
class AbnormalityCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "description")
    search_fields = ("name",)


@admin.register(XRayExamination)
class XRayExaminationAdmin(admin.ModelAdmin):
    list_display = ("id", "patient", "doctor", "hospital_clinic", "examination_date", "status")
    list_filter = ("status", "examination_date")
    search_fields = ("patient__user__username", "hospital_clinic")


@admin.register(XRayImage)
class XRayImageAdmin(admin.ModelAdmin):
    list_display = ("examination", "uploaded_at")


@admin.register(DetectionResult)
class DetectionResultAdmin(admin.ModelAdmin):
    list_display = ("xray_image", "abnormality_category", "confidence_score")
    list_filter = ("abnormality_category",)


@admin.register(ClassificationResult)
class ClassificationResultAdmin(admin.ModelAdmin):
    list_display = ("detection", "predicted_category", "confidence_score")
    list_filter = ("predicted_category",)


@admin.register(MedicalReport)
class MedicalReportAdmin(admin.ModelAdmin):
    list_display = ("examination", "status", "reviewed_at")
    list_filter = ("status",)