"""Provider wire-format tests with synthetic responses and no real credentials.

These exercise adapter contracts only. No real model or Apollo execution is
claimed, and no network request is made by this module's fake opener.
"""
from copy import deepcopy
import json
import os
import unittest
from unittest.mock import patch

from backend.crew_ai import ModelProvider, decode, provider_from_environment, tool_names


def context():
    return {'mode': 'EDUCATIONAL_PHYSICS_LAB', 'runId': 'unit-run', 'status': 'running',
            'physics': {'simTimeSeconds': 2, 'spacecraft': {'altitudeM': 100},
                        'engine': {'thrustN': 0}, 'thresholds': {'verticalSpeedMps': 2},
                        'provenance': {'native_path': 'UNIT_PRIVATE_NATIVE_PATH'}},
            'crew': [{'role': 'commander', 'kind': 'llm'}], 'checklist': {},
            'messages': [{'text': 'Untrusted crew data'}],
            'participants': {'UNIT_PRIVATE_PARTICIPANT': {}},
            'privateKey': 'UNIT_PRIVATE_CONFIG'}


class Response:
    def __init__(self, raw):
        self.raw = raw if isinstance(raw, bytes) else json.dumps(raw).encode()
        self.limit = None
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self, limit):
        self.limit = limit
        return self.raw[:limit]


class Opener:
    def __init__(self, reply): self.reply, self.calls = reply, []
    def __call__(self, request, timeout):
        self.calls.append((request, timeout))
        if isinstance(self.reply, Exception): raise self.reply
        self.response = Response(self.reply)
        return self.response


def reply(protocol, name='crew_message', arguments='{"text":"Synthetic provider fixture"}'):
    if protocol == 'responses':
        return {'output': [{'type': 'function_call', 'id': 'unit-item', 'call_id': 'unit-call',
                            'name': name, 'arguments': arguments}]}
    return {'choices': [{'message': {'tool_calls': [{'id': 'unit-call', 'type': 'function',
                      'function': {'name': name, 'arguments': arguments}}]}}]}


class CrewProviderTests(unittest.TestCase):
    def provider(self, data, protocol='responses', key=''):
        opener = Opener(data)
        return ModelProvider('https://provider.invalid/v1', 'explicit-unit-model', key=key,
                             protocol=protocol, opener=opener), opener

    def test_no_implicit_model_or_credentials_are_used(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(provider_from_environment())
        with patch.dict(os.environ, {'APOLLO_AI_BASE_URL':'https://provider.invalid/v1'}, clear=True):
            with self.assertRaises(ValueError): provider_from_environment()

    def test_explicit_environment_supports_both_formats_without_requesting_any_model(self):
        for protocol in ('responses', 'chat-completions'):
            with patch.dict(os.environ, {'APOLLO_AI_MODEL':'unit-model',
                  'APOLLO_AI_BASE_URL':'https://provider.invalid/v1',
                  'APOLLO_AI_PROTOCOL':protocol, 'APOLLO_AI_API_KEY':'UNIT_FAKE_KEY'}, clear=True):
                provider = provider_from_environment()
                self.assertEqual(provider.model, 'unit-model')
                self.assertEqual(provider.protocol, protocol)
                self.assertEqual(provider.base_url, 'https://provider.invalid/v1')

    def test_responses_and_chat_formats_parse_only_declared_role_tools(self):
        for protocol in ('responses', 'chat-completions'):
            for role, tool, args, action in (
                    ('commander','flight_controls','{"throttle":0.5,"pitch":-0.2}','controls'),
                    ('lunar-module-pilot','review_checklist','{"item":"braking"}','checklist'),
                    ('command-module-pilot','crew_message','{"text":"Orbital support"}','message')):
                with self.subTest(protocol=protocol, role=role):
                    provider, opener = self.provider(reply(protocol, tool, args), protocol)
                    self.assertEqual(provider.decide(role, context(), []), [{'action':action,'payload':json.loads(args)}])
                    request, timeout = opener.calls[0]
                    self.assertTrue(request.full_url.endswith('/responses' if protocol=='responses' else '/chat/completions'))
                    body = json.loads(request.data)
                    self.assertEqual(body['model'], 'explicit-unit-model')
                    self.assertFalse(body['parallel_tool_calls'])
                    self.assertEqual(timeout, 4.)
                    if protocol == 'responses': self.assertFalse(body['store'])

    def test_tools_have_strict_bounded_schemas_and_role_scopes(self):
        for protocol in ('responses', 'chat-completions'):
            for role in ('commander','lunar-module-pilot','command-module-pilot'):
                provider, opener = self.provider(reply(protocol), protocol)
                provider.decide(role, context(), [])
                body = json.loads(opener.calls[0][0].data)
                tools = [tool if protocol=='responses' else tool['function'] for tool in body['tools']]
                self.assertEqual([tool['name'] for tool in tools], tool_names(role))
                for tool in tools:
                    self.assertTrue(tool['strict'])
                    self.assertFalse(tool['parameters']['additionalProperties'])
                    self.assertEqual(set(tool['parameters']['required']), set(tool['parameters']['properties']))
                if role == 'commander':
                    properties = tools[1]['parameters']['properties']
                    self.assertEqual((properties['throttle']['minimum'],properties['throttle']['maximum']), (0,1))
                    self.assertEqual((properties['pitch']['minimum'],properties['pitch']['maximum']), (-1,1))

    def test_private_keys_tokens_native_paths_are_omitted_from_model_context(self):
        for protocol in ('responses', 'chat-completions'):
            provider, opener = self.provider(reply(protocol), protocol, key='UNIT_FAKE_BEARER')
            snapshot = context()
            before = deepcopy(snapshot)
            provider.decide('commander', snapshot, [{'action':'message','accepted':True}]*10)
            request = opener.calls[0][0]
            body_text = request.data.decode()
            for marker in ('UNIT_PRIVATE_NATIVE_PATH','UNIT_PRIVATE_PARTICIPANT','UNIT_PRIVATE_CONFIG','UNIT_FAKE_BEARER'):
                self.assertNotIn(marker, body_text)
            self.assertEqual(request.get_header('Authorization'), 'Bearer UNIT_FAKE_BEARER')
            body = json.loads(request.data)
            content = body['input'][0]['content'] if protocol=='responses' else body['messages'][1]['content']
            submitted = json.loads(content)
            self.assertEqual(len(submitted['recentCommandResults']), 6)
            self.assertNotIn('provenance', submitted['physics'])
            instruction = body['instructions'] if protocol=='responses' else body['messages'][0]['content']
            self.assertIn('untrusted', instruction)
            self.assertEqual(snapshot, before)

    def test_unknown_roles_and_unavailable_tools_fail_before_proposals_are_returned(self):
        provider, opener = self.provider(reply('responses'))
        with self.assertRaises(ValueError): provider.decide('mission-control',context(),[])
        self.assertFalse(opener.calls)
        for protocol in ('responses','chat-completions'):
            for role, tool in [('command-module-pilot','flight_controls'),
                               ('lunar-module-pilot','flight_controls'),('commander','set_state')]:
                provider, _ = self.provider(reply(protocol,tool),protocol)
                with self.assertRaises(ValueError):provider.decide(role,context(),[])

    def test_duplicate_nonfinite_malformed_and_nonobject_arguments_fail_closed(self):
        for protocol in ('responses','chat-completions'):
            for args in ('{"text":"a","text":"b"}','{"throttle":NaN}',
                         '{"throttle":Infinity}', '[]','null','false','{'):
                provider, _ = self.provider(reply(protocol,arguments=args),protocol)
                with self.assertRaises((ValueError,TypeError)):
                    provider.decide('commander',context(),[])
        for raw in (b'{"output":[],"output":[]}', b'null', b'[]', b'{', b'\xff'):
            provider, _ = self.provider(raw)
            with self.assertRaises((ValueError,TypeError,AttributeError)):
                provider.decide('commander',context(),[])

    def test_response_size_and_command_count_are_bounded(self):
        provider, opener = self.provider(b' '*262145)
        with self.assertRaisesRegex(ValueError,'bounded size'):provider.decide('commander',context(),[])
        self.assertEqual(opener.response.limit, 262145)
        for protocol in ('responses','chat-completions'):
            data = reply(protocol)
            if protocol=='responses':data['output']*=5
            else:data['choices'][0]['message']['tool_calls']*=5
            provider, _ = self.provider(data,protocol)
            with self.assertRaisesRegex(ValueError,'too many'):provider.decide('commander',context(),[])

    def test_timeout_propagates_for_the_service_to_use_labeled_fallback(self):
        provider, _ = self.provider(TimeoutError('synthetic provider timeout'))
        with self.assertRaises(TimeoutError):provider.decide('commander',context(),[])

    def test_provider_url_model_protocol_and_timeout_configuration_fail_closed(self):
        for url in ('ftp://provider.invalid','http://provider.invalid/v1',
                    'https://user:password@provider.invalid/v1','https://provider.invalid?key=private',
                    'https://provider.invalid#fragment'):
            with self.assertRaises(ValueError):ModelProvider(url,'unit-model')
        for timeout in (0,-1,11):
            with self.assertRaises(ValueError):ModelProvider('https://provider.invalid','unit-model',timeout=timeout)
        with self.assertRaises(ValueError):ModelProvider('https://provider.invalid','')
        with self.assertRaises(ValueError):ModelProvider('https://provider.invalid','unit-model',protocol='invented')
        self.assertIsInstance(ModelProvider('http://127.0.0.1:10000/v1','unit-model'), ModelProvider)


if __name__ == '__main__':unittest.main()
