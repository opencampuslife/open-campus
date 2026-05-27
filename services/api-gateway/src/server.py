from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
from http.cookies import SimpleCookie
from http.client import HTTPMessage
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse
from typing import Any


def _load_env(project_root: Path) -> None:
    env_path = project_root / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val

from admin_gateway import (
    admin_approve_staging_doc,
    admin_cancel_ingestion_run,
    admin_create_graph_run,
    admin_create_ingestion_run,
    admin_get_audit_event,
    admin_get_graph_run,
    admin_get_ingestion_run,
    admin_get_latest_graph,
    admin_get_staging_doc,
    admin_health,
    admin_list_audit_events,
    admin_list_audit_logs,
    admin_list_graph_runs,
    admin_list_ingestion_runs,
    admin_list_sources,
    admin_list_staging_docs,
    admin_publish_staging_doc,
    admin_query_audit_by_lead,
    admin_query_audit_by_session,
    admin_query_audit_by_trace,
    admin_reject_staging_doc,
    admin_sources_upload,
    admin_update_staging_doc,
    admin_validate_staging_doc,
)
from bff_gateway import (
    add_crm_lead_followup,
    add_followup,
    assign_crm_lead,
    create_crm_lead,
    get_crm_lead,
    get_sales_session,
    list_sales_leads,
    list_sales_sessions,
    list_sessions,
    patch_crm_lead,
    post_chat,
    post_handoff,
    takeover_session,
    update_crm_lead_status,
)
from campus_gateway import (
    approve_campus_leave,
    assign_campus_repair,
    cancel_campus_meal_order,
    close_campus_repair,
    complete_campus_repair,
    confirm_campus_delivery,
    get_campus_daily_report,
    get_campus_leave,
    get_campus_meal_summary,
    get_campus_repair,
    get_campus_wecom_callback,
    get_campus_wecom_start,
    issue_campus_wecom_state,
    list_campus_leaves,
    list_campus_repairs,
    post_campus_leave,
    post_campus_meal_order,
    post_campus_repair,
    reject_campus_leave,
)
from campus_auth import load_wecom_session_identity
from mealbot_gateway import (
    get_h5_attachment,
    get_h5_students,
    get_logistics_meal_summary,
    get_mealbot_orders,
    get_pilot_status,
    get_vendor_confirm_page,
    get_wecom_message_callback,
    post_mealbot_lock,
    post_mealbot_meal_order,
    post_mealbot_meal_order_cancel,
    post_scheduler_run_due_reminders,
    post_vendor_confirmation,
    post_vendor_confirm_action,
    post_wecom_message_callback,
    post_wecom_process_media_downloads,
    post_pilot_runtime_control,
)
from campus_modules_gateway import (
    get_modules_dashboard,
    post_attendance_records,
    post_attendance_session,
    post_collection_task,
    post_material_missing,
    post_material_submission,
    post_module_leave,
    post_module_leave_decision,
    post_module_leave_return,
    post_overdue_returns,
    post_payment_confirm,
    post_payment_missing,
    post_payment_record,
    post_payment_task,
    post_process_ocr,
    post_score_batch,
    post_score_confirm,
    post_score_rpa_dry_run,
    post_module_export,
)
from multipart_parser import parse_multipart
from csrf_protection import generate_csrf_token, is_admin_path, verify_csrf
from health_checks import (
    db_health,
    filesystem_health,
    full_health_check,
    llm_health,
    public_health,
    healthz,
    readyz,
    rag_health,
    security_health,
    worker_status,
)
from admin_policy import UntrustedProxyError, validate_trusted_proxy
from rate_limiter import check_rate_limit
from structured_logger import RequestLogger

ADMIN_LEGACY_MUTATION_SUNSET = os.environ.get("ADMIN_LEGACY_MUTATION_SUNSET", "Wed, 30 Sep 2026 23:59:59 GMT")


class GaokaoHandler(BaseHTTPRequestHandler):
    project_root = Path(__file__).resolve().parents[3]

    _chat_routes = {"/api/gaokao/chat", "/api/gaokao/handoff"}
    _local_consumer_chat_route = "/api/local/consumer-chat"

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        query_identity = _identity_from_query(query)
        identity = self._resolve_identity(query_identity)
        self._check_rate_limit(path, identity.get("user_id", ""))

        try:
            if path == "/wecom/callback/message":
                result = get_wecom_message_callback({k: v[0] for k, v in query.items()}, self.project_root)
                self._write_text(result, HTTPStatus.OK)
                return
            if path == "/healthz":
                self._write_json(healthz(self.project_root), HTTPStatus.OK)
                return
            if path == "/readyz":
                ready = readyz(self.project_root)
                self._write_json(ready, HTTPStatus.OK if ready["ok"] else HTTPStatus.SERVICE_UNAVAILABLE)
                return
            if path == "/" or path == "":
                html_path = self.project_root / "standalone-gaokao.html"
                if html_path.exists():
                    body = html_path.read_bytes()
                    self.send_response(HTTPStatus.OK.value)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                self._write_json({"error": "not_found"}, HTTPStatus.NOT_FOUND)
                return
            if path.startswith("/h5/"):
                if (
                    os.environ.get("GAOKAO_ENV", "development") == "production"
                    and identity.get("role") == "visitor"
                    and os.environ.get("WECOM_H5_OAUTH_AUTO_REDIRECT", "1") != "0"
                ):
                    redirect_path = path + (f"?{parsed.query}" if parsed.query else "")
                    self._write_redirect(
                        f"/api/campus/auth/wecom/start?redirect_path={quote(redirect_path, safe='')}",
                        HTTPStatus.FOUND,
                    )
                    return
                relative_h5_path = path.removeprefix("/")
                if not Path(relative_h5_path).suffix:
                    relative_h5_path += ".html"
                h5_path = self.project_root / "services" / "mealbot-service" / "src" / "app" / "static" / relative_h5_path
                if h5_path.exists():
                    html = h5_path.read_text("utf-8")
                    # H5 calls the serving gateway by default so its HttpOnly OAuth cookie remains first-party.
                    api_base = os.environ.get("H5_API_BASE_URL", "").rstrip("/")
                    wecom_userid = identity.get("wecom_userid") or query.get("wecom_userid", [""])[0]
                    if not wecom_userid and os.environ.get("GAOKAO_ENV", "development") != "production":
                        wecom_userid = query.get("wecom_userid", [""])[0] or identity.get("user_id", "")
                    html = html.replace("{{API_BASE}}", api_base)
                    html = html.replace("{{WECOM_USERID}}", wecom_userid)
                    body = html.encode("utf-8")
                    self.send_response(HTTPStatus.OK.value)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
            if path == "/api/csrf-token":
                session_id = identity.get("user_id", self.headers.get("X-Forwarded-For", self.client_address[0]))
                token = generate_csrf_token(session_id)
                self._write_json({"csrf_token": token}, HTTPStatus.OK)
                return
            if path == "/api/health":
                result = public_health(self.project_root)
            elif path == "/api/health/full":
                result = full_health_check(self.project_root)
            elif path == "/api/health/db":
                result = db_health(self.project_root)
            elif path == "/api/health/rag":
                result = rag_health(self.project_root)
            elif path == "/api/health/llm":
                result = llm_health(self.project_root)
            elif path == "/api/health/security":
                result = security_health(self.project_root)
            elif path == "/api/health/filesystem":
                result = filesystem_health(self.project_root)
            elif path == "/api/internal/worker-status":
                if identity.get("role") not in {"admin", "super_admin", "school_admin", "campus_admin", "logistics_staff"}:
                    raise ValueError("FORBIDDEN")
                result = worker_status(self.project_root)
            elif path == "/api/pilot/status":
                result = get_pilot_status({k: v[0] for k, v in query.items()}, identity, self.project_root)
            elif path == "/api/sessions":
                result = list_sessions(identity, self.project_root)
            elif path == "/api/sales/sessions":
                result = list_sales_sessions(identity, self.project_root)
            elif path.startswith("/api/sales/sessions/") and path.endswith("/detail"):
                session_id = path.removeprefix("/api/sales/sessions/").removesuffix("/detail")
                result = get_sales_session(session_id, identity, self.project_root)
            elif path == "/api/sales/leads":
                result = list_sales_leads(identity, self.project_root)
            elif path == "/api/crm/leads":
                result = list_sales_leads(identity, self.project_root)
            elif path.startswith("/api/crm/leads/"):
                lead_id = path.removeprefix("/api/crm/leads/")
                result = get_crm_lead(lead_id, identity, self.project_root)
            elif path == "/api/campus/auth/wecom/callback":
                result = get_campus_wecom_callback({k: v[0] for k, v in query.items()}, identity, self.project_root)
                cookie = self._campus_session_cookie(str(result["session_id"]))
                if query.get("redirect", [""])[0] == "1":
                    redirect_path = str(result.get("redirect_path") or "/h5/campus/index")
                    if not redirect_path.startswith("/h5/") or redirect_path.startswith("//"):
                        raise ValueError("invalid OAuth redirect path")
                    self._write_redirect(redirect_path, HTTPStatus.FOUND, {"Set-Cookie": cookie})
                    return
                self._write_json(result, HTTPStatus.OK, extra_headers={"Set-Cookie": cookie})
                return
            elif path == "/api/campus/auth/wecom/start":
                result = get_campus_wecom_start({k: v[0] for k, v in query.items()}, identity, self.project_root)
                self._write_redirect(str(result["authorize_url"]), HTTPStatus.FOUND)
                return
            elif path == "/api/campus/leaves":
                result = list_campus_leaves(identity, self.project_root)
            elif path.startswith("/api/campus/leaves/"):
                leave_id = path.removeprefix("/api/campus/leaves/")
                result = get_campus_leave(leave_id, identity, self.project_root)
            elif path == "/api/campus/meals/summary":
                result = get_campus_meal_summary({k: v[0] for k, v in query.items()}, identity, self.project_root)
            elif path == "/api/meal-orders":
                result = get_mealbot_orders({k: v[0] for k, v in query.items()}, identity, self.project_root)
            elif path == "/api/logistics/meal-summary":
                result = get_logistics_meal_summary({k: v[0] for k, v in query.items()}, identity, self.project_root)
            elif path == "/vendor/confirm":
                result = get_vendor_confirm_page({k: v[0] for k, v in query.items()}, identity, self.project_root)
            elif path == "/api/h5/students":
                result = get_h5_students({k: v[0] for k, v in query.items()}, identity, self.project_root)
            elif path.startswith("/api/h5/attachments/"):
                attachment_id = path.removeprefix("/api/h5/attachments/")
                result = get_h5_attachment(attachment_id, identity, self.project_root)
            elif path == "/api/campus/repairs":
                result = list_campus_repairs(identity, self.project_root)
            elif path.startswith("/api/campus/repairs/"):
                ticket_id = path.removeprefix("/api/campus/repairs/")
                result = get_campus_repair(ticket_id, identity, self.project_root)
            elif path == "/api/campus/reports/daily":
                result = get_campus_daily_report({k: v[0] for k, v in query.items()}, identity, self.project_root)
            elif path == "/api/campus/modules/dashboard":
                result = get_modules_dashboard(identity)
            elif path == "/api/admin/health":
                result = admin_health(identity, self.project_root)
            elif path == "/api/admin/sources":
                result = admin_list_sources(identity, self.project_root)
            elif path == "/api/admin/ingestion/runs":
                result = admin_list_ingestion_runs(identity, self.project_root)
            elif path.startswith("/api/admin/ingestion/runs/") and path.endswith("/cancel"):
                result = self._dispatch_admin_legacy_mutation(path, identity)
                self._record_legacy_admin_get_usage(path, "POST " + path)
                self._write_json(result, HTTPStatus.OK, extra_headers=self._legacy_admin_alias_headers(path))
                return
            elif path.startswith("/api/admin/ingestion/runs/"):
                run_id = path.removeprefix("/api/admin/ingestion/runs/")
                result = admin_get_ingestion_run(run_id, identity, self.project_root)
            elif path == "/api/admin/staging/docs":
                result = admin_list_staging_docs(identity, self.project_root)
            elif path.startswith("/api/admin/staging/docs/") and path.endswith("/validate"):
                result = self._dispatch_admin_legacy_mutation(path, identity)
                self._record_legacy_admin_get_usage(path, "POST " + path)
                self._write_json(result, HTTPStatus.OK, extra_headers=self._legacy_admin_alias_headers(path))
                return
            elif path.startswith("/api/admin/staging/docs/") and path.endswith("/approve"):
                result = self._dispatch_admin_legacy_mutation(path, identity)
                self._record_legacy_admin_get_usage(path, "POST " + path)
                self._write_json(result, HTTPStatus.OK, extra_headers=self._legacy_admin_alias_headers(path))
                return
            elif path.startswith("/api/admin/staging/docs/") and path.endswith("/reject"):
                result = self._dispatch_admin_legacy_mutation(path, identity)
                self._record_legacy_admin_get_usage(path, "POST " + path)
                self._write_json(result, HTTPStatus.OK, extra_headers=self._legacy_admin_alias_headers(path))
                return
            elif path.startswith("/api/admin/staging/docs/") and path.endswith("/publish"):
                result = self._dispatch_admin_legacy_mutation(path, identity)
                self._record_legacy_admin_get_usage(path, "POST " + path)
                self._write_json(result, HTTPStatus.OK, extra_headers=self._legacy_admin_alias_headers(path))
                return
            elif path.startswith("/api/admin/staging/docs/"):
                staging_doc_id = path.removeprefix("/api/admin/staging/docs/")
                result = admin_get_staging_doc(staging_doc_id, identity, self.project_root)
            elif path == "/api/admin/graph/runs":
                result = admin_list_graph_runs(identity, self.project_root)
            elif path == "/api/admin/graph/latest":
                result = admin_get_latest_graph(identity, self.project_root)
            elif path.startswith("/api/admin/graph/runs/"):
                graph_run_id = path.removeprefix("/api/admin/graph/runs/")
                result = admin_get_graph_run(graph_run_id, identity, self.project_root)
            elif path == "/api/admin/audit":
                result = admin_list_audit_logs(identity, self.project_root)
            elif path == "/api/admin/audit/events":
                kw = _audit_query_params(query)
                result = admin_list_audit_events(identity, self.project_root, **kw)
            elif path.startswith("/api/admin/audit/events/by-trace/"):
                trace_id = path.removeprefix("/api/admin/audit/events/by-trace/")
                kw = _audit_query_params(query)
                result = admin_query_audit_by_trace(trace_id, identity, self.project_root, **kw)
            elif path.startswith("/api/admin/audit/events/by-session/"):
                session_id = path.removeprefix("/api/admin/audit/events/by-session/")
                kw = _audit_query_params(query)
                result = admin_query_audit_by_session(session_id, identity, self.project_root, **kw)
            elif path.startswith("/api/admin/audit/events/by-lead/"):
                lead_id = path.removeprefix("/api/admin/audit/events/by-lead/")
                kw = _audit_query_params(query)
                result = admin_query_audit_by_lead(lead_id, identity, self.project_root, **kw)
            elif path.startswith("/api/admin/audit/events/"):
                event_id = path.removeprefix("/api/admin/audit/events/")
                result = admin_get_audit_event(event_id, identity, self.project_root)
            elif path.startswith("/api/knowledge/"):
                result = self._forward_to_knowledge_service("GET", path, parsed.query, identity, self.project_root)
            else:
                self._write_json({"error": "not_found"}, HTTPStatus.NOT_FOUND)
                return
            self._write_json(result, HTTPStatus.OK)
        except ValueError as exc:
            self._write_json({"error": str(exc)}, HTTPStatus.FORBIDDEN)
        except Exception as exc:
            self._write_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        query_str = self.path.split("?")[1] if "?" in self.path else ""
        query_identity = _identity_from_query(parse_qs(query_str))
        self._check_rate_limit(path, query_identity.get("user_id", ""))
        self._check_csrf(path)

        try:
            if path == "/wecom/callback/message":
                raw_xml = self._read_body_bytes().decode("utf-8")
                result = post_wecom_message_callback(
                    {k: v[0] for k, v in parse_qs(query_str).items()},
                    raw_xml,
                    self.project_root,
                )
                self._write_text(result, HTTPStatus.OK)
                return
            content_type = self.headers.get("Content-Type", "")
            if "multipart/form-data" in content_type:
                payload = self._read_multipart(content_type)
            else:
                payload = self._read_json()
            body_identity = {}
            if os.environ.get("GAOKAO_ENV", "development") != "production":
                body_identity = payload.pop("identity", {})
            identity = self._resolve_identity(query_identity, body_identity)

            if path == self._local_consumer_chat_route:
                self._require_loopback_client()
                result = post_chat(payload, self._localhost_consumer_identity(), self.project_root)
            elif path in self._chat_routes:
                if path == "/api/gaokao/chat":
                    result = post_chat(payload, identity, self.project_root)
                else:
                    result = post_handoff(payload, identity, self.project_root)
            elif path == "/api/campus/auth/wecom/state":
                result = issue_campus_wecom_state(payload, identity, self.project_root)
            elif path == "/api/campus/leaves":
                result = post_campus_leave(payload, identity, self.project_root)
            elif path.startswith("/api/campus/leaves/") and path.endswith("/approve"):
                leave_id = path.removeprefix("/api/campus/leaves/").removesuffix("/approve")
                result = approve_campus_leave(leave_id, payload, identity, self.project_root)
            elif path.startswith("/api/campus/leaves/") and path.endswith("/reject"):
                leave_id = path.removeprefix("/api/campus/leaves/").removesuffix("/reject")
                result = reject_campus_leave(leave_id, payload, identity, self.project_root)
            elif path == "/api/campus/meals/orders":
                result = post_campus_meal_order(payload, identity, self.project_root)
            elif path.startswith("/api/campus/meals/orders/") and path.endswith("/cancel"):
                order_id = path.removeprefix("/api/campus/meals/orders/").removesuffix("/cancel")
                result = cancel_campus_meal_order(order_id, payload, identity, self.project_root)
            elif path == "/api/meal-orders":
                result = post_mealbot_meal_order(payload, identity, self.project_root)
            elif path.startswith("/api/meal-orders/") and path.endswith("/cancel"):
                order_id = path.removeprefix("/api/meal-orders/").removesuffix("/cancel")
                result = post_mealbot_meal_order_cancel(order_id, payload, identity, self.project_root)
            elif path == "/api/meal-locks":
                result = post_mealbot_lock(payload, identity, self.project_root)
            elif path == "/api/vendor-confirmations":
                result = post_vendor_confirmation(payload, identity, self.project_root)
            elif path == "/api/vendor-confirmations/confirm":
                result = post_vendor_confirm_action(payload, identity, self.project_root)
            elif path == "/api/scheduler/run-due-reminders":
                result = post_scheduler_run_due_reminders(payload, identity, self.project_root)
            elif path == "/api/wecom/process-media-downloads":
                result = post_wecom_process_media_downloads(payload, identity, self.project_root)
            elif path == "/api/campus/materials/tasks":
                result = post_collection_task(payload, identity)
            elif path == "/api/campus/materials/submissions":
                result = post_material_submission(payload, identity)
            elif path.startswith("/api/campus/materials/tasks/") and path.endswith("/missing/remind"):
                task_id = path.removeprefix("/api/campus/materials/tasks/").removesuffix("/missing/remind")
                result = post_material_missing(task_id, payload, identity)
            elif path == "/api/campus/modules/leaves":
                result = post_module_leave(payload, identity)
            elif path.startswith("/api/campus/modules/leaves/") and path.endswith("/approve"):
                leave_id = path.removeprefix("/api/campus/modules/leaves/").removesuffix("/approve")
                result = post_module_leave_decision(leave_id, "approve", payload, identity)
            elif path.startswith("/api/campus/modules/leaves/") and path.endswith("/reject"):
                leave_id = path.removeprefix("/api/campus/modules/leaves/").removesuffix("/reject")
                result = post_module_leave_decision(leave_id, "reject", payload, identity)
            elif path.startswith("/api/campus/modules/leaves/") and path.endswith("/return"):
                leave_id = path.removeprefix("/api/campus/modules/leaves/").removesuffix("/return")
                result = post_module_leave_return(leave_id, payload, identity)
            elif path == "/api/campus/modules/leaves/process-overdue":
                result = post_overdue_returns(payload, identity)
            elif path == "/api/campus/scores/batches":
                result = post_score_batch(payload, identity)
            elif path.startswith("/api/campus/scores/batches/") and path.endswith("/confirm"):
                batch_id = path.removeprefix("/api/campus/scores/batches/").removesuffix("/confirm")
                result = post_score_confirm(batch_id, payload, identity)
            elif path.startswith("/api/campus/scores/batches/") and path.endswith("/rpa-dry-run"):
                batch_id = path.removeprefix("/api/campus/scores/batches/").removesuffix("/rpa-dry-run")
                result = post_score_rpa_dry_run(batch_id, payload, identity)
            elif path == "/api/campus/payments/tasks":
                result = post_payment_task(payload, identity)
            elif path == "/api/campus/payments/records":
                result = post_payment_record(payload, identity)
            elif path.startswith("/api/campus/payments/records/") and path.endswith("/confirm"):
                record_id = path.removeprefix("/api/campus/payments/records/").removesuffix("/confirm")
                result = post_payment_confirm(record_id, payload, identity)
            elif path.startswith("/api/campus/payments/tasks/") and path.endswith("/missing/remind"):
                task_id = path.removeprefix("/api/campus/payments/tasks/").removesuffix("/missing/remind")
                result = post_payment_missing(task_id, payload, identity)
            elif path == "/api/campus/attendance/sessions":
                result = post_attendance_session(payload, identity)
            elif path.startswith("/api/campus/attendance/sessions/") and path.endswith("/records"):
                session_id = path.removeprefix("/api/campus/attendance/sessions/").removesuffix("/records")
                result = post_attendance_records(session_id, payload, identity)
            elif path == "/api/campus/jobs/ocr/process":
                result = post_process_ocr(payload, identity)
            elif path == "/api/campus/modules/exports":
                result = post_module_export(payload, identity, self.project_root)
            elif path == "/api/pilot/control/pause":
                result = post_pilot_runtime_control("pause", payload, identity, self.project_root)
            elif path == "/api/pilot/control/resume":
                result = post_pilot_runtime_control("resume", payload, identity, self.project_root)
            elif path.startswith("/api/campus/meals/delivery/") and path.endswith("/confirm"):
                delivery_id = path.removeprefix("/api/campus/meals/delivery/").removesuffix("/confirm")
                result = confirm_campus_delivery(delivery_id, payload, identity, self.project_root)
            elif path == "/api/campus/repairs":
                result = post_campus_repair(payload, identity, self.project_root)
            elif path.startswith("/api/campus/repairs/") and path.endswith("/assign"):
                ticket_id = path.removeprefix("/api/campus/repairs/").removesuffix("/assign")
                result = assign_campus_repair(ticket_id, payload, identity, self.project_root)
            elif path.startswith("/api/campus/repairs/") and path.endswith("/complete"):
                ticket_id = path.removeprefix("/api/campus/repairs/").removesuffix("/complete")
                result = complete_campus_repair(ticket_id, payload, identity, self.project_root)
            elif path.startswith("/api/campus/repairs/") and path.endswith("/close"):
                ticket_id = path.removeprefix("/api/campus/repairs/").removesuffix("/close")
                result = close_campus_repair(ticket_id, payload, identity, self.project_root)

            elif path.startswith("/api/sales/sessions/") and path.endswith("/takeover"):
                session_id = path.removeprefix("/api/sales/sessions/").removesuffix("/takeover")
                result = takeover_session(session_id, identity, self.project_root)

            elif path.startswith("/api/sales/sessions/") and path.endswith("/followup"):
                session_id = path.removeprefix("/api/sales/sessions/").removesuffix("/followup")
                result = add_followup(session_id, payload, identity, self.project_root)

            elif path == "/api/crm/leads":
                result = create_crm_lead(payload, identity, self.project_root)

            elif path.startswith("/api/crm/leads/") and path.endswith("/followups"):
                lead_id = path.removeprefix("/api/crm/leads/").removesuffix("/followups")
                result = add_crm_lead_followup(lead_id, payload, identity, self.project_root)

            elif path.startswith("/api/crm/leads/") and path.endswith("/assign"):
                lead_id = path.removeprefix("/api/crm/leads/").removesuffix("/assign")
                result = assign_crm_lead(lead_id, payload, identity, self.project_root)

            elif path.startswith("/api/crm/leads/") and path.endswith("/status"):
                lead_id = path.removeprefix("/api/crm/leads/").removesuffix("/status")
                result = update_crm_lead_status(lead_id, payload, identity, self.project_root)

            elif path.startswith("/api/crm/leads/") and "/" not in path.removeprefix("/api/crm/leads/"):
                lead_id = path.removeprefix("/api/crm/leads/")
                result = patch_crm_lead(lead_id, payload, identity, self.project_root)

            elif path == "/api/admin/sources/upload":
                import uuid as _uuid
                raw = self._read_body_bytes()
                content_type = self.headers.get("Content-Type", "")
                filename = "upload.bin"
                if "filename=" in content_type:
                    m = __import__("re").search(r'filename="?([^";\n]+)"?', content_type)
                    if m:
                        filename = m.group(1)
                upload_dir = self.project_root / "data" / "ingestion" / _uuid.uuid4().hex
                upload_dir.mkdir(parents=True, exist_ok=True)
                file_path = upload_dir / filename
                file_path.write_bytes(raw)
                files = [{"path": str(file_path), "filename": filename}]
                result = admin_sources_upload(payload, files, identity, self.project_root)

            elif path == "/api/admin/ingestion/runs":
                result = admin_create_ingestion_run(payload, identity, self.project_root)
            elif path.startswith("/api/admin/ingestion/runs/") and path.endswith("/cancel"):
                result = self._dispatch_admin_legacy_mutation(path, identity, payload)
            elif path.startswith("/api/admin/staging/docs/") and path.endswith("/validate"):
                result = self._dispatch_admin_legacy_mutation(path, identity, payload)
            elif path.startswith("/api/admin/staging/docs/") and path.endswith("/approve"):
                result = self._dispatch_admin_legacy_mutation(path, identity, payload)
            elif path.startswith("/api/admin/staging/docs/") and path.endswith("/reject"):
                result = self._dispatch_admin_legacy_mutation(path, identity, payload)
            elif path.startswith("/api/admin/staging/docs/") and path.endswith("/publish"):
                result = self._dispatch_admin_legacy_mutation(path, identity, payload)

            elif path.startswith("/api/admin/staging/docs/") and path.endswith("/update"):
                staging_doc_id = path.removeprefix("/api/admin/staging/docs/").removesuffix("/update")
                result = admin_update_staging_doc(staging_doc_id, payload, identity, self.project_root)

            elif path == "/api/admin/graph/runs":
                result = admin_create_graph_run(payload, identity, self.project_root)

            elif path.startswith("/api/knowledge/"):
                result = self._forward_to_knowledge_service("POST", path, None, identity, self.project_root, payload)

            else:
                self._write_json({"error": "not_found"}, HTTPStatus.NOT_FOUND)
                return

            self._write_json(result, HTTPStatus.OK)
        except ValueError as exc:
            self._write_json({"error": str(exc)}, HTTPStatus.FORBIDDEN)
        except Exception as exc:
            self._write_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)

    def do_PATCH(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        query_identity = _identity_from_query(parse_qs(self.path.split("?")[1] if "?" in self.path else ""))
        self._check_rate_limit(path, query_identity.get("user_id", ""))
        self._check_csrf(path)

        try:
            payload = self._read_json()
            body_identity = {}
            if os.environ.get("GAOKAO_ENV", "development") != "production":
                body_identity = payload.pop("identity", {})
            identity = self._resolve_identity(query_identity, body_identity)

            if path.startswith("/api/admin/staging/docs/"):
                staging_doc_id = path.removeprefix("/api/admin/staging/docs/")
                result = admin_update_staging_doc(staging_doc_id, payload, identity, self.project_root)
                self._write_json(result, HTTPStatus.OK)
                return
        except ValueError as exc:
            self._write_json({"error": str(exc)}, HTTPStatus.FORBIDDEN)
            return
        except Exception as exc:
            self._write_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        self.do_POST()

    def _read_json(self) -> dict[str, object]:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8") if length else "{}"
        return json.loads(raw or "{}")

    def _read_body_bytes(self) -> bytes:
        length = int(self.headers.get("Content-Length", "0"))
        return self.rfile.read(length) if length else b""

    def _read_multipart(self, content_type: str) -> dict[str, object]:
        body = self._read_body_bytes()
        return parse_multipart(content_type, body)  # type: ignore[return-value]

    def _write_json(
        self,
        payload: dict[str, object],
        status: HTTPStatus,
        rate_limit_info: dict[str, object] | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status.value)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        if rate_limit_info:
            self.send_header("X-RateLimit-Limit", str(rate_limit_info.get("limit", "")))
            self.send_header("X-RateLimit-Window", str(rate_limit_info.get("window", "")))
            self.send_header("X-RateLimit-Category", str(rate_limit_info.get("category", "")))
        if extra_headers:
            for name, value in extra_headers.items():
                self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def _write_redirect(
        self,
        location: str,
        status: HTTPStatus,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        self.send_response(status.value)
        self.send_header("Location", location)
        if extra_headers:
            for name, value in extra_headers.items():
                self.send_header(name, value)
        self.end_headers()

    def _write_text(self, payload: str, status: HTTPStatus) -> None:
        body = payload.encode("utf-8")
        self.send_response(status.value)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _resolve_identity(self, query_identity: dict[str, str], body_identity: dict[str, str] | None = None) -> dict[str, object]:
        """Resolve authenticated identity with 0-trust source priority.
        Production: ONLY headers (x-gaokao-*) are trusted.
        Dev mode: headers > body > query (query/body are convenience fallbacks).
        Body-supplied identity is NEVER trusted in production.
        """
        raw_headers = {k.lower(): v for k, v in self.headers.items()}
        header_ids = _identity_from_headers(raw_headers)
        is_dev = os.environ.get("GAOKAO_ENV", "development") != "production"

        trust_error = validate_trusted_proxy(raw_headers)
        if trust_error:
            raise UntrustedProxyError(trust_error)

        merged: dict[str, object] = {
            "user_id": "anonymous",
            "role": "visitor",
            "campus": "all",
            "auth_level": "anonymous",
        }

        identity_keys = ("user_id", "role", "campus", "auth_level", "school_id", "student_id", "class_id", "wecom_userid")

        session_identity = _identity_from_campus_session_cookie(
            self.headers.get("Cookie", ""),
            self.project_root,
        )
        for key in identity_keys:
            if key in session_identity and session_identity[key]:
                merged[key] = session_identity[key]

        if is_dev:
            for key in identity_keys:
                if key in query_identity:
                    merged[key] = query_identity[key]
            if body_identity:
                for key in identity_keys:
                    if key in body_identity and body_identity[key]:
                        merged[key] = body_identity[key]

        for key in identity_keys:
            if key in header_ids and header_ids[key]:
                merged[key] = header_ids[key]

        return merged

    def _campus_session_cookie(self, session_id: str) -> str:
        host = self.headers.get("Host", "").split(":", 1)[0].lower()
        is_loopback = host in {"127.0.0.1", "localhost", "::1"}
        secure = not is_loopback and (
            self.headers.get("X-Forwarded-Proto", "").lower() == "https"
            or os.environ.get("APP_BASE_URL", "").startswith("https://")
        )
        parts = [
            f"campus_session={session_id}",
            "Path=/",
            "HttpOnly",
            "SameSite=Lax",
            "Max-Age=28800",
        ]
        if secure:
            parts.append("Secure")
        return "; ".join(parts)

    def _dispatch_admin_legacy_mutation(
        self,
        path: str,
        identity: dict[str, object],
        payload: dict[str, object] | None = None,
    ) -> dict[str, object]:
        payload = payload or {}
        if path.startswith("/api/admin/ingestion/runs/") and path.endswith("/cancel"):
            run_id = path.removeprefix("/api/admin/ingestion/runs/").removesuffix("/cancel")
            return admin_cancel_ingestion_run(run_id, identity, self.project_root)
        if path.startswith("/api/admin/staging/docs/") and path.endswith("/validate"):
            staging_doc_id = path.removeprefix("/api/admin/staging/docs/").removesuffix("/validate")
            return admin_validate_staging_doc(staging_doc_id, identity, self.project_root)
        if path.startswith("/api/admin/staging/docs/") and path.endswith("/approve"):
            staging_doc_id = path.removeprefix("/api/admin/staging/docs/").removesuffix("/approve")
            return admin_approve_staging_doc(staging_doc_id, identity, self.project_root)
        if path.startswith("/api/admin/staging/docs/") and path.endswith("/reject"):
            staging_doc_id = path.removeprefix("/api/admin/staging/docs/").removesuffix("/reject")
            return admin_reject_staging_doc(staging_doc_id, payload, identity, self.project_root)
        if path.startswith("/api/admin/staging/docs/") and path.endswith("/publish"):
            staging_doc_id = path.removeprefix("/api/admin/staging/docs/").removesuffix("/publish")
            return admin_publish_staging_doc(staging_doc_id, identity, self.project_root)
        raise ValueError("not_found")

    def _legacy_admin_alias_headers(self, path: str) -> dict[str, str]:
        return {
            "Deprecation": "true",
            "Sunset": ADMIN_LEGACY_MUTATION_SUNSET,
            "Link": f"<{path}>; rel=\"successor-version\"",
            "X-Gaokao-Legacy-Route": "state-changing-get",
        }

    def _record_legacy_admin_get_usage(self, route: str, successor: str) -> None:
        try:
            ua = self.headers.get("User-Agent", "")
            ua_hash = hashlib.sha256(ua.encode("utf-8", errors="replace")).hexdigest()[:16] if ua else ""
            referer = self.headers.get("Referer", "")
            referer_path = ""
            if referer:
                try:
                    from urllib.parse import urlparse as _urlparse
                    ref_parsed = _urlparse(referer)
                    referer_path = ref_parsed.path or ""
                except Exception:
                    referer_path = ""
            client_ip = self.headers.get("X-Forwarded-For", self.client_address[0])
            ip_hash = hashlib.sha256(client_ip.encode("utf-8")).hexdigest()[:16]
            from structured_logger import structured_log
            structured_log(
                self.project_root,
                "legacy_admin_get_mutation_used",
                action="legacy_admin_get_mutation_used",
                status="ok",
                details={
                    "route": route,
                    "successor": successor,
                    "request_id": getattr(self, "_request_id", ""),
                    "actor_role": "admin",
                    "user_agent_hash": f"sha256:{ua_hash}" if ua_hash else "",
                    "referer_path": referer_path,
                    "client_ip_hash": f"sha256:{ip_hash}",
                    "sunset": ADMIN_LEGACY_MUTATION_SUNSET,
                },
            )
        except Exception:
            pass

    def _check_rate_limit(self, path: str, user_id: str = "") -> None:
        ip = self.headers.get("X-Forwarded-For", self.client_address[0])
        allowed, info = check_rate_limit(ip, path, user_id)
        if not allowed:
            self.send_response(HTTPStatus.TOO_MANY_REQUESTS.value)
            self.send_header("Retry-After", str(info.get("window", "60")))
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            body = json.dumps({
                "error": "rate_limit_exceeded",
                "limit": info.get("limit"),
                "window": info.get("window"),
                "category": info.get("category"),
            }).encode("utf-8")
            self.wfile.write(body)
            try:
                from structured_logger import structured_log
                structured_log(
                    self.project_root, "rate_limit_exceeded",
                    user_id=user_id,
                    action="rate_limit",
                    status="blocked",
                    details={"path": path, "ip": ip, "category": str(info.get("category", ""))},
                )
            except Exception:
                pass
            raise ValueError("rate limit exceeded")

    def _check_csrf(self, path: str) -> None:
        if not is_admin_path(path):
            return
        raw_headers = {k.lower(): v for k, v in self.headers.items()}
        if not verify_csrf(raw_headers):
            self.send_response(HTTPStatus.FORBIDDEN.value)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            body = json.dumps({"error": "csrf_token_required"}).encode("utf-8")
            self.wfile.write(body)
            try:
                from structured_logger import structured_log
                structured_log(
                    self.project_root, "csrf_validation_failed",
                    action="csrf",
                    status="blocked",
                    details={"path": path},
                )
            except Exception:
                pass
            raise ValueError("csrf token required for admin mutation")

    def _require_loopback_client(self) -> None:
        host = str(self.client_address[0])
        if host not in {"127.0.0.1", "::1", "::ffff:127.0.0.1"}:
            raise ValueError("localhost_only")

    def _localhost_consumer_identity(self) -> dict[str, str]:
        return {
            "user_id": "localhost_consumer",
            "role": "customer",
            "campus": "all",
            "auth_level": "local_consumer",
        }

    def _forward_to_knowledge_service(
        self,
        method: str,
        path: str,
        query: dict[str, list[str]] | None,
        identity: dict[str, object],
        project_root: Path,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Proxy /api/knowledge/* to the knowledge-service with X-Identity-* headers.

        The campus_session cookie is NOT forwarded — only derived identity fields
        (school_id, role, user_id, auth_level) are injected as X-Identity-* headers.
        """
        host = os.environ.get("KNOWLEDGE_SERVICE_HOST", "localhost")
        port = int(os.environ.get("KNOWLEDGE_SERVICE_PORT", "8789"))
        # Strip /api/knowledge prefix to get the service path
        service_path = path.removeprefix("/api/knowledge")
        # Rebuild query string from parsed query dict
        qstr = ""
        if query:
            parts = []
            for k, vals in query.items():
                for v in vals:
                    parts.append(f"{quote(k, safe='')}={quote(v, safe='')}")
            qstr = "?" + "&".join(parts) if parts else ""

        target_path = service_path + qstr
        body_bytes: bytes | None = None
        if body is not None:
            body_bytes = json.dumps(body, ensure_ascii=False).encode("utf-8")

        conn = http.client.HTTPConnection(host, port, timeout=10)
        try:
            # ── Security: deny-list client-supplied identity headers ──
            # Gateway is the ONLY injection point for X-Identity-*. Any client-supplied
            # X-Identity-* or Cookie headers are stripped before forwarding.
            forwarded_headers: dict[str, str] = {
                "X-Forwarded-Path": path,
                "Content-Type": "application/json; charset=utf-8",
            }
            # Strip any client-supplied X-Identity-* or Cookie before injecting ours
            _strip_client_identity_headers(self.headers, forwarded_headers)
            forwarded_headers.update(_identity_headers_for_knowledge(identity))

            conn.request(method, target_path, body=body_bytes, headers=forwarded_headers)
            resp = conn.getresponse()
            resp_body = resp.read()
            if resp.status >= 400:
                return {"error": f"knowledge_service_error", "status": resp.status, "body": resp_body.decode("utf-8", errors="replace")}
            return json.loads(resp_body.decode("utf-8"))
        except OSError as exc:
            return {"error": f"knowledge_service_unavailable: {exc}"}
        except json.JSONDecodeError as exc:
            return {"error": f"knowledge_service_invalid_response: {exc}"}
        finally:
            conn.close()


def _identity_from_headers(headers: dict[str, str]) -> dict[str, str]:
    """Parse identity from trusted headers. Used for admin role attribution.
    Headers x-gaokao-user-id, x-gaokao-role, x-gaokao-campus are the trusted source.
    Body-supplied role/campus is ignored (0-trust principle).
    """
    identity: dict[str, str] = {}
    # Map header names to identity keys
    header_map = {
        "x-gaokao-user-id": "user_id",
        "x-gaokao-role": "role",
        "x-gaokao-campus": "campus",
        "x-gaokao-auth-level": "auth_level",
        "x-gaokao-school-id": "school_id",
        "x-gaokao-student-id": "student_id",
        "x-gaokao-class-id": "class_id",
        "x-gaokao-wecom-userid": "wecom_userid",
    }
    for header_name, identity_key in header_map.items():
        value = headers.get(header_name, "")
        if value:
            identity[identity_key] = value
    return identity


def _identity_from_campus_session_cookie(raw_cookie: str, project_root: Path) -> dict[str, object]:
    if not raw_cookie:
        return {}
    cookie = SimpleCookie()
    try:
        cookie.load(raw_cookie)
    except Exception:
        return {}
    morsel = cookie.get("campus_session")
    if not morsel:
        return {}
    return load_wecom_session_identity(project_root, morsel.value) or {}


def _identity_from_query(query: dict[str, list[str]]) -> dict[str, str]:
    return {
        "user_id": query.get("user_id", ["anonymous"])[0],
        "role": query.get("role", ["visitor"])[0],
        "campus": query.get("campus", ["all"])[0],
        "auth_level": query.get("auth_level", ["anonymous"])[0],
        "school_id": query.get("school_id", [""])[0],
        "student_id": query.get("student_id", [""])[0],
        "class_id": query.get("class_id", [""])[0],
        "wecom_userid": query.get("wecom_userid", [""])[0],
    }


# Identity fields forwarded to knowledge service via X-Identity-* headers.
# "source" is always set to "gateway" to mark the injection point.
_IDENTITY_FORWARD_KEYS = (
    "school_id",
    "role",
    "user_id",
    "auth_level",
    "display_name",
    "wecom_userid",
)


# Prefixes of headers that clients must never be able to influence.
_CLIENT_IDENTITY_DENY_PREFIXES = (
    "x-identity-",
    "cookie",
)


def _strip_client_identity_headers(
    request_headers: HTTPMessage,
    out: dict[str, str],
) -> None:
    """Strip client-supplied identity headers from the forwarded request.

    Iterates the raw request headers and copies everything EXCEPT headers
    matching the _CLIENT_IDENTITY_DENY_PREFIXES deny-list. This ensures the
    gateway is the sole injection point for X-Identity-* headers and prevents
    clients from spoofing identity by passing X-Identity-School-Id etc.

    Callers pass a mutable `out` dict so headers can be accumulated during iteration.
    """
    for name in request_headers:
        value = request_headers[name]
        name_lower = name.lower()
        for prefix in _CLIENT_IDENTITY_DENY_PREFIXES:
            if name_lower.startswith(prefix):
                break  # skip denied header
        else:
            out[name] = value


def _identity_headers_for_knowledge(identity: dict[str, object]) -> dict[str, str]:
    """Build X-Identity-* headers for knowledge-service forwarding.

    Explicitly denies client-supplied X-Identity-* and Cookie headers to prevent
    identity spoofing. Only server-side derived identity fields are passed.
    """
    headers: dict[str, str] = {
        "X-Identity-Source": "gateway",
    }
    for key in _IDENTITY_FORWARD_KEYS:
        val = identity.get(key, "")
        if val:
            headers[f"X-Identity-{key.replace('_', '-').title()}"] = str(val)
    return headers


def _audit_query_params(query: dict[str, list[str]]) -> dict[str, Any]:
    kw: dict[str, Any] = {}
    for k in ("event_type", "action", "status", "since", "until", "user_id", "role", "trace_id"):
        if k in query:
            kw[k] = query[k][0]
    for k in ("limit", "offset"):
        if k in query:
            try:
                kw[k] = int(query[k][0])
            except (ValueError, TypeError):
                pass
    return kw


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args()
    _load_env(args.root)
    GaokaoHandler.project_root = args.root
    server = ThreadingHTTPServer((args.host, args.port), GaokaoHandler)
    print(f"gaokao api listening on http://{args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
