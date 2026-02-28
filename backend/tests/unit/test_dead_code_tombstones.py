"""
Tombstone tests — verify removed dead code stays removed.

These tests prevent accidental resurrection of code that was intentionally
deleted during the Feb 2026 dead code review. If any of these fail, it means
someone re-introduced dead code that should not exist.
"""
import importlib
import pytest


class TestRemovedModules:
    """Verify deleted modules are not re-introduced."""

    def test_query_router_module_removed(self):
        """query_router.py was superseded by intent_classifier.py."""
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module("app.services.query_router")


class TestRemovedFunctions:
    """Verify deleted factory functions and helpers are not re-introduced."""

    def test_no_get_notification_service(self):
        from app.services import notification_service
        assert not hasattr(notification_service, "get_notification_service")

    def test_no_get_quota_service(self):
        from app.services import quota_service
        assert not hasattr(quota_service, "get_quota_service")

    def test_no_quota_service_dead_methods(self):
        from app.services.quota_service import QuotaService
        assert not hasattr(QuotaService, "set_admin_override")
        assert not hasattr(QuotaService, "reset_usage")
        assert not hasattr(QuotaService, "refresh_limits_from_tier")
        assert not hasattr(QuotaService, "get_all_quotas")

    def test_no_get_recommendation_engine(self):
        try:
            from app.services import recommendation_service
        except ImportError:
            return  # Module can't load (missing dep) — dead code can't exist
        assert not hasattr(recommendation_service, "get_recommendation_engine")

    def test_no_get_video_summarizer_service(self):
        try:
            from app.services import video_summarizer
        except ImportError:
            return  # Module can't load (missing dep) — dead code can't exist
        assert not hasattr(video_summarizer, "get_video_summarizer_service")

    def test_no_get_evaluation_service(self):
        from app.services import evaluation
        assert not hasattr(evaluation, "get_evaluation_service")

    def test_no_pricing_dead_functions(self):
        from app.core import pricing
        assert not hasattr(pricing, "calculate_stripe_net")
        assert not hasattr(pricing, "get_message_cost")

    def test_no_usage_collector_get_total_cost(self):
        from app.services.usage_collector import LLMUsageCollector
        assert not hasattr(LLMUsageCollector, "get_total_cost")

    def test_no_job_is_terminal_state(self):
        from app.models.job import Job
        assert not hasattr(Job, "is_terminal_state")


class TestRemovedConfig:
    """Verify orphaned config fields are not re-introduced."""

    def test_no_orphaned_config_fields(self):
        from app.core.config import Settings
        removed_fields = [
            "whisper_compute_type",
            "free_tier_video_limit",
            "free_tier_minutes_limit",
            "free_tier_messages_limit",
            "free_tier_storage_mb_limit",
            "stripe_publishable_key",
            "stripe_pro_monthly_price_id",
            "stripe_pro_yearly_price_id",
            "stripe_enterprise_monthly_price_id",
            "stripe_enterprise_yearly_price_id",
            "youtube_api_key",
            "log_format",
        ]
        for field_name in removed_fields:
            assert field_name not in Settings.model_fields, (
                f"Orphaned config field '{field_name}' was re-introduced. "
                f"This field was removed because it was never read by application code."
            )
