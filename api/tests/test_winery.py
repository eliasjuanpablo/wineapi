from django.test import TestCase, Client
from django.urls import reverse
from django.core.exceptions import ValidationError

from rest_framework import status

from users.models import WineUser
from api.models import Country, Winery, WineLine, Wine, Gender, Language, Varietal
from api.serializers import WinerySerializer, WineLineSerializer, WineSerializer


class TestWinery(TestCase):
    def setUp(self):
        self.gender = Gender.objects.create(name='Other')
        self.language = Language.objects.create(name='English')
        self.valid_winery_data = {
                'name': 'Bodega1',
                'description': 'Hola',
                'website': 'hola.com',
                'location': 'POINT (106.84341430665 -6.1832427978516)',
        }
        self.invalid_winery_data = {
                'description': 'description',
        }
        self.required_fields = set(['name', ])
        self.client = Client()

    def test_winery_creation(self):
        winery = Winery(**self.valid_winery_data)
        winery.full_clean()
        winery.save()

    def test_invalid_winery_creation(self):
        winery = Winery(**self.invalid_winery_data)
        with self.assertRaises(Exception):
            winery.full_clean()

    def test_winery_serializer(self):
        serializer = WinerySerializer(data=self.valid_winery_data)
        self.assertTrue(serializer.is_valid())
        winery_fields = ['name', 'description', 'website', 'location']
        self.assertEqual(set(serializer.validated_data.keys()), set(winery_fields))

    def test_invalid_winery_serializer(self):
        serializer = WinerySerializer(data=self.invalid_winery_data)
        self.assertFalse(serializer.is_valid())
        self.assertEqual(set(serializer.errors), self.required_fields)

    def test_winery_endpoint_get(self):
        response = self.client.get(
            reverse('winery-list')
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

    def test_winery_endpoint_create_should_not_be_allowed(self):
        data = self.valid_winery_data
        response = self.client.post(
            reverse('winery-list'),
            data
        )
        self.assertEqual(status.HTTP_401_UNAUTHORIZED, response.status_code)

    def test_winery_approval(self):
        admin = WineUser.objects.create_superuser(
            email='admin@admin.com',
            password='12345678',
            first_name='User',
            last_name='Test',
            gender=self.gender.id,
            language=self.language.id,
            country=Country.objects.create(name='Test').id,
        )
        winery = Winery.objects.create(name='Test Winery')
        self.assertIsNone(winery.available_since)

        self.client.force_login(admin)
        response = self.client.post(
            reverse('approve-wineries-approve', kwargs={'pk': winery.id})
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        winery.refresh_from_db()
        self.assertIsNotNone(winery.available_since)


class TestWines(TestCase):
    def setUp(self):
        self.country = Country.objects.create(name='Argentina')
        self.gender = Gender.objects.create(name='Other')
        self.language = Language.objects.create(name='English')
        self.varietal = Varietal.objects.create(value='Malbec')
        self.winery = Winery.objects.create(
                name='Bodega1',
                description='Test Bodega',
                website='webpage.com',
        )
        self.user = WineUser.objects.create(
            email='testuser@winecompanion.com',
            winery=self.winery,
            gender=self.gender,
            language=self.language,
            country=self.country,
        )
        self.wine_line = WineLine.objects.create(
            name='Example Wine Line',
            winery=self.winery
        )
        self.valid_wine_data = {
                'name': 'Example wine',
                'description': 'Amazing wine',
                'winery': self.winery.id,
                'varietal': self.varietal.id,
                'wine_line': self.wine_line.id,
        }
        self.invalid_wine_data = {
                'description': 'description',
        }
        self.wine_creation_data = {
            'name': 'Example wine',
            'description': 'Amazing wine',
            'winery': self.winery,
            'varietal': self.varietal,
            'wine_line': self.wine_line,
        }
        self.wine_required_fields = set(['name', 'varietal'])

    def test_wine_creation(self):
        wine = Wine(**self.wine_creation_data)
        wine.full_clean()
        wine.save()

    def test_invalid_wine_creation(self):
        wine = Wine(**self.invalid_wine_data)
        with self.assertRaises(ValidationError) as context:
            wine.full_clean()
        self.assertEqual(
            set(context.exception.error_dict),
            set(['name', 'winery', 'wine_line', 'varietal'])
        )

    def test_wine_serializer(self):
        serializer = WineSerializer(data=self.valid_wine_data)
        self.assertTrue(serializer.is_valid())
        wine_fields = ['name', 'description', 'varietal']
        self.assertEqual(set(serializer.validated_data.keys()), set(wine_fields))

    def test_invalid_wine_serializer(self):
        serializer = WineSerializer(data=self.invalid_wine_data)
        self.assertFalse(serializer.is_valid())
        self.assertEqual(set(serializer.errors), self.wine_required_fields)

    def test_wine_endpoint_get(self):
        response = self.client.get(
            reverse('wines-list', kwargs={'winery_pk': self.winery.id, 'wineline_pk': self.wine_line.id})
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

    def test_wine_endpoint_create(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('wines-list', kwargs={'winery_pk': self.winery.id, 'wineline_pk': self.wine_line.id}),
            self.valid_wine_data
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

    def test_wine_endpoint_create_with_invalid_data(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('wines-list', kwargs={'winery_pk': self.winery.id, 'wineline_pk': self.wine_line.id}),
            self.invalid_wine_data
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertEqual(response.data['errors'].keys(), self.wine_required_fields)

    def test_wine_detail_get(self):
        wine = Wine.objects.create(**self.wine_creation_data)
        response = self.client.get(
            reverse(
                'wines-detail',
                kwargs={'winery_pk': self.winery.id, 'wineline_pk': self.wine_line.id, 'pk': wine.id}
            )
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        serializer = WineSerializer(wine)
        self.assertEqual(response.data, serializer.data)

    def test_varietal_get(self):
        response = self.client.get(
            reverse('varietals-list')
        )
        expected = [{'id': self.varietal.id, 'value': self.varietal.value}]
        self.assertEqual(response.data, expected)


class TestWineLines(TestCase):
    def setUp(self):
        self.country = Country.objects.create(name='Argentina')
        self.gender = Gender.objects.create(name='Other')
        self.language = Language.objects.create(name='English')
        self.winery = Winery.objects.create(
                name='Bodega1',
                description='Test Bodega',
                website='webpage.com',
        )
        self.user = WineUser.objects.create(
            email='testuser@winecompanion.com',
            winery=self.winery,
            gender=self.gender,
            language=self.language,
            country=self.country,
        )
        self.wine_line_creation_data = {
                'name': 'Wine Line',
                'description': 'Testing wine line',
                'winery': self.winery,
        }
        self.valid_wineline_data = {
                'name': 'Wine Line',
                'description': 'Testing wine line',
                'winery': self.winery.id,
        }
        self.invalid_wineline_data = {
                'description': 'description',
        }
        self.wineline_required_fields = set(['name', ])
        self.client = Client()

    def test_wineline_creation(self):
        wineline = WineLine(**self.wine_line_creation_data)
        wineline.full_clean()
        wineline.save()

    def test_invalid_wineline_creation(self):
        wineline = WineLine(**self.invalid_wineline_data)
        with self.assertRaises(ValidationError) as context:
            wineline.full_clean()
        self.assertEqual(set(context.exception.error_dict), set(['name', 'winery']))

    def test_wineline_serializer(self):
        serializer = WineLineSerializer(data=self.valid_wineline_data)
        self.assertTrue(serializer.is_valid())
        wine_line_fields = ['name', 'description']
        self.assertEqual(set(serializer.data.keys()), set(wine_line_fields))

    def test_invalid_wineline_serializer(self):
        serializer = WineLineSerializer(data=self.invalid_wineline_data)  # dezerialize
        self.assertFalse(serializer.is_valid())
        self.assertEqual(set(serializer.errors), self.wineline_required_fields)

    def test_wineline_endpoint_get(self):
        response = self.client.get(
            reverse('winelines-list', kwargs={'winery_pk': self.winery.id}),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

    def test_wineline_endpoint_create(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('winelines-list', kwargs={'winery_pk': self.winery.id}),
            self.valid_wineline_data
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

    def test_wineline_endpoint_create_with_invalid_data(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('winelines-list', kwargs={'winery_pk': self.winery.id}),
            self.invalid_wineline_data
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertEqual(response.data['errors'].keys(), self.wineline_required_fields)

    def test_wineline_detail_get(self):
        wine_line = WineLine.objects.create(**self.wine_line_creation_data)
        response = self.client.get(
            reverse('winelines-detail', kwargs={'winery_pk': self.winery.id, 'pk': wine_line.id})
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        serializer = WineLineSerializer(wine_line)
        self.assertEqual(response.data, serializer.data)
