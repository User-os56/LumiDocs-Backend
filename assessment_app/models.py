from datetime import timedelta
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class UserProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile'
    )

    def __str__(self):
        return self.user.username


class EmailVerification(models.Model):
    email = models.EmailField()
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)

    def is_expired(self):
        return timezone.now() > self.created_at + timedelta(minutes=10)

    def __str__(self):
        return f"{self.email} - {self.code}"


class AssessmentResult(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    skill_category = models.CharField(max_length=100)
    score = models.FloatField()
    date_taken = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.skill_category} - {self.score}"


class UploadedDocument(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('ready', 'Ready'),
        ('failed', 'Failed'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='documents')
    file = models.FileField(upload_to='uploads/%Y/%m/')
    original_name = models.CharField(max_length=255)
    extracted_text = models.TextField(blank=True)
    file_type = models.CharField(max_length=10, blank=True)  # pdf, docx, pptx, etc.
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.original_name} ({self.user.username})"


class TestAttempt(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='test_attempts')
    document = models.ForeignKey(UploadedDocument, on_delete=models.SET_NULL, null=True, blank=True, related_name='test_attempts')
    
    # Questionnaire settings
    difficulty = models.CharField(max_length=50)  # Easy, Medium, Hard
    question_type = models.CharField(max_length=50, default='multiple_choice')
    
    # Scoring results
    score = models.IntegerField()
    total_questions = models.IntegerField()
    percentage = models.FloatField()
    grade = models.CharField(max_length=5)  # A, B, C, D, F
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        doc_name = self.document.original_name if self.document else 'Deleted Doc'
        return f"{self.user.username} - {doc_name} - {self.percentage}%"


class QuestionAttempt(models.Model):
    test_attempt = models.ForeignKey(TestAttempt, on_delete=models.CASCADE, related_name='questions')
    question_text = models.TextField()
    options = models.JSONField(default=dict)  # Supports both dict {"a": "..."} and list ["..."]
    user_answer = models.TextField(blank=True)
    correct_answer = models.TextField()
    is_correct = models.BooleanField(default=False)
    explanation = models.TextField(blank=True)

    def __str__(self):
        return f"Q: {self.question_text[:30]} | Correct: {self.is_correct}"