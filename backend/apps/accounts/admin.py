from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Interest, Location, OnboardingLink, Profile, User, UserRole


class UserRoleInline(admin.TabularInline):
    model = UserRole
    extra = 0
    autocomplete_fields = ["community"]


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ["email"]
    list_display = ["email", "display_name", "preferred_language", "reader_situation", "onboarded", "is_staff"]
    list_filter = ["preferred_language", "reader_situation", "onboarded", "is_staff", "is_superuser"]
    search_fields = ["email", "display_name"]
    inlines = [UserRoleInline]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Profile", {"fields": ("display_name", "preferred_language", "reader_situation", "arrival_date", "onboarded")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = ((None, {"classes": ("wide",), "fields": ("email", "password1", "password2")}),)


@admin.register(Interest)
class InterestAdmin(admin.ModelAdmin):
    list_display = ["slug", "name", "parent"]
    search_fields = ["slug", "name"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ["name", "postal_code", "municipality", "lat", "lng"]
    list_filter = ["municipality"]
    search_fields = ["name", "postal_code", "municipality"]


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "location", "updated_at"]
    search_fields = ["user__email"]
    filter_horizontal = ["interests"]


@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ["user", "role", "language", "community"]
    list_filter = ["role", "language", "community"]
    search_fields = ["user__email"]


@admin.register(OnboardingLink)
class OnboardingLinkAdmin(admin.ModelAdmin):
    list_display = ["code", "community", "language", "default_arrival_offset_days", "created_at"]
    list_filter = ["community", "language"]
    search_fields = ["code"]
