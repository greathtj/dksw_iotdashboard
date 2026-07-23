from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

class UserRegistrationForm(UserCreationForm):
    last_name = forms.CharField(max_length=30, required=True, help_text='필수 항목입니다.')
    first_name = forms.CharField(max_length=30, required=True, help_text='필수 항목입니다.')
    email = forms.EmailField(max_length=254, required=True, help_text='필수 항목입니다. 유효한 이메일 주소를 입력해주세요.')

    class Meta(UserCreationForm.Meta):
        model = User
        fields = UserCreationForm.Meta.fields + ('last_name', 'first_name', 'email')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        placeholder_map = {
            'username': '사용자명을 입력하세요',
            'first_name': '이름을 입력하세요',
            'last_name': '성을 입력하세요',
            'email': '이메일을 입력하세요',
            'password1': '비밀번호를 입력하세요',
            'password2': '비밀번호를 다시 입력하세요',
        }
        help_text_map = {
            'username': '필수 항목입니다. 150자 이내로 입력해주세요. 문자, 숫자, @/./+/-/_ 만 사용 가능합니다.',
            'password1': (
                '• 다른 개인 정보와 너무 유사한 비밀번호는 사용할 수 없습니다.\n'
                '• 비밀번호는 최소 8자 이상이어야 합니다.\n'
                '• 자주 사용되는 비밀번호는 사용할 수 없습니다.\n'
                '• 비밀번호는 숫자로만 구성될 수 없습니다.'
            ),
        }
        for field_name, field in self.fields.items():
            field.widget.attrs.update({
                'class': 'form-control',
                'placeholder': placeholder_map.get(field_name, f'{field_name}을(를) 입력하세요')
            })
            if field_name in help_text_map:
                field.help_text = help_text_map[field_name]

    def save(self, commit=True):
        user = super().save(commit=False)
        user.first_name = self.cleaned_data.get('first_name')
        user.last_name = self.cleaned_data.get('last_name')
        user.email = self.cleaned_data.get('email')
        if commit:
            user.save()
        return user
