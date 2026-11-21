from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import FormView, ListView, TemplateView

from accounts.permissions import (
    PERMISSION_MAP, ROLE_CHOICES, RoleRequiredMixin, can, user_role,
)
from accounts.services import deactivate_user, delete_user, set_user_role
from personnel.models import PersonnelProfile

User = get_user_model()


class UserCreateForm(forms.Form):
    username = forms.CharField(max_length=150)
    first_name = forms.CharField(max_length=150, required=False)
    last_name = forms.CharField(max_length=150, required=False)
    email = forms.EmailField(required=False)
    role = forms.ChoiceField(choices=[(r, r) for r in ROLE_CHOICES])
    password = forms.CharField(widget=forms.PasswordInput)
    reason = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 2}))

    def clean_username(self):
        value = self.cleaned_data['username']
        if User.objects.filter(username__iexact=value).exists():
            raise forms.ValidationError('That operator ID is already in use.')
        return value

    def clean_password(self):
        value = self.cleaned_data['password']
        validate_password(value)
        return value


class UserEditForm(forms.Form):
    username = forms.CharField(max_length=150)
    first_name = forms.CharField(max_length=150, required=False)
    last_name = forms.CharField(max_length=150, required=False)
    email = forms.EmailField(required=False)
    role = forms.ChoiceField(choices=[(r, r) for r in ROLE_CHOICES])
    is_active = forms.BooleanField(required=False, label='Account active')
    reason = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 2}))

    def __init__(self, *args, user_obj, **kwargs):
        super().__init__(*args, **kwargs)
        self.user_obj = user_obj
        if not self.is_bound:
            self.initial.update({
                'username': user_obj.username, 'first_name': user_obj.first_name,
                'last_name': user_obj.last_name, 'email': user_obj.email,
                'role': user_role(user_obj), 'is_active': user_obj.is_active,
            })

    def clean_username(self):
        value = self.cleaned_data['username']
        if User.objects.filter(username__iexact=value).exclude(pk=self.user_obj.pk).exists():
            raise forms.ValidationError('That operator ID is already in use.')
        return value


class ProfileContactForm(forms.ModelForm):
    class Meta:
        model = PersonnelProfile
        fields = ['contact_number', 'emergency_contact']


class ProfileView(RoleRequiredMixin, TemplateView):
    permission_action = 'profile.view'
    template_name = 'registration/profile.html'

    def get_context_data(self, **kwargs):
        c = super().get_context_data(**kwargs)
        c['profile'] = getattr(self.request.user, 'field_profile', None)
        c['role_name'] = user_role(self.request.user)
        return c


class ProfileContactUpdateView(RoleRequiredMixin, FormView):
    permission_action = 'profile.edit.self'
    template_name = 'registration/profile_edit.html'
    form_class = ProfileContactForm

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not can(request.user, self.permission_action):
            raise PermissionDenied
        self.profile = get_object_or_404(PersonnelProfile, user=request.user)
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['instance'] = self.profile
        return kwargs

    def form_valid(self, form):
        form.instance._history_user = self.request.user
        form.save()
        messages.success(self.request, 'Contact details updated.')
        return redirect('profile')


class UserListView(RoleRequiredMixin, ListView):
    permission_action = 'user.manage'
    template_name = 'accounts/user_list.html'
    context_object_name = 'operators'
    paginate_by = 30

    def get_queryset(self):
        users = list(User.objects.prefetch_related('groups').order_by('username'))
        for user in users:
            user.role_name = user_role(user) or 'Unassigned'
        return users

    def get_context_data(self, **kwargs):
        c=super().get_context_data(**kwargs)
        return c


class UserCreateView(RoleRequiredMixin, FormView):
    permission_action = 'user.manage'
    template_name = 'accounts/user_form.html'
    form_class = UserCreateForm

    @transaction.atomic
    def form_valid(self, form):
        data = form.cleaned_data
        user = User(username=data['username'], first_name=data['first_name'], last_name=data['last_name'], email=data['email'])
        user.set_password(data['password'])
        user.save()
        set_user_role(actor=self.request.user, user=user, role=data['role'], reason=data['reason'])
        messages.success(self.request, f'Operator {user.username} created as {data["role"]}.')
        return redirect('user_list')


class UserEditView(RoleRequiredMixin, FormView):
    permission_action = 'user.manage'
    template_name = 'accounts/user_form.html'
    form_class = UserEditForm

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not can(request.user, self.permission_action):
            raise PermissionDenied
        self.operator = get_object_or_404(User, pk=kwargs['pk'])
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user_obj'] = self.operator
        return kwargs

    @transaction.atomic
    def form_valid(self, form):
        data = form.cleaned_data
        try:
            desired_role = data['role']
            if user_role(self.operator) != desired_role:
                set_user_role(actor=self.request.user, user=self.operator, role=desired_role, reason=data['reason'])
            self.operator.username = data['username']
            self.operator.first_name = data['first_name']
            self.operator.last_name = data['last_name']
            self.operator.email = data['email']
            self.operator.save()
            if not data['is_active'] and self.operator.is_active:
                deactivate_user(actor=self.request.user, user=self.operator, reason=data['reason'])
            elif data['is_active'] and not self.operator.is_active:
                self.operator.is_active = True
                self.operator.save(update_fields=['is_active'])
                from accounts.models import RoleAuditEvent
                event = RoleAuditEvent(user=self.operator, actor=self.request.user, user_label=self.operator.get_username(), actor_label=self.request.user.get_username(), old_role=user_role(self.operator) or '', new_role=user_role(self.operator) or '', action='activated', reason=data['reason'])
                event._history_user = self.request.user
                event.save()
        except (PermissionDenied, ValidationError) as error:
            if isinstance(error, PermissionDenied):
                raise
            form.add_error(None, error)
            return self.form_invalid(form)
        messages.success(self.request, f'Operator {self.operator.username} updated.')
        return redirect('user_list')


class UserDeleteView(RoleRequiredMixin, View):
    permission_action = 'user.manage'

    def get(self, request, pk):
        operator = get_object_or_404(User, pk=pk)
        from django.shortcuts import render
        return render(request, 'accounts/user_confirm_delete.html', {'operator': operator})

    def post(self, request, pk):
        operator = get_object_or_404(User, pk=pk)
        try:
            delete_user(actor=request.user, user=operator, reason=request.POST.get('reason', ''))
        except (PermissionDenied, ValidationError) as error:
            if isinstance(error, PermissionDenied):
                raise
            from django.shortcuts import render
            return render(request, 'accounts/user_confirm_delete.html', {'operator': operator, 'error': error}, status=400)
        messages.success(request, 'Operator account deleted.')
        return redirect('user_list')


class PermissionMatrixView(RoleRequiredMixin, TemplateView):
    permission_action = 'permission_matrix.view'
    template_name = 'accounts/permission_matrix.html'

    def get_context_data(self, **kwargs):
        c = super().get_context_data(**kwargs)
        c['roles'] = ROLE_CHOICES
        c['permission_rows'] = [
            {'action': action, 'allowed': allowed, 'values': [role in allowed for role in ROLE_CHOICES]}
            for action, allowed in PERMISSION_MAP.items()
        ]
        return c
