from django import forms
from emergency.models import SOSEvent
from expeditions.models import Expedition
class SOSSubmitForm(forms.ModelForm):
    class Meta:
        model=SOSEvent
        fields=['expedition','latitude','longitude','details']
        widgets={'details':forms.Textarea(attrs={'rows':3,'maxlength':300,'placeholder':'Describe the emergency in a few words.'})}
    def __init__(self,*args,profile,**kwargs):
        super().__init__(*args,**kwargs)
        self.profile=profile
        expeditions=profile.expeditions.all()
        self.fields['expedition'].queryset=expeditions
        if not self.is_bound:
            chosen=expeditions.filter(status='active').first() or expeditions.first()
            if chosen:
                self.initial.update({'expedition':chosen.pk,'latitude':chosen.latitude,'longitude':chosen.longitude})
    def clean_expedition(self):
        expedition=self.cleaned_data['expedition']
        if not self.profile.expeditions.filter(pk=expedition.pk).exists(): raise forms.ValidationError('You can only send an SOS for your assigned expedition.')
        return expedition
    def save(self,commit=True):
        event=super().save(commit=False)
        event.reported_by=self.profile.user
        if commit: event.save()
        return event
