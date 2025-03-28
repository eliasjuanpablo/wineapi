from django.test import TestCase, Client
from django.urls import reverse

from rest_framework import status

from api.models import (
    Country,
    Event,
    EventCategory,
    EventOccurrence,
    Rate,
    Reservation,
    Winery,
    Gender,
    Language,
)


from users.models import WineUser

GENDER_MALE = 'Male'
GENDER_FEMALE = 'Female'
GENDER_OTHER = 'Other'
LANGUAGE_SPANISH = 'Spanish'
LANGUAGE_ENGLISH = 'English'
LANGUAGE_FRENCH = 'French'


class TestReports(TestCase):
    def setUp(self):
        self.client = Client()
        self.country = Country.objects.create(name='Argentina')
        self.male = Gender.objects.create(name=GENDER_MALE)
        self.spanish = Language.objects.create(name=LANGUAGE_SPANISH)
        self.female = Gender.objects.create(name=GENDER_FEMALE)
        self.english = Language.objects.create(name=LANGUAGE_ENGLISH)
        self.other_gender = Gender.objects.create(name=GENDER_OTHER)
        self.french = Language.objects.create(name=LANGUAGE_FRENCH)

        self.winery = Winery.objects.create(
            name='My Winery',
            description='Test Winery',
            website='website.com',
        )
        self.user = WineUser.objects.create_user(
            email='example@winecompanion.com',
            password='testuserpass',
            first_name='First Name',
            last_name='Last Name',
            gender=self.other_gender,
            language=self.english,
            phone='2616489178',
            country=self.country,
            winery=self.winery,
        )
        self.tourist_1 = WineUser.objects.create_user(
            email='example2@winecompanion.com',
            password='testuserpass',
            first_name='First Name',
            last_name='Last Name',
            birth_date='1950-03-02',
            gender=self.male,
            language=self.spanish,
            phone='2616489178',
            country=self.country,
        )
        self.tourist_2 = WineUser.objects.create_user(
            email='example3@winecompanion.com',
            password='testuserpass',
            first_name='First Name',
            last_name='Last Name',
            birth_date='2000-03-02',
            gender=self.female,
            language=self.french,
            phone='2616489178',
            country=self.country,
        )
        self.event_category = EventCategory.objects.create(name="Test category")
        self.event_1 = Event.objects.create(
            name='Experiencia Malbec',
            description='a test event',
            winery=self.winery,
            price=500.0
        )
        self.event_2 = Event.objects.create(
            name='Gran cabalgata',
            description='a test event',
            winery=self.winery,
            price=500.0
        )
        self.event_1.categories.add(self.event_category)
        self.event_2.categories.add(self.event_category)
        self.event_occ_october = EventOccurrence.objects.create(
            start='2020-10-31T20:00:00',
            end='2020-10-31T23:00:00',
            vacancies=50,
            event=self.event_1
        )
        self.event_occ_december = EventOccurrence.objects.create(
            start='2020-12-11T20:00:00',
            end='2020-12-11T23:00:00',
            vacancies=50,
            event=self.event_1
        )
        self.reservation_1 = Reservation.objects.create(
            attendee_number=2,
            observations='No kids',
            paid_amount=1000.0,
            user=self.tourist_1,
            event_occurrence=self.event_occ_october,
        )
        self.reservation_2 = Reservation.objects.create(
            attendee_number=2,
            observations='No kids',
            paid_amount=1000.0,
            user=self.tourist_2,
            event_occurrence=self.event_occ_october,
        )
        self.reservation_3 = Reservation.objects.create(
            attendee_number=2,
            observations='No kids',
            paid_amount=1000.0,
            user=self.tourist_2,
            event_occurrence=self.event_occ_december,
        )

        Rate.objects.create(
            rate=5,
            user=self.tourist_1,
            comment="test_comment",
            event=self.event_1,
        )
        Rate.objects.create(
            rate=4,
            user=self.tourist_2,
            comment="test_comment",
            event=self.event_1,
        )

        Rate.objects.create(
            rate=3,
            user=self.tourist_1,
            comment="test_comment",
            event=self.event_2,
        )
        Rate.objects.create(
            rate=3,
            user=self.tourist_2,
            comment="test_comment",
            event=self.event_2,
        )

    def test_reservations_report(self):
        self.client.force_login(self.user)
        response = self.client.get(
            reverse('reservation-count-reports'),
        )
        expected_reservations_by_event = [
            {
                "name": self.event_1.name,
                "count": 3,
            }
        ]
        expected_reservations_by_month = [
            {
                "month": 1,
                "count": 0,
            },
            {
                "month": 2,
                "count": 0,
            },
            {
                "month": 3,
                "count": 0,
            },
            {
                "month": 4,
                "count": 0,
            },
            {
                "month": 5,
                "count": 0,
            },
            {
                "month": 6,
                "count": 0,
            },
            {
                "month": 7,
                "count": 0,
            },
            {
                "month": 8,
                "count": 0,
            },
            {
                "month": 9,
                "count": 0,
            },
            {
                "month": 10,
                "count": 2,
            },
            {
                "month": 11,
                "count": 0,
            },
            {
                "month": 12,
                "count": 1,
            },
        ]
        expected_events_by_rating = [
            {
                "name": self.event_1.name,
                "avg_rating": 4.5,
            },
            {
                "name": self.event_2.name,
                "avg_rating": 3,
            },
        ]
        expected_reservations_by_earnings = [
            {
                "name": self.event_1.name,
                "earnings": 3000,
            },
        ]
        expected_attendees_languages = [
            {
                'language': 'French',
                'count': 2,
            },
            {
                'language': 'Spanish',
                'count': 1,
            },
        ]
        expected_attendees_countries = [
            {
                'country': 'Argentina',
                'count': 3,
            },
        ]
        expected_attendees_age_groups = [
            {
                'group': 'young',
                'count': 2,
            },
            {
                'group': 'midage',
                'count': 0,
            },
            {
                'group': 'old',
                'count': 1,
            },
        ]

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(list(response.data['reservations_by_event']), expected_reservations_by_event)
        self.assertEqual(list(response.data['reservations_by_month']), expected_reservations_by_month)
        self.assertEqual(list(response.data['events_by_rating']), expected_events_by_rating)
        self.assertEqual(list(response.data['reservations_by_earnings']), expected_reservations_by_earnings)
        self.assertEqual(list(response.data['attendees_languages']), expected_attendees_languages)
        self.assertEqual(list(response.data['attendees_countries']), expected_attendees_countries)
        self.assertEqual(list(response.data['attendees_age_groups']), expected_attendees_age_groups)
