from rest_framework import generics, permissions, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from .models import Review
from .serializers import ReviewCreateSerializer, ReviewSerializer


def _related(qs):
    return qs.select_related("client", "booking__master__user", "booking__master__shop", "booking__service")


def _int_param(request, name):
    value = request.query_params.get(name)
    if value is None or value == "":
        return None
    if not value.isdigit():
        raise ValidationError({name: "Son bo'lishi kerak."})
    return int(value)


class ReviewListCreateView(generics.ListCreateAPIView):
    """GET (hamma): sharhlar, ?shop=<id>&master=<id>.  POST (mijoz): bajarilgan bronga sharh."""

    def get_permissions(self):
        if self.request.method == "POST":
            return [permissions.IsAuthenticated()]
        return [permissions.AllowAny()]

    def get_serializer_class(self):
        return ReviewCreateSerializer if self.request.method == "POST" else ReviewSerializer

    def get_queryset(self):
        qs = _related(
            Review.objects.filter(
                booking__master__shop__is_active=True, booking__master__shop__is_approved=True
            )
        )
        shop_id = _int_param(self.request, "shop")
        if shop_id:
            qs = qs.filter(booking__master__shop_id=shop_id)
        master_id = _int_param(self.request, "master")
        if master_id:
            qs = qs.filter(booking__master_id=master_id)
        return qs

    def create(self, request, *args, **kwargs):
        serializer = ReviewCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        review = serializer.save(client=request.user)
        review = _related(Review.objects.filter(pk=review.pk)).get()
        return Response(ReviewSerializer(review).data, status=status.HTTP_201_CREATED)


class MyReviewListView(generics.ListAPIView):
    serializer_class = ReviewSerializer

    def get_queryset(self):
        return _related(Review.objects.filter(client=self.request.user))
