from django import forms

class UploadForm(forms.Form):
    bucket = forms.CharField(max_length=64, initial="assets")
    file = forms.FileField()