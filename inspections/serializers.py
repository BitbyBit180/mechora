from rest_framework import serializers

from .models import Inspection, InspectionBatch, InspectionReview


class InspectionReviewSerializer(serializers.ModelSerializer):
    reviewer_name = serializers.CharField(source="reviewer.username", read_only=True)

    class Meta:
        model = InspectionReview
        fields = ("id", "inspection", "reviewed_class", "review_status", "reviewer", "reviewer_name", "comment", "reviewed_at")
        read_only_fields = ("id", "reviewer", "reviewer_name", "review_status", "reviewed_at")


class InspectionSerializer(serializers.ModelSerializer):
    review_status = serializers.CharField(read_only=True)
    review = InspectionReviewSerializer(read_only=True)
    submitted_by_name = serializers.CharField(source="submitted_by.username", read_only=True)

    class Meta:
        model = Inspection
        fields = ("id", "inspection_id", "batch", "product", "image", "original_filename", "submitted_by", "submitted_by_name", "assigned_to", "predicted_class", "confidence", "defect_probability", "model_version", "status", "review_status", "failure_reason", "created_at", "completed_at", "review")
        read_only_fields = ("id", "inspection_id", "batch", "original_filename", "submitted_by", "predicted_class", "confidence", "defect_probability", "model_version", "status", "review_status", "failure_reason", "created_at", "completed_at", "review")


class InspectionBatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = InspectionBatch
        fields = ("id", "batch_id", "submitted_by", "total_items", "created_at")
        read_only_fields = ("id", "batch_id", "submitted_by", "total_items", "created_at")
