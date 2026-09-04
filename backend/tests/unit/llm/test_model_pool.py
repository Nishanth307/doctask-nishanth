import time
from concurrent.futures import ThreadPoolExecutor
import pytest

from app.llm.pool import (
    ModelCapability,
    ModelPool,
    ModelStatus,
    get_model_pool,
    reset_global_model_pool,
)


class TestModelPool:

    def setup_method(self):
        reset_global_model_pool()

    def teardown_method(self):
        reset_global_model_pool()

    def test_pool_initialization_and_order(self):
        pool_config = "gemini:gemini-2.5-flash,gemini:gemini-2.5-flash-lite,groq:llama-3.3-70b-versatile,openrouter:openrouter/free"
        pool = ModelPool(pool_config=pool_config, primary_model="gemini-2.5-flash")

        targets = pool.get_eligible_models()
        assert len(targets) == 4
        assert targets[0].provider == "gemini" and targets[0].model == "gemini-2.5-flash"
        assert targets[1].provider == "gemini" and targets[1].model == "gemini-2.5-flash-lite"
        assert targets[2].provider == "groq" and targets[2].model == "llama-3.3-70b-versatile"
        assert targets[3].provider == "openrouter" and targets[3].model == "openrouter/free"

    def test_no_ollama_or_localhost_in_pool(self):
        pool_config = "ollama:llama3,gemini:gemini-2.5-flash,groq:localhost:11434,openrouter:openrouter/free"
        pool = ModelPool(pool_config=pool_config)

        targets = pool.get_eligible_models()
        for t in targets:
            assert t.provider != "ollama"
            assert "localhost" not in t.model.lower()
            assert "11434" not in t.model
        assert len(targets) == 2  # Only gemini and openrouter

    def test_capability_filtering(self):
        pool = ModelPool(pool_config="gemini:gemini-2.5-flash,groq:llama-3.3-70b-versatile")
        targets = pool.get_eligible_models(required_capabilities={ModelCapability.STRUCTURED_OUTPUT})
        assert len(targets) == 2

        # Manually alter one target to lack a custom capability
        pool.get_all_targets()[0].capabilities.remove(ModelCapability.STRUCTURED_OUTPUT)
        filtered = pool.get_eligible_models(required_capabilities={ModelCapability.STRUCTURED_OUTPUT})
        assert len(filtered) == 1
        assert filtered[0].provider == "groq"

    def test_temporary_cooldown_and_automatic_recovery(self):
        pool = ModelPool(
            pool_config="gemini:gemini-2.5-flash,gemini:gemini-2.5-flash-lite",
            cooldown_seconds=0.1,  # Short cooldown for test
        )

        eligible = pool.get_eligible_models()
        assert len(eligible) == 2
        assert eligible[0].model == "gemini-2.5-flash"

        # Mark primary model temporarily unavailable
        pool.mark_unavailable("gemini", "gemini-2.5-flash", error_type="QUOTA_EXHAUSTED", cooldown_seconds=0.1)

        # Immediate check: primary model should be excluded
        eligible_now = pool.get_eligible_models()
        assert len(eligible_now) == 1
        assert eligible_now[0].model == "gemini-2.5-flash-lite"

        # Status check
        status = pool.get_model_status("gemini", "gemini-2.5-flash")
        assert status is not None
        assert status["status"] == ModelStatus.TEMPORARILY_UNAVAILABLE.value
        assert status["last_error_type"] == "QUOTA_EXHAUSTED"
        assert status["failure_count"] == 1

        # Wait for cooldown to expire
        time.sleep(0.15)

        # Automatic recovery: primary model should be eligible again
        eligible_after_cooldown = pool.get_eligible_models()
        assert len(eligible_after_cooldown) == 2
        assert eligible_after_cooldown[0].model == "gemini-2.5-flash"

        recovered_status = pool.get_model_status("gemini", "gemini-2.5-flash")
        assert recovered_status["status"] == ModelStatus.AVAILABLE.value

    def test_mark_success_resets_failure_count(self):
        pool = ModelPool(pool_config="gemini:gemini-2.5-flash")
        pool.mark_unavailable("gemini", "gemini-2.5-flash", error_type="RATE_LIMIT", cooldown_seconds=60)
        assert pool.get_model_status("gemini", "gemini-2.5-flash")["status"] == ModelStatus.TEMPORARILY_UNAVAILABLE.value

        pool.mark_success("gemini", "gemini-2.5-flash")
        status = pool.get_model_status("gemini", "gemini-2.5-flash")
        assert status["status"] == ModelStatus.AVAILABLE.value
        assert status["failure_count"] == 0
        assert status["success_count"] == 1

    def test_thread_safe_concurrency(self):
        pool = ModelPool(pool_config="gemini:gemini-2.5-flash,groq:llama-3.3-70b-versatile,openrouter:openrouter/free")

        def worker(thread_id: int):
            for _ in range(50):
                models = pool.get_eligible_models()
                assert len(models) >= 0
                if thread_id % 2 == 0:
                    pool.mark_unavailable("gemini", "gemini-2.5-flash", cooldown_seconds=0.01)
                else:
                    pool.mark_success("gemini", "gemini-2.5-flash")
            return True

        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(worker, i) for i in range(8)]
            results = [f.result() for f in futures]

        assert all(results)
