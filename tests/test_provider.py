import asyncio
import gzip
import json
import unittest
from unittest.mock import patch

import httpx
from print_agent.planner import plan_from_text, plan_with_llm, provider_config


class ProviderTests(unittest.IsolatedAsyncioTestCase):
    async def test_existing_material_and_purchase_actions_do_not_call_provider_in_llm_mode(self):
        for environment in ({}, {'PPA_LLM_BASE_URL': 'https://provider.example/v1', 'PPA_LLM_MODEL': 'model'}):
            with self.subTest(environment=bool(environment)), patch.dict('os.environ', environment, clear=True), \
                    patch('print_agent.planner.httpx.AsyncClient') as client:
                for text, action in (('PLA 필라멘트 온도 설정', 'open_profiles'), ('저렴한 상품 구매 비교', 'open_offers')):
                    result = await plan_with_llm(text)
                    self.assertEqual(result, plan_from_text(text))
                    self.assertEqual(result['action'], action)
                    self.assertNotIn('parameters', result)
                client.assert_not_called()

    async def test_http_client_invalid_url_is_an_explainable_error(self):
        def handler(request):
            raise httpx.InvalidURL('synthetic invalid URL')
        with patch.dict('os.environ',{'PPA_LLM_BASE_URL':'https://provider.example/v1','PPA_LLM_MODEL':'model'},clear=True), patch('print_agent.planner.httpx.AsyncClient',self.client_factory(handler)):
            with self.assertRaisesRegex(ValueError,'서버 연결'):
                await plan_with_llm('수납함')

    def client_factory(self, handler):
        original = httpx.AsyncClient
        return lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs)

    async def test_real_adapter_protocol_and_typed_output_with_mock_server(self):
        calls=[]
        def handler(request):
            calls.append(request)
            result={'parameters':{'template':'tray','width':144,'depth':91,'height':41},'explanation':'제안한 치수','questions':[]}
            return httpx.Response(200,json={'choices':[{'message':{'content':json.dumps(result)}}]})
        env={'PPA_LLM_BASE_URL':'http://127.0.0.1:1234/v1','PPA_LLM_MODEL':'local-model','PPA_LLM_API_KEY':'test-key-not-real'}
        with patch.dict('os.environ',env,clear=True), patch('print_agent.planner.httpx.AsyncClient',self.client_factory(handler)):
            result=await plan_with_llm('가로 144mm 수납함')
        self.assertEqual(result['engine'],'llm')
        self.assertEqual(result['parameters']['width'],144)
        self.assertEqual(str(calls[0].url),'http://127.0.0.1:1234/v1/chat/completions')
        self.assertEqual(calls[0].headers['Authorization'],'Bearer test-key-not-real')
        self.assertEqual(json.loads(calls[0].content)['model'],'local-model')

    async def test_untrusted_provider_cannot_supply_executable_code(self):
        content=json.dumps({'parameters':{'template':'tray','code':'import os'},'questions':[]})
        handler=lambda request:httpx.Response(200,json={'choices':[{'message':{'content':content}}]})
        with patch.dict('os.environ',{'PPA_LLM_BASE_URL':'https://provider.example/v1','PPA_LLM_MODEL':'model'},clear=True), patch('print_agent.planner.httpx.AsyncClient',self.client_factory(handler)):
            with self.assertRaisesRegex(ValueError,'허용 범위'):
                await plan_with_llm('수납함')

    async def test_provider_error_does_not_echo_body_or_key(self):
        handler=lambda request:httpx.Response(401,text='sensitive upstream body')
        with patch.dict('os.environ',{'PPA_LLM_BASE_URL':'https://provider.example/v1','PPA_LLM_MODEL':'model','PPA_LLM_API_KEY':'synthetic-secret'},clear=True), patch('print_agent.planner.httpx.AsyncClient',self.client_factory(handler)):
            with self.assertRaisesRegex(ValueError,'HTTP 401') as caught:
                await plan_with_llm('수납함')
        self.assertNotIn('sensitive',str(caught.exception))
        self.assertNotIn('synthetic-secret',str(caught.exception))

    async def test_non_loopback_plain_http_is_not_accepted(self):
        with patch.dict('os.environ',{'PPA_LLM_BASE_URL':'http://remote.example/v1','PPA_LLM_MODEL':'model'},clear=True):
            self.assertFalse(provider_config()['configured'])
            with self.assertRaises(ValueError):
                await plan_with_llm('수납함')


class ObservedStream(httpx.AsyncByteStream):
    def __init__(self, chunks, *, delay=0):
        self.chunks = chunks
        self.delay = delay
        self.consumed = 0
        self.closed = False

    async def __aiter__(self):
        for chunk in self.chunks:
            if self.delay:
                await asyncio.sleep(self.delay)
            self.consumed += len(chunk)
            yield chunk

    async def aclose(self):
        self.closed = True


class ProviderStreamingTests(unittest.IsolatedAsyncioTestCase):
    env = {'PPA_LLM_BASE_URL': 'https://provider.example/v1', 'PPA_LLM_MODEL': 'model',
           'PPA_LLM_API_KEY': 'synthetic-key-never-display'}

    def client_factory(self, response):
        original = httpx.AsyncClient
        return lambda **kwargs: original(transport=httpx.MockTransport(lambda _: response), **kwargs)

    async def invoke(self, response):
        with patch.dict('os.environ', self.env, clear=True), \
             patch('print_agent.planner.httpx.AsyncClient', self.client_factory(response)):
            return await plan_with_llm('수납함')

    async def test_oversized_success_stops_reading_and_closes_stream(self):
        stream = ObservedStream([b'x' * 16384] * 64)
        with self.assertRaisesRegex(ValueError, '허용 크기'):
            await self.invoke(httpx.Response(200, stream=stream))
        self.assertLessEqual(stream.consumed, 100000 + 16384)
        self.assertTrue(stream.closed)

    async def test_advertised_oversize_is_rejected_before_body(self):
        stream = ObservedStream([b'x' * 16384] * 64)
        with self.assertRaisesRegex(ValueError, '허용 크기'):
            await self.invoke(httpx.Response(200, headers={'Content-Length': '1048576'}, stream=stream))
        self.assertEqual(stream.consumed, 0)
        self.assertTrue(stream.closed)

    async def test_failure_response_body_is_never_consumed_or_exposed(self):
        stream = ObservedStream([b'sensitive upstream response'] * 10000)
        with self.assertRaisesRegex(ValueError, 'HTTP 503') as caught:
            await self.invoke(httpx.Response(503, stream=stream))
        self.assertEqual(stream.consumed, 0)
        self.assertTrue(stream.closed)
        self.assertNotIn('sensitive', str(caught.exception))
        self.assertNotIn(self.env['PPA_LLM_API_KEY'], str(caught.exception))

    async def test_whole_request_deadline_closes_trickling_response(self):
        stream = ObservedStream([b' '] * 100, delay=0.01)
        with patch('print_agent.planner.LLM_DEADLINE_SECONDS', 0.025, create=True):
            with self.assertRaisesRegex(ValueError, '시간'):
                await self.invoke(httpx.Response(200, stream=stream))
        self.assertLess(stream.consumed, 100)
        self.assertTrue(stream.closed)

    async def test_valid_chunked_response_keeps_typed_plan_contract(self):
        plan = {'parameters': {'template': 'tray', 'width': 123}, 'questions': []}
        payload = json.dumps({'choices': [{'message': {'content': json.dumps(plan)}}]}).encode()
        stream = ObservedStream([payload[index:index + 7] for index in range(0, len(payload), 7)])
        result = await self.invoke(httpx.Response(200, stream=stream))
        self.assertEqual(result['parameters']['width'], 123)
        self.assertEqual(result['capability'], 'supported_template_only')
        self.assertEqual(stream.consumed, len(payload))
        self.assertTrue(stream.closed)

    async def test_compressed_expansion_is_rejected_without_reading_or_decoding(self):
        compressed = gzip.compress(b' ' * (8 * 1024 * 1024))
        stream = ObservedStream([compressed])
        response = httpx.Response(200, headers={'Content-Encoding': 'gzip', 'Content-Length': str(len(compressed))}, stream=stream)
        with self.assertRaisesRegex(ValueError, '압축'):
            await self.invoke(response)
        self.assertEqual(response.request.headers['accept-encoding'], 'identity')
        self.assertEqual(stream.consumed, 0)
        self.assertTrue(stream.closed)

    async def test_excessively_nested_response_returns_explainable_error(self):
        stream = ObservedStream([b'[' * 1500 + b'0' + b']' * 1500])
        with self.assertRaisesRegex(ValueError, '응답 형식'):
            await self.invoke(httpx.Response(200, stream=stream))
        self.assertTrue(stream.closed)
