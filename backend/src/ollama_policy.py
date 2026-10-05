"""PhotoRAG's per-request Ollama policy; never changes server preferences."""

import ipaddress
import os
from contextlib import contextmanager
from dataclasses import dataclass
from urllib.parse import urlsplit

DEFAULT_URL = 'http://localhost:11434'
INFERENCE_TIMEOUT = 120.0
OCR_INFERENCE_TIMEOUT = 300.0
IMAGE_ROLES = frozenset({'vision', 'ocr', 'clip'})


def timeout_for_role(role):
    """Return a bounded per-inference deadline; OCR gets more reading time."""
    return OCR_INFERENCE_TIMEOUT if role == 'ocr' else INFERENCE_TIMEOUT


def is_local_ollama(base_url):
    host = urlsplit(base_url or DEFAULT_URL).hostname
    if host == 'localhost':
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except (ValueError, TypeError):
        return False


def _host_memory_gib():
    try:
        import psutil

        return psutil.virtual_memory().total / (1024**3)
    except ImportError:
        import sys

        if sys.platform == 'win32':
            try:
                import ctypes

                class MemoryStatusEx(ctypes.Structure):
                    _fields_ = [
                        ('dwLength', ctypes.c_uint32),
                        ('dwMemoryLoad', ctypes.c_uint32),
                        ('ullTotalPhys', ctypes.c_uint64),
                        ('ullAvailPhys', ctypes.c_uint64),
                        ('ullTotalPageFile', ctypes.c_uint64),
                        ('ullAvailPageFile', ctypes.c_uint64),
                        ('ullTotalVirtual', ctypes.c_uint64),
                        ('ullAvailVirtual', ctypes.c_uint64),
                        ('ullAvailExtendedVirtual', ctypes.c_uint64),
                    ]

                status = MemoryStatusEx()
                status.dwLength = ctypes.sizeof(status)
                if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                    return status.ullTotalPhys / (1024**3)
            except (AttributeError, OSError):
                return None
        try:
            return os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES') / (1024**3)
        except (ValueError, OSError, AttributeError):
            return None


def _show(base_url, model_name):
    return _request(f'{(base_url or DEFAULT_URL).rstrip("/")}/api/show', {'model': model_name}, 5)


@dataclass(frozen=True)
class OllamaPolicy:
    effective_num_ctx: int
    reason: str
    vision_capable: bool | None
    capacity_known: bool
    native_num_ctx: int | None = None
    local: bool = False
    reason_code: str = 'remote_capacity_unverified'
    host_memory_gib: float | None = None

    def require_vision(self):
        if self.vision_capable is False:
            raise ValueError('Selected Ollama model does not support vision; choose an image-capable model.')


def resolve_ollama_policy(base_url, model_name, role, workload_roles=None):
    """Choose one bounded context for all configured roles using this model.

    Role budgets describe request shape, host RAM and native model metadata cap
    that budget. They do not claim that model weights will fit in available RAM.
    """
    local = is_local_ollama(base_url)
    try:
        metadata = _show(base_url, model_name)
    except Exception:
        metadata = {}
    if not isinstance(metadata, dict):
        metadata = {}
    capabilities = metadata.get('capabilities')
    vision = ('vision' in capabilities) if isinstance(capabilities, list) else None
    info = metadata.get('model_info') or {}
    limits = (
        [
            value
            for key, value in info.items()
            if key.endswith('.context_length') and isinstance(value, int) and not isinstance(value, bool) and value > 0
        ]
        if isinstance(info, dict)
        else []
    )
    limit = min(limits) if limits else None
    memory = _host_memory_gib() if local else None
    known = memory is not None and limit is not None
    roles = set(workload_roles or ())
    roles.add(role)
    image_workload = bool(roles & IMAGE_ROLES)
    if image_workload:
        budget = 16384
        budget_name = 'image-processing'
    else:
        role_budgets = {'chat': 8192, 'translator': 8192, 'embedding': 4096}
        budget = max((role_budgets.get(item, 4096) for item in roles), default=4096)
        budget_name = 'text-processing'

    # Image workloads can use 8k on 8 GiB and 16k on 16 GiB hosts. Text
    # workloads stay at 4k below 16 GiB. Remote RAM is not measurable locally.
    if image_workload:
        ceiling = (
            16384
            if local and memory is not None and memory >= 16
            else 8192
            if local and memory is not None and memory >= 8
            else 4096
        )
    else:
        ceiling = 8192 if local and memory is not None and memory >= 16 else 4096
    effective = min(budget, ceiling, limit or 4096)
    if not local:
        reason_code = 'remote_capacity_unverified'
        reason = (
            f'Remote host capacity is not measurable; {effective} tokens is the conservative {budget_name} context.'
        )
    elif memory is None:
        reason_code = 'host_memory_unavailable'
        reason = f'Host memory is unavailable; {effective} tokens is the conservative {budget_name} context.'
    elif limit is None:
        reason_code = 'model_context_unavailable'
        reason = f'Model native context is unavailable; {effective} tokens is the conservative {budget_name} context.'
    else:
        reason_code = 'capacity_bounded'
        reason = f'{effective} tokens selected for {budget_name}; host RAM {memory:.1f} GiB, model native limit {limit}. Model fit is not guaranteed.'
    if vision is None:
        reason += ' Vision compatibility unverified.'
    return OllamaPolicy(effective, reason, vision, known, limit, local, reason_code, memory)


def _normalized_endpoint(url):
    return (url or DEFAULT_URL).rstrip('/')


def configured_model_roles(base_url, model_name, fallback_role):
    """Read roles sharing this Ollama model/server; fall back safely without DB access."""
    roles = {fallback_role}
    endpoint = _normalized_endpoint(base_url)
    try:
        from src.db.database import SessionLocal
        from src.models import AIModelConfig

        with SessionLocal() as db:
            configs = (
                db.query(
                    AIModelConfig.type,
                    AIModelConfig.mode,
                    AIModelConfig.model_provider,
                    AIModelConfig.model_name,
                    AIModelConfig.url,
                )
                .filter_by(mode='remote', model_provider='ollama', model_name=model_name)
                .all()
            )
        for cfg in configs:
            if (
                cfg.mode == 'remote'
                and cfg.model_provider == 'ollama'
                and cfg.model_name == model_name
                and _normalized_endpoint(cfg.url) == endpoint
            ):
                roles.add(cfg.type)
    except Exception:
        # Keep inference bounded if the database is unavailable during startup or migration.
        pass
    return sorted(roles)


# Each synchronous caller owns an event loop only inside its inference thread.
# Cancellation closes the HTTP connection before releasing the OS-backed gate.
def _request(url, payload, timeout):
    import asyncio

    import httpx

    async def send():
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, json=payload)
            if response.is_error:
                # Never echo server response bodies: they may contain prompts/URLs.
                body = response.text.lower()
                kind = (
                    'context overflow'
                    if 'context' in body
                    else 'insufficient memory'
                    if 'memory' in body
                    else 'runner failure'
                )
                raise RuntimeError(
                    f'Ollama {kind} (HTTP {response.status_code}); check model compatibility and resources.'
                )
            result = response.json()
            if result.get('error'):
                raise RuntimeError('Ollama runner failure; check the selected model and available memory.')
            return result

    async def bounded():
        return await asyncio.wait_for(send(), timeout=timeout)

    try:
        return asyncio.run(bounded())
    except (httpx.TimeoutException, TimeoutError) as exc:
        raise TimeoutError('Ollama request deadline exceeded') from exc


class OllamaClient:
    """Small LangChain-compatible sync adapter with explicit Ollama request policy."""

    def __init__(self, base_url, model_name, role):
        self.base_url = (base_url or DEFAULT_URL).rstrip('/')
        self.model_name = model_name
        self.role = role
        self._started = None
        roles = configured_model_roles(base_url, model_name, role)
        self.policy = resolve_ollama_policy(base_url, model_name, role, workload_roles=roles)
        if role in IMAGE_ROLES:
            self.policy.require_vision()

    def _call(self, endpoint, payload, validate):
        import time

        from loguru import logger

        started = time.monotonic()
        if self._started is None:
            self._started = started
        error_class = 'none'
        try:
            deadline = timeout_for_role(self.role)
            remaining = deadline - (time.monotonic() - self._started)
            if remaining <= 0:
                raise TimeoutError("Ollama inference deadline exceeded")
            with local_inference_gate(self.base_url, remaining):
                remaining = deadline - (time.monotonic() - self._started)
                if remaining <= 0:
                    raise TimeoutError('Ollama inference queue deadline exceeded')
                result = _request(
                    self.base_url + endpoint,
                    {'model': self.model_name, 'options': {'num_ctx': self.policy.effective_num_ctx}, **payload},
                    remaining,
                )
                return validate(result)
        except Exception as exc:
            error_class = type(exc).__name__
            raise
        finally:
            from src.pipeline_tracker import _inference_ids

            ids = _inference_ids.get()
            logger.info(
                'Ollama photo_id={} run_id={} task_id={} model={} effective_context={} role={} duration={:.3f} error_class={}',
                ids.get('photo_id'),
                ids.get('run_id'),
                ids.get('task_id'),
                self.model_name,
                self.policy.effective_num_ctx,
                self.role,
                time.monotonic() - started,
                error_class,
            )

    def invoke(self, messages):
        from langchain_core.messages import AIMessage

        converted = []
        for message in messages:
            role = {'human': 'user', 'ai': 'assistant'}.get(message.type, message.type)
            content = message.content
            images = []
            if isinstance(content, list):
                texts = []
                for block in content:
                    if block.get('type') == 'text':
                        texts.append(block['text'])
                    elif block.get('type') == 'image_url':
                        image_url = block['image_url']['url']
                        if not image_url.startswith('data:') or ';base64,' not in image_url:
                            raise ValueError('Ollama requires an inline base64 image')
                        images.append(image_url.split(';base64,', 1)[1])
                    else:
                        raise ValueError(
                            'Unsupported message content block; Ollama image content must use inline base64.'
                        )
                content = '\n'.join(texts)
            converted.append({'role': role, 'content': content, **({'images': images} if images else {})})

        def validate(result):
            if (
                result.get('done_reason') == 'length'
                or result.get('prompt_eval_count', 0) >= self.policy.effective_num_ctx - 256
            ):
                raise ValueError('Ollama context overflow or truncated response; use a model with sufficient context.')
            content = result.get('message', {}).get('content')
            if not isinstance(content, str) or not content.strip():
                raise ValueError('Ollama returned an empty response')
            return AIMessage(content=content)

        return self._call('/api/chat', {'messages': converted, 'stream': False}, validate)

    def embed_query(self, text):
        def validate(result):
            vectors = result.get('embeddings')
            if not vectors or not vectors[0]:
                raise ValueError('Ollama returned an empty embedding')
            return vectors[0]

        return self._call('/api/embed', {'input': text, 'truncate': False}, validate)


def _gate_path():
    from pathlib import Path

    from src.config import Database_Settings

    return Path(Database_Settings().DATABASE_PATH).resolve().parent / 'ollama-inference.lock'


@contextmanager
def local_inference_gate(base_url, timeout):
    """OS-owned lock shared across loops, threads and processes; no stale lease."""
    import time

    if not is_local_ollama(base_url):
        yield
        return
    path = _gate_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout
    with open(path, 'a+b') as lock:
        if os.name == 'nt':
            import msvcrt

            lock.seek(0, 2)
            if lock.tell() == 0:
                lock.write(b'0')
                lock.flush()

            def acquire():
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)

            def release():
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            def acquire():
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

            def release():
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

        while True:
            try:
                acquire()
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise TimeoutError('Ollama inference queue deadline exceeded') from None
                time.sleep(min(0.05, max(0, deadline - time.monotonic())))
        try:
            yield
        finally:
            release()


def policy_status(configs):
    """Read-only serializable information; omit endpoint URLs and credentials."""
    from dataclasses import asdict

    result = []
    grouped = {}
    for cfg in configs:
        if cfg.mode == 'remote' and cfg.model_provider == 'ollama':
            endpoint = _normalized_endpoint(cfg.url)
            key = (endpoint, cfg.model_name)
            grouped.setdefault(key, set()).add(cfg.type)
    policies = {
        key: resolve_ollama_policy(key[0], key[1], min(roles), workload_roles=sorted(roles))
        for key, roles in grouped.items()
    }
    for cfg in configs:
        if cfg.mode == 'remote' and cfg.model_provider == 'ollama':
            key = (_normalized_endpoint(cfg.url), cfg.model_name)
            result.append(
                {
                    'type': cfg.type,
                    'model_name': cfg.model_name,
                    'workload_roles': sorted(grouped[key]),
                    **asdict(policies[key]),
                }
            )
    return result


def validate_configuration(role, mode, provider, model_name, base_url):
    if mode == 'remote' and provider == 'ollama' and role in IMAGE_ROLES:
        roles = configured_model_roles(base_url, model_name, role)
        resolve_ollama_policy(base_url, model_name, role, workload_roles=roles).require_vision()


def langchain_options(base_url, model_name, role):
    """Keep interactive tool-chat context aligned with pipeline model policy."""
    roles = configured_model_roles(base_url, model_name, role)
    policy = resolve_ollama_policy(base_url, model_name, role, workload_roles=roles)
    return {'num_ctx': policy.effective_num_ctx, 'client_kwargs': {'timeout': timeout_for_role(role)}}
