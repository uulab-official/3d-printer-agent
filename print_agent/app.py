"""Loopback web app: plan, generate CAD, review evidence, and prepare slicing."""
import json
import logging
import os
import secrets
import threading
import uuid
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from . import __version__
from .geometry import generate_model, template_catalog
from .offers import compare_offers
from .planner import plan_from_text, plan_with_llm, provider_config
from .preset_library import resolve_profile_documents
from .profiles import evaluate_profile, review_calibrations
from .schemas import GeometryRequest
from .slicer import detect_environment, execute_slice, prepare_slice, probe_environment
from .storage import JobStore
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

        async def reject(code, detail):
            await JSONResponse({'detail':detail}, status_code=code)(scope, receive, send)

        if mutates:
            if not secrets.compare_digest(headers.get('x-session-token',''), self.token):
                return await reject(403, '현재 앱 화면에서 요청해주세요. 페이지를 새로 고치면 다시 연결됩니다.')
            origin = headers.get('origin')
            expected_origin = scope.get('scheme','http') + '://' + headers.get('host','')
            if origin is not None and origin != expected_origin:
                return await reject(403, '다른 웹사이트의 요청은 허용하지 않습니다.')
            if headers.get('content-type','').split(';')[0].strip().lower() != 'application/json':
                return await reject(415, 'JSON 요청 본문이 필요합니다.')
            # Full native configs and retained original/draft collections need
            # the same bounded import budget. Individual validators still apply.
            path = scope['path']
            large_import = (path in ('/api/slice', '/api/profiles/resolve', '/api/profile-workspaces')
                            or path.startswith('/api/profile-workspaces/'))
            max_body = MAX_WORKSPACE_BODY if large_import else MAX_BODY
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


class ProfilePayload(StrictPayload):
    profile: dict = Field(default_factory=dict)
    setup: dict = Field(default_factory=dict)


class ProfileDocumentPayload(StrictPayload):
    filename: str = Field(min_length=1, max_length=240)
    profile: dict


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
    config_bundle: dict
    execute: bool = False


class SlicerProbePayload(StrictPayload):
    """Only the server-configured executable may be probed."""


class OutcomePayload(StrictPayload):
    result: Literal['success','failure','not_tested']
    notes: str = Field(default='', max_length=4000)


def create_app(data_dir: Path | None = None, *, test_mode=False):
    data_root = data_dir or Path(os.getenv('PPA_DATA_DIR','data'))
    store = JobStore(data_root)
    workspaces = ProfileWorkspaceStore(data_root)
    token = secrets.token_urlsafe(32)
    app = FastAPI(title='3D Printer Agent', version=__version__, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.store = store
    app.state.workspaces = workspaces
    app.add_middleware(LocalSessionMiddleware, token=token)
    hosts = ['localhost','127.0.0.1'] + (['testserver'] if test_mode else [])
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=hosts)

    @app.exception_handler(WorkspaceConflict)
    async def workspace_conflict(_request, exception):
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
                'environment':detect_environment(),'provider':provider_config(),'session_token':token}

    @app.post('/api/slicer/probe')
    def slicer_probe(_payload: SlicerProbePayload):
        with SLICER_LOCK:
            return probe_environment()

    @app.post('/api/plan')
    async def plan(payload: PlanPayload):
        return await plan_with_llm(payload.text) if payload.mode == 'llm' else plan_from_text(payload.text)

    @app.post('/api/models')
    def models(payload: GeometryRequest):
        job_id, folder = store.reserve()
        try:
            with CAD_LOCK:
                result = generate_model(payload,folder)
            return store.finish(job_id,result)
        except ValueError as exc:
            store.fail(job_id,str(exc))
            raise
        except Exception as exc:
            store.fail(job_id,'CAD 생성 중 오류가 발생했습니다. 치수를 줄이거나 다른 템플릿으로 다시 시도해주세요.')
            LOGGER.error('CAD generation failed: job=%s, exception=%s',job_id,type(exc).__name__)
            raise HTTPException(500,'CAD 생성에 실패했습니다. 작업 기록에서 상태를 확인할 수 있습니다.') from exc

    @app.get('/api/jobs')
    def jobs():
        return {'jobs':store.list_jobs()}

    @app.get('/api/jobs/{job_id}')
    def job(job_id: str):
        return store.get(job_id)

    @app.get('/api/jobs/{job_id}/files/{kind}')
    def artifact(job_id: str, kind: str):
        path = store.artifact_path(job_id,kind)
        media = {'stl':'model/stl','step':'application/step','three_mf':'model/3mf',
                 'sliced_three_mf':'model/3mf','source':'text/plain','manifest':'application/json'}.get(kind,'application/octet-stream')
        return FileResponse(path,media_type=media,filename=path.name)

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

    @app.post('/api/profiles/resolve')
    def profile_resolve(payload: ProfileResolvePayload):
        return resolve_profile_documents(
            [document.model_dump() for document in payload.documents],
            payload.target_name,
            payload.setup,
            baseline=payload.baseline.model_dump() if payload.baseline is not None else None,
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

    @app.post('/api/slice')
    def slice_model(payload: SlicePayload):
        job = store.get(payload.job_id)
        if job['status'] != 'geometry_validated':
            raise ValueError('형상 검증이 완료된 모델이 필요합니다.')
        input_path = store.artifact_path(payload.job_id,'three_mf')
        work_dir = store.directory(payload.job_id) / 'slices' / uuid.uuid4().hex
        with SLICER_LOCK:
            plan = prepare_slice(input_path,work_dir,payload.config_bundle)
            execution = execute_slice(plan) if payload.execute and plan['ready'] else None
        store.record_slice(payload.job_id,plan,execution)
        return {'plan':plan,'execution':execution}

    static_dir = Path(__file__).parent/'static'

    @app.get('/')
    def index():
        return FileResponse(static_dir/'index.html',media_type='text/html')

    @app.get('/favicon.ico')
    def favicon():
        return Response(status_code=204)

    app.mount('/static',StaticFiles(directory=static_dir,check_dir=False),name='static')
    return app
