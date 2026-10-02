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


def test_context_override_ignores_262k_server_default_without_changing_it():
    import os

    p = policy_module()
    from langchain_core.messages import HumanMessage

    requests = []
    def request(url, payload, timeout):
        requests.append((url, payload))
        return {'message':{'content':'Description'}}

    metadata = {'capabilities':['vision'], 'model_info':{'x.context_length':262144}}
    with patch.dict(os.environ, {'OLLAMA_CONTEXT_LENGTH':'262144'}), patch.object(p, 'configured_model_roles', return_value=['vision']), patch.object(p, '_show', return_value=metadata), patch.object(p, '_host_memory_gib', return_value=16), patch.object(p, '_request', side_effect=request):
        response = p.OllamaClient('http://localhost:11434', 'vision-model', 'vision').invoke([HumanMessage(content='Describe.')])
        assert os.environ['OLLAMA_CONTEXT_LENGTH'] == '262144'

    assert response.content == 'Description'
    assert requests[0][1]['options']['num_ctx'] == 16384
    assert requests[0][0].endswith('/api/chat')


def test_same_model_has_stable_context_across_roles():
    p = policy_module()
    roles = ['vision', 'clip', 'ocr', 'translator', 'embedding']
    with patch.object(p, '_show', return_value={'capabilities':['vision'], 'model_info':{'x.context_length':262144}}), patch.object(p, '_host_memory_gib', return_value=16):
        contexts = [p.resolve_ollama_policy(None, 'shared', role, workload_roles=roles).effective_num_ctx for role in roles]
    assert contexts == [16384] * len(roles)


@pytest.mark.parametrize(
    'role,memory,expected',
    [('vision',16,16384), ('clip',8,8192), ('translator',16,8192), ('embedding',16,4096), ('translator',8,4096)],
)
def test_context_budget_uses_role_and_host_capacity(role, memory, expected):
    p = policy_module()
    with patch.object(p, '_show', return_value={'capabilities':['vision'], 'model_info':{'x.context_length':262144}}), patch.object(p, '_host_memory_gib', return_value=memory):
        policy = p.resolve_ollama_policy('http://localhost:11434', 'model', role)
    assert policy.effective_num_ctx == expected


def test_context_budget_caps_to_largest_configured_role_for_shared_model():
    p = policy_module()
    roles = ['vision', 'translator', 'embedding']
    with patch.object(p, '_show', return_value={'capabilities':['vision'], 'model_info':{'x.context_length':8192}}), patch.object(p, '_host_memory_gib', return_value=16):
        contexts = [p.resolve_ollama_policy(None, 'shared', role, workload_roles=roles).effective_num_ctx for role in roles]
    assert contexts == [8192, 8192, 8192]


def test_pipeline_and_chat_client_use_the_same_configured_role_context():
    p = policy_module()
    roles = ['chat', 'translator', 'vision']
    metadata = {'capabilities':['vision'], 'model_info':{'x.context_length':262144}}
    with patch.object(p, 'configured_model_roles', return_value=roles), patch.object(p, '_show', return_value=metadata), patch.object(p, '_host_memory_gib', return_value=16):
        pipeline_client = p.OllamaClient('http://localhost:11434', 'shared-model', 'translator')
        chat_options = p.langchain_options('http://localhost:11434', 'shared-model', 'chat')
    assert pipeline_client.policy.effective_num_ctx == 16384
    assert chat_options['num_ctx'] == pipeline_client.policy.effective_num_ctx


def test_configured_model_roles_match_server_and_model(monkeypatch, tmp_path):
    p = policy_module()
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from src.db import database
    from src.models import AIModelConfig

    engine = create_engine(f"sqlite:///{tmp_path / 'model-config.db'}")
    AIModelConfig.__table__.create(engine)
    with Session(engine) as db:
        db.add_all([
            AIModelConfig(type='vision', mode='remote', model_provider='ollama', model_name='same', url=None),
            AIModelConfig(type='clip', mode='remote', model_provider='ollama', model_name='same', url='http://localhost:11434/'),
            AIModelConfig(type='ocr', mode='remote', model_provider='ollama', model_name='other', url='http://localhost:11434'),
            AIModelConfig(type='translator', mode='remote', model_provider='ollama', model_name='same', url='https://ollama.example:11434'),
        ])
        db.commit()
    monkeypatch.setattr(database, 'SessionLocal', lambda: Session(engine))
    try:
        assert p.configured_model_roles('http://localhost:11434', 'same', 'translator') == ['clip', 'translator', 'vision']
    finally:
        engine.dispose()


def test_policy_status_uses_union_of_roles_for_shared_model():
    p = policy_module()
    from types import SimpleNamespace
    configs = [
        SimpleNamespace(type='vision',model_provider='ollama',mode='remote',model_name='v',url='http://localhost:11434'),
        SimpleNamespace(type='translator',model_provider='ollama',mode='remote',model_name='v',url='http://localhost:11434'),
    ]
    policy = p.OllamaPolicy(16384, 'image role budget', True, True)
    with patch.object(p, 'resolve_ollama_policy', return_value=policy) as resolve:
        results = p.policy_status(configs)
    assert len(results) == 2
    resolve.assert_called_once_with('http://localhost:11434', 'v', 'translator', workload_roles=['translator', 'vision'])


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


def test_custom_ollama_url_is_used_for_metadata_and_inference():
    p = policy_module()
    from langchain_core.messages import HumanMessage

    base_url = 'https://ollama.example:11435/'
    request_urls = []

    def request(url, payload, timeout):
        request_urls.append(url)
        if url.endswith('/api/show'):
            assert payload == {'model': 'custom-vision-model'}
            return {'capabilities':['vision'], 'model_info':{'x.context_length':8192}}
        return {'message':{'content':'Processed by the custom Ollama server.'}}

    with (
        patch.object(p, 'configured_model_roles', return_value=['vision']),
        patch.object(p, '_request', side_effect=request),
    ):
        client = p.OllamaClient(base_url, 'custom-vision-model', 'vision')
        response = client.invoke([HumanMessage(content='Describe this photo.')])

    assert response.content == 'Processed by the custom Ollama server.'
    assert request_urls == [
        'https://ollama.example:11435/api/show',
        'https://ollama.example:11435/api/chat',
    ]

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


def test_inline_image_is_forwarded_to_ollama_without_loss():
    p = policy_module()
    from langchain_core.messages import HumanMessage

    observed = []
    def request(url, payload, timeout):
        observed.append(payload)
        return {'message':{'content':'A red car.'}}

    image_b64 = 'AAECAwQ='
    message = HumanMessage(content=[
        {'type':'image_url', 'image_url':{'url':f'data:image/jpeg;base64,{image_b64}'}},
        {'type':'text', 'text':'Describe this photo.'},
    ])
    with patch.object(p, 'configured_model_roles', return_value=['vision']), patch.object(p, 'resolve_ollama_policy', return_value=p.OllamaPolicy(8192,'test',True,True)), patch.object(p, '_request', side_effect=request):
        assert p.OllamaClient('http://remote.example', 'vision-model', 'vision').invoke([message]).content == 'A red car.'

    assert observed[0]['messages'][0]['images'] == [image_b64]
    assert observed[0]['messages'][0]['content'] == 'Describe this photo.'
    assert observed[0]['options']['num_ctx'] == 8192


def test_non_inline_image_url_is_rejected_instead_of_silently_omitted():
    p = policy_module()
    from langchain_core.messages import HumanMessage

    message = HumanMessage(content=[{'type':'image_url', 'image_url':{'url':'https://example.test/photo.jpg'}}])
    with patch.object(p, 'configured_model_roles', return_value=['vision']), patch.object(p, 'resolve_ollama_policy', return_value=p.OllamaPolicy(8192,'test',True,True)):
        with pytest.raises(ValueError, match='inline base64 image'):
            p.OllamaClient('http://remote.example', 'vision-model', 'vision').invoke([message])


def test_unsupported_image_content_block_is_not_silently_dropped():
    p = policy_module()
    from langchain_core.messages import HumanMessage

    message = HumanMessage(content=[{'type':'image', 'data':'AAECAwQ='}])
    with patch.object(p, 'configured_model_roles', return_value=['vision']), patch.object(p, 'resolve_ollama_policy', return_value=p.OllamaPolicy(8192,'test',True,True)), patch.object(p, '_request', return_value={'message':{'content':'answer'}}):
        with pytest.raises(ValueError, match='Unsupported message content'):
            p.OllamaClient('http://remote.example', 'vision-model', 'vision').invoke([message])


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


def test_ollama_ocr_role_has_a_longer_deadline_than_other_roles():
    p = policy_module()
    assert hasattr(p, 'timeout_for_role'), 'Per-role Ollama timeout policy is missing'
    assert p.timeout_for_role('ocr') == 300.0
    assert p.timeout_for_role('vision') == p.INFERENCE_TIMEOUT
    assert p.timeout_for_role('clip') == p.INFERENCE_TIMEOUT


@pytest.mark.parametrize(('role', 'expected'), [('ocr', 300.0), ('vision', 120.0)])
def test_ollama_role_deadline_is_applied_to_queue_and_http_request(role, expected):
    p = policy_module()
    from contextlib import contextmanager

    from langchain_core.messages import HumanMessage

    queue_timeouts = []
    request_timeouts = []

    @contextmanager
    def gate(_url, timeout):
        queue_timeouts.append(timeout)
        yield

    def request(_url, _payload, timeout):
        request_timeouts.append(timeout)
        return {'message': {'content': 'answer'}}

    with (
        patch.object(p, 'resolve_ollama_policy', return_value=p.OllamaPolicy(4096, 'test', True, True)),
        patch.object(p, 'local_inference_gate', gate),
        patch.object(p, '_request', side_effect=request),
    ):
        p.OllamaClient('http://localhost:11434', 'model', role).invoke([HumanMessage(content='read')])

    assert queue_timeouts[0] > expected - 1
    assert request_timeouts[0] > expected - 1


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
