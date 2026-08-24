from django.contrib import admin
from .models import (
    UserProfile,
    EmailVerification,
    AssessmentResult,
    UploadedDocument,
    TestAttempt,
    QuestionAttempt
)

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'user_email')

    def user_email(self, obj):
        return obj.user.email

    user_email.short_description = 'Email'


@admin.register(UploadedDocument)
class UploadedDocumentAdmin(admin.ModelAdmin):
    list_display = ('original_name', 'user', 'file_type', 'status', 'uploaded_at')
    list_filter = ('status', 'file_type')


@admin.register(TestAttempt)
class TestAttemptAdmin(admin.ModelAdmin):
    list_display = ('user', 'document', 'difficulty', 'score', 'total_questions', 'percentage', 'grade', 'created_at')
    list_filter = ('difficulty', 'grade')


@admin.register(QuestionAttempt)
class QuestionAttemptAdmin(admin.ModelAdmin):
    list_display = ('test_attempt', 'question_text', 'is_correct')
    list_filter = ('is_correct',)
admin.site.register(AssessmentResult)
admin.site.register(EmailVerification)