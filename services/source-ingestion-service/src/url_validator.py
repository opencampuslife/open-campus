from __future__ import annotations

import ipaddress
import os
import re
import socket
from typing import Any
from urllib.parse import urlparse

ALLOWED_DOMAINS: list[str] = []
BLOCKED_SCHEMES = {"file", "ftp", "gopher", "javascript", "data", "vbscript", "jar", "ldap", "ldaps", "dict"}
MAX_REDIRECTS = 3


def _is_private_ip(host: str) -> bool:
    host_clean = host.strip("[]")
    try:
        addr = ipaddress.ip_address(host_clean)
    except ValueError:
        return False
    return addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_multicast or addr.is_unspecified


def _resolve_dns(hostname: str) -> list[str]:
    if not hostname:
        return []
    hostname = hostname.strip("[]")
    try:
        _, _, ips = socket.gethostbyname_ex(hostname)
        return ips
    except Exception:
        return []


def _is_safe_host(hostname: str) -> bool:
    if not hostname:
        return False
    hostname = hostname.strip("[]")
    try:
        ipaddress.ip_address(hostname)
        return not _is_private_ip(hostname)
    except ValueError:
        pass
    for ip in _resolve_dns(hostname):
        if _is_private_ip(ip):
            return False
    return True


def validate_url(url: str, timeout: int = 5) -> dict[str, Any]:
    result: dict[str, Any] = {
        "valid": False,
        "normalized_url": "",
        "warnings": [],
        "ssrf_blocked": False,
    }

    remote_enabled = os.environ.get("ENABLE_REMOTE_URL_INGESTION", "0") == "1"
    if not remote_enabled:
        result["warnings"].append("remote URL ingestion is disabled (ENABLE_REMOTE_URL_INGESTION=0)")
        result["ssrf_blocked"] = True
        return result

    try:
        url_stripped = url.strip()
        if not url_stripped:
            result["warnings"].append("empty URL")
            return result

        parsed = urlparse(url_stripped)

        if parsed.scheme.lower() in BLOCKED_SCHEMES:
            result["warnings"].append("blocked scheme: {}".format(parsed.scheme))
            result["ssrf_blocked"] = True
            return result

        if parsed.scheme not in ("http", "https"):
            if not parsed.scheme:
                parsed = urlparse("https://" + url_stripped)
            else:
                result["warnings"].append("unsupported scheme: {}".format(parsed.scheme))
                result["ssrf_blocked"] = True
                return result

        hostname = parsed.hostname or ""
        if not hostname:
            result["warnings"].append("URL has no hostname")
            return result

        if not _is_safe_host(hostname):
            result["warnings"].append("host resolves to private/internal IP: {}".format(hostname))
            result["ssrf_blocked"] = True
            return result

        if hostname in ("localhost", "0.0.0.0", "127.0.0.1", "::1"):
            result["warnings"].append("blocked hostname: {}".format(hostname))
            result["ssrf_blocked"] = True
            return result

        if not re.match(r"^[a-zA-Z0-9.\-:\[\]]+$", hostname):
            result["warnings"].append("hostname contains disallowed characters: {}".format(hostname))
            result["ssrf_blocked"] = True
            return result

        normalized = "{}://{}{}".format(
            parsed.scheme,
            hostname,
            parsed.path.rstrip("/") or "/",
        )
        if parsed.query:
            normalized += "?" + parsed.query

        result["normalized_url"] = normalized

        if ALLOWED_DOMAINS:
            domain = hostname.lower()
            if not any(domain == d or domain.endswith("." + d) for d in ALLOWED_DOMAINS):
                result["warnings"].append("domain '{}' is not in the allowed domains list".format(domain))

        result["valid"] = True

    except Exception as exc:
        result["warnings"].append("URL validation error: {}".format(str(exc)))

    return result


def fetch_url_content(url: str, timeout: int = 10) -> dict[str, Any]:
    result: dict[str, Any] = {
        "ok": False,
        "content": b"",
        "content_type": "",
        "status_code": 0,
        "error": "",
    }

    validation = validate_url(url, timeout=timeout)
    if not validation["valid"] or validation.get("ssrf_blocked"):
        result["error"] = "URL failed SSRF validation: {}".format(validation.get("warnings", []))
        return result

    import urllib.request

    safe_url = validation["normalized_url"]

    class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    class _SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
        max_redirects = MAX_REDIRECTS

        def redirect_request(self, req, fp, code, msg, headers, newurl):
            if not hasattr(self, "_redirect_count"):
                self._redirect_count = 0
            self._redirect_count += 1
            if self._redirect_count > self.max_redirects:
                raise urllib.request.HTTPError(req.full_url, code, "too many redirects", headers, fp)
            new_parsed = urlparse(newurl)
            new_hostname = new_parsed.hostname or ""
            if not _is_safe_host(new_hostname):
                raise urllib.request.HTTPError(req.full_url, code, "redirect to unsafe host", headers, fp)
            return urllib.request.HTTPRedirectHandler.redirect_request(self, req, fp, code, msg, headers, newurl)

    try:
        req = urllib.request.Request(safe_url, method="GET")
        req.add_header("User-Agent", "GaokaoAgent/1.0 IngestionBot")
        opener = urllib.request.build_opener(_SafeRedirectHandler())
        resp = opener.open(req, timeout=timeout)
        result["ok"] = True
        result["content"] = resp.read()
        result["content_type"] = resp.headers.get("Content-Type", "")
        result["status_code"] = resp.getcode()
    except urllib.request.HTTPError as exc:
        result["error"] = "HTTP {} fetching URL: {}".format(exc.code, str(exc))
    except Exception as exc:
        result["error"] = "fetch error: {}".format(str(exc))

    return result
