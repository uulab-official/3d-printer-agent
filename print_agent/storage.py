"""Per-job artifacts with atomic manifests and a small SQLite history index."""
import copy
import hashlib
import io
import json
import re
import sqlite3
import threading
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from . import __version__


def now_iso():
    return datetime.now(timezone.utc).isoformat()


class JobStore:
    def __init__(self, root: Path):
        self.root = Path(root).expanduser().resolve()
        self.jobs_dir = self.root / 'jobs'
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.root / 'history.sqlite3'
        self.lock = threading.RLock()
        with sqlite3.connect(self.db_path) as db:
            db.execute('CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, created_at TEXT NOT NULL, title TEXT NOT NULL, template TEXT, status TEXT NOT NULL, user_outcome TEXT)')

    def directory(self, job_id: str) -> Path:
        if not isinstance(job_id, str) or not re.fullmatch(r'[a-f0-9]{32}', job_id):
            raise ValueError('올바른 작업 ID가 필요합니다.')
        folder = self.jobs_dir / job_id
        if folder.is_symlink():
            raise ValueError('작업 폴더는 심볼릭 링크일 수 없습니다.')
        return folder

    def _write(self, job):
        folder = self.directory(job['id'])
        destination = folder / 'job.json'
        temporary = folder / ('.job-' + uuid.uuid4().hex + '.tmp')
        temporary.write_text(json.dumps(job, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
        temporary.replace(destination)
        with sqlite3.connect(self.db_path) as db:
            db.execute('INSERT OR REPLACE INTO jobs VALUES (?,?,?,?,?,?)', (
                job['id'], job['created_at'], job['title'], job.get('template'), job['status'],
                json.dumps(job.get('user_outcome'), ensure_ascii=False)))

    def _read(self, job_id):
        path = self.directory(job_id) / 'job.json'
        if not path.is_file():
            raise KeyError('작업을 찾을 수 없습니다.')
        return json.loads(path.read_text(encoding='utf-8'))

    @staticmethod
    def _public(job):
        return {key:value for key,value in job.items() if not key.startswith('_')}

    def reserve(self):
        with self.lock:
            job_id = uuid.uuid4().hex
            folder = self.directory(job_id)
            folder.mkdir(mode=0o700)
            created = now_iso()
            self._write({'id':job_id, 'created_at':created, 'title':'모델 생성 중', 'template':None,
                         'status':'generating','result':None,'artifacts':{},'_files':{},'bundle_url':None,
                         'events':[],'latest_slice':None,'user_outcome':None})
            return job_id, folder

    def finish(self, job_id, result):
        expected = {'stl':'model.stl','step':'model.step','three_mf':'model.3mf','source':'model.py'}
        with self.lock:
            job = self._read(job_id)
            folder = self.directory(job_id)
            hashes = {}
            for kind, filename in result['files'].items():
                if expected.get(kind) != filename:
                    raise ValueError('허용되지 않은 생성 파일입니다.')
                path = folder / filename
                if path.is_symlink() or not path.is_file() or path.stat().st_size <= 0:
                    raise ValueError('생성 파일의 내용이 없습니다.')
                hashes[kind] = {'filename':filename,'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
            manifest = {
                'schema_version':1,'app_version':__version__,'job_id':job_id,'created_at':job['created_at'],
                'template':result['template'],'units':'mm','parameters':result['parameters'],
                'dimensions_mm':result['dimensions_mm'],'volume_mm3':result['volume_mm3'],
                'geometry_status':result['geometry_status'],'physical_print_status':'not_tested',
                'slicer_status':'not_run','checks':result['checks'],'warnings':result['warnings'],
                'artifacts':hashes,
            }
            (folder / 'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
            job['_files'] = {**result['files'],'manifest':'manifest.json'}
            job['artifacts'] = {kind:f'/api/jobs/{job_id}/files/{kind}' for kind in job['_files']}
            job['bundle_url'] = f'/api/jobs/{job_id}/bundle'
            job['result'] = copy.deepcopy(result)
            job['template'] = result['template']
            title = {'tray':'칸막이 수납함','cable_comb':'열린 케이블 받침','magnet_frame':'원형 인셋 프레임'}[result['template']]
            size = result['dimensions_mm']
            job['title'] = f"{title} · {size['x']:g} × {size['y']:g} × {size['z']:g} mm"
            job['status'] = 'geometry_validated'
            job['events'].append({'at':now_iso(),'type':'geometry_validated','message':'CAD 형상 검증 및 파일 내보내기 완료. 실물 출력은 미검증입니다.'})
            self._write(job)
            return self._public(job)

    def fail(self, job_id, message):
        with self.lock:
            job = self._read(job_id)
            job['status'] = 'failed'
            job['title'] = '모델 생성 실패'
            job['events'].append({'at':now_iso(),'type':'generation_failed','message':str(message)[:1000]})
            self._write(job)

    def get(self, job_id):
        with self.lock:
            return self._public(self._read(job_id))

    def list_jobs(self):
        with self.lock, sqlite3.connect(self.db_path) as db:
            db.row_factory = sqlite3.Row
            rows = db.execute('SELECT * FROM jobs ORDER BY created_at DESC LIMIT 100').fetchall()
            return [{**dict(row),'user_outcome':json.loads(row['user_outcome'])} for row in rows]

    def artifact_path(self, job_id, kind):
        with self.lock:
            job = self._read(job_id)
            filename = job['_files'].get(kind)
            if not filename:
                raise KeyError('등록된 파일이 없습니다.')
            folder = self.directory(job_id)
            path = folder / filename
            if path.is_symlink() or not path.resolve().is_relative_to(folder.resolve()) or not path.is_file():
                raise ValueError('파일 경로를 확인할 수 없습니다.')
            return path

    def bundle(self, job_id):
        with self.lock:
            job = self._read(job_id)
            if not job['artifacts']:
                raise KeyError('내려받을 생성 파일이 없습니다.')
            stream = io.BytesIO()
            with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
                for kind in job['_files']:
                    path = self.artifact_path(job_id,kind)
                    archive.write(path,arcname=path.name)
                archive.writestr('job.json',json.dumps(self._public(job),ensure_ascii=False,indent=2,allow_nan=False))
            return stream.getvalue()

    def record_outcome(self, job_id, result, notes):
        if result not in ('success','failure','not_tested') or not isinstance(notes,str) or len(notes)>4000:
            raise ValueError('출력 결과와 4,000자 이내의 메모가 필요합니다.')
        with self.lock:
            job = self._read(job_id)
            report = {'result':result,'notes':notes,'source':'user_reported','recorded_at':now_iso()}
            job['user_outcome'] = report
            job['events'].append({'at':now_iso(),'type':'user_reported_outcome','message':result,'report':report})
            self._write(job)
            return self._public(job)

    def record_slice(self, job_id, plan, execution):
        with self.lock:
            job = self._read(job_id)
            job['latest_slice'] = {'recorded_at':now_iso(),'plan':plan,'execution':execution}
            # A previous run must not masquerade as the result of new settings.
            job['_files'].pop('sliced_three_mf',None)
            job['artifacts'].pop('sliced_three_mf',None)
            if execution and execution.get('output_path') and execution['status'] in ('sliced','needs_review'):
                path = Path(execution['output_path']).resolve()
                folder = self.directory(job_id).resolve()
                if not path.is_relative_to(folder) or not path.is_file() or path.suffix.lower() != '.3mf':
                    raise ValueError('슬라이싱 파일 경로가 올바르지 않습니다.')
                job['_files']['sliced_three_mf'] = str(path.relative_to(folder))
                job['artifacts']['sliced_three_mf'] = f'/api/jobs/{job_id}/files/sliced_three_mf'
            status = execution['status'] if execution else ('prepared' if plan['ready'] else 'blocked')
            job['events'].append({'at':now_iso(),'type':'slicer_'+status,'message':'프린터 실행은 수행하지 않았습니다.'})
            self._write(job)
            return self._public(job)
