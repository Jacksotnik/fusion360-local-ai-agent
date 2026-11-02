"""Small Ollama client: chat (cancellable from another thread), version, tags, show, ps."""
import http.client
import json
import os
import socket
import threading
import urllib.parse

DEFAULT_PORT = 11434


class OllamaError(Exception):
    """Ollama answered with an error (unknown model, bad request, out of memory...)."""


class OllamaUnavailable(OllamaError):
    """Ollama did not answer at all."""


class OllamaCancelled(OllamaError):
    """The chat request was cancelled by cancel()."""


def base_url_from_env():
    """The Ollama address, honouring OLLAMA_HOST like the ollama CLI does (e.g. '0.0.0.0', 'host:port')."""
    host = os.environ.get("OLLAMA_HOST", "").strip()
    if not host:
        return "http://127.0.0.1:%d" % DEFAULT_PORT
    if "://" not in host:
        host = "http://" + host
    parsed = urllib.parse.urlparse(host)
    hostname = parsed.hostname or "127.0.0.1"
    if hostname in ("0.0.0.0", "::"):
        hostname = "127.0.0.1"
    port = parsed.port or DEFAULT_PORT
    return "%s://%s:%d" % (parsed.scheme or "http", hostname, port)


class Ollama:
    def __init__(self, base_url=None):
        self.base_url = base_url or base_url_from_env()
        parsed = urllib.parse.urlparse(self.base_url)
        self.host = parsed.hostname
        self.port = parsed.port or DEFAULT_PORT
        self.is_https = parsed.scheme == "https"
        self._lock = threading.Lock()
        self._active_connection = None

    def _connection(self, timeout_sec):
        if self.is_https:
            return http.client.HTTPSConnection(self.host, self.port, timeout=timeout_sec)
        return http.client.HTTPConnection(self.host, self.port, timeout=timeout_sec)

    def _request(self, method, path, body=None, timeout_sec=10, cancel_event=None):
        """One HTTP request. With cancel_event, cancel() can stop it from another thread."""
        connection = self._connection(timeout_sec)
        if cancel_event is not None:
            with self._lock:
                self._active_connection = connection
            if cancel_event.is_set():
                self._forget(connection)
                raise OllamaCancelled("cancelled")
        try:
            data = json.dumps(body).encode("utf-8") if body is not None else None
            headers = {"Content-Type": "application/json"} if data is not None else {}
            connection.request(method, path, body=data, headers=headers)
            response = connection.getresponse()
            raw = response.read().decode("utf-8", errors="replace")
            status = response.status
        except (OSError, http.client.HTTPException) as error:
            if cancel_event is not None and cancel_event.is_set():
                raise OllamaCancelled("cancelled") from None
            raise OllamaUnavailable("Ollama at %s did not answer: %s" % (self.base_url, error)) from None
        finally:
            self._forget(connection)

        if cancel_event is not None and cancel_event.is_set():
            raise OllamaCancelled("cancelled")
        try:
            parsed = json.loads(raw) if raw.strip() else {}
        except ValueError:
            parsed = {"error": raw.strip()[:300]}
        if status >= 400:
            message = parsed.get("error") if isinstance(parsed, dict) else None
            raise OllamaError(message or "HTTP %d" % status)
        return parsed

    def _forget(self, connection):
        with self._lock:
            if self._active_connection is connection:
                self._active_connection = None
        connection.close()

    def cancel(self):
        """Stop the request in flight (the caller sets its cancel_event first): closing the connection
        makes Ollama stop generating."""
        with self._lock:
            connection = self._active_connection
        if connection is not None and connection.sock is not None:
            try:
                connection.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

    def chat(self, body, cancel_event=None, timeout_sec=900):
        return self._request("POST", "/api/chat", body, timeout_sec=timeout_sec, cancel_event=cancel_event)

    def version(self, timeout_sec=3):
        return self._request("GET", "/api/version", timeout_sec=timeout_sec).get("version", "")

    def tags(self):
        """Installed models: a list of dicts with name, size, details."""
        return self._request("GET", "/api/tags").get("models", [])

    def show(self, model):
        return self._request("POST", "/api/show", {"model": model})

    def ps(self):
        """Loaded models: a list of dicts with name, size, size_vram."""
        return self._request("GET", "/api/ps").get("models", [])


def capabilities(show_reply):
    """Capability names from an /api/show reply, e.g. ['completion', 'tools', 'vision', 'thinking']."""
    found = show_reply.get("capabilities") if isinstance(show_reply, dict) else None
    if not isinstance(found, list):
        return []
    return [str(name) for name in found]
