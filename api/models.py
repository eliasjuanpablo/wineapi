import datetime
from django.db import models
from django.contrib.gis.db import models as gis_models
from django.contrib.gis import geos
from django.contrib.gis.measure import Distance

from . import VARIETALS


class Winery(models.Model):
    """Model for winery"""

    name = models.CharField(max_length=30)
    description = models.TextField()
    website = models.CharField(max_length=40)
    available_since = models.DateTimeField(null=True, blank=True)
    location = gis_models.PointField(u"longitude/latitude", geography=True, blank=True, null=True)

    class Meta:
        verbose_name = 'Winery'
        verbose_name_plural = 'Wineries'

    def __str__(self):
        return self.name

    @staticmethod
    def get_nearly_wineries(location):
        current_point = geos.fromstr(location)
        distance_from_point = {'km': 10}
        wineries = Winery.objects.filter(location__distance_lt=(current_point, Distance(**distance_from_point)))
        return wineries


class WineLine(models.Model):
    """Model for winery wine lines"""
    name = models.CharField(max_length=20)
    description = models.TextField()
    winery = models.ForeignKey(Winery, on_delete=models.CASCADE)

    class Meta:
        verbose_name = 'Wine-line'
        verbose_name_plural = 'Wine-lines'

    def __str__(self):
        return self.name


class Wine(models.Model):
    """Model for winery wines"""
    name = models.CharField(max_length=20)
    description = models.TextField()
    winery = models.ForeignKey(Winery, on_delete=models.CASCADE)
    # to discuss: choices vs foreign key
    varietal = models.CharField(
        max_length=20,
        choices=VARIETALS,
        default='4',
    )
    wine_line = models.ForeignKey(WineLine, on_delete=models.CASCADE)

    def __str__(self):
        return self.name


class Event(models.Model):
    """"Model for Events"""

    name = models.CharField(max_length=80)
    description = models.TextField()
    cancelled = models.DateTimeField(null=True, blank=True)
    winery = models.ForeignKey(Winery, on_delete=models.PROTECT)

    @staticmethod
    def calculate_dates_in_threshold(start, end, weekdays):
        """Returns a list of dates for certain weekdays
        between start and end."""
        if not end:
            return [start]
        dates = []
        days_between = (end - start).days + 1
        for i in range(days_between):
            day = start + datetime.timedelta(days=i)
            if day.weekday() in weekdays:
                dates.append(day)
        return dates


class EventOccurrence(models.Model):
    start = models.DateTimeField()
    end = models.DateTimeField()
    vacancies = models.IntegerField()
    event = models.ForeignKey(
        Event,
        related_name='occurrences',
        on_delete=models.CASCADE)
