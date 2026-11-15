"""Synthetic provider protocol tests; these do not qualify a live provider."""
import importlib
import json
import unittest
from unittest.mock import patch

import httpx

from tests.test_model_edits import BASE
from tests.test_provider import ObservedStream


class ModelEditProviderTests(unittest.IsolatedAsyncioTestCase):
    env={'PPA_LLM_BASE_URL':'https://provider.example/v1','PPA_LLM_MODEL':'synthetic-model','PPA_LLM_API_KEY':'synthetic-private-key'}

    def engine(self):
        return importlib.import_module('print_agent.model_edits')

    async def invoke(self, raw, *, base=None, response=None):
        original=httpx.AsyncClient
        self.requests=[]
        def handler(request):
            self.requests.append(request)
            return response if response is not None else httpx.Response(200,json={'choices':[{'message':{'content':json.dumps(raw)}}]})
        def factory(**kwargs):
            self.client_options=kwargs
            return original(transport=httpx.MockTransport(handler),**kwargs)
        with patch.dict('os.environ',self.env,clear=True), patch('print_agent.planner.httpx.AsyncClient',factory):
            return await self.engine().plan_model_edit_with_llm('높이를 5mm 늘려줘', BASE if base is None else base)

    async def test_typed_operations_preserve_dimensions_and_use_protected_transport(self):
        result=await self.invoke({'operations':[{'field':'height','op':'add','value':5}],'questions':[]})
        self.assertEqual(result['engine'],'llm')
        self.assertEqual(result['review']['parameters']['height'],35)
        self.assertEqual(result['review']['parameters']['width'],150)
        self.assertEqual(result['review']['changes'],[{'field':'height','before':30,'after':35}])
        self.assertNotIn('parameters',result)
        self.assertFalse(self.client_options['trust_env'])
        self.assertFalse(self.client_options['follow_redirects'])
        payload=json.loads(self.requests[0].content)
        user=json.loads(payload['messages'][1]['content'])
        self.assertEqual(set(user),{'request_text','base_parameters'})
        self.assertEqual(user['base_parameters']['dividers'],2)
        self.assertNotIn(self.env['PPA_LLM_API_KEY'],json.dumps(result))

    async def test_clarification_is_fixed_application_text_without_provider_prose(self):
        result=await self.invoke({'operations':[],'questions':['sensitive provider prose']})
        self.assertEqual(result['status'],'needs_input')
        self.assertNotIn('review',result)
        self.assertNotIn('sensitive',json.dumps(result))

    async def test_invalid_operation_response_is_never_a_partial_proposal(self):
        invalid=[{'parameters':{'height':35},'questions':[]},
                 {'operations':[{'field':'height','op':'add','value':5}],'questions':['confirm']},
                 {'operations':[{'field':'height','op':'set','value':True}],'questions':[]},
                 {'operations':[{'field':'height','op':'set','value':35},{'field':'slots','op':'set','value':6}],'questions':[]},
                 {'operations':[],'questions':[]},
                 {'operations':[],'questions':['x'*501]},
                 {'operations':[],'questions':['x']*6},
                 {'operations':[],'questions':'x'},
                 {'operations':[],'questions':[],'code':'x'}]
        for raw in invalid:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                await self.invoke(raw)

    async def test_typed_no_effect_or_invalid_result_requests_clarification(self):
        for value in (30, 2, 301):
            with self.subTest(height=value):
                result=await self.invoke({'operations':[{'field':'height','op':'set','value':value}],'questions':[]})
                self.assertEqual(result['status'],'needs_input')
                self.assertEqual(result['engine'],'llm')
                self.assertNotIn('review',result)
                self.assertNotIn('parameters',result)
                self.assertTrue(result['questions'])

    async def test_malformed_base_rejected_before_provider(self):
        with patch('print_agent.planner.httpx.AsyncClient') as client:
            for base in ({**BASE,'width':True},{**BASE,'template':[]},{**BASE,'template':{}},
                         {**BASE,'height':2}):
                with self.subTest(base=base), self.assertRaises(ValueError):
                    await self.engine().plan_model_edit_with_llm('높이35mm',base)
            client.assert_not_called()

    async def test_provider_failure_never_reads_secret_body(self):
        stream=ObservedStream([b'sensitive body']*1000)
        with self.assertRaisesRegex(ValueError,'HTTP 503') as caught:
            await self.invoke(None,response=httpx.Response(503,stream=stream))
        self.assertEqual(stream.consumed,0)
        self.assertTrue(stream.closed)
        self.assertNotIn('sensitive',str(caught.exception))
        self.assertNotIn(self.env['PPA_LLM_API_KEY'],str(caught.exception))

    async def test_shared_transport_bounds_edit_response_stream_and_deadline(self):
        stream=ObservedStream([b'x'*16384]*64)
        with self.assertRaisesRegex(ValueError,'허용 크기'):
            await self.invoke(None,response=httpx.Response(200,stream=stream))
        self.assertLessEqual(stream.consumed,100000+16384)
        self.assertTrue(stream.closed)
        stream=ObservedStream([b' ']*100,delay=0.01)
        with patch('print_agent.planner.LLM_DEADLINE_SECONDS',0.025):
            with self.assertRaisesRegex(ValueError,'시간'):
                await self.invoke(None,response=httpx.Response(200,stream=stream))
        self.assertLess(stream.consumed,100)
        self.assertTrue(stream.closed)
