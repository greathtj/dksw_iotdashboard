from django.shortcuts import render, redirect
from django.utils import timezone
from django.contrib.auth import login
from django.contrib import messages
from .forms import UserRegistrationForm

def home_page_view(request):
    now = timezone.now()
    context = {
        'current_time': now,
    }
    return render(request, 'pages/home.html', context)

def about_page_view(request):
    return render(request, 'pages/about.html')

def contact_page_view(request):
    return render(request, 'pages/contact.html')

def register_view(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f'Account created for {user.username}!')
            return redirect('home')
        else:
            messages.error(request, 'Registration failed. Please correct the errors below.')
    else:
        form = UserRegistrationForm()
    
    return render(request, 'registration/register.html', {'form': form})
