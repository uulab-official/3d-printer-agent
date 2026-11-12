import json
import unittest
from unittest.mock import patch

import httpx
from print_agent.planner import plan_with_llm, provider_config


class ProviderTests(unittest.IsolatedAsyncioTestCase):
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
