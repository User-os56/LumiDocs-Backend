import random
import json
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from django.core.mail import send_mail
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from .models import UserProfile, EmailVerification, UserProgress, AssessmentResult
from .intelligence import (
    generate_question_batch,
    calculate_next_difficulty,
    get_recommendations
)


# ─────────────────────────────────────────────
# HELPER: Generate JWT tokens for a user
# ─────────────────────────────────────────────
def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }


# ─────────────────────────────────────────────
# SEND VERIFICATION CODE
# ─────────────────────────────────────────────
@api_view(['POST'])
@permission_classes([AllowAny])
def send_verification_code(request):
    email = request.data.get('email', '').strip().lower()

    if not email:
        return Response({'error': 'Email is required.'}, status=status.HTTP_400_BAD_REQUEST)
    
    print("Checking if user exists...")
    if User.objects.filter(email=email).exists():
        return Response({'error': 'An account with this email already exists.'}, status=status.HTTP_400_BAD_REQUEST)

    code = str(random.randint(100000, 999999))
    EmailVerification.objects.filter(email=email, is_used=False).delete()
    
    print("Creating verification code...")
    EmailVerification.objects.create(email=email, code=code)

    print("Verification code saved to database.")
    
    print("EMAIL_HOST:", settings.EMAIL_HOST)
    print("EMAIL_PORT:", settings.EMAIL_PORT)
    print("EMAIL_HOST_USER:", settings.EMAIL_HOST_USER)
    print("Password exists:", bool(settings.EMAIL_HOST_PASSWORD))

    try:
        print("About to send email...")

        send_mail(
            subject='Your LUMIERE Verification Code',
            message=(
                f'Hello,\n\n'
                f'Your verification code is: {code}\n\n'
                f'This code expires in 10 minutes.\n\n'
                f'If you did not request this, please ignore this email.\n\n'
                f'— The LUMIERE Team'
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )
        print("Email sent successfully!")

    except Exception as e:
        print("Email sending failed:", repr(e))
        
        return Response(
            {'error': f'Failed to send email: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    return Response({'message': 'Verification code sent. Please check your email.'}, status=status.HTTP_200_OK)


# ─────────────────────────────────────────────
# REGISTER
# ─────────────────────────────────────────────
@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    full_name  = request.data.get('full_name', '').strip()
    email      = request.data.get('email', '').strip().lower()
    department = request.data.get('department', '').strip()
    password   = request.data.get('password', '')
    code       = request.data.get('code', '').strip()

    if not all([full_name, email, department, password, code]):
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
        return Response({'error': 'Verification code has expired. Please request a new one.'}, status=status.HTTP_400_BAD_REQUEST)

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
    UserProfile.objects.create(user=user, department=department)
    verification.is_used = True
    verification.save()

    tokens = get_tokens_for_user(user)
    return Response({
        'message': 'Account created successfully.',
        'user': {'full_name': full_name, 'email': email, 'department': department},
        **tokens
    }, status=status.HTTP_201_CREATED)


# ─────────────────────────────────────────────
# LOGIN
# ─────────────────────────────────────────────
@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    email    = request.data.get('email', '').strip().lower()
    password = request.data.get('password', '')

    if not email or not password:
        print("❌ Missing email or password")
        return Response({'error': 'Email and password are required.'}, status=status.HTTP_400_BAD_REQUEST)

    user = authenticate(username=email, password=password)
    if user is None:
        print("❌ Authentication failed - wrong credentials or user not found")
        return Response({'error': 'Invalid email or password.'}, status=status.HTTP_401_UNAUTHORIZED)

    print("✅ Authentication successful for user:", user.email)

    tokens = get_tokens_for_user(user)
    department = ''
    try:
        department = user.profile.department
    except UserProfile.DoesNotExist:
        pass

    return Response({
        'message': 'Login successful.',
        'user': {
            'full_name': f'{user.first_name} {user.last_name}'.strip(),
            'email': user.email,
            'department': department,
        },
        **tokens
    }, status=status.HTTP_200_OK)


# ─────────────────────────────────────────────
# RESEND CODE
# ─────────────────────────────────────────────
@api_view(['POST'])
@permission_classes([AllowAny])
def resend_code(request):
    email = request.data.get('email', '').strip().lower()
    if not email:
        return Response({'error': 'Email is required.'}, status=status.HTTP_400_BAD_REQUEST)

    code = str(random.randint(100000, 999999))
    EmailVerification.objects.filter(email=email, is_used=False).delete()
    EmailVerification.objects.create(email=email, code=code)

    try:
        send_mail(
            subject='Your LUMIERE Verification Code (Resent)',
            message=f'Your new verification code is: {code}\n\nExpires in 10 minutes.\n\n— The LUMIERE Team',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )
    except Exception as e:
        return Response({'error': f'Failed to resend email: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return Response({'message': 'A new code has been sent to your email.'}, status=status.HTTP_200_OK)


# ─────────────────────────────────────────────
# START ASSESSMENT SESSION
# Called from onboarding page with field + level
# ─────────────────────────────────────────────
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def start_assessment(request):
    """
    Creates a fresh UserProgress session and pre-fetches the first batch.
    Called when user completes the onboarding questionnaire.
    """
    user            = request.user
    expertise_field = request.data.get('expertise_field', 'Full Stack Developer').strip()
    entry_level     = request.data.get('entry_level', 'Beginner').strip()

    # Map entry level to starting theta
    theta_map = {'Beginner': -1.0, 'Intermediate': 0.0, 'Expert': 1.5}
    starting_theta = theta_map.get(entry_level, 0.0)

    # Close any incomplete sessions for this user
    UserProgress.objects.filter(user=user, is_completed=False).delete()

    # Generate first batch of 10 questions immediately
    first_batch = generate_question_batch(
        start_step=1,
        current_theta=starting_theta,
        skill_type='technical',
        expertise_field=expertise_field,
        batch_size=10,
        previously_asked=[]
    )

    # Create the session, storing the question batch as JSON
    progress = UserProgress.objects.create(
        user=user,
        expertise_field=expertise_field,
        current_step=1,
        current_theta=starting_theta,
        is_completed=False,
        question_batch=json.dumps(first_batch),
        batch_index=0,
        asked_topics=json.dumps([q.get('topic', '') for q in first_batch])
    )

    # Return the first question immediately
    first_question = first_batch[0]
    return Response({
        **first_question,
        'step': 1,
        'total': 50,
        'is_completed': False,
        'theta': starting_theta,
        'expertise_field': expertise_field,
    }, status=status.HTTP_200_OK)


# ─────────────────────────────────────────────
# PROCESS ANSWER — serves from batch cache
# ─────────────────────────────────────────────
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def process_answer(request):
    user        = request.user
    was_correct = request.data.get('was_correct', None)
    new_session = request.data.get('new_session', False)  # frontend sends this when starting fresh

    # If frontend is starting a new test, wipe old sessions first
    if new_session:
        UserProgress.objects.filter(user=user).delete()

    # Get active session
    progress = UserProgress.objects.filter(user=user, is_completed=False).first()

    if not progress:
        # Auto-create a session using expertise_field from request
        expertise_field = request.data.get('expertise_field', 'Full Stack Developer').strip()
        entry_level     = request.data.get('entry_level', 'Beginner').strip()
        theta_map       = {'Beginner': -1.0, 'Intermediate': 0.0, 'Expert': 1.5}
        starting_theta  = theta_map.get(entry_level, 0.0)

        first_batch = generate_question_batch(
            start_step=1,
            current_theta=starting_theta,
            skill_type='technical',
            expertise_field=expertise_field,
            batch_size=10,
            previously_asked=[]
        )

        progress = UserProgress.objects.create(
            user=user,
            expertise_field=expertise_field,
            current_step=1,
            current_theta=starting_theta,
            is_completed=False,
            question_batch=json.dumps(first_batch),
            batch_index=0,
            asked_topics=json.dumps([q.get('topic', '') for q in first_batch])
        )
        # Return first question from the new session
        first_question = first_batch[0]
        progress.batch_index   = 1
        progress.current_step  = 2
        progress.save()
        return Response({
            **first_question,
            'step': 1,
            'total': 50,
            'is_completed': False,
            'theta': starting_theta,
        })

    # Update theta based on previous answer
    if was_correct is True:
        progress.current_theta = calculate_next_difficulty(progress.current_theta, True)
    elif was_correct is False:
        progress.current_theta = calculate_next_difficulty(progress.current_theta, False)

    # Check if assessment is complete
    if progress.current_step > 50:
        progress.is_completed = True
        progress.save()
        AssessmentResult.objects.create(
            user=user,
            skill_category=progress.expertise_field,
            score=progress.current_theta
        )
        return Response({
            'is_completed': True,
            'final_score': progress.current_theta,
            'expertise_field': progress.expertise_field,
            'message': 'Assessment complete!'
        })

    # Load current batch from DB
    try:
        batch = json.loads(progress.question_batch) if progress.question_batch else []
    except (json.JSONDecodeError, TypeError):
        batch = []

    batch_index = progress.batch_index or 0

    # If we've exhausted the current batch, fetch the next one
    if batch_index >= len(batch):
        skill_type = 'technical' if progress.current_step <= 40 else 'soft_skill'

        try:
            asked_topics = json.loads(progress.asked_topics) if progress.asked_topics else []
        except (json.JSONDecodeError, TypeError):
            asked_topics = []

        batch = generate_question_batch(
            start_step=progress.current_step,
            current_theta=progress.current_theta,
            skill_type=skill_type,
            expertise_field=progress.expertise_field,
            batch_size=10,
            previously_asked=asked_topics
        )

        # Track asked topics to prevent repetition in future batches
        new_topics = asked_topics + [q.get('topic', '') for q in batch]
        progress.asked_topics    = json.dumps(new_topics[-40:])  # keep last 40
        progress.question_batch  = json.dumps(batch)
        batch_index = 0

    # Serve the current question from the batch
    current_question = batch[batch_index]

    # Advance counters
    progress.batch_index   = batch_index + 1
    progress.current_step += 1
    progress.save()

    return Response({
        **current_question,
        'step':         progress.current_step - 1,
        'total':        50,
        'is_completed': False,
        'theta':        round(progress.current_theta, 2),
    })
    
# ─────────────────────────────────────────────
# AI RECOMMENDATIONS GENERATOR
# ─────────────────────────────────────────────
# ── Replace recommendations_view in views.py with this ───────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def recommendations_view(request):
    user        = request.user
    tier_filter = request.query_params.get('tier', 'free').lower()

    # ── DEBUG: print everything we can see about this user ───────────────
    print(f"[RECS] User: {user.email}")
    try:
        profile = user.profile
        print(f"[RECS] profile.department:      {profile.department!r}")
        print(f"[RECS] profile.expertise_field: {profile.expertise_field!r}")
        expertise_from_profile = profile.expertise_field.strip()
    except Exception as e:
        print(f"[RECS] UserProfile error: {e}")
        expertise_from_profile = ''

    latest_result = AssessmentResult.objects.filter(user=user).order_by('-date_taken').first()
    if latest_result:
        print(f"[RECS] latest AssessmentResult: field={latest_result.skill_category!r}, score={latest_result.score}")
    else:
        print(f"[RECS] No AssessmentResult found for this user")

    # ── Determine field and score ────────────────────────────────────────
    if expertise_from_profile:
        skill_category = expertise_from_profile
        score = latest_result.score if latest_result else 0.0
        print(f"[RECS] Using profile expertise: {skill_category!r}")
    elif latest_result:
        skill_category = latest_result.skill_category
        score          = latest_result.score
        print(f"[RECS] Using assessment result: {skill_category!r}")
    else:
        skill_category = 'Full Stack Developer'
        score          = 0.0
        print(f"[RECS] Using hardcoded default")

    print(f"[RECS] Final: field={skill_category!r}, score={score}, tier={tier_filter!r}")

    try:
        raw = get_recommendations(
            skill_category=skill_category,
            final_score=score,
            tier=tier_filter
        )

        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except json.JSONDecodeError:
                pass

        return Response({
            'skill_development':     raw.get('skill_development', []),
            'improvement_resources': raw.get('improvement_resources', []),
            'field':                 skill_category,
            'score':                 round(score, 2),
        }, status=status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {'error': f'Failed to generate recommendations: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
@require_http_methods(["GET"])
def recommendations_api(request):
    """
    GET /api/recommendations/?tier=free|paid&field=Data+Scientist&score=0.75
    
    Returns AI-generated learning resource recommendations based on:
    - tier: 'free' or 'paid'
    - field: user's expertise field (e.g., 'Data Scientist', 'AI Engineer')
    - score: IRT theta score from assessment
    """
    # Extract query parameters
    tier = request.GET.get('tier', 'free')
    field = request.GET.get('field', 'Full Stack Developer')
    
    # Parse score safely
    try:
        score = float(request.GET.get('score', 0))
    except (ValueError, TypeError):
        score = 0.0
    
    # DEBUG: Log what we received
    print(f"[DEBUG] API received: tier={tier}, field={field}, score={score}")
    
    # Call the intelligence function
    result = get_recommendations(field, score, tier)
    
    return JsonResponse(result)

# ── Add this view to your views.py ──────────────────────────────────────

@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated])
def profile_view(request):
    """
    GET  /api/profile/  — returns the user's current profile data
    PATCH /api/profile/ — updates name, department, and/or expertise_field
    """
    user = request.user

    if request.method == 'GET':
        try:
            profile = user.profile
            department = profile.department
            expertise_field = profile.expertise_field  # new field — see models note below
        except UserProfile.DoesNotExist:
            department = ''
            expertise_field = ''

        return Response({
            'full_name':      f'{user.first_name} {user.last_name}'.strip(),
            'email':          user.email,
            'department':     department,
            'expertise_field': expertise_field,
        })

    # PATCH — update profile
    full_name       = request.data.get('full_name', '').strip()
    department      = request.data.get('department', '').strip()
    expertise_field = request.data.get('expertise_field', '').strip()

    # Update User name
    if full_name:
        parts = full_name.split(' ', 1)
        user.first_name = parts[0]
        user.last_name  = parts[1] if len(parts) > 1 else ''
        user.save()

    # Update UserProfile
    try:
        profile = user.profile
    except UserProfile.DoesNotExist:
        profile = UserProfile(user=user)

    if department:
        profile.department = department
    if expertise_field:
        profile.expertise_field = expertise_field
    profile.save()

    return Response({
        'message':        'Profile updated successfully.',
        'full_name':      f'{user.first_name} {user.last_name}'.strip(),
        'email':          user.email,
        'department':     profile.department,
        'expertise_field': profile.expertise_field,
    })
