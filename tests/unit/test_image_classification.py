import json
from io import BytesIO
from unittest.mock import patch

import httpx
import pytest
from app.providers.common import ProviderError
from app.providers.vision.classification import classify_image
from app.settings import VlmSettings
from PIL import Image


def photo():
    out = BytesIO()
    Image.new('RGB', (640, 480), 'white').save(out, format='PNG')
    return out.getvalue()


def test_high_score_still_needs_confirmation_and_keeps_multiple_uses():
    def handler(request):
        body = json.loads(request.content)
        assert '不依据文件名' in body['messages'][0]['content']
        return httpx.Response(200, json={'choices': [{'message': {'content': json.dumps({
            'category': 'panorama', 'confidence': .99, 'reason': '可见阵列布局',
            'alternatives': [{'category': 'component_surface', 'confidence': .75,
                              'reason': '部分组件表面清晰可见'}]})}}]})
    client = httpx.Client(transport=httpx.MockTransport(handler))
    with patch('app.providers.vision.classification.httpx.Client', return_value=client):
        result = classify_image(photo(), VlmSettings('https://example.com', 'secret', 'test'))
    assert result['requires_confirmation'] is True
    assert [c['category'] for c in result['candidates']] == ['panorama', 'component_surface']
    assert 'secret' not in json.dumps(result)


def test_invalid_category_is_rejected_instead_of_routing_checks():
    def handler(request):
        return httpx.Response(200, json={'choices': [{'message': {'content':
            '{"category":"invented","confidence":0.99,"reason":"test","alternatives":[]}'}}]})
    with (
        patch(
            'app.providers.vision.classification.httpx.Client',
            return_value=httpx.Client(transport=httpx.MockTransport(handler)),
        ),
        pytest.raises(ProviderError, match='分类失败'),
    ):
        classify_image(photo(), VlmSettings('https://example.com', 'secret', 'test'))
