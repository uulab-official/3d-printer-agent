"""Loopback web app: plan, generate CAD, review evidence, and prepare slicing."""
import base64
import binascii
from contextlib import asynccontextmanager
import json
import logging
import secrets
import sqlite3
import threading
import uuid
from pathlib import Path
from typing import Literal
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, model_validator
from starlette.middleware.trustedhost import TrustedHostMiddleware

from . import __version__
from .discovery import (
    DiscoveryRequest, ProjectSelection, StaleProjectSelection,
    project_catalog, recommend_projects, resolve_project_selection,
)
from .geometry import generate_model, template_catalog
from .offers import compare_offers
from .planner import plan_from_text, plan_with_llm, provider_config
from .preset_archive import import_preset_archive
from .preset_library import resolve_profile_documents
from .profiles import evaluate_profile, review_calibrations
from .runtime import DataDirectoryLease, require_compatible_data, resolve_data_directory
from .schemas import GeometryRequest
from .slicer import detect_environment, execute_slice, prepare_slice, prepare_project_slice, probe_environment
from .storage import ArtifactIntegrityError, JobRecordError, JobStore
from .studio_project import MAX_ARCHIVE_BYTES, MAX_IMPORT_REQUEST_BYTES
from .studio_sources import StudioProjectStore, StudioSourceIntegrityError
from .workspaces import ProfileWorkspaceStore, WorkspaceConflict

MAX_BODY = 2 * 1024 * 1024
MAX_WORKSPACE_BODY = 8 * 1024 * 1024
CAD_LOCK = threading.Lock()
SLICER_LOCK = threading.Lock()
LOGGER = logging.getLogger(__name__)


class LocalSessionMiddleware:
    """Keep a malicious web page from issuing local generation/native commands."""
    def __init__(self, app, token):
        self.app, self.token = app, token

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        headers = {key.decode('latin-1').lower():value.decode('latin-1') for key,value in scope.get('headers',[])}
        mutates = scope['path'].startswith('/api/') and scope['method'] not in ('GET','HEAD','OPTIONS')

        async def reject(code, detail, *, reason=None):
            content = {'detail':detail}
            if reason:
                content['code'] = reason
            await JSONResponse(content, status_code=code)(scope, receive, send)

        if mutates:
            # ASGI header values are arbitrary bytes. compare_digest(str, str)
            # rejects non-ASCII strings; byte comparison safely rejects them.
            if not secrets.compare_digest(headers.get('x-session-token','').encode('latin-1'), self.token.encode('ascii')):
                return await reject(403, '작업 공간의 연결이 만료됐습니다. 다시 연결하면 입력 내용을 유지할 수 있습니다.', reason='session_expired')
            origin = headers.get('origin')
            expected_origin = scope.get('scheme','http') + '://' + headers.get('host','')
            if origin is not None and origin != expected_origin:
                return await reject(403, '다른 웹사이트의 요청은 허용하지 않습니다.')
            if headers.get('content-type','').split(';')[0].strip().lower() != 'application/json':
                return await reject(415, 'JSON 요청 본문이 필요합니다.')
            # Full native configs and retained original/draft collections need
            # the same bounded import budget. Individual validators still apply.
            path = scope['path']
            large_import = (path in ('/api/slice', '/api/profiles/resolve', '/api/profiles/import-archive', '/api/profile-workspaces')
                            or path.startswith('/api/profile-workspaces/'))
            max_body = (MAX_IMPORT_REQUEST_BYTES if path == '/api/studio-projects/import'
                        else MAX_WORKSPACE_BODY if large_import else MAX_BODY)
            size_message = f'요청 전체는 {max_body // (1024 * 1024)} MiB 이하여야 합니다.'
            try:
                if int(headers.get('content-length','0')) > max_body:
                    return await reject(413, size_message)
            except ValueError:
                return await reject(400, '요청 길이가 올바르지 않습니다.')
            body = bytearray()
            while True:
                event = await receive()
                if event['type'] == 'http.disconnect':
                    return
                body.extend(event.get('body',b''))
                if len(body) > max_body:
                    return await reject(413, size_message)
                if not event.get('more_body',False):
                    break
            try:
                def reject_nonfinite(_):
                    raise ValueError('Nonfinite JSON')
                json.loads(body, parse_constant=reject_nonfinite)
            except (ValueError, UnicodeDecodeError, RecursionError):
                return await reject(400, '유효한 JSON이 필요합니다. NaN·Infinity는 허용하지 않습니다.')
            delivered = False
            original_receive = receive
            async def replay():
                nonlocal delivered
                if not delivered:
                    delivered = True
                    return {'type':'http.request','body':bytes(body),'more_body':False}
                return await original_receive()
            receive = replay

        async def security_send(event):
            if event['type'] == 'http.response.start':
                response_headers = list(event.get('headers',[]))
                response_headers.extend([
                    (b'x-content-type-options', b'nosniff'),
                    (b'referrer-policy', b'no-referrer'),
                    (b'content-security-policy', b"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'"),
                    (b'cache-control', b'no-store'),
                ])
                event = {**event,'headers':response_headers}
            await send(event)
        await self.app(scope, receive, security_send)


class StrictPayload(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class PlanPayload(StrictPayload):
    text: str = Field(min_length=1, max_length=4000)
    mode: Literal['templates','llm'] = 'templates'


class ModelPayload(GeometryRequest):
    """A source reference accompanies geometry; it never becomes CAD parameters."""
    project_selection: ProjectSelection | None = None


class ProfilePayload(StrictPayload):
    profile: dict = Field(default_factory=dict)
    setup: dict = Field(default_factory=dict)


class ProfileDocumentPayload(StrictPayload):
    filename: str = Field(min_length=1, max_length=240)
    profile: dict
    origin: dict | None = None


class ProfileArchivePayload(StrictPayload):
    filename: str = Field(min_length=1, max_length=240)
    # 4 MiB of archive bytes, including base64 padding. The middleware separately
    # enforces the whole JSON request budget before Pydantic or ZIP parsing.
    content_base64: str = Field(min_length=1, max_length=4 * ((4 * 1024 * 1024 + 2) // 3))


class ProfileBaselinePayload(StrictPayload):
    documents: list[ProfileDocumentPayload] = Field(min_length=1, max_length=64)
    # A previously unnamed input cannot establish a resolved original baseline.
    target_name: str = Field(max_length=256)


class ProfileResolvePayload(StrictPayload):
    documents: list[ProfileDocumentPayload] = Field(min_length=1, max_length=64)
    target_name: str = Field(min_length=1, max_length=256)
    setup: dict = Field(default_factory=dict)
    baseline: ProfileBaselinePayload | None = None


class WorkspaceCreatePayload(StrictPayload):
    # The store validates length after trimming surrounding whitespace.
    title: str
    snapshot: dict


class WorkspaceUpdatePayload(WorkspaceCreatePayload):
    expected_revision: int = Field(strict=True, ge=1)


class WorkspaceDeletePayload(StrictPayload):
    expected_revision: int = Field(strict=True, ge=1)


class CalibrationPayload(StrictPayload):
    records: list[dict] = Field(max_length=100)
    changes: dict


class OffersPayload(StrictPayload):
    offers: list[dict] = Field(min_length=1, max_length=50)


class SlicePayload(StrictPayload):
    job_id: str
    config_bundle: dict | None = None
    studio_project_id: str | None = Field(default=None, pattern=r'^[a-f0-9]{32}$')
    execute: bool = False

    @model_validator(mode='after')
    def one_source(self):
        if (self.config_bundle is None) == (self.studio_project_id is None):
            raise ValueError('전체 설정 묶음 또는 Studio 프로젝트 원본 중 하나만 선택하세요.')
        return self


class StudioProjectPayload(StrictPayload):
    filename: str = Field(min_length=1, max_length=240)
    content_base64: str = Field(min_length=1, max_length=4 * ((MAX_ARCHIVE_BYTES + 2) // 3))


class SlicerProbePayload(StrictPayload):
    """Only the server-configured executable may be probed."""


class OutcomePayload(StrictPayload):
    result: Literal['success','failure','not_tested']
    notes: str = Field(default='', max_length=4000)


def create_app(data_dir: Path | None = None, *, test_mode=False):
    selection = resolve_data_directory(data_dir)
    data_root = Path(selection['path'])
    recovery = {'indexed': 0, 'interrupted': 0, 'unreadable': 0}
    # Tests explicitly opt into an isolated, eagerly available factory. Normal
    # ASGI/CLI startup opens neither database until it owns the directory lease.
    store = JobStore(data_root) if test_mode else None
    workspaces = ProfileWorkspaceStore(data_root) if test_mode else None
    studio_sources = StudioProjectStore(data_root) if test_mode else None

    @asynccontextmanager
    async def lifespan(application):
        nonlocal store, workspaces, studio_sources, recovery
        if test_mode:
            yield
            return
        with DataDirectoryLease(data_root):
            require_compatible_data(data_root)
            store = JobStore(data_root)
            workspaces = ProfileWorkspaceStore(data_root)
            studio_sources = StudioProjectStore(data_root)
            recovery = store.recover()
            application.state.store = store
            application.state.workspaces = workspaces
            application.state.studio_sources = studio_sources
            yield

    token = secrets.token_urlsafe(32)
    app = FastAPI(title='3D Printer Agent', version=__version__, docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.state.store = store
    app.state.workspaces = workspaces
    app.state.studio_sources = studio_sources
    app.add_middleware(LocalSessionMiddleware, token=token)
    hosts = ['localhost','127.0.0.1'] + (['testserver'] if test_mode else [])
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=hosts)

    @app.exception_handler(ArtifactIntegrityError)
    async def artifact_integrity(_request, exception):
        return JSONResponse({'detail': str(exception), 'code': 'artifact_integrity'}, status_code=409)

    @app.exception_handler(JobRecordError)
    async def unreadable_job(_request, exception):
        return JSONResponse({'detail': str(exception), 'code': 'job_record_unreadable'}, status_code=409)

    @app.exception_handler(StudioSourceIntegrityError)
    async def studio_source_integrity(_request, exception):
        return JSONResponse({'detail': str(exception), 'code': 'studio_source_integrity'}, status_code=409)

    @app.exception_handler(OSError)
    @app.exception_handler(sqlite3.Error)
    async def storage_error(_request, exception):
        LOGGER.error('Local storage operation failed: exception=%s', type(exception).__name__)
        return JSONResponse({'detail': '저장 작업을 완료했는지 확인할 수 없습니다. 데이터 폴더의 권한·여유 공간을 확인한 뒤 작업 기록을 먼저 확인해 주세요.',
                             'code': 'storage_unavailable'}, status_code=503)

    @app.exception_handler(WorkspaceConflict)
    async def workspace_conflict(_request, exception):
        return JSONResponse({'detail': str(exception)}, status_code=409)

    @app.exception_handler(StaleProjectSelection)
    async def stale_project_selection(_request, exception):
        return JSONResponse({'detail': str(exception)}, status_code=409)

    @app.exception_handler(ValueError)
    async def value_error(_request, exception):
        return JSONResponse({'detail':str(exception)}, status_code=422)

    @app.exception_handler(KeyError)
    async def not_found(_request, _exception):
        return JSONResponse({'detail':'작업 또는 파일을 찾을 수 없습니다.'}, status_code=404)

    @app.get('/api/bootstrap')
    def bootstrap():
        return {'app':{'name':'3D Printer Agent','version':__version__},'templates':template_catalog(),
                'discovery':project_catalog(), 'environment':detect_environment(),
                'provider':provider_config(),'session_token':token,
                'storage': {**selection, 'recovery': dict(recovery)}}

    def resource_busy():
        return JSONResponse({'detail': '다른 작업이 이 컴퓨터의 생성·슬라이싱 기능을 사용하고 있습니다. 잠시 뒤 직접 다시 시도해 주세요.',
                             'code': 'resource_busy'}, status_code=409, headers={'Retry-After': '2'})

    @app.post('/api/discovery')
    def discovery(payload: DiscoveryRequest):
        return recommend_projects(payload)

    @app.post('/api/slicer/probe')
    def slicer_probe(_payload: SlicerProbePayload):
        if not SLICER_LOCK.acquire(blocking=False):
            return resource_busy()
        try:
            return probe_environment()
        finally:
            SLICER_LOCK.release()

    @app.post('/api/plan')
    async def plan(payload: PlanPayload):
        return await plan_with_llm(payload.text) if payload.mode == 'llm' else plan_from_text(payload.text)

    @app.post('/api/models')
    def models(payload: ModelPayload):
        spec = GeometryRequest.model_validate(payload.model_dump(exclude={'project_selection'}))
        design_source = (resolve_project_selection(payload.project_selection, spec)
                         if payload.project_selection is not None else None)
        if not CAD_LOCK.acquire(blocking=False):
            return resource_busy()
        job_id = None
        try:
            job_id, folder = store.reserve(request=spec.model_dump(), design_source=design_source)
            result = generate_model(spec,folder)
            return store.finish(job_id,result,design_source=design_source)
        except ValueError as exc:
            if job_id is not None:
                store.fail(job_id,str(exc))
            raise
        except Exception as exc:
            if job_id is not None:
                store.fail(job_id,'CAD 생성 중 오류가 발생했습니다. 치수를 줄이거나 다른 템플릿으로 다시 시도해주세요.')
            LOGGER.error('CAD generation failed: job=%s, exception=%s',job_id,type(exc).__name__)
            raise HTTPException(500,'CAD 생성에 실패했습니다. 작업 기록에서 상태를 확인할 수 있습니다.') from exc
        finally:
            CAD_LOCK.release()

    @app.get('/api/jobs')
    def jobs(limit: int | None = Query(default=None, ge=1, le=100), before: str | None = Query(default=None, max_length=512)):
        if limit is None and before is None:
            return {'jobs': store.list_jobs()}
        return store.list_jobs_page(limit=limit if limit is not None else 100, before=before)

    @app.get('/api/jobs/{job_id}')
    def job(job_id: str):
        return store.get(job_id)

    @app.get('/api/jobs/{job_id}/files/{kind}')
    def artifact(job_id: str, kind: str):
        path, content = store.read_artifact(job_id,kind)
        media = {'stl':'model/stl','step':'application/step','three_mf':'model/3mf',
                 'sliced_three_mf':'model/3mf','prepared_three_mf':'model/3mf',
                 'source':'text/plain','manifest':'application/json'}.get(kind,'application/octet-stream')
        filename = quote(path.name)
        disposition = f'attachment; filename="{path.name}"' if filename == path.name else "attachment; filename*=utf-8''" + filename
        return Response(content, media_type=media, headers={'Content-Disposition': disposition})

    @app.get('/api/jobs/{job_id}/bundle')
    def bundle(job_id: str):
        content = store.bundle(job_id)
        return Response(content,media_type='application/zip',headers={'Content-Disposition':f'attachment; filename="print-job-{job_id[:8]}.zip"'})

    @app.post('/api/jobs/{job_id}/outcome')
    def outcome(job_id: str,payload: OutcomePayload):
        return store.record_outcome(job_id,payload.result,payload.notes)

    @app.post('/api/profiles/review')
    def profile_review(payload: ProfilePayload):
        return evaluate_profile(payload.profile,payload.setup)

    @app.post('/api/profiles/import-archive')
    def profile_archive(payload: ProfileArchivePayload):
        try:
            content = base64.b64decode(payload.content_base64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError('묶음 파일을 다시 선택해 주세요. 올바른 base64 데이터가 필요합니다.') from exc
        return import_preset_archive(payload.filename, content)

    @app.post('/api/profiles/resolve')
    def profile_resolve(payload: ProfileResolvePayload):
        return resolve_profile_documents(
            [document.model_dump(exclude_unset=True) for document in payload.documents],
            payload.target_name,
            payload.setup,
            baseline=payload.baseline.model_dump(exclude_unset=True) if payload.baseline is not None else None,
        )

    @app.get('/api/profile-workspaces')
    def list_profile_workspaces():
        return {'workspaces': workspaces.list_workspaces()}

    @app.post('/api/profile-workspaces', status_code=201)
    def create_profile_workspace(payload: WorkspaceCreatePayload):
        return workspaces.create(payload.title, payload.snapshot)

    @app.get('/api/profile-workspaces/{workspace_id}')
    def get_profile_workspace(workspace_id: str):
        return workspaces.get(workspace_id)

    @app.put('/api/profile-workspaces/{workspace_id}')
    def update_profile_workspace(workspace_id: str, payload: WorkspaceUpdatePayload):
        return workspaces.update(workspace_id, payload.title, payload.snapshot, payload.expected_revision)

    @app.delete('/api/profile-workspaces/{workspace_id}')
    def delete_profile_workspace(workspace_id: str, payload: WorkspaceDeletePayload):
        return workspaces.delete(workspace_id, payload.expected_revision)

    @app.post('/api/calibrations/review')
    def calibration_review(payload: CalibrationPayload):
        return {'records':review_calibrations(payload.records,payload.changes)}

    @app.post('/api/offers/compare')
    def offers_compare(payload: OffersPayload):
        return compare_offers(payload.offers)

    @app.post('/api/studio-projects/import', status_code=201)
    def import_studio_project(payload: StudioProjectPayload):
        try:
            content = base64.b64decode(payload.content_base64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError('Studio 프로젝트 파일을 다시 선택해 주세요. 올바른 base64 데이터가 필요합니다.') from exc
        return studio_sources.import_project(payload.filename, content)

    @app.get('/api/studio-projects/{source_id}')
    def get_studio_project(source_id: str):
        return studio_sources.get(source_id)

    @app.get('/api/studio-projects/{source_id}/archive')
    def studio_project_archive(source_id: str):
        filename, content = studio_sources.archive(source_id)
        return Response(content, media_type='model/3mf',
                        headers={'Content-Disposition': "attachment; filename*=utf-8''" + quote(filename)})

    @app.post('/api/slice')
    def slice_model(payload: SlicePayload):
        job = store.get(payload.job_id)
        if job['status'] != 'geometry_validated':
            raise ValueError('형상 검증이 완료된 모델이 필요합니다.')
        if not SLICER_LOCK.acquire(blocking=False):
            return resource_busy()
        began = False
        try:
            store.begin_slice(payload.job_id)
            began = True
            input_path = store.artifact_path(payload.job_id,'three_mf')
            work_dir = store.directory(payload.job_id) / 'slices' / uuid.uuid4().hex
            if payload.studio_project_id is not None:
                snapshot, source_content = studio_sources.read(payload.studio_project_id)
                plan = prepare_project_slice(input_path, work_dir, snapshot['source']['filename'], source_content,
                                             source_id=payload.studio_project_id)
            else:
                plan = prepare_slice(input_path,work_dir,payload.config_bundle)
            execution = execute_slice(plan) if payload.execute and plan['ready'] else None
            store.record_slice(payload.job_id,plan,execution)
            return {'plan':plan,'execution':execution}
        except Exception as exc:
            if began:
                store.record_slice(payload.job_id,
                    {'ready': False, 'diagnostics': ['새 슬라이싱 요청을 완료하지 못했습니다. 설정과 저장 위치를 확인해 주세요.']},
                    {'status': 'failed', 'print_status': 'not_started', 'output_path': None})
            if isinstance(exc, (ValueError, KeyError, OSError, sqlite3.Error)):
                raise
            LOGGER.error('Slice operation failed: job=%s, exception=%s', payload.job_id, type(exc).__name__)
            raise HTTPException(500, '슬라이싱 요청을 완료하지 못했습니다. 작업 기록에서 마지막 상태를 확인해 주세요.') from exc
        finally:
            SLICER_LOCK.release()

    static_dir = Path(__file__).parent/'static'

    @app.get('/')
    def index():
        return FileResponse(static_dir/'index.html',media_type='text/html')

    @app.get('/favicon.ico')
    def favicon():
        return Response(status_code=204)

    app.mount('/static',StaticFiles(directory=static_dir,check_dir=False),name='static')
    return app
