from datetime import (
    date,
    datetime,
)
from dateutil.relativedelta import relativedelta

from django.db.models import (
    Avg,
    Case,
    Count,
    IntegerField,
    F,
    Sum,
    When,
)
from django.db.models.functions import (
    Coalesce,
    ExtractMonth,
)
from django_filters import (
    DateTimeFromToRangeFilter,
    FilterSet,
    ModelMultipleChoiceFilter,
)
from django_filters.rest_framework import DjangoFilterBackend
from django.shortcuts import get_object_or_404
from rest_framework import filters
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.mixins import ListModelMixin, RetrieveModelMixin
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.viewsets import GenericViewSet

from . import (
    DEFAULT_CANCELLATION_REASON,
)
from users.permissions import (
    AdminOnly,
    AdminOrReadOnly,
    AllowCreateButUpdateOwnerOnly,
    AllowEventOwnerOrReadOnly,
    AllowWineryOwnerOrReadOnly,
    CreateOnlyIfWineryApproved,
    IsOwnerOrReadOnly,
    ListAdminOnly,
    LoginRequiredToEdit,
)
from .models import (
    Country,
    Event,
    EventCategory,
    EventOccurrence,
    Rate,
    Reservation,
    Tag,
    Wine,
    WineLine,
    Winery,
    ImagesWinery,
    ImagesEvent,
    ImagesWines,
    Varietal,
    Gender,
    Language,
)
from .serializers import (
    CountrySerializer,
    EventCategorySerializer,
    EventOccurrenceSerializer,
    EventSerializer,
    RateSerializer,
    ReservationSerializer,
    TagSerializer,
    WinerySerializer,
    WineLineSerializer,
    WineSerializer,
    FileSerializer,
    VarietalSerializer,
    GenderSerializer,
    LanguageSerializer,
)


class EventFilter(FilterSet):
    # https://django-filter.readthedocs.io/en/latest/guide/usage.html#declaring-filters

    start = DateTimeFromToRangeFilter(field_name="occurrences__start")
    category = ModelMultipleChoiceFilter(
        field_name="categories__name",
        to_field_name="name",
        queryset=EventCategory.objects.all(),
    )
    tag = ModelMultipleChoiceFilter(
        field_name="tags__name", to_field_name="name", queryset=Tag.objects.all()
    )

    class Meta:
        model = Event
        fields = ["occurrences__start", "category", "tag"]


class EventsView(viewsets.ModelViewSet):

    serializer_class = EventSerializer

    # search elements (must use search= as query params)
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    search_fields = ["name", "description"]

    # filter elements (must use field= as query params )
    filterset_class = EventFilter

    permission_classes = [AllowWineryOwnerOrReadOnly & CreateOnlyIfWineryApproved]
    http_method_names = ['get', 'post', 'patch', 'head', 'options', 'trace']

    def create(self, request):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
            )
        event = serializer.create(serializer.validated_data)
        return Response(
            {"url": reverse("event-detail", args=[event.id])},
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['post'], name='cancel-event')
    def cancel_event(self, request, pk):
        event = get_object_or_404(Event, id=pk)
        if event.cancelled:
            return Response({'detail': 'Event already cancelled'}, status=status.HTTP_200_OK)
        if not getattr(request.user, 'winery', None) or request.user.winery.id != event.winery.id:
            return Response({'detail': 'Access Denied'}, status=status.HTTP_403_FORBIDDEN)
        try:
            reason = request.data.get('reason', DEFAULT_CANCELLATION_REASON)
            message = event.cancel(reason)
            return Response({'detail': message}, status=status.HTTP_200_OK)
        except Exception:
            return Response(
                {"errors": "Bad Request."}, status=status.HTTP_400_BAD_REQUEST
            )

    def get_queryset(self):
        if getattr(self.request.user, 'winery', None):
            own_events = Event.objects.filter(
                winery=self.request.user.winery.id,
            ).exclude(categories__name__icontains='restaurant').distinct()
            return own_events

        all_events = Event.objects.filter(
            occurrences__start__gt=datetime.now(),
            occurrences__cancelled__isnull=True,
            cancelled__isnull=True,
        ).exclude(categories__name__icontains='restaurant').distinct()
        return all_events


class WineryView(viewsets.ModelViewSet):
    queryset = Winery.objects.filter(available_since__isnull=False)
    serializer_class = WinerySerializer

    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    search_fields = ["name", "description"]
    http_method_names = ['get', 'patch', 'head', 'options', 'trace']

    permission_classes = [AllowWineryOwnerOrReadOnly]

    @action(detail=True, methods=['get'], name='get-winery-events')
    def events(self, request, pk=None):
        events = Event.objects.filter(
            occurrences__start__gt=datetime.now(),
            winery=pk,
            cancelled__isnull=True,
        ).exclude(categories__name__icontains='restaurant').distinct()

        own_events = None
        if getattr(request.user, 'winery', None) and request.user.winery.id == int(pk):
            own_events = Event.objects.filter(
                winery=pk,
            ).exclude(categories__name__icontains='restaurant').distinct()
        query = events | own_events if own_events else events
        event_list = EventSerializer(query, many=True)
        return Response(event_list.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], name='get-winery-restaurants')
    def restaurants(self, request, pk=None):
        restaurants = Event.objects.filter(
            occurrences__start__gt=datetime.now(),
            categories__name__icontains='restaurant',
            winery=pk,
            cancelled__isnull=True,
        ).distinct()

        own_restaurants = None
        if getattr(request.user, 'winery', None) and request.user.winery.id == int(pk):
            own_restaurants = Event.objects.filter(
                winery=pk,
                categories__name__icontains='restaurant',
            ).distinct()
        query = restaurants | own_restaurants if own_restaurants else restaurants
        restaurants_list = EventSerializer(query, many=True)
        return Response(restaurants_list.data, status=status.HTTP_200_OK)


class WineView(viewsets.ModelViewSet):
    serializer_class = WineSerializer

    permission_classes = [AllowWineryOwnerOrReadOnly]

    def create(self, request, winery_pk, wineline_pk):
        serializer = serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
            )
        wine = serializer.create(serializer.validated_data, winery_pk, wineline_pk)
        return Response(
            {
                "url": reverse(
                    "wines-detail",
                    kwargs={
                        "winery_pk": winery_pk,
                        "wineline_pk": wineline_pk,
                        "pk": wine.id,
                    },
                )
            },
            status=status.HTTP_201_CREATED,
        )

    def get_queryset(self):
        wine_line = get_object_or_404(WineLine, id=self.kwargs["wineline_pk"])
        winery = get_object_or_404(Winery, id=self.kwargs["winery_pk"])
        if wine_line.winery.id != winery.id:
            raise PermissionDenied(detail="winery and wine line don't match")
        return Wine.objects.filter(wine_line=wine_line.id)


class WineLineView(viewsets.ModelViewSet):
    serializer_class = WineLineSerializer

    permission_classes = [AllowWineryOwnerOrReadOnly]

    def create(self, request, winery_pk):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
            )
        wine_line = serializer.create(serializer.validated_data, winery_pk)
        return Response(
            {
                "url": reverse(
                    "winelines-detail",
                    kwargs={"winery_pk": winery_pk, "pk": wine_line.id},
                )
            },
            status=status.HTTP_201_CREATED,
        )

    def get_queryset(self):
        winery = get_object_or_404(Winery, id=self.kwargs["winery_pk"])
        return WineLine.objects.filter(winery=winery.id)


class MapsView(APIView):
    def get(self, request, *args, **kwargs):
        q = request.GET.get("q")
        r = request.GET.get("r")
        if r is None:
            r = 100
        try:
            q = "POINT({})".format(q.replace(",", " "))
            queryset = Winery.get_nearly_wineries(q, r)
            serializer = WinerySerializer(queryset, many=True)
            return Response(serializer.data)
        except Exception:
            return Response(
                {"errors": "Invalid Request."}, status=status.HTTP_400_BAD_REQUEST
            )


class TagView(viewsets.ModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    model_class = Tag

    permission_classes = [AdminOrReadOnly]

    def create(self, request):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
            )
        tag = serializer.create(serializer.validated_data)
        return Response(
            {"url": reverse("tags-detail", args=[tag.id])},
            status=status.HTTP_201_CREATED,
        )


class CountryView(viewsets.ModelViewSet):
    queryset = Country.objects.all()
    serializer_class = CountrySerializer
    model_class = Country

    # TODO: permission_classes

    def create(self, request):
        serializer = CountrySerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        country = serializer.create(serializer.validated_data)
        return Response(
            {'url': reverse('countries-detail', args=[country.id])},
            status=status.HTTP_201_CREATED)


class LanguageView(viewsets.ModelViewSet):
    queryset = Language.objects.all()
    serializer_class = LanguageSerializer
    model_class = Language

    def create(self, request):
        serializer = LanguageSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        language = serializer.create(serializer.validated_data)
        return Response(
            {'url': reverse('languages-detail', args=[language.id])},
            status=status.HTTP_201_CREATED)


class GenderView(viewsets.ModelViewSet):
    queryset = Gender.objects.all()
    serializer_class = GenderSerializer
    model_class = Gender

    def create(self, request):
        serializer = GenderSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        gender = serializer.create(serializer.validated_data)
        return Response(
            {'url': reverse('genders-detail', args=[gender.id])},
            status=status.HTTP_201_CREATED)


class VarietalView(viewsets.ModelViewSet):
    queryset = Varietal.objects.all()
    serializer_class = VarietalSerializer
    model_class = Varietal

    def create(self, request):
        serializer = VarietalSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        varietal = serializer.create(serializer.validated_data)
        return Response(
            {'url': reverse('countries-detail', args=[varietal.id])},
            status=status.HTTP_201_CREATED)


class EventCategoryView(viewsets.ModelViewSet):
    queryset = EventCategory.objects.all()
    serializer_class = EventCategorySerializer
    model_class = EventCategory

    permission_classes = [AdminOrReadOnly]

    def create(self, request):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
            )
        event_category = serializer.create(serializer.validated_data)
        return Response(
            {"url": reverse("event-categories-detail", args=[event_category.id])},
            status=status.HTTP_201_CREATED,
        )


class ReservationView(viewsets.ModelViewSet):
    queryset = Reservation.objects.all()
    serializer_class = ReservationSerializer
    model_class = Reservation

    permission_classes = [IsAuthenticated & ListAdminOnly & AllowCreateButUpdateOwnerOnly]
    http_method_names = ['get', 'post', 'head', 'options', 'trace']

    def create(self, request):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        reservation = serializer.create(serializer.validated_data, request.user.id)

        # get event occurrency and decrement vacancies
        event_occurrence = get_object_or_404(
            EventOccurrence, pk=request.data["event_occurrence"]
        )
        event_occurrence.vacancies -= int(request.data["attendee_number"])
        event_occurrence.save()
        return Response(
            {"url": reverse("reservations-detail", args=[reservation.id])},
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['post'], name='cancel-reservation')
    def cancel_reservation(self, request, pk):
        reservation = get_object_or_404(Reservation, id=pk)
        if reservation.user.id != request.user.id:
            return Response({'detail': 'Permission Denied'}, status=status.HTTP_403_FORBIDDEN)
        try:
            reason = request.data.get('reason', DEFAULT_CANCELLATION_REASON)
            message = reservation.cancel(reason)
            return Response({'detail': message}, status=status.HTTP_200_OK)
        except Exception:
            return Response(
                {"errors": "Bad Request."}, status=status.HTTP_400_BAD_REQUEST
            )


class RatingView(viewsets.ModelViewSet):
    serializer_class = RateSerializer
    model_class = Rate

    permission_classes = [LoginRequiredToEdit & IsOwnerOrReadOnly]

    def create(self, request, event_pk):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
            )

        user = request.user
        rate = serializer.create(serializer.validated_data, event_pk, user.id)
        return Response(
            {
                "url": reverse(
                    "event-ratings-detail", kwargs={"event_pk": event_pk, "pk": rate.id}
                )
            },
            status=status.HTTP_201_CREATED,
        )

    def get_queryset(self):
        event = get_object_or_404(Event, id=self.kwargs["event_pk"])
        return Rate.objects.filter(event=event.id)


class FileUploadView(APIView):
    def post(self, request):
        serializer = FileSerializer(data=request.data)
        model = None
        kwargs = {}

        if not serializer.is_valid():
            return Response(
                {"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
            )
        if serializer.validated_data["type"] == "winery":
            model = ImagesWinery
            kwargs["winery"] = get_object_or_404(
                Winery, pk=serializer.validated_data["id"]
            )
        elif serializer.validated_data["type"] == "event":
            model = ImagesEvent
            kwargs["event"] = get_object_or_404(
                Event, pk=serializer.validated_data["id"]
            )
        elif serializer.validated_data["type"] == "wine":
            model = ImagesWines
            kwargs["wine"] = get_object_or_404(
                Wine, pk=serializer.validated_data["id"]
            )
        else:
            return Response(
                {"errors": "Type not found"}, status=status.HTTP_400_BAD_REQUEST
            )

        for onefile in serializer.validated_data["filefield"]:
            model.objects.create(filefield=onefile, **kwargs)
        return Response(status=status.HTTP_201_CREATED)


class RestaurantsView(EventsView):

    def get_queryset(self):
        all_restaurants = Event.objects.filter(
            occurrences__start__gt=datetime.now(),
            occurrences__cancelled__isnull=True,
            categories__name__icontains='restaurant',
            cancelled__isnull=True,
        ).distinct()

        own_restaurants = None
        if getattr(self.request.user, 'winery', None):
            own_restaurants = Event.objects.filter(
                winery=self.request.user.winery.id,
                categories__name__icontains='restaurant',
            ).distinct()

        queryset = all_restaurants if not own_restaurants else all_restaurants | own_restaurants
        return queryset


class EventOccurrencesView(viewsets.ModelViewSet):
    serializer_class = EventOccurrenceSerializer
    model_class = EventOccurrence

    permission_classes = [AllowEventOwnerOrReadOnly]
    http_method_names = ['get', 'post', 'patch', 'head', 'options', 'trace']

    def create(self, request, event_pk):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
            )

        occurrence = serializer.create(serializer.validated_data, event_pk)
        return Response(
            {
                "url": reverse(
                    "event-occurrences-detail",
                    kwargs={"event_pk": event_pk, "pk": occurrence.id},
                )
            },
            status=status.HTTP_201_CREATED,
        )

    def get_queryset(self):
        event = get_object_or_404(Event, id=self.kwargs["event_pk"])
        occurrences = EventOccurrence.objects.filter(
            event=event.id,
            cancelled__isnull=True,
        )
        cancelled_occurrences = None
        user_winery = getattr(self.request.user, 'winery', None)
        if user_winery and user_winery == event.winery:
            cancelled_occurrences = EventOccurrence.objects.filter(
                event=event.id,
                cancelled__isnull=False,
            )
        queryset = occurrences if not cancelled_occurrences else occurrences | cancelled_occurrences
        return queryset.order_by('id')

    @action(detail=True, methods=['post'], name='cancel-occurrence')
    def cancel_occurrence(self, request, event_pk, pk):
        occurrence = get_object_or_404(EventOccurrence, id=pk)
        if occurrence.cancelled:
            return Response({'detail': 'Occurrence already cancelled'}, status=status.HTTP_200_OK)
        if not getattr(request.user, 'winery', None) or request.user.winery.id != occurrence.event.winery.id:
            return Response({'detail': 'Access Denied'}, status=status.HTTP_403_FORBIDDEN)
        reason = request.data.get('reason')
        message = occurrence.cancel(reason)
        return Response({'detail': message}, status=status.HTTP_200_OK)


class RestaurantOccurrencesView(viewsets.ModelViewSet):
    serializer_class = EventOccurrenceSerializer
    model_class = EventOccurrence
    http_method_names = ['get', 'post', 'patch', 'head', 'options', 'trace']

    def create(self, request, restaurant_pk):
        serializer = EventOccurrenceSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        occurrence = serializer.create(serializer.validated_data, restaurant_pk)
        return Response(
            {
                'url': reverse(
                    'restaurant-occurrences-detail',
                    kwargs={'restaurant_pk': restaurant_pk, 'pk': occurrence.id}
                )
            },
            status=status.HTTP_201_CREATED)

    def get_queryset(self):
        restaurant = get_object_or_404(Event, id=self.kwargs.get("restaurant_pk"))
        occurrences = EventOccurrence.objects.filter(
            event=restaurant.id,
            cancelled__isnull=True,
        )
        cancelled_occurrences = None
        user_winery = getattr(self.request.user, 'winery', None)
        if user_winery and user_winery == restaurant.winery:
            cancelled_occurrences = EventOccurrence.objects.filter(
                event=restaurant.id,
                cancelled__isnull=False,
            )
        queryset = occurrences if not cancelled_occurrences else occurrences | cancelled_occurrences
        return queryset.order_by('id')

    @action(detail=True, methods=['post'], name='cancel-occurrence')
    def cancel_occurrence(self, request, restaurant_pk, pk):
        occurrence = get_object_or_404(EventOccurrence, id=pk)
        if occurrence.cancelled:
            return Response({'detail': 'Occurrence already cancelled'}, status=status.HTTP_200_OK)
        if not getattr(request.user, 'winery', None) or request.user.winery.id != occurrence.event.winery.id:
            return Response({'detail': 'Access Denied'}, status=status.HTTP_403_FORBIDDEN)
        reason = request.data.get('reason')
        message = occurrence.cancel(reason)
        return Response({'detail': message}, status=status.HTTP_200_OK)


class WineryApprovalView(ListModelMixin, RetrieveModelMixin, GenericViewSet):
    queryset = Winery.objects.filter(available_since__isnull=True)
    serializer_class = WinerySerializer

    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    search_fields = ['name', 'description']
    http_method_names = ['get', 'head', 'options', 'post']

    permission_classes = [AdminOnly]

    @action(detail=True, methods=['post'], name='approve')
    def approve(self, request, pk):
        winery = get_object_or_404(Winery, id=pk)
        winery.available_since = datetime.now()
        winery.save()
        return Response({'detail': 'Winery successfully approved'}, status=status.HTTP_200_OK)


class ReportsView(APIView):
    def get(self, request, *args, **kwargs):
        DATE_FORMAT = "%Y-%m-%d"
        user_events = request.user.winery.events.all()
        user_events_reservations = Reservation.objects.filter(event_occurrence__event__in=user_events)
        user_events_ratings = Rate.objects.filter(event__in=user_events)
        from_date = request.query_params.get('from_date')
        to_date = request.query_params.get('to_date')
        try:
            if from_date:
                from_date = datetime.strptime(from_date, DATE_FORMAT)
                user_events_reservations = user_events_reservations.filter(event_occurrence__start__gte=from_date)
                user_events_ratings = user_events_ratings.filter(created__gte=from_date)

            if to_date:
                to_date = datetime.strptime(to_date, DATE_FORMAT)
                user_events_reservations = user_events_reservations.filter(event_occurrence__end__lte=to_date)
                user_events_ratings = user_events_ratings.filter(created__lte=to_date)
        except (ValueError, TypeError):
            return Response(
                {"errors": "Dates format must be 'YYYY-MM-DD'"}, status=status.HTTP_400_BAD_REQUEST
            )
        today = date.today()
        age_18_birth_year = (today - relativedelta(years=18)).year
        age_35_birth_year = (today - relativedelta(years=35)).year
        age_50_birth_year = (today - relativedelta(years=50)).year
        response = {
            "reservations_by_event": (
                user_events_reservations
                .values("event_occurrence__event__name")
                .annotate(name=F("event_occurrence__event__name"))
                .annotate(count=Count("id"))
                .values("name", "count")
                .order_by("count")[:10]
            ),
            "reservations_by_month": (
                user_events_reservations
                .annotate(month=ExtractMonth("event_occurrence__start"))
                .values("month")
                .annotate(count=Count("id"))
                .values("month", "count")
                .order_by("month")
            ),
            "attendees_languages": (
                user_events_reservations
                .values("user__language__name")
                .annotate(language=F("user__language__name"))
                .annotate(count=Count("id"))
                .values("language", "count")
            ),
            "attendees_countries": (
                user_events_reservations
                .values("user__country__name")
                .annotate(country=F("user__country__name"))
                .annotate(count=Count("id"))
                .values("country", "count")
            ),
            "attendees_age_groups": (
                user_events_reservations
                .annotate(young=Case(
                    When(user__birth_date__year__range=(age_35_birth_year, age_18_birth_year), then=1),
                    default=0,
                    output_field=IntegerField())
                )
                .annotate(midage=Case(
                    When(user__birth_date__year__range=(age_50_birth_year, age_35_birth_year - 1), then=1),
                    default=0,
                    output_field=IntegerField())
                )
                .annotate(old=Case(
                    When(user__birth_date__year__lt=age_50_birth_year, then=1),
                    default=0,
                    output_field=IntegerField())
                )
                .aggregate(
                    young_sum=Sum('young'),
                    midage_sum=Sum('midage'),
                    old_sum=Sum('old')
                )
            ),
            "events_by_rating": (
                user_events_ratings
                .values("event__name")
                .annotate(avg_rating=Coalesce(Avg("rate"), 0))
                .annotate(name=F("event__name"))
                .values("name", "avg_rating")
                .order_by("-avg_rating")[:10]
            ),
            "reservations_by_earnings": (
                user_events_reservations
                .values("event_occurrence__event__name")
                .annotate(earnings=Sum("paid_amount"))
                .annotate(name=F("event_occurrence__event__name"))
                .values("name", "earnings")
                .order_by("-earnings")[:10]
            )
        }

        # Awful hack to return months with count = 0
        # To achieve this with SQL, a Month table is needed :(
        zero_count_months = [{"month": i, "count": 0} for i in range(1, 13)]
        reservations = response["reservations_by_month"]

        for elem in reservations:
            zero_count_months[elem['month'] - 1].update(elem)

        response['reservations_by_month'] = zero_count_months
        response['attendees_age_groups'] = [
            {"group": k.split("_")[0], "count": v} for k, v in response['attendees_age_groups'].items()
        ]

        return Response(response)


class EventReservationsView(RetrieveModelMixin,
                            ListModelMixin,
                            GenericViewSet):

    serializer_class = ReservationSerializer
    model_class = Reservation

    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        occurrence = get_object_or_404(
            EventOccurrence,
            id=self.kwargs["occurrence_pk"],
            event__winery=self.request.user.winery,
        )
        return Reservation.objects.filter(event_occurrence=occurrence.id)

    @action(detail=True, methods=['post'], name='cancel-reservation')
    def cancel_reservation(self, request, event_pk, occurrence_pk, pk):
        reservation = get_object_or_404(Reservation, id=pk)
        if reservation.event_occurrence.event.winery != request.user.winery:
            return Response({'detail': 'Permission Denied'}, status=status.HTTP_403_FORBIDDEN)
        reason = request.data.get('reason')
        message = reservation.cancel(reason)
        return Response({'detail': message}, status=status.HTTP_200_OK)
