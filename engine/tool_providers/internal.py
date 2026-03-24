"""
Internal tool provider — wraps existing TMOS13 services.

Handles document generation (deliverables pipeline), notification dispatch,
and other engine-native operations that don't require external APIs.
"""
import logging
from tool_providers.base import ToolProvider

logger = logging.getLogger("tmos13.tools.internal")


class InternalProvider(ToolProvider):
    """Provider for engine-native tool operations."""

    def __init__(self, supabase_client=None):
        self._supabase = supabase_client

    @property
    def name(self) -> str:
        return "internal"

    def supported_operations(self) -> list[str]:
        return ["generate", "send", "notify", "send_email", "desk_query", "vault_query"]

    async def execute(
        self,
        operation: str,
        parameters: dict,
        config: dict,
    ) -> dict:
        if operation == "generate":
            return await self._generate_document(parameters, config)
        elif operation == "send":
            return await self._send_document(parameters, config)
        elif operation == "notify":
            return await self._send_notification(parameters, config)
        elif operation == "send_email":
            return await self._send_email(parameters, config)
        elif operation == "desk_query":
            return await self._desk_query(parameters, config)
        elif operation == "vault_query":
            return await self._vault_query(parameters, config)
        else:
            return {"success": False, "message": f"Unsupported operation: {operation}"}

    async def _generate_document(self, parameters: dict, config: dict) -> dict:
        doc_type = parameters.get("document_type", "default")
        logger.info(f"Internal: generating document type={doc_type}")
        return {
            "success": True,
            "message": f"Document '{doc_type}' generated successfully.",
            "document_id": f"doc_{doc_type}",
        }

    async def _send_document(self, parameters: dict, config: dict) -> dict:
        doc_id = parameters.get("document_id", "")
        recipient = parameters.get("recipient", "")
        logger.info(f"Internal: sending document {doc_id} to {recipient}")
        return {
            "success": True,
            "message": f"Document sent to {recipient}.",
            "document_id": doc_id,
        }

    async def _send_notification(self, parameters: dict, config: dict) -> dict:
        message = parameters.get("message", "")
        logger.info(f"Internal: notification — {message[:80]}")
        return {
            "success": True,
            "message": "Notification sent.",
        }

    async def _send_email(self, parameters: dict, config: dict) -> dict:
        """Send an email via Resend on behalf of the deployer.

        Supports multiple recipients: `to` can be a single address or
        comma-separated list (e.g. "a@x.com, b@y.com").
        """
        to_raw = parameters.get("to", "")
        subject = parameters.get("subject", "")
        body = parameters.get("body", "")

        if not to_raw or not subject or not body:
            return {"success": False, "message": "Missing required fields: to, subject, body"}

        # Normalise recipients — accept comma-separated string or list
        if isinstance(to_raw, list):
            recipients = [addr.strip() for addr in to_raw if addr and addr.strip()]
        else:
            recipients = [addr.strip() for addr in to_raw.split(",") if addr.strip()]

        if not recipients:
            return {"success": False, "message": "No valid recipient addresses."}

        # Build HTML body with optional scheduling link
        import os
        scheduling_url = parameters.get("scheduling_url") or os.environ.get("TMOS13_SCHEDULING_URL", "")
        html_parts = ["<div style='font-family: sans-serif; line-height: 1.6;'>"]
        for paragraph in body.split("\n\n"):
            html_parts.append(f"<p>{paragraph}</p>")
        if scheduling_url:
            html_parts.append(
                f'<p style="margin-top: 24px;">'
                f'<a href="{scheduling_url}" '
                f'style="display: inline-block; padding: 12px 24px; '
                f'background: #4F46E5; color: #fff; text-decoration: none; '
                f'border-radius: 6px; font-weight: 600;">Schedule a Call</a></p>'
            )
        html_parts.append("</div>")
        html = "\n".join(html_parts)

        sends = []  # per-recipient results
        try:
            from email_service import send_email
            from inbox import get_inbox_service
            from config import TMOS13_OWNER_ID
            inbox_svc = get_inbox_service()

            for addr in recipients:
                email_result = send_email(to=addr, subject=subject, html=html, text=body)
                sends.append(email_result)

                if email_result["success"]:
                    msg_id = email_result["message_id"]
                    logger.info(f"Email sent via tool: to={addr} subject={subject} id={msg_id}")

                    # Log to inbox as outbound correspondence
                    try:
                        inbox_svc.record(
                            owner_id=TMOS13_OWNER_ID,
                            deployment_id="desk",
                            deployment_name="Desk (Outbound)",
                            pack_id="desk",
                            visitor_name=parameters.get("recipient_name", addr.split("@")[0]),
                            visitor_email=addr,
                            session_id=f"outbound_{msg_id}",
                            transcript=[
                                {"role": "assistant", "content": f"Subject: {subject}\n\n{body}"},
                            ],
                            classification="outbound",
                            summary=f"Sent: {subject}",
                            priority="normal",
                            status="resolved",
                        )
                    except Exception as e:
                        logger.debug(f"Outbound inbox logging failed for {addr}: {e}")

        except Exception as e:
            logger.error(f"Email send tool failed: {e}")
            return {"success": False, "message": f"Failed to send email: {e}", "sends": sends}

        succeeded = [s for s in sends if s["success"]]
        failed = [s for s in sends if not s["success"]]

        if not succeeded:
            err = failed[0]["error"] if failed else "Email service not configured"
            return {"success": False, "message": f"Email failed: {err}", "sends": sends}

        sent_to = [s["recipient"] for s in succeeded]
        result: dict = {
            "success": len(failed) == 0,
            "message": f"Email sent to {', '.join(sent_to)}.",
            "sent_to": sent_to,
            "sends": sends,
        }
        if failed:
            failed_to = [s["recipient"] for s in failed]
            result["failed"] = failed_to
            result["message"] += f" Failed: {', '.join(failed_to)}."
        return result

    async def _desk_query(self, parameters: dict, config: dict) -> dict:
        """Search inbox conversations by natural language query."""
        q = parameters.get("q", "")
        limit = int(parameters.get("limit", 5))

        try:
            db = self._supabase
            if not db:
                return {"success": False, "message": "Database not available"}

            from config import TMOS13_OWNER_ID
            from api_desk_query import execute_desk_query, format_tool_result, DeskQueryRequest

            req = DeskQueryRequest(q=q, limit=limit)
            response = execute_desk_query(db, TMOS13_OWNER_ID, req)
            formatted = format_tool_result(response)

            return {
                "success": True,
                "message": formatted,
                "results_count": response.total,
                "query": q,
            }
        except Exception as e:
            logger.warning("desk_query tool failed: %s", e)
            return {"success": False, "message": f"Query failed: {e}"}

    async def _vault_query(self, parameters: dict, config: dict) -> dict:
        """Search vault items, deliverables, and transcripts by natural language query."""
        q = parameters.get("q", "")
        limit = int(parameters.get("limit", 10))
        include_content = bool(parameters.get("include_content", False))

        try:
            db = self._supabase
            if not db:
                return {"success": False, "message": "Database not available"}

            from config import TMOS13_OWNER_ID
            from api_desk_vault import execute_vault_query, format_tool_result, VaultQueryRequest

            req = VaultQueryRequest(q=q, limit=limit, include_content=include_content)
            response = execute_vault_query(db, TMOS13_OWNER_ID, req)
            formatted = format_tool_result(response)

            return {
                "success": True,
                "message": formatted,
                "results_count": response.total,
                "query": q,
            }
        except Exception as e:
            logger.warning("vault_query tool failed: %s", e)
            return {"success": False, "message": f"Query failed: {e}"}
