""" 
Defines user-related models for ED equivalent 
"""

from django.db import models

class UserType(models.Model):
    """
    Defines whether a user is a 'serf' or an 'admin' - i.e. do they have moderation privileges?
    """
    name = models.CharField(max_length=50, unique=True)
    can_moderate = models.BooleanField(default=False)

    def __str__(self):
        return self.name

class User(models.Model):
    """
    Defines a user.
    """
    user = models.OneToOneField("auth.User", on_delete=models.CASCADE)
    user_type = models.ForeignKey(UserType, on_delete=models.CASCADE)
    bio = models.TextField(blank=True, null=True)
    avatar = models.ForeignKey("Avatar", null=True, blank=True, on_delete=models.SET_NULL, related_name="users")

    def __str__(self):
        return f"{self.user.username}"

class Avatar(models.Model):
    """
    Defines an avatar image for a user profile
    """
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="avatars")
    image = models.ImageField(upload_to="avatars/")
    avatar_upload_datetime = models.DateTimeField(auto_now_add=True)
    deleted = models.BooleanField(default=False)

    def __str__(self):
        return f"Avatar of {self.owner.user.username}"

class Post(models.Model):
    """
    Defines a post made by a user.
    """
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    content = models.TextField()
    date = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    is_suppressed = models.BooleanField(default=False)
    suppressed_reason = models.ForeignKey("SuppressionReason", null=True, blank=True, on_delete=models.SET_NULL)
    suppressed_datetime = models.DateTimeField(blank=True, null=True)
    suppressed_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="suppressed_posts")

    def __str__(self):
        return f"Post by {self.author.user.username} at {self.date}"

class Comment(models.Model):
    """
    Defines a comment made on a post
    """
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    date = models.DateTimeField(auto_now_add=True)
    is_suppressed = models.BooleanField(default=False)
    suppressed_reason = models.ForeignKey("SuppressionReason", null=True, blank=True, on_delete=models.SET_NULL)
    suppressed_datetime = models.DateTimeField(blank=True, null=True)
    suppressed_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="suppressed_comments")

    def __str__(self):
        return f"Comment by {self.author.user.username} on {self.post.title}"

class SuppressionReason(models.Model):
    """
    Defines the reason(s) for which a post or comment was suppressed
    """
    suppressed_code = models.CharField(max_length=50, unique=True)
    description = models.TextField()

    def __str__(self):
        return self.suppressed_code

class Media(models.Model):
    """
    Defines any and all media files uploaded by users
    """
    uploader = models.ForeignKey(User, on_delete=models.CASCADE)
    file = models.FileField(upload_to="media/")
    size_in_bytes = models.BigIntegerField()
    media_uploaded_datetime = models.DateTimeField(auto_now_add=True)
    is_displayable = models.BooleanField(default=True)
    attached_post = models.ForeignKey(Post, null=True, blank=True, on_delete=models.CASCADE)
    attached_comment = models.ForeignKey(Comment, null=True, blank=True, on_delete=models.CASCADE)

    def __str__(self):
        return f"Uploaded by {self.uploader.user.username} at {self.media_uploaded_datetime}"
