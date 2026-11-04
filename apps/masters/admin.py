from django.contrib import admin
from .models import Master,WorkSchedule,DayOff


class WorkScheduleInline(admin.TabularInline):
    model = WorkSchedule
    extra = 1


class DayOffline(admin.TabularInline):
    model = DayOff
    extra = 0

@admin.register(Master)
class MasterAdmin(admin.ModelAdmin):
    list_display = ['user','shop','is_active','created_at']
    list_filter = ('shop','is_active')
    search_fields = ('user__phone','user__first_name')
    inlines = [WorkScheduleInline,DayOffline]


class ModelAdmin(admin.ModelAdmin):
    list_display = ['user', 'shop', 'is_active']
    list_filter = ['shop', 'is_active']

