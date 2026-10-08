from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("register/patient/", views.patient_register, name="patient_register"),
    path("register/doctor/", views.doctor_register, name="doctor_register"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("dashboard/patient/", views.patient_dashboard, name="patient_dashboard"),
    path("dashboard/doctor/", views.doctor_dashboard, name="doctor_dashboard"),
    path("examination/new/", views.new_examination, name="new_examination"),
    path("examination/<int:exam_id>/", views.examination_detail, name="examination_detail"),
    path("examination/<int:exam_id>/review/", views.examination_review, name="examination_review"),
    path("examination/<int:exam_id>/report/pdf/", views.download_report_pdf, name="download_report_pdf"),
    
]
