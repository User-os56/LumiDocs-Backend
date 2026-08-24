from rest_framework import serializers
from django.contrib.auth.models import User
from .models import UploadedDocument, TestAttempt, QuestionAttempt


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'full_name']

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip()


class UploadedDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = UploadedDocument
        fields = ['id', 'original_name', 'file', 'file_type', 'status', 'uploaded_at']



class QuestionAttemptSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionAttempt
        fields = ['id', 'question_text', 'options', 'user_answer', 'correct_answer', 'is_correct', 'explanation']


class TestAttemptListSerializer(serializers.ModelSerializer):
    document_title = serializers.SerializerMethodField()

    class Meta:
        model = TestAttempt
        fields = ['id', 'document_title', 'difficulty', 'score', 'total_questions', 'percentage', 'grade', 'created_at']

    def get_document_title(self, obj):
        return obj.document.original_name if obj.document else "Deleted Document"


class TestAttemptDetailSerializer(serializers.ModelSerializer):
    document_title = serializers.SerializerMethodField()
    questions = QuestionAttemptSerializer(
        many=True,
        read_only=True
    )

    class Meta:
        model = TestAttempt
        fields = [
            'id',
            'document_title',
            'difficulty',
            'score',
            'total_questions',
            'percentage',
            'grade',
            'created_at',
            'questions'
        ]

    def get_document_title(self, obj):
        return (
            obj.document.original_name
            if obj.document
            else "Deleted Document"
        )
    