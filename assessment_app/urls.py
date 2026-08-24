from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from . import views 
from django.conf import settings
from django.conf.urls.static import static

app_name = 'api'

urlpatterns = [
    # Auth & Profile
    path('auth/send-code/', views.send_verification_code, name='send_verification_code'),
    path('auth/register/', views.register, name='register'),
    path('auth/login/', views.login_view, name='login'),
    path('auth/profile/', views.profile_view, name='profile'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # Dashboard & Document Library
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('documents/', views.document_library_view, name='document_library'),
    
    # Test Generation & Submissions
    path('tests/generate/', views.generate_test_view, name='generate_test'),
    path('tests/submit/', views.submit_test_view, name='submit_test'),
    path('documents/upload/', views.upload_document_view, name='upload_document'),
    path('documents/<int:doc_id>/', views.document_detail_view, name='document_detail'),
    # Test History
    path('tests/history/', views.test_history_list_view, name='test_history_list'),
    path('tests/history/<int:attempt_id>/', views.test_history_detail_view, name='test_history_detail'),
]

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )