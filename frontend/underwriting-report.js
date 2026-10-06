/* Presentation only: the server remains the source of underwriting decisions. */
(function(global){
const decisions={accept:'建议承保',recommend_reject:'建议拒保',surcharge:'建议加费',conditional_accept:'附条件承保',request_more:'需补充材料',manual_review:'需人工复核'};
const environment=new Set(['agriculture_environment','forest_environment','livestock_environment','fishery_environment','water_adjacent_environment','tidal_flat_environment','mountain_environment','desertification_environment']);
const rejectionRules=new Set(['ENV-EXCLUDED-001','IMG-SHADING-SEVERE-001','ELEC-UNPROTECTED-CABLE-REJECT-001','DOC-FILING-EXCLUDED-001']);
const neutral=new Set(['installation_type','cleanroom','monitoring_effective_coverage']);
const n=(tag,cls,text)=>{const el=document.createElement(tag);el.className=cls||'';if(text!=null)el.textContent=text;return el;};
function build(result){
 const reviews=result.material_reviews||[], findings=result.findings||[];
 const reviewFor=f=>reviews.filter(r=>r.material_id===f.material_id&&(r.finding_ids||[]).includes(f.finding_id));
 const rejectRule=f=>environment.has(f.category)?'ENV-EXCLUDED-001':f.category==='severe_shading'?'IMG-SHADING-SEVERE-001':f.category==='unprotected_cable'?'ELEC-UNPROTECTED-CABLE-REJECT-001':null;
 const decisive=[], risks=[], pending=[], observations=[];
 for(const f of findings){const refs=reviewFor(f), rule=rejectRule(f);const item={...f,rules:[...new Set(refs.flatMap(r=>r.triggered_rule_ids||[]))]};
  if(f.detection_status==='detected'&&rule&&refs.some(r=>(r.triggered_rule_ids||[]).includes(rule))){item.rules=[rule];decisive.push(item);}
  else if(f.detection_status==='uncertain'||f.category==='image_quality'&&f.detection_status==='detected'||f.requires_manual_review&&f.detection_status==='not_detected')pending.push(item);
  else if(f.detection_status==='detected'&&!neutral.has(f.category))risks.push(item);
  else observations.push(item);
 }
 const unique=xs=>[...new Set(xs.filter(Boolean))];
 const tasks=unique([...(result.package_assessment?.missing_requirements||[]),...(result.decision?.missing_requirements||[]),...reviews.flatMap(r=>r.missing_requirements||[])]).map(text=>({text,materials:unique(reviews.filter(r=>(r.missing_requirements||[]).includes(text)).map(r=>r.material_id))}));
 return {decisive,risks,pending,observations,tasks,reviews};
}
function screeningData(result){
 const a=result.catastrophe_assessment,c=result.component_profile,w=result.weather_profile;
 const stored=a?.comparisons||[];
 const rows=['wind','hail','snow'].map(hazard=>{
  const item=stored.find(r=>r.hazard===hazard);if(item)return {...item,persisted:true};
  const capacityKey={wind:'wind_load_pa',hail:'hail_resistance_mm',snow:'snow_load_pa'}[hazard];
  const eventKey={wind:'historical_max_wind_m_s',hail:'historical_max_hail_mm',snow:'historical_max_snow_load_pa'}[hazard];
  return {hazard,capacity:c?.[capacityKey]??null,event:w?.[eventKey]??null,demand:null,ratio:null,unit:hazard==='hail'?'mm':'Pa',status:a?'not_saved':'not_evaluated',risk:'unknown',persisted:false};
 });
 return {assessment:a,rows,calculated:rows.filter(r=>r.persisted&&r.status==='calculated').length,legacy:!!a&&!stored.length};
}
function renderScreening(report,result){
 const {assessment:a,rows,calculated,legacy}=screeningData(result),c=result.component_profile,w=result.weather_profile;
 const hazardNames={wind:'风灾',hail:'雹灾',snow:'雪灾'},riskNames={low:'余量充足',medium:'余量有限',high:'能力不足',critical:'明显不足',unknown:'无法完成综合判断'};
 const resistanceNames={high:'高',medium:'中',low:'低',unknown:'无法判断'};
 const section=n('section','uw-section uw-screening');section.append(n('h3','','自然灾害抗灾筛查'));report.append(section);
 const summary=n('div','uw-screening-summary');summary.append(n('strong','',a?riskNames[a.expected_loss_risk]||a.expected_loss_risk:'本次未执行抗灾评估'));
 summary.append(n('p','',a?.explanation||'本次记录没有抗灾评估结果，不能据此认定项目风险低。'));
 if(a)summary.append(n('div','uw-meta',`综合抗灾等级：${resistanceNames[a.resistance_level]||a.resistance_level} · ${a.requires_manual_review?'需人工复核':'当前规则未要求额外复核'}`));
 if(!legacy&&a)summary.append(n('div','uw-meta',`${calculated} / 3 项具备计算条件。程序执行完成与数据足够完成判断分别显示。`));
 if(legacy)summary.append(n('p','uw-meta','历史记录未保存逐项计算明细；以下保留原始输入与既有结论，不重新计算。重新运行整条链路可生成完整明细。'));
 const windTrace=(result.processing_trace||[]).find(t=>t.step==='catastrophe_assessment');if(windTrace)summary.append(n('div','uw-meta','评估程序：'+({success:'执行完成',partial:'部分完成',failed:'执行失败'}[windTrace.status]||windTrace.status)));
 section.append(summary);
 const f=value=>typeof value==='number'&&Number.isFinite(value)?value.toLocaleString('zh-CN',{maximumFractionDigits:3}):'—';
 const wrap=n('div','uw-screening-table');const table=n('table');const head=n('thead'),hr=n('tr');['灾害','组件能力','历史灾害指标','比较需求','能力比','检查结果'].forEach(text=>hr.append(n('th','',text)));head.append(hr);table.append(head);const body=n('tbody');
 for(const row of rows){const tr=n('tr');const status=row.status==='calculated'?riskNames[row.risk]:row.status==='insufficient'?'数据不足':row.status==='not_saved'?'明细未留存':'未评估';
  [hazardNames[row.hazard],row.capacity==null?'缺失':f(row.capacity)+' '+row.unit,row.event==null?'缺失':f(row.event)+' '+(row.hazard==='wind'?'m/s':row.unit),row.demand==null?'—':f(row.demand)+' '+row.unit,row.ratio==null?'—':f(row.ratio),status].forEach((text,index)=>tr.append(n(index===0?'th':'td',index===5?'uw-screening-state':'',text)));body.append(tr);
 }table.append(body);wrap.append(table);section.append(wrap);
 const details=n('details');details.append(n('summary','','计算过程、缺口与规则依据'));
 for(const row of rows){const item=n('div','uw-rule');item.append(n('strong','',hazardNames[row.hazard]));if(row.persisted){item.append(n('p','',row.formula));if(row.status==='calculated')item.append(n('p','',`${f(row.capacity)} ÷ ${f(row.demand)} = ${row.ratio==null?'未形成正值比较需求，不计算比值':f(row.ratio)}`));if(row.reason)item.append(n('p','',row.reason));if(row.rule_ids?.length)item.append(n('div','uw-meta','关联规则：'+row.rule_ids.join('、')));}else item.append(n('p','',a?'未保存该项计算过程，请以已有结论和原始依据为准。':'该项未评估。'));details.append(item);}
 if(a?.critical_shortfall_ratio!=null&&a?.adequate_margin_ratio!=null)details.append(n('p','',`本次阈值：能力比＜${a.critical_shortfall_ratio} 明显不足；${a.critical_shortfall_ratio}～＜1 能力不足；1～＜${a.adequate_margin_ratio} 余量有限；≥${a.adequate_margin_ratio} 余量充足。`));else details.append(n('p','uw-meta','此记录未留存完整阈值，不使用当前阈值解释历史结果。'));
 for(const factor of a?.factors||[])details.append(n('p','',factor));section.append(details);
 const sources=n('details');sources.append(n('summary','','组件参数与历史气象来源'));
 function source(title,profile){const box=n('div','uw-rule');box.append(n('strong','',title));if(!profile){box.append(n('p','',title+'未取得；该部分不能完成筛查。'));sources.append(box);return box;}box.append(n('p','',profile.source_name||'未留存数据来源'));
  if(profile.source_url&&/^https?:\/\//.test(profile.source_url)){const link=n('a','','查看数据来源');link.href=profile.source_url;link.target='_blank';link.rel='noopener';box.append(link);}if(profile.retrieved_at)box.append(n('div','uw-meta','取得时间：'+new Date(profile.retrieved_at).toLocaleString('zh-CN')));sources.append(box);return box;}
 const component=source('组件参数',c);if(c){component.append(n('p','',`型号：${c.component_model}；厂商：${c.manufacturer||'未提供'}`));if(c.front_static_load_pa!=null||c.back_static_load_pa!=null)component.append(n('p','uw-meta',`静态载荷参考：正面 ${f(c.front_static_load_pa)} Pa，背面 ${f(c.back_static_load_pa)} Pa；未自动当作风、雪荷载能力。`));for(const note of c.lookup_notes||[])component.append(n('p','uw-meta',note));for(const [key,url] of Object.entries(c.parameter_sources||{})){if(!/^https?:\/\//.test(url))continue;const p=n('p','uw-meta'),link=n('a','',key+' · 参数来源');link.href=url;link.target='_blank';link.rel='noopener';p.append(link);component.append(p);}}
 const weather=source('历史气象',w);if(w){weather.append(n('p','',`查询坐标：${w.longitude}, ${w.latitude}；观测范围：${w.observation_start||'未记录'} 至 ${w.observation_end||'未记录'}`),n('p','uw-meta',result.location_assessment?.weather_coordinates_verified?'气象查询位置已核验。':'气象数据按候选位置解读；位置尚未完成核验。'));if(w.historical_max_daily_snowfall_cm!=null)weather.append(n('p','uw-meta',`历史最大单日降雪 ${f(w.historical_max_daily_snowfall_cm)} cm，仅供气候背景参考，不自动换算为雪荷载。`));}
 section.append(sources,n('p','uw-meta','结果为组件抗灾能力与历史指标的筛查，不代表出险概率、预计赔款或整套电站承载合格；当前阈值仍需业务确认。'));
}
function render(root,result,{resolveSource=()=>null,renderLocation=()=>{},demo=false}={}){
 const data=build(result),decision=result.decision||{}, materials=result.materials||[], name=id=>materials.find(m=>m.material_id===id)?.file_name||id||'无来源材料';
 const report=n('article','uw-report');root.append(report);
 const gate=result.package_assessment;
 if(gate?.minimum_gate_passed!=null){const box=n('section','notice');box.append(n('strong','',`Demo 材料数量与视角门槛：${gate.minimum_gate_passed?'已达到':'未达到'}`),n('p','',`现场照片 ${gate.image_count} 张 · 全景 ${gate.panorama_count} 张 · 备案证 ${gate.has_filing_certificate?'已提供':'缺失'} · 证照图片 ${gate.document_image_count??0} 张（单独计数）`),n('p','','数量门槛与最终承保结论分别评估；后者还取决于识别证据、风险规则和抗灾数据。'));if(gate.coverage_requirements?.length)box.append(n('p','',`完整投保清单尚未覆盖：${gate.coverage_requirements.join('、')}。${gate.requirement_profile==='full_intake'?'当前执行完整清单门槛。':'当前执行 Demo 最低材料门槛；未覆盖类别列为后续收集项。'}`));report.append(box);}
 const header=n('header','uw-header');const heading=n('div');heading.append(n('div','uw-eyebrow',demo?'版式预览 · 示例数据，非真实核保结论':'核保审阅报告'),n('h2','',result.project?.project_name||'光伏项目 · 材料审查'));header.append(heading,n('span','uw-meta',result.case_id||'未提供案件编号'));report.append(header);
 const hero=n('section','uw-decision '+(decision.decision==='recommend_reject'?'reject':''));hero.append(n('div','uw-eyebrow','系统建议 · 待核保人员审阅'),n('h3','',decisions[decision.decision]||'尚未生成建议'));
 const basis=data.decisive.length?'已识别 '+data.decisive.length+' 项触发拒保规则的图片证据，请优先核对原图。':decision.decision==='recommend_reject'?'存在触发拒保的规则，请查看下方决定性规则依据及原始材料。':decision.decision==='request_more'?'现有资料不足以完成核保判断，请先处理补充材料与待核实事项。':decision.decision==='accept'?'现有规则给出承保建议；审阅时仍需核对证据与评估覆盖范围。':'请结合风险证据、规则依据及待核实事项完成审阅。';hero.append(n('p','',basis));
 const counts=n('div','uw-counts');for(const [count,label] of [[data.decisive.length,'拒保候选证据'],[data.risks.length,'其他风险提示'],[data.pending.length,'待核实检查项'],[data.tasks.length,'补充要求']]){const cell=n('div');cell.append(n('b','',count),n('span','',label));counts.append(cell);}hero.append(counts);report.append(hero);
 const status=n('div','uw-coverage');status.append(n('strong','','评估范围'),n('span','',materials.length+' 份材料'),n('span','',result.location_assessment?.status==='verified'?'位置已交叉核验':'位置尚未完成交叉核验'),n('span','',!result.weather_profile?'历史气象未取得，灾害评估依据不完整':result.location_assessment?.weather_coordinates_verified?'已取得核验位置的历史气象':'已取得候选位置气象，位置待核实'));report.append(status);
 function section(title,items,cls,empty){const s=n('section','uw-section '+(cls||''));s.append(n('h3','',title+' · '+items.length));if(!items.length)s.append(n('p','uw-empty',empty));report.append(s);return s;}
 function evidence(parent,f,kind){const card=n('article','uw-evidence');const top=n('div','uw-evidence-head');top.append(n('strong','',f.label||f.category),n('span','uw-badge '+kind,kind==='reject'?'触发拒保规则':kind==='pending'?'证据不足 / 待核实':'风险提示'));card.append(top,n('div','uw-meta','来源：'+name(f.material_id)),n('p','',f.evidence_text||'未提供可观察证据，需要核对原图。'));
  if(f.rules?.length)card.append(n('div','uw-meta','材料关联规则：'+f.rules.join('、')));
  if(f.confidence!=null)card.append(n('div','uw-meta','模型参考分 '+Math.round(f.confidence*100)+'% · 不代表风险发生概率'));
  const detail=n('details','uw-source');detail.append(n('summary','',f.bbox?'查看原图及模型定位':'查看原图（无可靠定位框）'));let loaded=false;detail.addEventListener('toggle',()=>{if(!detail.open||loaded)return;loaded=true;const source=resolveSource(f.material_id);if(!source?.url){detail.append(n('p','uw-empty','当前记录未保存可用原件，请从原始材料中核对。'));return;}if(source.pdf){const iframe=n('iframe');iframe.src=source.url;iframe.title=name(f.material_id);detail.append(iframe);return;}
   const wrap=n('div','uw-image');const img=n('img');img.src=source.url;img.alt=name(f.material_id);wrap.append(img);const b=f.bbox;if(b&&b.coordinate_space==='normalized_0_1'&&[b.x_min,b.y_min,b.x_max,b.y_max].every(x=>Number.isFinite(x)&&x>=0&&x<=1)&&b.x_max>b.x_min&&b.y_max>b.y_min){const box=n('div','uw-box '+kind);box.style.cssText=`left:${b.x_min*100}%;top:${b.y_min*100}%;width:${(b.x_max-b.x_min)*100}%;height:${(b.y_max-b.y_min)*100}%`;wrap.append(box);}detail.append(wrap,n('p','uw-meta',kind==='pending'?'虚线框表示待核实区域；未显示的区域不能据此认定无风险。':'框仅标示模型返回的证据位置，需核保人员核对。'));
  });card.append(detail);parent.append(card);
 }
 const priority=section(decision.decision==='recommend_reject'?'优先审阅 · 决定性依据':'本次建议依据',data.decisive,'uw-priority',decision.decision==='recommend_reject'?'没有返回可单独定位的拒保候选图片证据；请结合规则依据审阅。':'请展开规则依据，并结合下方补充要求与待核实事项审阅。');if(decision.decision!=='recommend_reject')priority.querySelector('h3').textContent='本次建议依据';data.decisive.forEach(f=>evidence(priority,f,'reject'));
 const rules=(decision.rule_explanations||[]).filter(r=>(decision.decisive_rule_ids||[]).includes(r.rule_id)&&(decision.decision!=='recommend_reject'||rejectionRules.has(r.rule_id)));if(rules.length){const d=n('details','uw-rule-details');d.append(n('summary','',(decision.decision==='recommend_reject'?'决定性规则依据':'建议关联规则')+' · '+rules.length));for(const r of rules){const row=n('div','uw-rule');row.append(n('strong','',r.title||r.rule_id),n('p','',r.trigger),n('p','',r.effect),n('div','uw-meta',r.rule_id));d.append(row);}priority.append(d);}
 for(const review of data.reviews.filter(r=>(r.triggered_rule_ids||[]).includes('DOC-FILING-EXCLUDED-001'))){const fields=(result.ocr_fields||[]).filter(f=>(review.ocr_field_ids||[]).includes(f.field_id));const card=n('article','uw-evidence');card.append(n('strong','','备案信息命中禁投规则'),n('div','uw-meta','来源：'+name(review.material_id)));for(const field of fields)card.append(n('p','',(field.field_name||'原文')+'：'+(field.raw_value||field.normalized_value||'未提取')));card.append(n('p','uw-meta','请核对备案原件与禁投关键词规则；此处展示该材料关联的文字证据。'));const source=resolveSource(review.material_id);if(source?.url){const a=n('a','','打开原始备案材料');a.href=source.url;a.target='_blank';a.rel='noopener';card.append(a);}priority.append(card);}
 const grid=n('div','uw-grid');report.append(grid);const risk=section('其他风险提示',data.risks,'','未返回其他已识别风险；这不代表所有区域均已检查。');grid.append(risk);data.risks.forEach(f=>evidence(risk,f,'risk'));const pending=section('待核实事项',data.pending,'','没有返回待核实检查项。');grid.append(pending);data.pending.forEach(f=>evidence(pending,f,'pending'));
 renderScreening(report,result);
 const tasks=section('补充材料与信息',data.tasks,'','本次规则未提出补充要求。');if(data.tasks.length){const list=n('ol','uw-tasks');data.tasks.forEach(t=>{const li=n('li');li.append(n('p','',t.text));if(t.materials.length)li.append(n('div','uw-meta','对应材料：'+t.materials.map(name).join('、')));list.append(li);});tasks.append(list,n('p','uw-meta','相同要求已合并；补充后需重新评估。'));
 }
 if(decision.conditions?.length){const s=section('承保条件',decision.conditions);decision.conditions.forEach(c=>s.append(n('p','',c)));}
 const audit=n('details','uw-audit');audit.append(n('summary','','完整核验记录与处理状态'));report.append(audit);renderLocation(audit,result.location_assessment,result.case_id);
 for(const f of data.observations)audit.append(n('p','',name(f.material_id)+' · '+(f.label||f.category)+' · '+({not_detected:'该图未发现',not_applicable:'不适用',detected:'观察信息'}[f.detection_status]||f.detection_status)+'：'+(f.evidence_text||'')));
 const allRules=n('details');allRules.append(n('summary','','全部已触发规则'));for(const rule of decision.rule_explanations||[])allRules.append(n('p','',(rule.title||rule.rule_id)+'：'+rule.trigger+'；'+rule.effect));audit.append(allRules);
 const original=n('details');original.append(n('summary','','查看系统原始依据'));for(const reason of decision.reasons||[])original.append(n('p','',reason));for(const warning of decision.warnings||[])original.append(n('p','',warning));audit.append(original);
 const trace=n('div','trace-list');for(const t of result.processing_trace||[])trace.append(n('span',t.status==='success'?'':'bad',({ocr:'文字提取',vision:'图片识别',equipment_inventory:'设备清单',component_lookup:'组件参数',weather_lookup:'历史气象',catastrophe_assessment:'灾害评估计算',rule_engine:'规则核验',decision:'建议生成'}[t.step]||t.step)+' · '+({success:'执行完成',partial:'部分完成',failed:'执行失败'}[t.status]||t.status)));audit.append(trace);for(const t of result.processing_trace||[])for(const task of t.task_executions||[]){const material=(result.materials||[]).find(m=>m.material_id===task.material_id);audit.append(n('p','',`${material?.file_name||task.material_id} · ${task.task==='watermark'?'拍摄水印提取':'业务文字提取'} · ${{success:'完成',failed:'失败',skipped:'跳过'}[task.status]||task.status}${task.reason?'：'+task.reason:''}`));}
 report.append(n('footer','uw-footer','系统建议供核保审阅；模型识别、未发现和证据不足均保留原始记录。最终结论以核保人员审核为准。'));return data;
}
global.UnderwritingReport={build,render,screeningData};if(typeof module!=='undefined')module.exports=global.UnderwritingReport;
})(typeof window==='undefined'?globalThis:window);
