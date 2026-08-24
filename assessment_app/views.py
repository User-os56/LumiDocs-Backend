import os
import json
import random
import requests
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from django.conf import settings
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from .models import UserProfile, EmailVerification, UploadedDocument, TestAttempt, QuestionAttempt
from .serializers import (
    UserSerializer,
    UploadedDocumentSerializer,
    TestAttemptListSerializer,
    TestAttemptDetailSerializer
)
from .file_utils import extract_text_from_file
from .intelligence import generate_questions_from_text


def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }

# ─────────────────────────────────────────────
# AUTHENTICATION & PROFILE
# ─────────────────────────────────────────────
from email.utils import parseaddr

@api_view(['POST'])
@permission_classes([AllowAny])
def send_verification_code(request):
    email = request.data.get('email', '').strip().lower()
    if not email:
        return Response({'error': 'Email is required.'}, status=status.HTTP_400_BAD_REQUEST)
    
    if User.objects.filter(email=email).exists():
        return Response({'error': 'An account with this email already exists.'}, status=status.HTTP_400_BAD_REQUEST)

    code = str(random.randint(100000, 999999))
    EmailVerification.objects.filter(email=email, is_used=False).delete()
    EmailVerification.objects.create(email=email, code=code)

    raw_sender = getattr(settings, 'DEFAULT_FROM_EMAIL', 'sijilumiere@gmail.com')
    
    # Clean 'LUMIERE <sijilumiere@gmail.com>' into ('LUMIERE', 'sijilumiere@gmail.com')
    sender_name, sender_email = parseaddr(raw_sender)
    if not sender_email:
        sender_email = raw_sender
    if not sender_name:
        sender_name = "LUMIERE"

    api_key = getattr(settings, 'BREVO_API_KEY', None)

    if not api_key:
        return Response({'error': 'Brevo API key is missing from server configuration.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    try:
        response = requests.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={
                "accept": "application/json",
                "api-key": api_key,
                "content-type": "application/json",
            },
            json={
                "sender": {"name": sender_name, "email": sender_email},
                "to": [{"email": email}],
                "subject": "Your Verification Code",
                "textContent": f"Your verification code is: {code}\n\nExpires in 10 minutes."
            },
            timeout=15,
        )
        response.raise_for_status()
    except requests.exceptions.HTTPError as err:
        return Response(
            {'error': f'Brevo API Error: {err.response.status_code} - {err.response.text}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    except Exception as e:
        return Response(
            {'error': f'Failed to send email: {str(e)}'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    return Response({'message': 'Verification code sent.'}, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    full_name = request.data.get('full_name', '').strip()
    email     = request.data.get('email', '').strip().lower()
    password  = request.data.get('password', '')
    code      = request.data.get('code', '').strip()

    if not all([full_name, email, password, code]):
        return Response({'error': 'All fields are required.'}, status=status.HTTP_400_BAD_REQUEST)

    if len(password) < 8:
        return Response({'error': 'Password must be at least 8 characters.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        verification = EmailVerification.objects.filter(
            email=email, code=code, is_used=False
        ).latest('created_at')
    except EmailVerification.DoesNotExist:
        return Response({'error': 'Invalid verification code.'}, status=status.HTTP_400_BAD_REQUEST)

    if verification.is_expired():
        return Response({'error': 'Verification code has expired.'}, status=status.HTTP_400_BAD_REQUEST)

    if User.objects.filter(email=email).exists():
        return Response({'error': 'An account with this email already exists.'}, status=status.HTTP_400_BAD_REQUEST)

    name_parts = full_name.split(' ', 1)
    user = User.objects.create_user(
        username=email,
        email=email,
        password=password,
        first_name=name_parts[0],
        last_name=name_parts[1] if len(name_parts) > 1 else '',
    )
    UserProfile.objects.create(user=user)
    verification.is_used = True
    verification.save()

    tokens = get_tokens_for_user(user)
    return Response({
        'message': 'Account created successfully.',
        'user': {'full_name': full_name, 'email': email},
        **tokens
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    email    = request.data.get('email', '').strip().lower()
    password = request.data.get('password', '')

    if not email or not password:
        return Response({'error': 'Email and password are required.'}, status=status.HTTP_400_BAD_REQUEST)

    user = authenticate(username=email, password=password)
    if user is None:
        return Response({'error': 'Invalid email or password.'}, status=status.HTTP_401_UNAUTHORIZED)

    tokens = get_tokens_for_user(user)
    return Response({
        'message': 'Login successful.',
        'user': {
            'full_name': f'{user.first_name} {user.last_name}'.strip(),
            'email': user.email,
        },
        **tokens
    }, status=status.HTTP_200_OK)


@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated])
def profile_view(request):
    user = request.user

    if request.method == 'GET':
        return Response({
            'full_name': f'{user.first_name} {user.last_name}'.strip(),
            'email': user.email,
        })

    full_name = request.data.get('full_name', '').strip()
    if full_name:
        parts = full_name.split(' ', 1)
        user.first_name = parts[0]
        user.last_name  = parts[1] if len(parts) > 1 else ''
        user.save()

    return Response({
        'message': 'Profile updated successfully.',
        'full_name': f'{user.first_name} {user.last_name}'.strip(),
        'email': user.email,
    })


# ─────────────────────────────────────────────
# DASHBOARD & DOCUMENT MANAGEMENT
# ─────────────────────────────────────────────

from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework import status

# ─────────────────────────────────────────────
# DASHBOARD & DOCUMENT MANAGEMENT
# ─────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_view(request):
    """
    Returns latest 3 documents and total document count.
    """

    documents = (
        UploadedDocument.objects
        .filter(user=request.user)
        .order_by('-uploaded_at')
    )

    total_count = documents.count()

    recent_documents = documents[:3]

    serializer = UploadedDocumentSerializer(
        recent_documents,
        many=True
    )

    return Response({
        'documents': serializer.data,
        'has_more': total_count > 3,
        'total_count': total_count
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def document_library_view(request):
    """
    List all user documents with sorting options.
    """

    sort_by = request.query_params.get(
        'sort',
        'date'
    )

    queryset = UploadedDocument.objects.filter(
        user=request.user
    )

    if sort_by == 'name':
        queryset = queryset.order_by(
            'original_name'
        )
    else:
        queryset = queryset.order_by(
            '-uploaded_at'
        )

    serializer = UploadedDocumentSerializer(
        queryset,
        many=True
    )

    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([
    MultiPartParser,
    FormParser
])
def upload_document_view(request):
    """
    Upload a document, extract its text,
    and save the document record.
    """

    file_obj = request.FILES.get('file')

    if not file_obj:
        return Response(
            {
                'error':
                'No file uploaded.'
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    ext = (
        os.path.splitext(
            file_obj.name
        )[1]
        .lower()
        .replace('.', '')
    )

    if ext not in [
        'pdf',
        'doc',
        'docx',
        'ppt',
        'pptx'
    ]:
        return Response(
            {
                'error':
                'Unsupported file format.'
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    doc = UploadedDocument.objects.create(
        user=request.user,
        file=file_obj,
        original_name=file_obj.name,
        file_type=ext,
        status='processing'
    )

    try:

        extracted = extract_text_from_file(
            doc.file.path
        )

        if not extracted or not extracted.strip():
            doc.status = 'failed'
            doc.save()
            return Response(
            {
                'error': 'Could not extract readable text from this document.',
                'document_id': doc.id,
                'status': doc.status
            },
            status=status.HTTP_400_BAD_REQUEST
        )
        doc.extracted_text = extracted
        doc.status = 'ready'
        doc.save()
    except Exception as e:
        doc.status = 'failed'
        doc.save()
        
        return Response(
            {
                'error': f'Failed to process file: {str(e)}',
            'document_id': doc.id,
            'status': doc.status
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    serializer = UploadedDocumentSerializer(doc)

    return Response(
        serializer.data,
        status=status.HTTP_201_CREATED
    )


@api_view(['GET', 'DELETE'])
@permission_classes([IsAuthenticated])
def document_detail_view(request, doc_id):

    try:

        doc = UploadedDocument.objects.get(
            id=doc_id,
            user=request.user
        )

    except UploadedDocument.DoesNotExist:

        return Response(
            {
                'error':
                'Document not found.'
            },
            status=status.HTTP_404_NOT_FOUND
        )

    if request.method == 'GET':

        serializer = UploadedDocumentSerializer(
            doc
        )

        return Response(
            serializer.data
        )

    if request.method == 'DELETE':

        if (
            doc.file and
            os.path.exists(doc.file.path)
        ):

            os.remove(doc.file.path)

        doc.delete()

        return Response(
            {
                'message':
                'Document deleted successfully.'
            },
            status=status.HTTP_200_OK
        )


# ─────────────────────────────────────────────
# QUIZ GENERATION
# ─────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_test_view(request):
    """
    Generate an assessment from an uploaded document.
    """

    document_id = request.data.get(
        'document_id'
    )

    difficulty = request.data.get(
        'difficulty',
        'medium'
    )

    raw_num_questions = request.data.get(
        'num_questions',
        10
    )

    # -----------------------------------------
    # Validate document
    # -----------------------------------------

    if not document_id:

        return Response(
            {
                'error':
                'A document is required to generate an assessment.'
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    # -----------------------------------------
    # Validate question count
    # -----------------------------------------

    try:

        num_questions = int(
            raw_num_questions
        )

    except (
        TypeError,
        ValueError
    ):

        return Response(
            {
                'error':
                'num_questions must be a valid number.'
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    if not 1 <= num_questions <= 30:

        return Response(
            {
                'error':
                'Number of questions must be between 1 and 30.'
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    # -----------------------------------------
    # Get user's document
    # -----------------------------------------

    try:

        doc = UploadedDocument.objects.get(
            id=document_id,
            user=request.user
        )

    except UploadedDocument.DoesNotExist:

        return Response(
            {
                'error':
                'Document not found.'
            },
            status=status.HTTP_404_NOT_FOUND
        )

    # -----------------------------------------
    # Check extracted text
    # -----------------------------------------

    if not doc.extracted_text:

        return Response(
            {
                'error':
                'This document does not contain extractable text.'
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    # -----------------------------------------
    # Generate questions
    # -----------------------------------------

    try:

        questions = generate_questions_from_text(
            text=doc.extracted_text,
            difficulty=difficulty,
            num_questions=num_questions
        )

    except Exception as e:

        print(
            f"Question generation error:"
            f"{type(e).__name__}: {e}"
        )

        return Response(
            {
                'error':
                'Unable to generate questions from this document.',
                'details':
                str(e)
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    # -----------------------------------------
    # Validate result
    # -----------------------------------------

    if not questions:

        return Response(
            {
                'error':
                'No questions could be generated from this document.'
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    # -----------------------------------------
    # Return quiz
    # -----------------------------------------

    return Response(
        {
            'document_id':
                doc.id,

            'document_name':
                doc.original_name,

            'difficulty':
                difficulty,

            'questions':
                questions
        },
        status=status.HTTP_200_OK
    )


# ─────────────────────────────────────────────
# QUIZ SUBMISSION
# ─────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_test_view(request):
    """
    Receive completed assessment answers,
    calculate score, and save assessment history.
    """

    document_id = request.data.get(
        'document_id'
    )

    difficulty = request.data.get(
        'difficulty',
        'Medium'
    )

    submissions = request.data.get(
        'answers',
        []
    )

    # -----------------------------------------
    # Validate submissions
    # -----------------------------------------

    if not submissions:

        return Response(
            {
                'error':
                'No answers submitted.'
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    if not isinstance(
        submissions,
        list
    ):

        return Response(
            {
                'error':
                'answers must be a list.'
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    # -----------------------------------------
    # Calculate score
    # -----------------------------------------

    total_questions = len(
        submissions
    )

    correct_count = 0

    for sub in submissions:

        user_ans = str(
            sub.get(
                'user_answer',
                ''
            )
        ).strip().lower()

        correct_ans = str(
            sub.get(
                'correct_answer',
                ''
            )
        ).strip().lower()

        if (
            user_ans and
            user_ans == correct_ans
        ):

            correct_count += 1

    percentage = round(
        (
            correct_count /
            total_questions
        ) * 100,
        2
    )

    # -----------------------------------------
    # Grade
    # -----------------------------------------

    if percentage >= 70:

        grade = 'A'

    elif percentage >= 60:

        grade = 'B'

    elif percentage >= 50:

        grade = 'C'

    elif percentage >= 45:

        grade = 'D'

    else:

        grade = 'F'

    # -----------------------------------------
    # Document
    # -----------------------------------------

    doc = None

    if document_id:

        doc = UploadedDocument.objects.filter(
            id=document_id,
            user=request.user
        ).first()

    # -----------------------------------------
    # Create attempt
    # -----------------------------------------

    test_attempt = TestAttempt.objects.create(

        user=request.user,

        document=doc,

        difficulty=difficulty,

        score=correct_count,

        total_questions=total_questions,

        percentage=percentage,

        grade=grade

    )

    # -----------------------------------------
    # Save individual questions
    # -----------------------------------------

    for sub in submissions:

        user_ans = str(
            sub.get(
                'user_answer',
                ''
            )
        ).strip().lower()

        correct_ans = str(
            sub.get(
                'correct_answer',
                ''
            )
        ).strip().lower()

        is_corr = (
            bool(user_ans) and
            user_ans == correct_ans
        )

        raw_options = sub.get(
            'options',
            {}
        )

        if isinstance(
            raw_options,
            (dict, list)
        ):

            formatted_options = (
                raw_options
            )

        else:

            formatted_options = {}

        QuestionAttempt.objects.create(

            test_attempt=test_attempt,

            question_text=sub.get(
                'question_text',
                ''
            ),

            options=formatted_options,

            user_answer=sub.get(
                'user_answer',
                ''
            ),

            correct_answer=sub.get(
                'correct_answer',
                ''
            ),

            is_correct=is_corr,

            explanation=sub.get(
                'explanation',
                ''
            )

        )

    # -----------------------------------------
    # Response
    # -----------------------------------------

    return Response(
        {
            'attempt_id':
                test_attempt.id,

            'score':
                correct_count,

            'total_questions':
                total_questions,

            'percentage':
                percentage,

            'grade':
                grade,

            'message':
                'Test submitted successfully.'
        },
        status=status.HTTP_201_CREATED
    )
# ─────────────────────────────────────────────
# TEST HISTORY
# ─────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def test_history_list_view(request):
    """
    Returns list of all test history records.
    """
    attempts = TestAttempt.objects.filter(user=request.user).order_by('-created_at')
    serializer = TestAttemptListSerializer(attempts, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def test_history_detail_view(request, attempt_id):
    """
    Returns full details for a clicked test attempt.
    """
    try:
        attempt = TestAttempt.objects.get(id=attempt_id, user=request.user)
    except TestAttempt.DoesNotExist:
        return Response({'error': 'Test record not found.'}, status=status.HTTP_404_NOT_FOUND)

    serializer = TestAttemptDetailSerializer(attempt)
    return Response(serializer.data)