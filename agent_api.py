from __future__ import annotations

import hmac
import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from agents.analista_perfilamiento import analyze_profile
from make_service import load_local_env
from vivi_agent_service import request_agent_reply


load_local_env()
HOST = os.getenv("VIVI_AGENT_HOST", "127.0.0.1")
PORT = int(os.getenv("VIVI_AGENT_PORT", "8000"))


def _valid_request(payload: Any) -> bool:
    return (
        isinstance(payload, dict)
        and isinstance(payload.get("lead_id"), str)
        and 0 < len(payload["lead_id"]) <= 100
        and isinstance(payload.get("message"), str)
        and 0 < len(payload["message"]) <= 3000
        and len(str(payload.get("history") or "")) <= 12000
    )


def _valid_profile_request(payload: Any) -> bool:
    """Validate the payload for the /v1/profile (Agent 2) endpoint."""
    return (
        isinstance(payload, dict)
        and isinstance(payload.get("lead_id"), str)
        and 0 < len(payload["lead_id"]) <= 100
        and isinstance(payload.get("project_origin"), str)
        and 0 < len(payload["project_origin"]) <= 200
        and isinstance(payload.get("campaign_id"), str)
        and 0 < len(payload["campaign_id"]) <= 100
        and len(str(payload.get("history") or "")) <= 20000
    )


class AgentHandler(BaseHTTPRequestHandler):
    server_version = "VIVIAgent/1.0"

    def _json_response(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self) -> bool:
        expected = os.getenv("VIVI_AGENT_API_KEY", "").strip()
        supplied = self.headers.get("x-vivi-api-key", "")
        return not expected or hmac.compare_digest(expected, supplied)

    def _parse_payload(self) -> dict[str, Any]:
        """Read and parse the request body."""
        size = int(self.headers.get("Content-Length", "0"))
        if size <= 0 or size > 50_000:
            raise ValueError("Tamaño de solicitud inválido.")
        return json.loads(self.rfile.read(size).decode("utf-8"))

    def do_GET(self) -> None:
        if self.path.rstrip("/") == "/health":
            self._json_response(
                HTTPStatus.OK,
                {"status": "ok", "service": "VIVI Agent API"},
            )
            return
        self._json_response(HTTPStatus.NOT_FOUND, {"detail": "Ruta no encontrada."})

    def do_POST(self) -> None:
        path = self.path.rstrip("/")

        if path == "/v1/chat":
            self._handle_chat()
        elif path == "/v1/profile":
            self._handle_profile()
        else:
            self._json_response(
                HTTPStatus.NOT_FOUND,
                {"detail": "Ruta no encontrada."},
            )

    def _handle_chat(self) -> None:
        """Agent 1: Conversational endpoint."""
        if not self._authorized():
            self._json_response(
                HTTPStatus.UNAUTHORIZED,
                {"detail": "API key inválida."},
            )
            return
        try:
            payload = self._parse_payload()
            if not _valid_request(payload):
                raise ValueError("lead_id o message inválidos.")
            result = request_agent_reply(payload)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
            self._json_response(
                HTTPStatus.BAD_REQUEST,
                {"detail": str(error)},
            )
            return
        except RuntimeError as error:
            self._json_response(
                HTTPStatus.BAD_GATEWAY,
                {"detail": str(error)},
            )
            return
        self._json_response(HTTPStatus.OK, result)

    def _handle_profile(self) -> None:
        """Agent 2: Profile analysis (structured extraction + scoring + persistence)."""
        if not self._authorized():
            self._json_response(
                HTTPStatus.UNAUTHORIZED,
                {"detail": "API key inválida."},
            )
            return
        try:
            payload = self._parse_payload()
            if not _valid_profile_request(payload):
                raise ValueError(
                    "lead_id, project_origin y campaign_id son obligatorios."
                )
            result = analyze_profile(
                lead_id=payload["lead_id"],
                channel=payload.get("channel", "api"),
                customer_name=payload.get("customer_name"),
                project_origin=payload["project_origin"],
                campaign_id=payload["campaign_id"],
                history=payload.get("history", ""),
                profile=payload.get("profile", payload.get("profile_json", {})),
                force=str(payload.get("force", "")).lower() in ("true", "1"),
                timeout=float(payload.get("timeout", 25.0)),
            )
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
            self._json_response(
                HTTPStatus.BAD_REQUEST,
                {"detail": str(error)},
            )
            return
        except RuntimeError as error:
            self._json_response(
                HTTPStatus.BAD_GATEWAY,
                {"detail": str(error)},
            )
            return
        self._json_response(HTTPStatus.OK, result)

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[VIVI API] {self.address_string()} - {format % args}")


def run() -> None:
    server = ThreadingHTTPServer((HOST, PORT), AgentHandler)
    print(f"VIVI Agent API escuchando en http://{HOST}:{PORT}")
    print(f"  Agent 1 (chat):    POST /v1/chat")
    print(f"  Agent 2 (profile): POST /v1/profile")
    print(f"  Health:            GET  /health")
    server.serve_forever()


if __name__ == "__main__":
    run()
