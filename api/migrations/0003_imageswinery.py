# Generated by Django 2.2.3 on 2019-09-27 13:03

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0002_auto_20190925_2303'),
    ]

    operations = [
        migrations.CreateModel(
            name='ImagesWinery',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('filefield', models.FileField(blank=True, null=True, upload_to='')),
                ('winery', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='images', to='api.Winery')),
            ],
        ),
    ]
