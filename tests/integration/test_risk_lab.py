from app.main import app
from app.rules.config import BusinessRulesConfig
from fastapi.testclient import TestClient

client=TestClient(app)

def payload():
    return {'mode':'simulated','component':{'component_model':'test','wind_load_pa':2400,'hail_resistance_mm':30,'snow_load_pa':5400,'source_name':'test','source_url':None,'retrieved_at':'2026-10-01T00:00:00Z','match_confidence':1},
            'weather':{'longitude':0,'latitude':0,'historical_max_wind_m_s':30,'historical_max_hail_mm':20,'historical_max_snow_load_pa':3000,'source_name':'test','retrieved_at':'2026-10-01T00:00:00Z'}}

def test_lab_exposes_working_page_and_calculation():
    assert client.get('/risk-lab').status_code==200
    assert client.get('/risk-lab.js').status_code==200
    r=client.post('/api/v1/risk/lab/assess',json=payload())
    assert r.status_code==200,r.text
    result=r.json();assert result['assessment']['expected_loss_risk']=='low'
    assert result['comparisons'][0]['demand']==0.613*30**2
    assert result['mode']=='simulated'

def test_threshold_overrides_are_isolated_and_marked():
    before=BusinessRulesConfig.load().model_dump()
    p=payload();p['mode']='real';p['adequate_margin_ratio']=3
    r=client.post('/api/v1/risk/lab/assess',json=p)
    assert r.status_code==200
    assert r.json()['mode']=='simulated'
    assert r.json()['thresholds_overridden'] is True
    assert r.json()['assessment']['expected_loss_risk']=='medium'
    assert BusinessRulesConfig.load().model_dump()==before

def test_zero_and_missing_inputs_are_explicit():
    p=payload();p['weather']['historical_max_hail_mm']=0;p['weather']['historical_max_snow_load_pa']=0
    r=client.post('/api/v1/risk/lab/assess',json=p)
    assert r.status_code==200
    assert r.json()['assessment']['expected_loss_risk']=='unknown'
    assert r.json()['comparisons'][1]['status']=='insufficient'
    missing=client.post('/api/v1/risk/lab/assess',json={})
    assert missing.status_code==200
    assert all(x['status']=='insufficient' for x in missing.json()['comparisons'])

def test_invalid_query_and_threshold_inputs_are_rejected_before_lookup():
    assert client.post('/api/v1/risk/lab/weather',json={'longitude':181,'latitude':0}).status_code==422
    assert client.post('/api/v1/risk/lab/weather',json={'longitude':0,'latitude':0,'observation_start':'2026-01-01'}).status_code==422
    assert client.post('/api/v1/risk/lab/assess',json={**payload(),'critical_shortfall_ratio':0}).status_code==422
