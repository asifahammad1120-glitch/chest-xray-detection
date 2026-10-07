from django import forms
from django.contrib.auth.models import User
from .models import Patient, Doctor


class PatientRegistrationForm(forms.Form):
    # Fields from the assignment's Patient Registration spec:
    # Full Name, Username, Email, Age, Gender, Mobile Number, Password
    full_name = forms.CharField(max_length=150)
    username = forms.CharField(max_length=150)
    email = forms.EmailField()
    age = forms.IntegerField(min_value=0, max_value=150)
    gender = forms.ChoiceField(choices=Patient.GENDER_CHOICES)
    mobile_number = forms.CharField(max_length=15)
    password = forms.CharField(widget=forms.PasswordInput)

    def clean_username(self):
        username = self.cleaned_data["username"]
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("This username is already taken.")
        return username

    def clean_email(self):
        email = self.cleaned_data["email"]
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def save(self):
        data = self.cleaned_data
        names = data["full_name"].split(" ", 1)
        first_name = names[0]
        last_name = names[1] if len(names) > 1 else ""

        user = User.objects.create_user(
            username=data["username"],
            email=data["email"],
            password=data["password"],
            first_name=first_name,
            last_name=last_name,
        )
        patient = Patient.objects.create(
            user=user,
            age=data["age"],
            gender=data["gender"],
            mobile_number=data["mobile_number"],
        )
        return patient


class DoctorRegistrationForm(forms.Form):
    # Fields from the assignment's Doctor Registration spec:
    # Doctor Name, Username, Email, Medical Registration Number,
    # Mobile Number, Specialization, Hospital/Clinic, City, Office Address, Password
    full_name = forms.CharField(max_length=150)
    username = forms.CharField(max_length=150)
    email = forms.EmailField()
    medical_registration_number = forms.CharField(max_length=50)
    mobile_number = forms.CharField(max_length=15)
    specialization = forms.CharField(max_length=100)
    hospital_clinic = forms.CharField(max_length=150)
    city = forms.CharField(max_length=100)
    office_address = forms.CharField(widget=forms.Textarea)
    password = forms.CharField(widget=forms.PasswordInput)

    def clean_username(self):
        username = self.cleaned_data["username"]
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("This username is already taken.")
        return username

    def clean_email(self):
        email = self.cleaned_data["email"]
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean_medical_registration_number(self):
        reg_number = self.cleaned_data["medical_registration_number"]
        if Doctor.objects.filter(medical_registration_number=reg_number).exists():
            raise forms.ValidationError("This registration number is already in use.")
        return reg_number

    def save(self):
        data = self.cleaned_data
        names = data["full_name"].split(" ", 1)
        first_name = names[0]
        last_name = names[1] if len(names) > 1 else ""

        user = User.objects.create_user(
            username=data["username"],
            email=data["email"],
            password=data["password"],
            first_name=first_name,
            last_name=last_name,
        )
        doctor = Doctor.objects.create(
            user=user,
            medical_registration_number=data["medical_registration_number"],
            mobile_number=data["mobile_number"],
            specialization=data["specialization"],
            hospital_clinic=data["hospital_clinic"],
            city=data["city"],
            office_address=data["office_address"],
            # is_approved defaults to False — admin must approve before login works
        )
        return doctor

from .models import Doctor, XRayExamination, XRayImage
 
 
class ExaminationForm(forms.Form):
    doctor = forms.ModelChoiceField(
        queryset=Doctor.objects.filter(is_approved=True),
        empty_label="Select a doctor",
    )
    hospital_clinic = forms.CharField(max_length=150)
    examination_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    symptoms = forms.CharField(widget=forms.Textarea, required=False)
    xray_image = forms.ImageField()
 