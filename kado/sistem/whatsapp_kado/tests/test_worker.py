import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# Unit tests require no user configuration or network.
sys.modules['app_config'] = types.SimpleNamespace(load_app_config=lambda: {})
import worker

class WorkerTests(unittest.TestCase):
    config = {'gemini_api_key': 'fake', 'whatsapp_model': 'test-model'}
    def reply(self):
        return {'candidates': [{'content': {'parts': [{'text': 'Merhaba, ben Kado yapay zeka asistanı.'}]}}]}

    def test_history_isolation(self):
        brain = worker.Brain()
        with patch.object(worker, 'load_app_config', return_value=self.config), patch.object(worker, 'request_json', return_value=self.reply()) as call:
            brain.answer({'chat': 'customer-A', 'text': 'A secret'})
            brain.answer({'chat': 'customer-B', 'text': 'B question'})
            body = call.call_args.args[2]
            self.assertNotIn('A secret', str(body))
            self.assertEqual(len(body['contents']), 1)
            brain.answer({'chat': 'customer-A', 'text': 'again'})
            self.assertEqual(len(call.call_args.args[2]['contents']), 3)

    def test_voice_failure_retains_text(self):
        with patch.object(worker, 'load_app_config', return_value=self.config), patch.object(worker, 'request_json', return_value=self.reply()), patch.object(worker.Brain, 'speak', side_effect=ValueError('missing')):
            result = worker.Brain().answer({'chat': 'A', 'text': 'hello', 'voice': True})
            self.assertTrue(result['voice_failed'])
            self.assertTrue(result['text'])
            self.assertNotIn('audio', result)

    def test_audio_not_retained(self):
        import base64
        payload = {'chat': 'A', 'audio': {'mime': 'audio/ogg; codecs=opus', 'data': base64.b64encode(b'audio').decode()}}
        brain = worker.Brain()
        with patch.object(worker, 'load_app_config', return_value=self.config), patch.object(worker, 'request_json', return_value=self.reply()) as call, patch.object(worker.Brain, 'speak', return_value='sound'):
            brain.answer(payload)
            self.assertEqual(call.call_args.args[2]['contents'][0]['parts'][0]['inlineData']['mimeType'], 'audio/ogg')
            self.assertNotIn('inlineData', str(brain.history))

    def test_no_key_no_network(self):
        with patch.object(worker, 'load_app_config', return_value={}), patch.object(worker, 'request_json') as call:
            with self.assertRaises(ValueError): worker.Brain().answer({'text': 'x'})
            call.assert_not_called()

    def test_empty_model_output_does_not_pollute_history(self):
        brain = worker.Brain()
        with patch.object(worker, 'load_app_config', return_value=self.config), patch.object(worker, 'request_json', return_value={'candidates': []}):
            with self.assertRaises(ValueError): brain.answer({'chat': 'A', 'text': 'x'})
            self.assertFalse(brain.history)

    def test_history_bounded(self):
        brain = worker.Brain()
        with patch.object(worker, 'load_app_config', return_value=self.config), patch.object(worker, 'request_json', return_value=self.reply()):
            for _ in range(15): brain.answer({'chat': 'A', 'text': 'hello'})
        self.assertEqual(len(brain.history['A'][1]), 12)

if __name__ == '__main__': unittest.main()
