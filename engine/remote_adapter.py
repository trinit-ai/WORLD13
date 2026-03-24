"""
13TMOS Remote Adapter — Production Platform API Client

Thin wrapper around the production engine's REST API.
Translates between local flat JSON vault format and production API format.
The Bridge talks to the engine, not the database.
"""
import json
import logging
from datetime import datetime, timezone

import httpx

logger = logging.getLogger("13tmos.remote_adapter")

# Request timeout (seconds)
TIMEOUT = 30.0


class RemoteAdapter:
    """Talks to the production TMOS13 engine's Vault API."""

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._client = httpx.Client(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=TIMEOUT,
        )

    def close(self):
        self._client.close()

    # ── Push ──────────────────────────────────────────────

    def push_record(self, record: dict) -> dict:
        """Push a local vault record to the production platform.

        POST /api/vault/bridge/push
        Body: local vault record in dimensional format

        Returns {success: bool, session_id: str, remote_id: str | None, error: str | None}
        """
        session_id = record.get("session", "")

        try:
            # Check if already exists
            if self.check_exists(session_id):
                return {
                    "success": False,
                    "session_id": session_id,
                    "remote_id": None,
                    "error": "already_exists",
                }

            resp = self._client.post("/api/vault/bridge/push", json=record)

            if resp.status_code in (200, 201):
                data = resp.json()
                return {
                    "success": True,
                    "session_id": session_id,
                    "remote_id": data.get("id", session_id),
                    "error": None,
                }
            else:
                return {
                    "success": False,
                    "session_id": session_id,
                    "remote_id": None,
                    "error": f"HTTP {resp.status_code}: {resp.text[:200]}",
                }

        except httpx.ConnectError:
            return {
                "success": False,
                "session_id": session_id,
                "remote_id": None,
                "error": "connection_failed",
            }
        except httpx.TimeoutException:
            return {
                "success": False,
                "session_id": session_id,
                "remote_id": None,
                "error": "timeout",
            }
        except Exception as e:
            return {
                "success": False,
                "session_id": session_id,
                "remote_id": None,
                "error": str(e)[:200],
            }

    # ── Pull ──────────────────────────────────────────────

    def pull_records(self, filters: dict = None) -> list[dict]:
        """Pull vault records from production.

        GET /api/vault/bridge/pull
        Query params: pack, since, limit

        Returns list of local-format vault records.
        """
        params = {}
        if filters:
            if filters.get("pack"):
                params["pack"] = filters["pack"]
            if filters.get("since"):
                params["since"] = filters["since"]
            if filters.get("limit"):
                params["limit"] = str(filters["limit"])

        try:
            resp = self._client.get("/api/vault/bridge/pull", params=params)

            if resp.status_code == 200:
                data = resp.json()
                records = data if isinstance(data, list) else data.get("records", [])
                return records
            else:
                logger.warning("Pull failed: HTTP %d", resp.status_code)
                return []

        except httpx.ConnectError:
            logger.error("Pull failed: cannot connect to remote")
            return []
        except httpx.TimeoutException:
            logger.error("Pull failed: timeout")
            return []
        except Exception as e:
            logger.error("Pull failed: %s", e)
            return []

    # ── Check ─────────────────────────────────────────────

    def check_exists(self, session_id: str) -> bool:
        """Check if a session exists on the remote platform."""
        try:
            resp = self._client.head(f"/api/vault/bridge/check/{session_id}")
            return resp.status_code == 200
        except Exception:
            return False

    def remote_count(self, filters: dict = None) -> int:
        """Get count of remote records matching filters."""
        params = {}
        if filters:
            if filters.get("pack"):
                params["pack"] = filters["pack"]
            if filters.get("since"):
                params["since"] = filters["since"]

        try:
            resp = self._client.get("/api/vault/bridge/count", params=params)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("count", 0)
            return -1
        except Exception:
            return -1

    def ping(self) -> bool:
        """Check if the remote platform is reachable."""
        try:
            resp = self._client.get("/health", timeout=5.0)
            return resp.status_code == 200
        except Exception:
            return False
