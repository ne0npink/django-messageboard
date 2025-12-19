
"""Creating views for messageboard."""
from datetime import datetime
import json
from functools import wraps
from django.http import JsonResponse, HttpResponse, HttpResponseBadRequest
from django.contrib.auth import login
from django.contrib.auth.hashers import make_password
from django.shortcuts import render, redirect
from django.contrib.auth.models import User as AuthUser
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Q
import pytz
from app.models import User, Post, Comment, UserType, SuppressionReason

def login_required_json(view_func):
    """decorator to ensure user is logged in for JSON responses"""
    @wraps(view_func) ##use wraps to preserve view_func metadata
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Unauthorized"}, status=401)
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def can_view(obj, user_profile):
    """Returns True if the logged-in user can see the object"""
    if not obj.is_suppressed:
        return True
    if user_profile.user_type.can_moderate:
        return True  ##admin users can see all content
    if obj.author == user_profile:
        return True  ##authors see their own suppressed content
    return False  ##others cannot see suppressed content

def index(request):
    """Renders the index page with bio and current time"""
    current_time = timezone.localtime(timezone.now()).strftime("%H:%M")
    bio = "I'm Nick Park. If you've found this, then you're reading my bio."
    context = {
        "current_time": current_time,
        "bio": bio,
    }
    return render(request, "app/index.html", context)

def new(request):
    """ Render the user signup form (GET only)."""
    if request.method != "GET":
        return HttpResponseBadRequest("Invalid request method") ##only GET allowed
    return render(request, "app/new.html")

def create_user(request):
    """ Handle POST requests to create a new user."""
    if request.method != "POST":
        return HttpResponseBadRequest("Invalid request method. Use POST.") ##only POST allowed

    ##extract form data to create user
    username = request.POST.get("user_name")
    email = request.POST.get("email")
    password = request.POST.get("password")
    is_admin = request.POST.get("is_admin")
    last_name = request.POST.get("last_name", "")  ##optional, default empty string

    ##run various checks
    if not all([username, password, email, is_admin]): ##include email later if needed
        return HttpResponseBadRequest("Missing required fields.") ##check required fields
    #if User.objects.filter(email=email).exists():
        #return HttpResponseBadRequest("Email already exists.") ##prevent duplicates

    ##hash the password
    hashed_password = make_password(password)

    ##build and save user
    auth_user = AuthUser.objects.create(
        username=username,
        email=email,
        password=hashed_password,
        last_name=last_name,
        is_staff=(is_admin == "1"),
    )
    user_type, _ = UserType.objects.get_or_create(name="admin" if is_admin == "1" else "serf")
    profile = User.objects.create(user=auth_user, user_type=user_type)
    login(request, auth_user)
    return HttpResponse(f"User '{username}' created successfully!", status=201)

def new_post(request):
    """Render HTML form for creating a new post"""
    return render(request, "app/new_post.html")

def new_comment(request):
    """Render HTML form for creating a new comment"""
    return render(request, "app/new_comment.html")

@login_required_json
def create_post(request):
    """Create a new post via POST request."""
    if request.method != "POST":
        return JsonResponse({"error": "Invalid method"}, status=405)

    # Support JSON or form POST
    if "application/json" in request.content_type:
        try:
            data = json.loads(request.body.decode("utf-8"))
            if not isinstance(data, dict):
                return JsonResponse({"error": "Invalid JSON structure"}, status=400)
            title = data.get("title")
            content = data.get("content")
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

    else:
        title = request.POST.get("title")
        content = request.POST.get("content")

    if not title or not content:
        return JsonResponse({"error": "Missing title or content"}, status=400)

    # Get or create a valid UserType
    user_type, _ = UserType.objects.get_or_create(
        name="serf", defaults={"can_moderate": False}
    )

    # Ensure app-level user profile exists
    try:
        profile = User.objects.get(user=request.user)
    except User.DoesNotExist:
        profile = User.objects.create(user=request.user, user_type=user_type)

    # If the profile exists but has no user_type, assign one (safety)
    if not profile.user_type:
        profile.user_type = user_type
        profile.save()

    # Create the post
    post = Post.objects.create(author=profile, title=title, content=content)

    # Debug: print all posts after creation

    return JsonResponse({"message": "Post created", "id": post.id}, status=201)

@login_required_json
def create_comment(request):
    """Create a new comment via POST request."""
    if request.method != "POST":
        return JsonResponse({"error": "Invalid method"}, status=405)

    post_id = request.POST.get("post_id")
    content = request.POST.get("content")

    if not post_id or not content:
        return JsonResponse({"error": "Missing post_id or content"}, status=400)

    try:
        post = Post.objects.get(id=post_id)
    except Post.DoesNotExist:
        return JsonResponse({"error": "Post does not exist."}, status=400)

    ##ensure a valid UserType exists
    user_type_name = "admin" if request.user.is_staff else "serf"
    user_type, _ = UserType.objects.get_or_create(
        name=user_type_name,
        defaults={"can_moderate": request.user.is_staff}
    )

    ##ensure the app's User exists
    profile, _ = User.objects.get_or_create(
        user=request.user,
        defaults={"user_type": user_type}
    )

    comment = Comment.objects.create(
        post=post,
        author=profile,
        content=content
)

    # If this is a browser form submission, redirect back to the board
    if "text/html" in request.headers.get("Accept", ""):
        return redirect("/app/board/")

    # Otherwise, behave like the API expects
    return JsonResponse(
        {"message": "Comment created", "id": comment.id},
        status=201
    )

@login_required_json
def hide_post(request):
    """Handles POST requests to hide/suppress a post."""
    if request.method != "POST":
        return JsonResponse({"error": "Invalid method"}, status=405) ##only POST allowed

    ##run various checks
    if not request.user.is_staff:
        return JsonResponse({"error": "Unauthorized"}, status=401) ##only admins can hide posts
    post_id = request.POST.get("post_id")
    reason_text = request.POST.get("reason", "default_reason")
    if not post_id:
        return JsonResponse({"error": "Missing post_id"}, status=400) ##require post id
    try:
        post = Post.objects.get(id=post_id)
    except Post.DoesNotExist:
        return JsonResponse({"error": "Post does not exist"}, status=400)

    ##prevent suppressing own posts
    profile = User.objects.get(user=request.user)
    if post.author == profile and not request.user.is_staff:
        return JsonResponse({"error": "You cannot hide your own post."}, status=403)

    ##ensure that the profile exists and is the correct type
    user_type, _ = UserType.objects.get_or_create(
        name="admin" if request.user.is_staff else "serf",
        defaults={"can_moderate": request.user.is_staff}
    )
    profile, _ = User.objects.get_or_create(
        user=request.user,
        defaults={"user_type": user_type}
    )

    ##build suppression fields
    post.is_suppressed = True
    post.suppressed_reason, _ = SuppressionReason.objects.get_or_create(
        suppressed_code=reason_text
    )
    post.suppressed_datetime = timezone.now()
    post.suppressed_by = profile
    post.save()
    return JsonResponse({"message": "Post suppressed"}, status=200)

@login_required_json
def hide_comment(request):
    """Suppresses a comment via POST request."""
    if request.method != "POST":
        return JsonResponse({"error": "Invalid method"}, status=405)

    if not request.user.is_staff:
        return JsonResponse({"error": "Unauthorized"}, status=401)

    # support JSON or form POST
    if request.content_type.startswith("application/json"):
        try:
            data = json.loads(request.body.decode("utf-8"))
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)
    else:
        data = request.POST.dict()

    comment_id = data.get("comment_id")
    reason_text = data.get("reason", "default_reason")

    if not comment_id:
        return JsonResponse({"error": "Missing comment_id"}, status=400)

    try:
        comment_id = int(comment_id)
    except (TypeError, ValueError):
        return JsonResponse({"error": "Invalid comment_id"}, status=400)

    # Fetch the comment
    try:
        comment = Comment.objects.get(id=comment_id)
    except Comment.DoesNotExist:
        return JsonResponse({"error": "Comment does not exist"}, status=400)

    # Fetch the user profile
    try:
        profile = User.objects.get(user=request.user)
    except User.DoesNotExist:
        return JsonResponse({"error": "User profile not found"}, status=400)

    # Prevent hiding own comment
    if comment.author == profile and not request.user.is_staff:
        return JsonResponse({"error": "You cannot hide your own comment."}, status=403)

    # Suppress comment safely
    try:
        comment.is_suppressed = True
        comment.suppressed_reason, _ = SuppressionReason.objects.get_or_create(
            suppressed_code=reason_text
        )
        comment.suppressed_datetime = timezone.now()
        comment.suppressed_by = profile
        comment.save()
    except Exception as e:
        return JsonResponse({"error": f"Failed to suppress comment: {str(e)}"}, status=500)

    return JsonResponse({"message": "Comment suppressed"}, status=200)

@login_required_json
def dump_feed(request):
    """Creates a JSON feed of all posts and comments, including suppressed ones."""
    user_profile = User.objects.get(user=request.user)
    posts = Post.objects.all().order_by("-date")
    feed = []

    for post in posts:
        visible = can_view(post, user_profile)
        if not visible:
            continue

        post_data = {
            "id": post.id,
            "author": post.author.user.username,
            "content": post.content,
            "suppressed": post.is_suppressed,
            "comments": []
        }

        for comment in Comment.objects.filter(post=post).order_by("date"):
            if not can_view(comment, user_profile):
                continue
            post_data["comments"].append({
                "id": comment.id,
                "author": comment.author.user.username,
                "content": comment.content,
                "suppressed": comment.is_suppressed
            })

        feed.append(post_data)

    return JsonResponse(feed, safe=False)

@login_required_json
def feed(request):
    """Public feed endpoint: lists all posts with truncated content."""
    ##determine which posts to show based on user type
    user_profile = User.objects.get(user=request.user)
    if user_profile.user_type.can_moderate:
        posts = Post.objects.all().order_by("-date")
    else:
        posts = Post.objects.filter(
            Q(is_suppressed=False) | Q(author=user_profile)
        ).order_by("-date")

    ##build the post feed
    feed_data = []
    for post in posts:
        feed_data.append({
            "id": post.id,
            "title": post.title,
            "username": post.author.user.username,
            "date": post.date.strftime("%Y-%m-%d %H:%M"),
            "content": post.content[:100],
            "status": "suppressed" if post.is_suppressed else "active"
        })
    return JsonResponse(feed_data, safe=False)

@login_required_json
def post_detail(request, post_id):
    """Single post endpoint with comments and suppression logic."""

    ##determine user profile
    user_profile = User.objects.get(user=request.user)
    try:
        post = Post.objects.get(id=post_id)
    except Post.DoesNotExist:
        return JsonResponse({"error": "Post does not exist."}, status=404)

    ##check if user can view suppressed post
    if post.is_suppressed and post.author != user_profile and not user_profile.user_type.can_moderate:
        return JsonResponse({"error": "Post not available."}, status=403)

    ##build comments list with suppression logic
    comments_data = []
    for comment in Comment.objects.filter(post=post).order_by("date"):
        if comment.is_suppressed and comment.author != user_profile and not user_profile.user_type.can_moderate:
            content = "This comment has been removed"
        else:
            content = comment.content
        comments_data.append({
            "id": comment.id,
            "username": comment.author.user.username,
            "date": comment.date.strftime("%Y-%m-%d %H:%M"),
            "content": content,
            "status": "suppressed" if comment.is_suppressed else "active"
        })

    ##build post data
    post_data = {
        "id": post.id,
        "title": post.title,
        "username": post.author.user.username,
        "date": post.date.strftime("%Y-%m-%d %H:%M"),
        "content": post.content,
        "status": "suppressed" if post.is_suppressed else "active",
        "comments": comments_data
    }
    return JsonResponse(post_data, safe=False)

@login_required
def feed_page(request):
    """Renders the feed page with all posts and comments."""
    if not request.user.is_authenticated:
        return redirect("/accounts/login/")

    user_profile = User.objects.get(user=request.user)
    posts = Post.objects.all().order_by("-date")

    feed = []
    for post in posts:
        if post.is_suppressed and not user_profile.user_type.can_moderate and post.author != user_profile:
            continue

        comments = Comment.objects.filter(post=post).order_by("date")
        feed.append({
            "post": post,
            "comments": comments,
        })

    return render(request, "app/feed.html", {"feed": feed})

def dummypage(request):
    """A dummy page that returns a simple message."""
    if request.method == "GET":
        return HttpResponse("No content here, sorry!")

def time(request):
    """Returns the current time in HH:MM format for CDT timezone."""
    if request.method == "GET":
        ##get current time in CDT (Central Daylight Time)
        cdt = pytz.timezone("America/Chicago")
        now = datetime.now(cdt)
        ##format as HH:MM
        time_str = now.strftime("%H:%M")
        return HttpResponse(time_str)

def sum_numbers(request):
    """Adds two numbers provided as GET parameters n1 and n2."""
    if request.method == "GET":
        try:
            n1 = request.GET.get("n1", "0")
            n2 = request.GET.get("n2", "0")
            ##convert to float to handle both integers and decimals
            result = float(n1) + float(n2)
            ##return as string
            return HttpResponse(str(result))
        except (ValueError, TypeError):
            return HttpResponse("Invalid parameters", status=400)
