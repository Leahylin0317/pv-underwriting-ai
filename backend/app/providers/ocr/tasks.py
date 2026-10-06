"""Independent watermark and business extraction with per-task failure isolation."""
from dataclasses import replace
from app.providers.common import ProviderError

WATERMARK_FIELDS = frozenset({'watermark_present','watermark_date','watermark_time','watermark_longitude','watermark_latitude','watermark_address','watermark_coordinate_system'})
WATERMARK_GUIDANCE = '''本次任务只提取现场照片的拍摄信息水印，不读取铭牌、包装标识、广告或监控系统时间。只有明确看到拍摄信息水印才提取 watermark_present=true；无法确认则标记 uncertain。提取清晰可见的 watermark_date（YYYY-MM-DD）、watermark_time、watermark_longitude、watermark_latitude、watermark_address、watermark_coordinate_system；坐标系按原文保留，不擅自换算。看不清或未出现的字段不猜测。'''


def extract_tasks(provider, material_input, *, raise_errors=False):
    from app.providers.routing import should_run_watermark_ocr, should_run_business_ocr
    fields, details = [], []
    for task, enabled in [('watermark',should_run_watermark_ocr(material_input)),('business',should_run_business_ocr(material_input))]:
        detail={'material_id':material_input.material.material_id,'task':task,'status':'skipped','field_ids':[],'reason':None}
        if not enabled:
            detail['reason']='未确认拍摄水印或该材料不适用' if task=='watermark' else '此类材料没有独立业务文字提取任务'
        else:
            try:
                output=provider.extract(replace(material_input,ocr_task=task))
                output=[f for f in output if (f.field_name in WATERMARK_FIELDS if task=='watermark' else not f.field_name.startswith('watermark_'))]
                for f in output:
                    item=f.model_copy(update={'field_id':f.field_id if all(existing.field_id!=f.field_id for existing in fields) else f.field_id+':'+task,'extraction_task':task})
                    fields.append(item);detail['field_ids'].append(item.field_id)
                detail['status']='success'
                if not output:detail['reason']='任务执行完成，但没有提取到可靠字段'
            except ProviderError:
                if raise_errors:raise
                detail['status']='failed';detail['reason']='字段提取服务失败，可单独重试此任务'
        details.append(detail)
    return fields,details
