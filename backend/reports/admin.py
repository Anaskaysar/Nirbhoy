from django.contrib import admin

from .models import Attachment, Report, ReviewAction


class AttachmentInline(admin.TabularInline):
    model = Attachment
    extra = 0
    readonly_fields = ["content_type", "size_bytes", "created_at"]


class ReviewActionInline(admin.TabularInline):
    model = ReviewAction
    extra = 0
    readonly_fields = ["reviewer", "decision", "note", "created_at"]
    can_delete = False


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ["id", "category", "district", "status", "created_at", "possible_duplicate_of"]
    list_filter = ["status", "category", "district"]
    readonly_fields = ["public_id", "receipt_hash", "created_at", "reviewed_at", "duplicate_score"]
    inlines = [AttachmentInline, ReviewActionInline]
