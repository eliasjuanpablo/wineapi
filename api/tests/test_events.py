import datetime
from django.test import Client, TestCase
from django.urls import reverse
from api.models import Event
from api.serializers import EventSerializer


class TestEvents(TestCase):
    def setUp(self):
        self.valid_data = {
            "one_schedule_no_to_date": {
                "name": "TEST_EVENT_NAME",
                "description": "TEST_EVENT_DESCRIPTION",
                "vacancies": 50,
                "schedule": [
                    {
                        "from_date": "2019-08-28",
                        "to_date": None,
                        "start_time": "15:30:00",
                        "end_time": "16:30:00",
                        "weekdays": None,
                    }
                ],
            },
            "one_schedule_with_weekdays": {
                "name": "TEST_EVENT_NAME",
                "description": "TEST_EVENT_DESCRIPTION",
                "vacancies": 50,
                "schedule": [
                    {
                        "from_date": "2019-08-28",
                        "to_date": "2019-09-11",
                        "start_time": "15:30:00",
                        "end_time": "16:30:00",
                        "weekdays": [1, 2, 3],
                    }
                ],
            },
            "multiple_schedules_with_weekdays": {
                "name": "TEST_EVENT_NAME",
                "description": "TEST_EVENT_DESCRIPTION",
                "vacancies": 50,
                "schedule": [
                    {
                        "from_date": "2019-08-28",
                        "to_date": "2019-09-11",
                        "start_time": "8:30:00",
                        "end_time": "10:30:00",
                        "weekdays": [1, 3, 5],
                    },
                    {
                        "from_date": "2019-08-28",
                        "to_date": "2019-09-11",
                        "start_time": "15:30:00",
                        "end_time": "16:30:00",
                        "weekdays": [1, 3, 5],
                    },
                ],
            },
        }

        self.client = Client()

    def test_dates_between_threshold(self):
        MONDAY, WEDNESDAY, FRIDAY = 0, 2, 4
        start = datetime.date(2019, 8, 18)
        end = datetime.date(2019, 8, 31)
        weekdays = [MONDAY, WEDNESDAY, FRIDAY]
        expected = [
            datetime.date(2019, 8, 19),
            datetime.date(2019, 8, 21),
            datetime.date(2019, 8, 23),
            datetime.date(2019, 8, 26),
            datetime.date(2019, 8, 28),
            datetime.date(2019, 8, 30),
        ]
        result = Event.calculate_dates_in_threshold(start, end, weekdays)

        self.assertEqual(expected, result)

    def test_single_ocurrence_event_creation_without_to_date(self):
        data = self.valid_data["one_schedule_no_to_date"]
        serializer = EventSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        response = self.client.post(
            reverse("event-list"), data=data, content_type="application/json"
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(set(response.json().keys()), set(["url"]))

        db_event = Event.objects.first()
        self.assertEqual(db_event.name, data["name"])
        self.assertEqual(1, len(db_event.occurrences.all()))

    def test_single_ocurrence_event_creation_with_weekdays(self):
        data = self.valid_data["one_schedule_with_weekdays"]
        serializer = EventSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        response = self.client.post(
            reverse("event-list"), data=data, content_type="application/json"
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(set(response.data.keys()), set(["url"]))

    def test_single_ocurrence_event_creation(self):
        data = self.valid_data["multiple_schedules_with_weekdays"]
        serializer = EventSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        response = self.client.post(
            reverse("event-list"), data=data, content_type="application/json"
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(set(response.data.keys()), set(["url"]))

    def test_event_endpoint_get(self):
        c = Client()
        response = c.get("/api/events/")
        result = response.status_code
        self.assertEqual(200, result)
