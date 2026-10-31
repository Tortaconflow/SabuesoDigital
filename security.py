import re
import socket
import ipaddress
import urllib.parse
import time
import requests
from config import MAX_RESPONSE_SIZE_BYTES, REQUEST_TIMEOUT_SECONDS

BLOCKED_HOSTNAMES = {
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "::1",
    "[::1]",
    "metadata.google.internal",
    "instance-data",
}

def is_ip_private_or_restricted(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
        return (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        )
    except ValueError:
        return False

def validate_public_url(url: str) -> tuple[bool, str]:
    if not url or not isinstance(url, str):
        return False, "URL vacía o inválida"

    cleaned_url = url.strip()
    if not (cleaned_url.startswith("http://") or cleaned_url.startswith("https://")):
        return False, "Esquema no permitido (solo http y https)"

    try:
        parsed = urllib.parse.urlsplit(cleaned_url)
    except Exception as e:
        return False, f"URL malformada: {e}"

    host = parsed.hostname
    if not host:
        return False, "Host ausente en la URL"

    host_lower = host.lower().strip("[]")
    if host_lower in BLOCKED_HOSTNAMES or host_lower.endswith(".local") or host_lower.endswith(".internal"):
        return False, f"Destino restringido o local: {host_lower}"

    # Check if host is direct IP
    try:
        if is_ip_private_or_restricted(host_lower):
            return False, f"Dirección IP privada o restringida: {host_lower}"
    except Exception:
        pass

    # Resolve hostname via DNS
    try:
        addr_info = socket.getaddrinfo(host_lower, None, proto=socket.IPPROTO_TCP)
        for family, _, _, _, sockaddr in addr_info:
            ip_resolved = sockaddr[0]
            if is_ip_private_or_restricted(ip_resolved):
                return False, f"La resolución DNS resolvió a una IP interna protegida ({ip_resolved})"
    except socket.gaierror:
        return False, f"No se pudo resolver el nombre de host: {host_lower}"
    except Exception as e:
        return False, f"Error validando destino DNS: {e}"

    return True, "URL pública permitida"


def safe_http_get(
    url: str,
    timeout: int = REQUEST_TIMEOUT_SECONDS,
    max_size: int = MAX_RESPONSE_SIZE_BYTES,
    max_redirects: int = 3
) -> dict:
    result = {
        "ok": False,
        "status_code": 0,
        "text": "",
        "content_type": "",
        "final_url": url,
        "load_time_seconds": 0.0,
        "ssl_valid": True,
        "error": None,
        "size_bytes": 0
    }

    current_url = url
    redirect_count = 0
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-MX,es;q=0.9,en;q=0.8"
    }

    start_total_time = time.time()

    while redirect_count <= max_redirects:
        is_safe, reason = validate_public_url(current_url)
        if not is_safe:
            result["error"] = f"Seguridad SSRF: {reason}"
            return result

        try:
            req_start = time.time()
            response = requests.get(
                current_url,
                headers=headers,
                timeout=timeout,
                stream=True,
                allow_redirects=False,
                verify=True
            )
            req_duration = round(time.time() - req_start, 2)
            result["load_time_seconds"] += req_duration
        except requests.exceptions.SSLError:
            result["ssl_valid"] = False
            # Intentar conexión con verify=False solo para capturar si el sitio vive pero carece de SSL
            try:
                response = requests.get(
                    current_url,
                    headers=headers,
                    timeout=timeout,
                    stream=True,
                    allow_redirects=False,
                    verify=False
                )
            except Exception as e:
                result["error"] = f"Fallo SSL y conexión fallida: {e}"
                return result
        except requests.exceptions.Timeout:
            result["error"] = "Tiempo de espera agotado al conectar con el servidor"
            return result
        except requests.exceptions.ConnectionError as e:
            result["error"] = f"Error de conexión: {e}"
            return result
        except Exception as e:
            result["error"] = str(e)
            return result

        result["status_code"] = response.status_code
        result["content_type"] = response.headers.get("Content-Type", "").lower()

        # Handle Redirects
        if response.status_code in (301, 302, 303, 307, 308):
            location = response.headers.get("Location")
            if not location:
                break
            redirect_count += 1
            current_url = urllib.parse.urljoin(current_url, location)
            result["final_url"] = current_url
            continue

        # Non-redirect response: read content with size cap
        content_chunks = []
        bytes_read = 0
        try:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    bytes_read += len(chunk)
                    if bytes_read > max_size:
                        result["error"] = f"Respuesta excede límite de tamaño ({max_size} bytes)"
                        break
                    content_chunks.append(chunk)
        except Exception as e:
            result["error"] = f"Error leyendo contenido: {e}"
            return result

        raw_bytes = b"".join(content_chunks)
        result["size_bytes"] = len(raw_bytes)

        # Detect encoding safely
        encoding = response.encoding or response.apparent_encoding or "utf-8"
        try:
            result["text"] = raw_bytes.decode(encoding, errors="replace")
        except Exception:
            result["text"] = raw_bytes.decode("utf-8", errors="replace")

        result["ok"] = (200 <= response.status_code < 400)
        break

    result["total_time_seconds"] = round(time.time() - start_total_time, 2)
    return result
