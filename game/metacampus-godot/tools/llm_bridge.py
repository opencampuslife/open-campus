#!/usr/bin/env python3
"""LLM Bridge — DeepSeek 对话桥接服务
为 Godot 游戏提供多轮对话能力。
监听 http://127.0.0.1:8787

API:
  POST /chat  {"query": "...", "session_id": "..."}
  GET  /health
  POST /reset {"session_id": "..."}
"""

import json
import sys
import ssl
import time
import uuid
import urllib.request
import urllib.error
import urllib.parse
import os
import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Lock

# SSL workaround
ssl_ctx = ssl._create_unverified_context()

# ── Config ──
API_KEY = "sk-dd31144ac16e4986a4c6b33ec9712541"
BASE_URL = "https://api.deepseek.com/v1"
MODEL = "deepseek-v4-pro"
PORT = 8788

# ── System Prompt ──
SYSTEM_PROMPT = """你是 MetaCampus 校园 AI 助手"小智"。
你的职责是帮助学校老师处理校园事务，提供准确、合规的信息。

## 核心原则
1. 回答必须引用可查证的政策或知识库来源
2. 绝对不承诺"保证录取""内部名额""一定能上"等
3. 遇到招生录取承诺类问题，必须明确表示"需要转人工招生老师确认"
4. 涉及学生隐私、成绩等敏感信息，不直接回答

## 回答格式
请用友好的语气回答，并在回答末尾列出信息来源（如有）。
如果问题超出你能回答的范围，请说明需要人工处理。

## 示例
问：报名需要哪些材料？
答：通常需要：1) 学生身份证明 2) 户口本 3) 学籍信息表 4) 近期照片。具体以当年招生简章为准。
来源：招生咨询 FAQ (admission_faq_2026)

问：能不能保证我家孩子录取？
答：我不能承诺录取结果。录取由招生委员会根据统一标准决定。建议联系招生办老师确认。
需要转人工处理。
"""

# ── Session Store ──
sessions = {}
sessions_lock = Lock()

# ── Bench log path (lazy init) ──
_bench_log_path = None

def get_or_create_session(session_id: str) -> list:
    with sessions_lock:
        if session_id not in sessions:
            sessions[session_id] = [
                {"role": "system", "content": SYSTEM_PROMPT}
            ]
        return sessions[session_id]

def call_deepseek(messages: list) -> dict:
    """Call DeepSeek chat completions API"""
    url = f"{BASE_URL}/chat/completions"
    body = json.dumps({
        "model": MODEL,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 512,
        "stream": False
    }).encode("utf-8")

    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {API_KEY}")

    try:
        with urllib.request.urlopen(req, timeout=30, context=ssl_ctx) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            choice = data.get("choices", [{}])[0]
            msg = choice.get("message", {})
            return {
                "ok": True,
                "answer": msg.get("content", ""),
                "role": msg.get("role", "assistant"),
                "model": data.get("model", MODEL),
                "usage": data.get("usage", {})
            }
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        return {
            "ok": False,
            "error": f"HTTP {e.code}: {err_body[:200]}"
        }
    except Exception as e:
        return {
            "ok": False,
            "error": str(e)[:200]
        }


class LLMBridgeHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/health" or path.endswith("/health"):
            self._json(200, {"status": "ok", "sessions": len(sessions)})
        else:
            self._json(404, {"error": "not found", "path": path})

    def do_POST(self):
        path = self.path.split("?")[0]
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8") if length else "{}"
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self._json(400, {"error": "invalid json"})
            return

        if path == "/chat" or path.endswith("/chat"):
            # ── Bench mode detection ──
            bench = self._is_bench_mode()
            if bench:
                t0 = time.time()

            query = data.get("query", "").strip()
            session_id = data.get("session_id", "default")

            if not query:
                self._json(400, {"error": "query is required"})
                return

            # Get session history
            messages = get_or_create_session(session_id)
            messages.append({"role": "user", "content": query})

            if bench:
                t1 = time.time()

            # Call DeepSeek
            result = call_deepseek(messages)

            if bench:
                t2 = time.time()

            if result.get("ok"):
                # Append assistant response to history
                messages.append({
                    "role": "assistant",
                    "content": result["answer"]
                })

            result["session_id"] = session_id
            result["turn"] = (len(messages) - 1) // 2

            # ── Bench: attach timing & write response with timing ──
            if bench:
                timing = {
                    "bridge_receive_ms": int(t0 * 1000),
                    "bridge_process_ms": int((t1 - t0) * 1000),
                    "provider_latency_ms": int((t2 - t1) * 1000),
                    "bridge_response_ms": 0,
                }
                result["_timing"] = timing

                code = 200 if result.get("ok") else 502
                resp_body = json.dumps(result, ensure_ascii=False).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", len(resp_body))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(resp_body)

                t3 = time.time()
                timing["bridge_response_ms"] = int((t3 - t2) * 1000)
                self._log_timing(timing, result, session_id)
            else:
                self._json(200 if result.get("ok") else 502, result)

        elif path == "/reset" or path.endswith("/reset"):
            session_id = data.get("session_id", "default")
            with sessions_lock:
                if session_id in sessions:
                    del sessions[session_id]
            self._json(200, {"status": "ok", "session_id": session_id})

        else:
            self._json(404, {"error": "not found"})

    def _json(self, code: int, data: dict):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    # ── Bench helpers ──

    def _is_bench_mode(self) -> bool:
        """Check if bench mode is activated via X-Bench header or ?bench=1 query."""
        if self.headers.get("X-Bench", "") == "1":
            return True
        if "?" in self.path:
            params = urllib.parse.parse_qs(self.path.split("?", 1)[1])
            return "bench" in params and params["bench"][0] == "1"
        return False

    def _log_timing(self, timing: dict, result: dict, session_id: str):
        global _bench_log_path
        now = datetime.datetime.utcnow()
        ts = now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"
        entry = {
            "type": "bench",
            "ts": ts,
            "session_id": session_id,
            "turn": result.get("turn"),
            "ok": result.get("ok", False),
            "_timing": timing,
        }
        line = json.dumps(entry, ensure_ascii=False) + "\n"
        sys.stdout.write(line)
        sys.stdout.flush()
        # Lazy-init log file
        if _bench_log_path is None:
            log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
            os.makedirs(log_dir, exist_ok=True)
            _bench_log_path = os.path.join(log_dir, f"llm_bridge_bench_{time.strftime('%Y%m%d')}.log")
        with open(_bench_log_path, "a") as f:
            f.write(line)

    def log_message(self, format, *args):
        # Quiet logging
        pass


if __name__ == "__main__":
    server = HTTPServer(("127.0.0.1", PORT), LLMBridgeHandler)
    print(f"[LLM Bridge] DeepSeek {MODEL} — listening on http://127.0.0.1:{PORT}")
    print(f"[LLM Bridge] Endpoints: POST /chat  GET /health  POST /reset")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[LLM Bridge] Shutting down")
        server.shutdown()
