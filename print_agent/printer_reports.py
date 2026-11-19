"""A printer's own finish/failure report, linked to the job this app sent.

Pure helpers. The record is what the printer reported (``source: printer_reported``),
kept apart from the person's outcome and measurements. Codes are shown as reported
and looked up by the person on Bambu Lab's own HMS search; this module never guesses
what a code means.
"""
from __future__ import annotations

TERMINAL_STATES = ('FINISH', 'FAILED')
HMS_SEARCH_URL = 'https://wiki.bambulab.com/en/hms/home'
MAX_CODES = 16


def subtask_for(job_id: str) -> str:
    """The job name this app gives a print it sends (see the print review)."""
    return f'printer-agent {job_id[:8]}'


def _dashed(code: str, groups: int) -> str | None:
    text = str(code or '').replace('_', '').replace('-', '').upper()
    if len(text) != groups * 4 or any(ch not in '0123456789ABCDEF' for ch in text):
        return None
    return '-'.join(text[index:index + 4] for index in range(0, len(text), 4))


def codes_of(printing: dict) -> list[dict]:
    """Reported error and HMS codes in the dash form Bambu Lab's search accepts."""
    codes = []
    error = _dashed(printing.get('error_code_hex'), 2) if printing.get('error_code') else None
    if error:
        codes.append({'kind': 'print_error', 'code': error})
    for entry in (printing.get('hms') or [])[:MAX_CODES]:
        hms = _dashed(entry.get('hms_code') if isinstance(entry, dict) else None, 4)
        if hms and all(item['code'] != hms for item in codes):
            codes.append({'kind': 'hms', 'code': hms})
    return codes


def terminal_record(job_id: str, serial: str, printing: dict, observed_at: str) -> tuple[dict | None, str]:
    """Build the stored record, or explain why this report does not belong to the job."""
    state = printing.get('state')
    if state not in TERMINAL_STATES:
        return None, '프린터가 아직 완료나 실패를 보고하지 않았습니다.'
    if printing.get('job_name') != subtask_for(job_id):
        return None, '프린터가 보고한 작업 이름이 이 모델을 보낸 작업과 달라 기록하지 않았습니다.'
    record = {'source': 'printer_reported', 'state': state, 'state_label': printing.get('state_label'),
              'observed_at': observed_at, 'serial': serial, 'job_name': printing.get('job_name'),
              'progress_percent': printing.get('progress_percent'), 'layer': printing.get('layer'),
              'total_layers': printing.get('total_layers'), 'codes': codes_of(printing)}
    return record, ''


def same_report(left: dict | None, right: dict | None) -> bool:
    if not isinstance(left, dict) or not isinstance(right, dict):
        return False
    keys = ('state', 'serial', 'job_name', 'progress_percent', 'layer', 'codes')
    return all(left.get(key) == right.get(key) for key in keys)


def recovery_item(report: dict | None) -> dict | None:
    """A first step for a printer-reported failure: check its own codes. No meaning is inferred."""
    if not isinstance(report, dict) or report.get('state') != 'FAILED':
        return None
    codes = [item['code'] for item in report.get('codes') or [] if isinstance(item, dict) and item.get('code')]
    where = []
    if report.get('layer') and report.get('total_layers'):
        where.append(f'{report["layer"]}/{report["total_layers"]} 레이어')
    if report.get('progress_percent') is not None:
        where.append(f'{report["progress_percent"]}%')
    stopped = f' ({", ".join(where)}에서 멈춤)' if where else ''
    actions = [f'프린터가 {report.get("observed_at") or "읽은 시각"}에 이 작업의 실패를 보고했습니다{stopped}.']
    if codes:
        actions.append(f'보고된 코드: {", ".join(codes)}. Bambu Lab 위키 HMS 검색에서 이 코드를 찾아 원인과 조치를 확인하세요.')
    else:
        actions.append('프린터가 오류 코드를 함께 보고하지 않았습니다. 사람이 정지했는지, 프린터 화면에 알림이 있는지 확인하세요.')
    actions.append('이 앱은 코드의 뜻을 해석하지 않습니다. 실물을 확인하고 아래에서 원인을 골라 기록하세요.')
    return {'reason': 'printer_reported', 'label': '프린터가 보고한 실패', 'actions': actions, 'model_edit': None,
            'codes': codes, 'lookup_url': HMS_SEARCH_URL if codes else None}
