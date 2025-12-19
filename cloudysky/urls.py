"""
URL configuration for cloudysky project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib.auth import views as auth_views
from django.contrib import admin
from django.urls import path
from . import views

urlpatterns = [
    # Admin and existing views
    path("admin/", admin.site.urls),
    path("", views.index, name="index"),
    path("index.html", views.index, name="index_html"),
    path("login/", auth_views.LoginView.as_view(template_name="app/login.html"), name="login"),
    path("accounts/login/", auth_views.LoginView.as_view(template_name="app/login.html"), name="accounts_login"),

    # User signup views
    path("app/new", views.new, name="new_user_form"),
    path("app/createUser/", views.create_user, name="create_user"),

    # Post/comment creation views
    path("app/new_post", views.new_post, name="new_post"),
    path("app/new_comment", views.new_comment, name="new_comment"),

    # API endpoint views
    path("app/createPost/", views.create_post, name="createPost"),
    path("app/createComment/", views.create_comment, name="createComment"),
    path("app/hidePost/", views.hide_post, name="hidePost"),
    path("app/hideComment/", views.hide_comment, name="hideComment"),
    path("app/dumpFeed", views.dump_feed, name="dumpFeed"),
    path("app/feed", views.feed, name="feed"),
    path("app/post/<int:post_id>", views.post_detail, name="post_detail"),

    # User and post views
    path("app/board/", views.feed_page, name="board"),

    # Random extra features
    path("dummypage", views.dummypage, name="dummypage"),
    path("app/time", views.time, name="time"),
    path("app/sum", views.sum_numbers, name="sum"),
]
