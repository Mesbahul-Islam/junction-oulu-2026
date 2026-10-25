from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from apps.common.choices import Language, ReaderSituation

from .models import Interest, Location, OnboardingLink, Profile, User, UserRole, username_validator


class InterestSerializer(serializers.ModelSerializer):
    class Meta:
        model = Interest
        fields = ["id", "slug", "name", "parent"]


class LocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = ["id", "name", "postal_code", "municipality", "lat", "lng"]


class ProfileSerializer(serializers.ModelSerializer):
    interests = serializers.SlugRelatedField(slug_field="slug", many=True, queryset=Interest.objects.all())
    location = LocationSerializer(read_only=True)

    class Meta:
        model = Profile
        fields = ["interests", "location", "interest_vector"]
        read_only_fields = ["interest_vector"]


class UserRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserRole
        fields = ["role", "language", "community"]


def validate_username_free(value: str, exclude_pk=None) -> str:
    value = value.strip()
    if User.objects.filter(username__iexact=value).exclude(pk=exclude_pk).exists():
        raise serializers.ValidationError("That username is taken. Try another.")
    return value


class UserSerializer(serializers.ModelSerializer):
    """GET/PATCH /me (FR-1.1). The username can be changed here (e.g. after Google sign-in)."""

    profile = ProfileSerializer(read_only=True)
    roles = UserRoleSerializer(many=True, read_only=True)

    class Meta:
        model = User
        fields = [
            "id", "email", "username", "display_name", "preferred_language", "reader_situation",
            "arrival_date", "onboarded", "profile", "roles", "is_staff",
        ]
        read_only_fields = ["id", "email", "onboarded", "profile", "roles", "is_staff"]

    def validate_username(self, value):
        return validate_username_free(value, exclude_pk=self.instance.pk if self.instance else None)


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    username = serializers.CharField(max_length=30, validators=[username_validator])
    password = serializers.CharField(write_only=True)
    display_name = serializers.CharField(required=False, allow_blank=True)

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Email already registered.")
        return value

    def validate_username(self, value):
        return validate_username_free(value)

    def validate(self, attrs):
        validate_password(attrs["password"], User(email=attrs["email"]))
        return attrs


class OnboardingSerializer(serializers.Serializer):
    """FR-1.1 onboarding + FR-3.11 QR code. Location: location_id, postal_code, or lat+lng."""

    interests = serializers.ListField(child=serializers.SlugField(), required=False, default=list)
    location_id = serializers.IntegerField(required=False)
    postal_code = serializers.CharField(required=False, allow_blank=True, max_length=10)
    lat = serializers.FloatField(required=False, min_value=-90, max_value=90)
    lng = serializers.FloatField(required=False, min_value=-180, max_value=180)
    # Statistics Finland's three-digit code, from POST /api/accounts/locate/ or the town picker.
    municipality_code = serializers.RegexField(r"^\d{3}$", required=False)
    preferred_language = serializers.ChoiceField(choices=Language.choices, required=False)
    reader_situation = serializers.ChoiceField(choices=ReaderSituation.choices)
    arrival_date = serializers.DateField(required=False, allow_null=True)
    onboarding_code = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        if ("lat" in attrs) != ("lng" in attrs):
            raise serializers.ValidationError("lat and lng must be given together.")
        code = attrs.get("onboarding_code")
        if code and not OnboardingLink.objects.filter(code=code).exists():
            raise serializers.ValidationError({"onboarding_code": "Unknown code."})
        town = attrs.get("municipality_code")
        if town:
            from apps.communities.places import municipality_name

            if not municipality_name(town):
                raise serializers.ValidationError({"municipality_code": "Unknown municipality."})
        return attrs


class LocateSerializer(serializers.Serializer):
    """Coordinates from the browser, used once to find the municipality and never stored."""

    lat = serializers.FloatField(min_value=-90, max_value=90)
    lng = serializers.FloatField(min_value=-180, max_value=180)


class OnboardingLinkSerializer(serializers.ModelSerializer):
    community_slug = serializers.CharField(source="community.slug", read_only=True, default=None)

    class Meta:
        model = OnboardingLink
        fields = ["code", "community", "community_slug", "language", "default_arrival_offset_days"]
