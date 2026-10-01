"""Policy contract: model metadata bounds requests, never server defaults."""
import importlib.util
from unittest.mock import patch

import pytest


def policy_module():
    assert importlib.util.find_spec('src.ollama_policy') is not None, 'Ollama policy is missing'
    from src import ollama_policy
    return ollama_policy


@pytest.mark.parametrize('limit,expected', [(4096,4096),(262144,16384)])
def test_model_limit_bounds_context(limit, expected):
    p = policy_module()
    with patch.object(p, '_show', return_value={'capabilities':['vision'], 'model_info':{'arbitrary.context_length':limit}}), patch.object(p, '_host_memory_gib', return_value=16):
        policy = p.resolve_ollama_policy('http://localhost:11434','other-model','vision')
    assert policy.effective_num_ctx == expected
    assert policy.vision_capable is True
    assert policy.capacity_known is True


def test_same_model_has_stable_context_across_roles():
    p = policy_module()
    with patch.object(p, '_show', return_value={'capabilities':['vision'], 'model_info':{'x.context_length':262144}}), patch.object(p, '_host_memory_gib', return_value=16):
        contexts = [p.resolve_ollama_policy(None,'anything',role).effective_num_ctx for role in ['vision','clip','ocr','translator']]
    assert len(set(contexts)) == 1


@pytest.mark.parametrize('metadata', [{}, {'model_info':{'bad.context_length':'invalid'}}])
def test_missing_metadata_is_explicit(metadata):
    p = policy_module()
    with patch.object(p, '_show', return_value=metadata):
        policy = p.resolve_ollama_policy(None,'unknown','vision')
    assert policy.vision_capable is None
    assert not policy.capacity_known
    assert policy.effective_num_ctx <= 4096
    assert 'unverified' in policy.reason


def test_unavailable_server_is_unverified():
    p = policy_module()
    with patch.object(p, '_show', side_effect=ConnectionError('secret-url')):
        policy = p.resolve_ollama_policy(None,'unknown','vision')
    assert not policy.capacity_known
    assert 'secret' not in policy.reason


def test_remote_host_does_not_use_local_memory():
    p = policy_module()
    with patch.object(p, '_show', return_value={'capabilities':['vision'],'model_info':{'x.context_length':262144}}), patch.object(p, '_host_memory_gib', side_effect=AssertionError('remote host')):
        policy = p.resolve_ollama_policy('https://my-server.example:11434','custom','clip')
    assert not policy.capacity_known
    assert policy.effective_num_ctx <= 4096


def test_text_only_model_rejected_for_image():
    p = policy_module()
    with patch.object(p, '_show', return_value={'capabilities':['completion'],'model_info':{'x.context_length':8192}}):
        with pytest.raises(ValueError, match='vision'):
            p.resolve_ollama_policy(None,'text-model','vision').require_vision()

@pytest.mark.parametrize('role', ['vision','clip','ocr','translator','embedding'])
def test_request_carries_context_and_embedding_disables_truncation(role):
    p = policy_module()
    assert hasattr(p, 'OllamaClient'), 'Bounded Ollama client missing'
    from langchain_core.messages import HumanMessage
    policy = p.OllamaPolicy(8192, 'test', True, True)
    observed = []
    def request(url, payload, timeout):
        observed.append(payload)
        return {'message':{'content':'answer'}, 'embeddings':[[0.1,0.2]]}
    with patch.object(p, 'resolve_ollama_policy', return_value=policy), patch.object(p, '_request', side_effect=request):
        client = p.OllamaClient('http://remote.example','model',role)
        if role == 'embedding':
            assert client.embed_query('hello') == [0.1,0.2]
        else:
            assert client.invoke([HumanMessage(content='hello')]).content == 'answer'
    assert observed[0]['options']['num_ctx'] == 8192
    if role == 'embedding':
        assert observed[0]['truncate'] is False


@pytest.mark.parametrize('error', [TimeoutError('timeout'), RuntimeError('runner terminated'), RuntimeError('context exceeded'), RuntimeError('out of memory')])
def test_errors_propagate(error):
    p = policy_module()
    assert hasattr(p, 'OllamaClient'), 'Bounded Ollama client missing'
    from langchain_core.messages import HumanMessage
    with patch.object(p, 'resolve_ollama_policy', return_value=p.OllamaPolicy(4096,'test',True,False)), patch.object(p, '_request', side_effect=error):
        client = p.OllamaClient('http://remote.example','model','vision')
        with pytest.raises(type(error)):
            client.invoke([HumanMessage(content='hello')])


def test_empty_generation_fails():
    p = policy_module()
    assert hasattr(p, 'OllamaClient'), 'Bounded Ollama client missing'
    with patch.object(p, 'resolve_ollama_policy', return_value=p.OllamaPolicy(4096,'test',True,False)), patch.object(p, '_request', return_value={'message':{'content':''}}):
        with pytest.raises(ValueError, match='empty'):
            p.OllamaClient('http://remote.example','model','vision').invoke([])


@pytest.mark.parametrize('module,class_name,method,args', [('ocr_remote','RemoteOCR','extract_text',('image',)), ('translator_remote','RemoteTranslator','translate',('hello',))])
def test_ollama_failure_not_swallowed(module,class_name,method,args):
    import importlib
    from unittest.mock import MagicMock
    mod = importlib.import_module('src.ai.'+module)
    llm = MagicMock()
    llm.invoke.side_effect = RuntimeError('runner terminated')
    instance = getattr(mod,class_name)(llm=llm)
    with patch('builtins.open', __import__('unittest.mock',fromlist=['mock_open']).mock_open(read_data=b'image')):
        with pytest.raises(RuntimeError, match='runner terminated'):
            getattr(instance,method)(*args)


def test_local_gate_serializes_threads_and_remote_bypasses(tmp_path, monkeypatch):
    import concurrent.futures
    import threading
    p = policy_module()
    assert hasattr(p, 'local_inference_gate'), 'Cross-process gate missing'
    monkeypatch.setattr(p, '_gate_path', lambda: tmp_path / 'gate.lock')
    with p.local_inference_gate('http://localhost:11434', 1):
        with p.local_inference_gate('http://remote.example', .1):
            pass
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(lambda: p.local_inference_gate('http://127.0.0.1:11434', .1).__enter__())
            with pytest.raises(TimeoutError):
                future.result(timeout=1)


def test_model_gateway_selects_bounded_client_for_both_request_types():
    from src.model_services import _build_langchain_embedder, _build_langchain_vision_model
    p = policy_module()
    with patch.object(p, 'resolve_ollama_policy', return_value=p.OllamaPolicy(4096,'test',True,False)):
        assert isinstance(_build_langchain_vision_model('ollama','test',None,'http://remote.example'), p.OllamaClient)
        assert isinstance(_build_langchain_embedder('ollama','test',None,'http://remote.example'), p.OllamaClient)


def test_deadline_closes_slow_http_request():
    import asyncio
    import time

    import httpx
    p = policy_module()
    closed = []
    class SlowStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            for _ in range(100):
                await asyncio.sleep(.01)
                yield b' '
        async def aclose(self):
            closed.append(True)
    transport = httpx.MockTransport(lambda request: httpx.Response(200, stream=SlowStream()))
    client = httpx.AsyncClient(transport=transport)
    started = time.monotonic()
    with patch('httpx.AsyncClient', return_value=client):
        with pytest.raises(TimeoutError):
            p._request('http://remote.example/api/chat',{},.1)
    assert time.monotonic()-started < .8
    assert closed


def test_clip_does_not_silently_drop_candidates(tmp_path):
    from unittest.mock import MagicMock

    from langchain_core.messages import AIMessage

    from src.ai.clip_remote import RemoteClipTagger
    image = tmp_path/'image.jpg'
    image.write_bytes(b'image')
    llm = MagicMock()
    llm.invoke.return_value = AIMessage(content='[]')
    tags = [f'tag_{i}' for i in range(201)]
    RemoteClipTagger(llm, tags, []).get_tags(str(image))
    texts = [block['text'] for call in llm.invoke.call_args_list for block in call.args[0][0].content if block['type']=='text']
    assert any('tag_200' in text for text in texts)


def test_policy_status_is_read_only_and_has_no_credentials():
    p = policy_module()
    assert hasattr(p, 'policy_status'), 'Read-only policy status missing'
    from types import SimpleNamespace
    cfg1 = SimpleNamespace(type='vision',model_provider='ollama',mode='remote',model_name='v',url='http://user:secret@remote.example')
    cfg2 = SimpleNamespace(type='clip',model_provider='ollama',mode='remote',model_name='v',url='http://user:secret@remote.example')
    with patch.object(p,'resolve_ollama_policy',return_value=p.OllamaPolicy(4096,'unverified',None,False)) as resolve:
        result = p.policy_status([cfg1, cfg2])
    resolve.assert_called_once()
    assert len(result) == 2
    assert result[0]['effective_num_ctx'] == 4096
    assert result[0]['type'] == 'vision'
    assert 'secret' not in repr(result)


def test_client_uses_one_deadline_across_candidate_retries(monkeypatch):
    p = policy_module()
    import time
    with patch.object(p,'resolve_ollama_policy',return_value=p.OllamaPolicy(4096,'test',True,False)):
        client = p.OllamaClient('http://remote.example','m','clip')
    monkeypatch.setattr(p, 'INFERENCE_TIMEOUT', .04)
    with patch.object(p, '_request', return_value={'message':{'content':'[]'}}):
        client.invoke([])
        time.sleep(.06)
        with pytest.raises(TimeoutError):
            client.invoke([])


@pytest.mark.asyncio
async def test_tracking_provides_inference_log_ids():
    from src import pipeline_tracker as tracker
    assert hasattr(tracker, '_inference_ids'), 'Inference log IDs missing'
    from unittest.mock import MagicMock
    with patch.object(tracker,'_task_id',return_value=12), patch.object(tracker,'_update_task_id'), patch.object(tracker,'SessionLocal',MagicMock()):
        with tracker.pipeline_run_context(9):
            async with tracker.track_task(3,'1','description'):
                assert tracker._inference_ids.get() == {'photo_id':3,'run_id':9,'task_id':12}
    assert tracker._inference_ids.get() == {}


def test_configuration_rejects_known_text_only_image_model():
    p = policy_module()
    assert hasattr(p, 'validate_configuration'), 'Save validation missing'
    with patch.object(p, '_show', return_value={'capabilities':['completion']}):
        with pytest.raises(ValueError, match='vision'):
            p.validate_configuration('vision','remote','ollama','text-model',None)


def test_chat_options_share_effective_context_and_timeout():
    p = policy_module()
    assert hasattr(p, 'langchain_options'), 'Chat per-request policy missing'
    with patch.object(p,'resolve_ollama_policy',return_value=p.OllamaPolicy(8192,'test',True,True)):
        options = p.langchain_options(None,'shared','chat')
    assert options['num_ctx'] == 8192
    assert options['client_kwargs']['timeout'] <= 120


def test_local_gate_covers_other_processes(tmp_path):
    import os
    import subprocess
    import sys
    p = policy_module()
    path = tmp_path/'gate.lock'
    code = """from pathlib import Path
from src import ollama_policy as p
p._gate_path = lambda: Path(__import__('sys').argv[1])
try:
    with p.local_inference_gate('http://localhost:11434', .1):
        raise AssertionError('Overlapping local inference')
except TimeoutError:
    print('serialized')
"""
    with patch.object(p, '_gate_path', return_value=path):
        with p.local_inference_gate('http://127.0.0.1:11434', 1):
            result = subprocess.run([sys.executable,'-c',code,str(path)],capture_output=True,text=True,env={**os.environ,'PYTHONPATH':str(__import__('pathlib').Path(__file__).resolve().parents[1])},timeout=5)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == 'serialized'


@pytest.mark.parametrize('response', [ {'message':{'content':'partial'},'done_reason':'length'}, {'message':{'content':'partial'},'prompt_eval_count':4090} ])
def test_saturated_context_never_returns_success(response):
    p = policy_module()
    with patch.object(p,'resolve_ollama_policy',return_value=p.OllamaPolicy(4096,'test',True,False)), patch.object(p,'_request',return_value=response):
        with pytest.raises(ValueError, match='context'):
            p.OllamaClient('http://remote.example','m','vision').invoke([])


def test_empty_failure_is_logged_with_ids_and_error_class():
    from loguru import logger

    from src.pipeline_tracker import _inference_ids
    p = policy_module()
    entries = []
    sink = logger.add(lambda message: entries.append(str(message)))
    token = _inference_ids.set({'photo_id':3,'run_id':9,'task_id':12})
    try:
        with patch.object(p,'resolve_ollama_policy',return_value=p.OllamaPolicy(4096,'test',True,False)), patch.object(p,'_request',return_value={'message':{'content':''}}):
            with pytest.raises(ValueError):
                p.OllamaClient('http://user:secret@remote.example','m','vision').invoke([])
        assert any('error_class=ValueError' in entry and 'photo_id=3 run_id=9 task_id=12' in entry for entry in entries)
        assert 'secret' not in ''.join(entries)
    finally:
        _inference_ids.reset(token)
        logger.remove(sink)


def test_host_capacity_does_not_require_optional_psutil():
    import sys
    p = policy_module()
    with patch.dict(sys.modules, {'psutil':None}):
        memory = p._host_memory_gib()
    assert memory is not None and memory > 0


def test_host_capacity_falls_back_to_windows_memory_api(monkeypatch):
    import ctypes
    import sys
    from types import SimpleNamespace
    p = policy_module()

    class Kernel32:
        def GlobalMemoryStatusEx(self, pointer):
            pointer._obj.ullTotalPhys = 8 * (1024 ** 3)
            return 1

    monkeypatch.setattr(sys, 'platform', 'win32')
    monkeypatch.setitem(sys.modules, 'psutil', None)
    monkeypatch.setattr(ctypes, 'windll', SimpleNamespace(kernel32=Kernel32()), raising=False)
    assert p._host_memory_gib() == 8


def test_transport_timeout_is_actionable():
    import asyncio

    import httpx
    p = policy_module()
    async def handler(request):
        await asyncio.sleep(1)
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with patch('httpx.AsyncClient',return_value=client):
        with pytest.raises(TimeoutError, match='deadline'):
            p._request('http://remote.example',{},.01)


def test_http_transport_timeout_is_actionable():
    import httpx
    p = policy_module()
    async def handler(request):
        raise httpx.ReadTimeout('timed out', request=request)
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with patch('httpx.AsyncClient', return_value=client):
        with pytest.raises(TimeoutError, match='deadline'):
            p._request('http://remote.example', {}, 1)
