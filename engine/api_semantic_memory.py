"""
TMOS13 Semantic Memory Admin API — trigger consolidation + stats.

2 endpoints:
  POST /api/admin/memory/consolidate  — trigger consolidation on demand
  GET  /api/admin/memory/stats        — embedding + consolidation stats
"""
import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

import config as cfg

logger = logging.getLogger("tmos13.api_semantic_memory")


def register_semantic_memory_endpoints(app: FastAPI, db=None):
    """Register admin endpoints for semantic memory management."""

    @app.post("/api/admin/memory/consolidate")
    async def trigger_consolidation(request: Request):
        """Trigger memory consolidation on demand. Admin-only."""
        if not cfg.MEMORY_CONSOLIDATION_ENABLED:
            return JSONResponse({"error": "Memory consolidation disabled"}, status_code=400)

        try:
            from memory_consolidation import get_memory_consolidation
            mc = get_memory_consolidation()
            if not mc:
                return JSONResponse({"error": "Consolidation service not initialized"}, status_code=503)

            candidates = mc.find_consolidation_candidates(limit=10)
            results = []
            for candidate in candidates:
                try:
                    consolidation = await mc.consolidate_user_pack(
                        candidate["user_id"], candidate.get("pack_id", "")
                    )
                    results.append({
                        "user_id": candidate["user_id"][:8] + "...",
                        "pack_id": candidate.get("pack_id", "cross-pack"),
                        "source_count": candidate.get("count", 0),
                        "success": consolidation is not None,
                    })
                except Exception as e:
                    results.append({
                        "user_id": candidate["user_id"][:8] + "...",
                        "pack_id": candidate.get("pack_id", ""),
                        "error": str(e),
                        "success": False,
                    })

            mc.mark_run()
            return {
                "candidates_found": len(candidates),
                "results": results,
            }
        except Exception as e:
            logger.exception("Consolidation trigger failed")
            return JSONResponse({"error": str(e)}, status_code=500)

    @app.get("/api/admin/memory/stats")
    async def memory_stats(request: Request):
        """Get semantic memory stats. Admin-only."""
        stats = {
            "vector_search_enabled": cfg.VECTOR_SEARCH_ENABLED,
            "embed_on_save": cfg.VECTOR_EMBED_ON_SAVE,
            "consolidation_enabled": cfg.MEMORY_CONSOLIDATION_ENABLED,
            "relevance_scoring_enabled": cfg.RELEVANCE_SCORING_ENABLED,
            "relevance_boost_factor": cfg.RELEVANCE_BOOST_FACTOR,
            "consolidation_threshold": cfg.MEMORY_CONSOLIDATION_THRESHOLD,
            "consolidation_interval_hours": cfg.MEMORY_CONSOLIDATION_INTERVAL_HOURS,
        }

        # Vector store stats
        try:
            from vector_store import _vector_store
            if _vector_store and _vector_store.enabled:
                stats["vector_store"] = _vector_store.get_stats()
            else:
                stats["vector_store"] = {"enabled": False}
        except Exception:
            stats["vector_store"] = {"enabled": False, "error": "not_initialized"}

        # Embedding pipeline stats
        try:
            from embedding_pipeline import get_embedding_pipeline
            ep = get_embedding_pipeline()
            stats["embedding_pipeline"] = {"enabled": ep is not None and ep.enabled}
        except Exception:
            stats["embedding_pipeline"] = {"enabled": False}

        # Consolidation service stats
        try:
            from memory_consolidation import get_memory_consolidation
            mc = get_memory_consolidation()
            if mc:
                stats["consolidation_service"] = {
                    "enabled": mc.enabled,
                    "should_run": mc.should_run(),
                }
            else:
                stats["consolidation_service"] = {"enabled": False}
        except Exception:
            stats["consolidation_service"] = {"enabled": False}

        # DB counts (if available)
        if db:
            try:
                cons_result = db.table("memory_consolidations").select("id", count="exact").execute()
                stats["total_consolidations"] = cons_result.count if hasattr(cons_result, "count") else len(cons_result.data or [])
            except Exception:
                stats["total_consolidations"] = "unknown"

        return stats
