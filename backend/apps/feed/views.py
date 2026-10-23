"""Feed API (FR-2.1 infinite-scroll feed, FR-2.3 ranking, FR-3.10 reports, FR-3.11 arrival)."""

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from . import recommend, services
from .models import Comment, Snippet
from .serializers import CommentSerializer, InteractSerializer, SnippetCardSerializer, SnippetReportSerializer


class FeedPagination(LimitOffsetPagination):
    """Offset pagination over the ranked candidate window (ranking is computed, so no DB cursor)."""

    default_limit = 20
    max_limit = 50


class SnippetViewSet(viewsets.GenericViewSet):
    """GET /api/feed/snippets/ (?community=, ?tag=, ?lang=, ?limit=&offset=), GET /snippets/{id}/."""

    serializer_class = SnippetCardSerializer
    pagination_class = FeedPagination
    filter_backends: list = []

    def _chain(self):
        return services.language_chain(services.requester_language(self.request))

    def get_queryset(self):
        return services.published_snippets(self._chain())

    def get_serializer_context(self):
        return {**super().get_serializer_context(), "language_chain": self._chain()}

    def list(self, request):
        """FR-2.1/FR-2.3: candidate window → score → paginate."""
        candidates = services.feed_candidates(
            self._chain(), community=request.query_params.get("community"), tag=request.query_params.get("tag")
        )
        ranked = recommend.rank(candidates, request.user, chain=self._chain())
        page = self.paginate_queryset(ranked)
        return self.get_paginated_response(self.get_serializer(page, many=True).data)

    def retrieve(self, request, pk=None):
        return Response(self.get_serializer(self.get_object()).data)

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated])
    def interact(self, request, pk=None):
        """FR-2.2: like/unlike, bookmark/unbookmark, share, expand, read_through, view."""
        ser = InteractSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        return Response(services.interact(request.user, self.get_object(), ser.validated_data["kind"]))

    @action(detail=True, methods=["get", "post"])
    def comments(self, request, pk=None):
        """Threaded comments: GET returns nested tree, POST {body, parent?}."""
        snippet = self.get_object()
        if request.method == "POST":
            ser = CommentSerializer(data=request.data, context={"snippet": snippet})
            ser.is_valid(raise_exception=True)
            ser.save(user=request.user, snippet=snippet)
            return Response(ser.data, status=status.HTTP_201_CREATED)
        comments = list(Comment.objects.filter(snippet=snippet).select_related("user"))
        return Response(services.build_comment_tree(comments))

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated])
    def report(self, request, pk=None):
        """FR-3.10: report wrong/outdated → editorial.reopen(snippet, reason='report')."""
        ser = SnippetReportSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        snippet = get_object_or_404(Snippet, pk=pk)
        rep = services.report(request.user, snippet, ser.validated_data["reason"], ser.validated_data.get("body", ""))
        return Response(SnippetReportSerializer(rep).data, status=status.HTTP_201_CREATED)


class ArrivalSequenceView(APIView):
    """FR-3.11: GET /api/feed/arrival/ — snippets for the newcomer's current arrival bucket
    (then earlier buckets), based on days since user.arrival_date."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        arrival = request.user.arrival_date
        days = (timezone.localdate() - arrival).days if arrival else None
        current = services.arrival_bucket_for(days)
        buckets = services.arrival_buckets_to_show(current)
        chain = services.language_chain(services.requester_language(request))
        qs = services.published_snippets(chain).filter(arrival_day_bucket__in=buckets)
        snippets = sorted(qs, key=lambda s: (buckets.index(s.arrival_day_bucket), -s.published_at.timestamp()))
        ctx = {"request": request, "language_chain": chain}
        return Response(
            {
                "days_since_arrival": days,
                "bucket": current,
                "results": SnippetCardSerializer(snippets, many=True, context=ctx).data,
            }
        )
