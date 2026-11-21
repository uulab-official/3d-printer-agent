(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const state = { offersResult: null, historyFilter: "all", downloadedJobId: null, printabilityReview: null, printabilityRequest: 0, printabilityPending: false, printabilityNozzle: 0.4, printabilityShown: false, printerPins: {}, printerStatus: null, printerRequest: 0, modelEditCandidate: null, modelEditApplied: null, modelEditAppliedSignature: null, modelEditRequest: 0, modelEditPending: false, modelEditBusyRequest: null, studioWorkspaceId: null, studioWorkspaceRevision: null, studioWorkspaceSavedSignature: null, studioWorkspaceCandidate: null, studioWorkspaceEpoch: 0, studioWorkspaceRequest: 0, studioWorkspaceBusy: false, studioLibraryItems: [], studioLibraryCursor: null, studioLibraryRequest: 0, studioLibraryPending: false, studioSettingsOpen: false, studioSettingsDescriptor: null, studioSettingsDraft: null, studioSettingsReview: null, studioSettingsReviewContext: null, studioSettingsPending: false, studioSettingsApplied: null, studioSettingsCandidate: null, studioSettingsRecorded: null, studioSettingsRecordedReview: null, studioRequest: 0, studioRevision: 0, studioPending: false, studioPendingName: "", studioCandidate: null, studioCandidateEpoch: null, studioCandidateStorage: null, studioApplied: null, studioAppliedEpoch: null, studioAppliedStorage: null, studioRecorded: null, studioSlicePrepared: false, studioPreparedSignature: null, studioSavedIdentity: null, offersRevision: 0, offersPending: false, retainedOutcomeDrafts: [], connectionState: "connecting", connectionEpoch: 0, bootstrapPending: false, storage: null, modelCleanSignature: null, modelReplacement: null, modelTransitionRequest: 0, slicerSavedText: "", historyItems: [], historyLoaded: false, historyRequest: 0, historyPending: false, historyCursor: null, discovery: null, discoveryPurpose: "all", discoveryMatches: [], discoveryBrowsed: null, discoveryPending: false, discoveryStale: false, discoveryRequest: 0, discoveryEpoch: 0, discoveryRevision: 0, projectSource: null, projectReplacement: null, bootstrapRequest: 0, token: null, templates: [], template: null, parameters: {}, environment: {}, provider: {}, job: null, slicePrepared: false, workflowBusy: false, slicerFiles: { machine: null, process: null, filaments: [] }, slicerStaged: false, slicerContext: 0, slicerRequests: {}, slicerPending: {}, profileDocuments: [], profileTarget: 0, profileRevision: 0, profileImport: 0, profileReport: null, profileDownloadUrl: null, guidedEdits: {}, guidedSources: {}, workspaceId: null, workspaceRevision: null, workspaceSavedSignature: null, workspaceEpoch: 0, workspaceEdits: 0, workspaceListRequest: 0, workspaceBusy: false, workspaces: [] };
  const pageNames = { models: "모델 만들기", imports: "가진 모델 점검", profiles: "재료 설정", offers: "구매 비교", printers: "프린터 상태", history: "작업 기록" };
  const fields = {
    width: { label: "가로", min: 10, max: 500, step: 0.1 },
    depth: { label: "세로", min: 10, max: 500, step: 0.1 },
    height: { label: "높이", min: 2, max: 300, step: 0.1 },
    wall: { label: "벽 두께", min: 0.8, max: 20, step: 0.1 },
    bottom: { label: "바닥 두께", min: 0.8, max: 20, step: 0.1 },
    dividers: { label: "칸막이 수", min: 0, max: 12, step: 1, unit: "개" },
    slots: { label: "케이블 홈 수", min: 1, max: 20, step: 1, unit: "개" },
    cable_diameter: { label: "케이블 지름", min: 1, max: 30, step: 0.1 },
    inset_diameter: { label: "원판 지름", min: 5, max: 450, step: 0.1 },
    inset_depth: { label: "포켓 깊이", min: 0.5, max: 30, step: 0.1 },
    fit_clearance: { label: "지름 여유", min: 0, max: 3, step: 0.05 },
    lean_angle: { label: "등판 각도", min: 50, max: 80, step: 1, unit: "°" },
    device_thickness: { label: "기기 두께(케이스 포함)", min: 4, max: 30, step: 0.1 },
    lip_height: { label: "앞턱 높이", min: 3, max: 60, step: 0.1 },
    text: { label: "글자", kind: "text", maxLength: 20, unit: "" },
    text_size: { label: "글자 크기", min: 3, max: 40, step: 0.5 },
    text_depth: { label: "글자 높이", min: 0.6, max: 6, step: 0.1 },
    hole_diameter: { label: "고리 구멍 지름", min: 2, max: 10, step: 0.1 },
    key_units: { label: "키 크기", min: 1, max: 7, step: 0.25, unit: "u" },
    drain_hole: { label: "배수 구멍 지름", min: 0, max: 30, step: 0.5 },
    color: { label: "모델 색", kind: "color", unit: "" },
    accent_color: { label: "글자 색", kind: "color", unit: "" },
  };
  // Same keys and names as schemas.PALETTE. Hex values only approximate the filament on screen.
  const PALETTE = {
    white: ["흰색", "#F4F4F1"], black: ["검정", "#232323"], gray: ["회색", "#8E9096"],
    red: ["빨강", "#D2302C"], orange: ["주황", "#F07F1F"], yellow: ["노랑", "#F4C430"],
    green: ["초록", "#2E9E4F"], blue: ["파랑", "#2563C9"], purple: ["보라", "#7B4BB8"],
    pink: ["분홍", "#EE7FB2"], brown: ["갈색", "#8B5A2B"],
  };
  // Optional colours: an empty value means "not chosen" and is never an incomplete input.
  const COLOR_PARAMETERS = new Set(["color", "accent_color"]);
  // Fields read and sent as strings rather than numbers.
  const TEXT_PARAMETERS = new Set(["text"]);
  const STRING_PARAMETERS = new Set([...TEXT_PARAMETERS, ...COLOR_PARAMETERS]);
  // Editing panel: one-line explanations, the +/- step and the group of each field.
  const fieldDescriptions = {
    width: "바깥 가로 길이(좌우)", depth: "바깥 세로 길이(앞뒤)", height: "바닥에서 가장 높은 곳까지",
    wall: "옆벽 두께. 노즐 지름의 2배 이상이면 튼튼합니다", bottom: "바닥판 두께",
    dividers: "가로 방향 칸막이 개수(칸 수 − 1)", slots: "케이블을 올릴 U자 홈 개수", cable_diameter: "올릴 케이블의 바깥 지름",
    inset_diameter: "넣을 원판·사진의 지름", inset_depth: "포켓이 파이는 깊이", fit_clearance: "넣을 물건보다 넓게 두는 여유",
    lean_angle: "바닥에서 등판까지의 각도. 클수록 똑바로 섭니다", device_thickness: "케이스를 포함한 기기 두께", lip_height: "앞에서 기기를 받치는 턱 높이",
    text: "키링에 새길 글자(한글·영문·숫자, 20자 이하)", text_size: "글자의 높이. 8 mm 이상이면 획이 잘 나옵니다", text_depth: "받침판 위로 솟은 글자 높이",
    hole_diameter: "고리나 줄을 끼울 구멍 지름",
    drain_hole: "바닥 가운데 구멍 지름. 0이면 구멍이 없고, 낼 때는 막히지 않게 3 mm 이상으로 하세요",
    key_units: "1u = 19.05 mm 간격. 1·1.25·1.5·1.75·2·2.25·2.75·6.25·7u를 만들 수 있고, 2u 이상은 스태빌라이저 스템이 붙습니다",
    color: "출력할 필라멘트 색. 화면 색은 비슷하게 보여 줄 뿐입니다",
    accent_color: "글자만 다른 색으로 뽑을 때 고릅니다(AMS 등 자동 교체 필요)",
  };
  const templateFieldDescriptions = { cup: { width: "컵의 바깥 지름(가로·세로가 같음)", height: "바닥에서 컵 위 끝까지", wall: "원통 옆벽 두께", bottom: "컵 바닥 두께" }, phone_stand: { wall: "등판과 앞턱의 두께", fit_clearance: "홈 폭에 더하는 여유" }, name_tag: { wall: "글자 둘레와 구멍 둘레에 남길 판 폭", bottom: "글자를 받치는 판의 두께" }, wall_hook: { width: "후크의 폭(벽에 붙는 면의 가로)", depth: "벽에서 앞으로 나온 걸이 길이", height: "등판 높이(나사 구멍 두 개가 들어감)", wall: "등판과 끝 턱의 두께", bottom: "물건이 걸리는 걸이 두께. 무거운 물건은 두껍게", hole_diameter: "벽 나사 구멍 지름. 위쪽이 뾰족한 물방울 모양이라 서포트 없이 출력됩니다", lip_height: "물건이 미끄러지지 않게 막는 끝 턱 높이" }, keycap: { text: "윗면에 새길 글자(6자 이하). 비워 두면 글자 없는 키캡입니다", text_size: "새긴 글자의 높이. 1u 윗면에는 5 mm 이하가 알맞습니다", text_depth: "윗면에 파이는 글자 깊이", height: "베드에서 키캡 윗면 가장자리까지", wall: "키캡 옆벽 두께", bottom: "오목한 윗면 가운데의 두께", fit_clearance: "체리 MX 십자 구멍(4.0 × 1.17 mm)에 더하는 여유. 빡빡하면 늘리고 헐거우면 줄이세요" } };
  const fieldNudges = { width: 1, depth: 1, height: 1, wall: 0.1, bottom: 0.1, dividers: 1, slots: 1, cable_diameter: 0.5, inset_diameter: 1, inset_depth: 0.1, fit_clearance: 0.05, lean_angle: 1, device_thickness: 0.5, lip_height: 1, text_size: 0.5, text_depth: 0.2, hole_diameter: 0.5, key_units: 0.25, drain_hole: 0.5 };
  const fieldGroups = [["text", "글자", ["text", "text_size", "text_depth"]], ["size", "크기", ["key_units", "width", "depth", "height"]], ["thickness", "두께", ["wall", "bottom"]], ["color", "색", ["color", "accent_color"]]];
  const PARAMETER_FORMAT = "3d-printer-agent/parameters";

  // Same field, different meaning per template.
  const templateFieldLabels = { cup: { width: "지름", wall: "옆벽 두께" }, phone_stand: { fit_clearance: "홈 여유", wall: "등판·앞턱 두께" }, name_tag: { wall: "테두리 여백", bottom: "받침 두께" }, wall_hook: { depth: "걸이 길이", wall: "등판·끝 턱 두께", bottom: "걸이 두께", hole_diameter: "나사 구멍 지름", lip_height: "끝 턱 높이" }, keycap: { height: "키캡 높이", wall: "옆벽 두께", bottom: "윗면 두께", text_depth: "글자 깊이", fit_clearance: "스템 십자 여유" } };
  const fieldNames = {
    ...Object.fromEntries(Object.entries(fields).map(([key, value]) => [key, value.label])),
    printer_model: "프린터 모델", printer_preset: "프린터 프리셋", nozzle_diameter: "노즐 지름",
    plate_type: "플레이트 종류", extruder: "압출기", feed_mode: "공급 방식", material_id: "재료 제품 식별자",
    material_identity_status: "제품 식별 상태", bed_temperature: "선택한 플레이트 베드 온도", bed_temperature_initial_layer: "선택한 플레이트 첫 레이어 베드 온도", nozzle_temperature: "노즐 온도",
    nozzle_temperature_initial_layer: "첫 레이어 노즐 온도", filament_flow_ratio: "유량 비율",
    filament_max_volumetric_speed: "최대 체적 속도", pressure_advance_k: "압력 선행 교정 K",
    filament_diameter: "필라멘트 지름", compatible_printers: "지원 프린터 프리셋",
    textured_plate_temp: "텍스처 PEI 베드 온도", textured_plate_temp_initial_layer: "텍스처 PEI 첫 레이어 베드 온도",
    hot_plate_temp: "고온·매끈한 PEI 베드 온도", hot_plate_temp_initial_layer: "고온·매끈한 PEI 첫 레이어 베드 온도",
    cool_plate_temp: "쿨 플레이트 베드 온도", cool_plate_temp_initial_layer: "쿨 플레이트 첫 레이어 베드 온도",
    eng_plate_temp: "엔지니어링 베드 온도", eng_plate_temp_initial_layer: "엔지니어링 첫 레이어 베드 온도",
    supertack_plate_temp: "슈퍼택 베드 온도", supertack_plate_temp_initial_layer: "슈퍼택 첫 레이어 베드 온도",
    name: "프로필 이름", filament_vendor: "재료 제조사", filament_type: "재료 종류", inherits: "상속 원본",
  };
  const numberFormat = new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 2 });

  function node(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = String(text);
    return element;
  }

  function friendly(text) {
    let value = String(text).replace(/^[A-Z_]+:\s*/, "");
    for (const key of Object.keys(fieldNames).sort((a, b) => b.length - a.length)) {
      value = value.replaceAll(key, fieldNames[key]);
    }
    return value;
  }

  function showNotice(id, text, tone = "info", items = []) {
    const area = $(id);
    area.className = `notice notice-${tone}`;
    area.replaceChildren(node("p", "", text));
    if (items.length) {
      const list = node("ul");
      items.forEach((item) => list.append(node("li", "", friendly(typeof item === "string" ? item : item.message || item.detail || JSON.stringify(item)))));
      area.append(list);
    }
    area.hidden = false;
  }

  function hideNotice(id) { $(id).hidden = true; }

  let toastTimer;
  function toast(message) {
    $("toast").textContent = message;
    $("toast").hidden = false;
    window.clearTimeout(toastTimer);
    toastTimer = window.setTimeout(() => { $("toast").hidden = true; }, 4200);
  }

  function errorMessage(detail) {
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) return detail.map((item) => `${(item.loc || []).filter((part) => part !== "body").join(" · ")}: ${item.msg || "입력값을 확인해 주세요."}`).join(" / ");
    return "처리 결과를 확인하지 못했습니다. 입력과 연결을 확인해 주세요.";
  }

  function updateConnectionActions() {
    $("reconnect-button").disabled = Boolean(state.bootstrapPending);
    $("retry-bootstrap").disabled = Boolean(state.bootstrapPending);
    $("reconnect-button").textContent = state.bootstrapPending ? "연결 확인 중" : "다시 연결";
    $("review-profile").disabled = !state.token || Boolean($("review-profile").dataset.busy) || Object.keys(state.guidedEdits || {}).length > 0;
    $("compare-offers").disabled = !state.token || Boolean($("compare-offers").dataset.busy);
    if (typeof updatePrinterControls === "function") updatePrinterControls();
  }

  function renderConnection() {
    const connected = state.connectionState === "connected";
    setBadge("connection-status", connected ? "로컬 서버 연결됨" : state.connectionState === "connecting" ? "연결 확인 중" : "다시 연결 필요", connected ? "success" : state.connectionState === "connecting" ? "neutral" : "warning");
    $("connection-detail").textContent = connected ? "입력과 파일 처리는 이 PC에서 이어집니다. 다시 연결해도 현재 편집 내용은 유지됩니다." : state.connectionState === "connecting" ? "현재 입력은 유지한 채 로컬 서버의 연결과 저장 위치를 확인합니다." : "현재 입력과 받은 결과는 이 화면에 남아 있습니다. 서버를 실행한 뒤 다시 연결해 주세요.";
    const storage = state.storage;
    $("storage-path").textContent = typeof storage?.path === "string" ? storage.path : "서버에서 저장 위치를 아직 확인하지 못했습니다.";
    const sources = { argument: "실행 시 지정한 폴더", environment: "환경 설정으로 지정한 폴더", legacy: "기존 작업이 있는 data 폴더", user_default: "이 사용자 계정의 기본 앱 폴더" };
    $("storage-source").textContent = sources[storage?.source] || "저장 위치 확인 전";
    const recovery = storage?.recovery || {};
    const count = (key) => Number.isInteger(recovery[key]) && recovery[key] >= 0 ? recovery[key] : 0;
    $("storage-recovery").textContent = storage ? `시작할 때 확인한 기록 ${count("indexed")}개 · 중단 처리 ${count("interrupted")}개 · 읽기 확인 필요 ${count("unreadable")}개. 중단되거나 손상된 기록의 원본은 보존합니다.` : "연결되면 현재 앱 데이터 위치와 시작 시 복구 결과를 보여줍니다.";
    // Healthy and nothing to recover: keep the card to one quiet line so the
    // first screen starts with the work. Problems keep the full explanation.
    $("local-runtime").classList.toggle("is-quiet", connected && Boolean(storage) && !count("interrupted") && !count("unreadable"));
    updateConnectionActions();
  }

  function connectionFailed(message) {
    state.connectionEpoch += 1;
    cancelModelEdit();
    invalidateStudioRequests();
    state.slicePrepared = false;
    if (state.job) showNotice("slice-feedback", "연결을 다시 확인한 뒤 현재 설정으로 준비해 주세요. 처리 중이던 요청의 결과는 작업 기록에서 확인할 수 있습니다. 요청을 자동으로 반복하지 않습니다.", "warning");
    state.connectionState = "disconnected";
    state.token = null;
    $("bootstrap-error").hidden = false;
    $("bootstrap-error-detail").textContent = message;
    renderConnection();
    updateWorkflowControls();
    updateWorkspaceStatus();
  }

  async function api(path, body, method, context = {}) {
    const options = { method: method || (body === undefined ? "GET" : "POST"), credentials: "same-origin", cache: "no-store", headers: {} };
    const epoch = state.connectionEpoch;
    const current = () => epoch === state.connectionEpoch && (!context.current || context.current());
    const requireCurrentConnection = () => {
      if (epoch === state.connectionEpoch) return;
      const message = body === undefined
        ? "연결이 바뀌어 이전 서버의 응답을 현재 화면에 적용하지 않았습니다. 현재 입력과 결과는 유지했습니다. 필요한 기록을 다시 불러와 주세요."
        : "연결이 바뀌어 이전 요청의 응답을 현재 작업에 적용하지 않았습니다. 이전 요청의 처리 여부는 이 화면에서 확정할 수 없습니다. 생성·저장이 완료됐을 수 있으니 이전 저장 위치의 작업 기록이나 저장된 재료 작업을 확인해 주세요. 요청을 취소하거나 자동으로 반복하지 않았습니다.";
      const error = new Error(message);
      error.code = "connection_changed";
      throw error;
    };
    if (body !== undefined) {
      if (!state.token) throw new Error("작업 공간에 다시 연결한 뒤 시도해 주세요. 현재 입력은 유지했습니다.");
      options.headers["Content-Type"] = "application/json";
      options.headers["X-Session-Token"] = state.token;
      options.body = JSON.stringify(body);
    }
    let response;
    try { response = await fetch(path, options); }
    catch {
      requireCurrentConnection();
      const message = body === undefined ? "로컬 서버에 연결하지 못했습니다. 서버가 실행 중인지 확인한 뒤 다시 연결해 주세요." : "서버 응답을 받지 못해 요청의 처리 여부를 확인할 수 없습니다. 다시 연결한 뒤 저장된 기록을 확인해 주세요. 요청을 자동으로 반복하지 않았습니다.";
      if (current()) connectionFailed(message);
      throw new Error(message);
    }
    if (response.status === 204 && response.ok) { requireCurrentConnection(); return null; }
    let data;
    try { data = await response.json(); }
    catch { requireCurrentConnection(); throw new Error(`서버 응답을 읽지 못했습니다. (HTTP ${response.status})`); }
    requireCurrentConnection();
    if (!response.ok) {
      const error = new Error(friendly(errorMessage(data.detail || data.message)));
      error.status = response.status;
      error.code = data.code;
      if (error.code === "session_expired" && current()) connectionFailed("서버가 다시 시작되어 연결을 갱신해야 합니다. 현재 입력은 유지했습니다. 다시 연결한 뒤 원하는 작업을 눌러 주세요.");
      throw error;
    }
    return data;
  }

  async function withBusy(button, label, task) {
    if (button.dataset.busy) throw new Error("이 요청을 처리하고 있습니다. 완료 후 다시 시도해 주세요.");
    const previous = button.textContent;
    const disabled = button.disabled;
    const controls = button.form ? Array.from(button.form.elements).filter((control) => "disabled" in control).map((control) => [control, control.disabled]) : [];
    controls.forEach(([control]) => { control.disabled = true; });
    button.disabled = true;
    button.dataset.busy = "true";
    button.classList.add("is-loading");
    button.textContent = label;
    try { return await task(); }
    finally {
      controls.forEach(([control, previousState]) => { control.disabled = previousState; });
      button.textContent = previous;
      button.disabled = disabled;
      delete button.dataset.busy;
      button.classList.remove("is-loading");
      updateConnectionActions();
    }
  }

  async function withWorkflow(button, label, task) {
    if (state.workflowBusy) throw new Error("진행 중인 모델 작업이 있습니다. 완료 후 다시 시도해 주세요.");
    state.workflowBusy = true;
    updateWorkflowControls();
    try { return await withBusy(button, label, task); }
    finally { state.workflowBusy = false; updateWorkflowControls(); }
  }

  function updateWorkflowControls() {
    const busy = state.workflowBusy;
    document.querySelectorAll("#view-models input, #view-models textarea, #view-models select, .template-card, #history-list .history-item button").forEach((control) => { control.disabled = busy; });
    $("view-models").setAttribute("aria-busy", String(busy));
    $("plan-button").disabled = busy || !state.token;
    $("generate-button").disabled = busy || !state.token || !state.template;
    $("reset-parameters").disabled = busy || !state.template;
    $("copy-parameters").disabled = busy || !state.template;
    $("paste-parameters").disabled = busy || !state.templates.length;
    $("save-outcome").disabled = busy || !state.token || !state.job;
    updateSliceControls();
    updateDiscoveryControls();
    renderModelEdit();
    $("model-confirm-replace").disabled = busy || !state.modelReplacement;
    $("model-cancel-replace").disabled = busy;
  }

  function invalidateCurrentJob(message) {
    resetPrintSend(null);
    retainOutcomeDraft();
    cancelSlicerReads();
    state.studioRecorded = null;
    state.studioSettingsRecorded = null;
    state.studioSettingsRecordedReview = null;
    state.studioSavedIdentity = null;
    renderSlicerFiles();
    if (!state.job) return;
    state.job = null;
    renderProjectSource("generated-source", null);
    state.slicePrepared = false;
    viewer.clear();
    renderColorLegend(null);
    $("model-result").hidden = true;
    $("outcome-card").hidden = true;
    $("download-links").replaceChildren();
    $("slice-result").replaceChildren();
    $("slice-compare").hidden = true;
    $("slice-compare").replaceChildren();
    setBadge("preview-status", "새 제작안 · 생성 전");
    $("preview-caption").textContent = "변경한 제작안은 아직 모델에 반영되지 않았습니다.";
    $("preview-empty").querySelector("h3").textContent = "새 제작안으로 다시 만들어 주세요";
    $("preview-empty").querySelector("p").textContent = "이전에 생성한 파일은 작업 기록에서 다시 열 수 있습니다.";
    showNotice("model-feedback", message);
    showNotice("slice-feedback", "현재 제작안의 모델을 생성한 뒤 슬라이싱을 준비할 수 있습니다.");
    updateWorkflowControls();
    if (typeof renderJourney === "function") renderJourney();
  }

  function parseObject(value, label) {
    let parsed, unsupportedNumber = false;
    try {
      parsed = JSON.parse(value, (_key, item) => {
        if (typeof item === "number" && (!Number.isFinite(item) || (Number.isInteger(item) && !Number.isSafeInteger(item)))) {
          unsupportedNumber = true;
          throw new Error("Unsupported JSON number");
        }
        return item;
      });
    } catch {
      if (unsupportedNumber) throw new Error(`${label}의 숫자를 정확하게 보존할 수 없습니다. 유한한 숫자와 안전한 범위의 정수를 사용해 주세요.`);
      throw new Error(`${label}의 JSON 문법을 확인해 주세요. 중괄호와 따옴표가 맞아야 합니다.`);
    }
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) throw new Error(`${label}은 JSON 객체여야 합니다.`);
    return parsed;
  }

  function setBadge(id, text, tone = "neutral") {
    $(id).textContent = text;
    $(id).className = `badge badge-${tone}`;
  }

  function changeView(name) {
    if (!pageNames[name]) return;
    for (const [view, label] of Object.entries(pageNames)) {
      $(`view-${view}`).hidden = view !== name;
      const button = document.querySelector(`.nav-item[data-view="${view}"]`);
      button.classList.toggle("active", view === name);
      if (view === name) button.setAttribute("aria-current", "page");
      else button.removeAttribute("aria-current");
      if (view === name) $("current-page").textContent = label;
    }
    closeMenu();
    if (name === "history") loadHistory();
    if (name === "offers") { renderOffersModelHint(); if (state.offersResult && !$("offers-result").hidden) renderOffers(state.offersResult); }
    if (name === "profiles") renderSetupPrinterFill();
    if (name === "models") viewer.requestDraw();
    if (name === "imports") { importViewer.requestDraw(); loadRecentImports(); }
    window.scrollTo({ top: 0, behavior: "auto" });
  }

  const mobileMenu = window.matchMedia("(max-width: 760px)");
  function closeMenu() {
    document.body.classList.remove("nav-open");
    $("menu-toggle").setAttribute("aria-expanded", "false");
    $("menu-toggle").setAttribute("aria-label", "메뉴 열기");
    $("nav-backdrop").hidden = true;
    $("sidebar").inert = mobileMenu.matches;
  }
  $("menu-toggle").addEventListener("click", () => {
    if (document.body.classList.contains("nav-open")) return closeMenu();
    document.body.classList.add("nav-open");
    $("sidebar").inert = false;
    $("nav-backdrop").hidden = false;
    $("menu-toggle").setAttribute("aria-expanded", "true");
    $("menu-toggle").setAttribute("aria-label", "메뉴 닫기");
    document.querySelector(".nav-item.active").focus();
  });
  $("nav-backdrop").addEventListener("click", closeMenu);
  mobileMenu.addEventListener("change", closeMenu);
  document.addEventListener("keydown", (event) => { if (event.key === "Escape") closeMenu(); });
  document.querySelectorAll(".nav-item").forEach((button) => button.addEventListener("click", () => changeView(button.dataset.view)));
  closeMenu();

  function discoverySignature() {
    return JSON.stringify([state.discoveryPurpose, ...["width", "depth", "height"].map((axis) => {
      const input = $(`space-${axis}`);
      return [input.value, Boolean(input.validity?.badInput), input.validity?.valid !== false];
    })]);
  }

  function discoveryQuery() {
    const available_space = {};
    for (const [axis, label] of [["width", "가로"], ["depth", "세로"], ["height", "높이"]]) {
      const input = $(`space-${axis}`);
      if (input.validity?.badInput || input.validity?.valid === false) throw new Error(`놓을 공간의 ${label}를 0보다 크고 10000 이하인 mm 숫자로 완성해 주세요.`);
      if (input.value === "") continue;
      const value = Number(input.value);
      if (!Number.isFinite(value) || value <= 0 || value > 10000) throw new Error(`놓을 공간의 ${label}를 0보다 크고 10000 이하인 mm 숫자로 입력해 주세요.`);
      available_space[axis] = value;
    }
    return { purpose: state.discoveryPurpose, available_space };
  }

  function discoveryFiltersChanged() {
    state.discoveryRevision += 1;
    state.discoveryRequest += 1;
    state.discoveryPending = false;
    state.discoveryStale = true;
    cancelProjectApplication();
    renderDiscovery();
    showNotice("discovery-feedback", "조건을 바꿨습니다. ‘조건으로 찾기’를 누르면 아래 시작점을 다시 비교합니다.");
    updateDiscoveryControls();
  }

  function setDiscoveryCatalog(catalog, preserveBrowsing = false) {
    state.discoveryEpoch += 1;
    state.discoveryRequest += 1;
    state.discoveryPending = false;
    state.discovery = catalog || { purposes: [], projects: [] };
    state.projectReplacement = null;
    // Reconnecting refreshes discovery only. It never reapplies a draft or a job's source.
    if (!preserveBrowsing) {
      state.discoveryMatches = state.discovery.projects.map((project) => ({ project, space_fit: { status: "not_checked" } }));
      state.discoveryBrowsed = null;
      state.discoveryStale = Boolean(state.discoveryRevision);
    } else {
      // Preserved matches identify the previous catalog, even when filters did not change.
      state.discoveryStale = true;
    }
    const purposes = $("discovery-purpose");
    purposes.replaceChildren();
    for (const purpose of state.discovery.purposes) {
      const button = node("button", "purpose-button", purpose.title);
      button.type = "button";
      button.dataset.purpose = purpose.id;
      button.addEventListener("click", () => {
        if (state.workflowBusy || state.discoveryPurpose === purpose.id) return;
        state.discoveryPurpose = purpose.id;
        discoveryFiltersChanged();
      });
      purposes.append(button);
    }
    renderDiscovery();
    if (state.discoveryRevision || preserveBrowsing) showNotice("discovery-feedback", "연결을 새로 확인했습니다. 입력한 조건은 그대로입니다. ‘조건으로 찾기’로 결과를 갱신해 주세요.");
    else hideNotice("discovery-feedback");
  }

  function renderDiscovery() {
    const list = $("discovery-cards");
    list.replaceChildren();
    const matches = state.discoveryMatches || [];
    $("discovery-summary").textContent = matches.length ? `${matches.length}개의 시작점 · ${state.discoveryStale ? "이전 조건의 결과 · 다시 찾아주세요" : "카드를 눌러 측정할 곳을 살펴보세요"}` : state.discoveryStale ? "이전 조건의 결과 · 조건으로 다시 찾아주세요" : "조건에 맞는 시작점이 없습니다";
    if (!matches.length) {
      const empty = node("div", "discovery-empty");
      empty.append(node("h3", "", state.discoveryStale ? "이전 조건에는 맞는 기본 크기가 없었어요" : "이 공간에 맞는 기본 크기가 없어요"), node("p", "", "용도나 공간 조건을 바꾸거나, 아래 기본 템플릿에서 직접 치수를 조정해 보세요. 크기는 자동으로 줄이지 않습니다."));
      list.append(empty);
    }
    for (const match of matches) {
      const project = match.project;
      const button = node("button", "project-card");
      button.type = "button";
      button.dataset.projectId = project.id;
      button.setAttribute("aria-pressed", String(state.discoveryBrowsed === project.id));
      const art = node("span", `project-art project-art-${project.template}`);
      art.setAttribute("aria-hidden", "true");
      const shape = node("span", "project-shape");
      const divisions = project.template === "cable_comb" ? project.parameters.slots : (project.parameters.dividers || 0);
      for (let i = 0; i < Math.min(divisions || 0, 5); i += 1) shape.append(node("i"));
      if (project.template === "name_tag" || project.template === "keycap") shape.textContent = project.parameters?.text || "";
      art.append(shape);
      button.append(art, node("strong", "project-title", project.title), node("span", "project-description", project.description), node("span", "project-size", projectSizeText(project)));
      if (!state.discoveryStale && match.space_fit?.status === "fits_rotated") button.append(node("span", "project-fit", "가로·세로를 90° 돌려 놓는 크기"));
      else if (!state.discoveryStale && match.space_fit?.status === "fits") button.append(node("span", "project-fit", "입력한 축의 공간 크기와 비교됨"));
      button.append(node("span", "project-more", "측정 안내 보기 ↗"));
      button.addEventListener("click", () => browseProject(project.id));
      list.append(button);
    }
    renderProjectDetail();
    updateDiscoveryControls();
  }

  function browseProject(id) {
    if (state.workflowBusy) return;
    if (!(state.discoveryMatches || []).some((match) => match.project.id === id)) return;
    state.discoveryBrowsed = id;
    cancelProjectApplication();
    renderDiscovery();
  }

  function projectSizeText(project) {
    // Name tags and keycaps are not sized by width × depth × height; their recipe states the outer size.
    const size = project.size_mm || project.parameters || {};
    const text = `${numberFormat.format(size.width)} × ${numberFormat.format(size.depth)} × ${numberFormat.format(size.height)} mm`;
    return project.size_mm?.basis === "upper_bound" ? `최대 ${text} · 글꼴에 따라 가로가 달라짐` : text;
  }

  function renderProjectDetail() {
    const match = (state.discoveryMatches || []).find((item) => item.project.id === state.discoveryBrowsed);
    const area = $("discovery-detail");
    area.hidden = !match;
    if (!match) return;
    const project = match.project;
    $("discovery-detail-title").textContent = project.title;
    $("discovery-detail-reason").textContent = project.reason;
    $("discovery-measurements").replaceChildren(...(project.measurements || []).map((text) => node("li", "", text)));
    $("discovery-limits").replaceChildren(...(project.limits || []).map((text) => node("li", "", text)));
    $("discovery-fit").textContent = state.discoveryStale ? "표시된 시작점은 이전 조건의 결과입니다. 현재 조건으로 다시 찾은 뒤 치수를 준비해 주세요." : match.space_fit?.status === "fits_rotated" ? "가로·세로를 90° 돌려 놓았을 때 입력한 축에 들어가는 기본 크기입니다. 제작 치수는 회전하거나 줄이지 않습니다." : match.space_fit?.status === "fits" ? "입력한 축의 놓을 공간과 기본 외곽 크기를 비교했습니다. 입력하지 않은 축은 확인하지 않았습니다." : "놓을 공간은 아직 비교하지 않았습니다. 아래 안내에 따라 실측해 주세요.";
    renderProjectSource("discovery-origin", project);
    $("discovery-replace-confirm").hidden = !state.projectReplacement;
  }

  function renderProjectSource(id, source) {
    const area = $(id);
    area.replaceChildren();
    area.hidden = !source;
    if (id === "generated-source") $("generated-source-record").hidden = !source;
    if (!source) return;
    if (source.kind === "imported_file") {
      area.append(node("strong", "", `불러온 파일 · ${source.filename}`),
        node("p", "", `출력 방향 · ${source.orientation?.label || "미기록"} (회전·이동만 함)`),
        node("p", "source-hash", `원본 SHA-256 · ${source.sha256}`));
      const original = node("a", "", "원본 파일 내려받기");
      original.href = source.source_url;
      original.download = "";
      area.append(original, node("p", "source-scope", "다른 곳에서 받은 메시입니다. 이 앱의 CAD 검증·벽 두께 점검·실물 출력 확인은 하지 않았습니다."));
      return;
    }
    const recipe = source.recipe || source;
    const origin = recipe.source || {};
    area.append(node("strong", "", recipe.title || "로컬 원본 시작점"));
    area.append(node("p", "", `출처 · ${origin.creator || "미기록"} · ${origin.license || "이용 조건 미기록"}`));
    const metadata = node("details", "source-metadata");
    metadata.append(node("summary", "", "원본 경로와 시작점 식별자"));
    if (origin.kind) metadata.append(node("p", "", `원본 종류 · ${origin.kind}`));
    if (origin.repository) metadata.append(node("p", "source-path", origin.repository));
    if (origin.path) metadata.append(node("p", "source-path", origin.path));
    if (source.recipe_sha256) metadata.append(node("p", "source-hash", `시작점 SHA-256 · ${source.recipe_sha256}`));
    if (source.customized) area.append(node("p", "", `시작점에서 수정한 치수 · ${(source.changed_parameters || []).map((key) => fieldNames[key] || key).join(", ")}`));
    area.append(node("p", "source-scope", "시작 설계의 기록입니다. 실물 출력·고정력·끼워맞춤을 검증한 표시는 아닙니다."), metadata);
  }

  function updateDiscoveryControls() {
    const busy = state.workflowBusy;
    $("discovery-submit").disabled = busy || !state.token || !state.discovery;
    $("discovery-submit").textContent = state.discoveryPending ? "새 조건으로 다시 찾기" : "조건으로 찾기";
    $("discovery-cards").setAttribute("aria-busy", String(Boolean(state.discoveryPending)));
    document.querySelectorAll(".purpose-button").forEach((button) => {
      button.disabled = busy;
      button.setAttribute("aria-pressed", String(button.dataset.purpose === state.discoveryPurpose));
    });
    document.querySelectorAll(".project-card").forEach((button) => { button.disabled = busy; });
    $("discovery-apply").disabled = busy || !state.discoveryBrowsed || state.discoveryStale;
    $("discovery-confirm-apply").disabled = busy || state.discoveryStale || !state.projectReplacement;
    $("discovery-cancel-apply").disabled = busy;
    $("detach-source").hidden = !state.projectSource;
    $("detach-source").disabled = busy || !state.projectSource;
  }

  function draftHasChanges() {
    if (state.job || $("request-text").value.trim()) return true;
    const template = state.templates.find((item) => item.id === state.template);
    return (template?.editable_fields || []).some((key) => {
      const input = $(`parameter-${key}`);
      return input.validity?.badInput || input.validity?.valid === false || (input.value === "" && !COLOR_PARAMETERS.has(key)) || input.value !== String(state.parameters[key] ?? "");
    });
  }

  function requestProjectApplication() {
    if (state.workflowBusy || state.discoveryStale) return;
    const match = (state.discoveryMatches || []).find((item) => item.project.id === state.discoveryBrowsed);
    if (!match) return;
    if (draftHasChanges()) {
      cancelModelReplacement();
      state.projectReplacement = match.project;
      $("discovery-replace-confirm").hidden = false;
      updateDiscoveryControls();
      $("discovery-confirm-apply").focus({ preventScroll: true });
    } else applyProject(match.project);
  }

  function confirmProjectApplication() {
    if (state.workflowBusy || state.discoveryStale || !state.projectReplacement) return;
    applyProject(state.projectReplacement);
  }

  function cancelProjectApplication() {
    if (state.workflowBusy) return;
    state.projectReplacement = null;
    $("discovery-replace-confirm").hidden = true;
  }

  function applyProject(project) {
    if (state.workflowBusy) return;
    applyDraft(project.template, project.parameters, project);
    hideNotice("plan-feedback");
    showNotice("model-feedback", "시작점의 치수를 준비했습니다. 내 물건과 공간에 맞게 확인한 뒤 모델을 생성해 주세요.");
    $("parameter-heading").focus({ preventScroll: true });
  }

  function detachProjectSource() {
    if (state.workflowBusy || !state.projectSource) return;
    state.projectSource = null;
    state.modelEditApplied = null;
    cancelModelEdit();
    invalidateCurrentJob("출처 연결을 해제했습니다. 현재 치수로 새 모델을 생성해 주세요.");
    renderProjectSource("draft-source", null);
    updateDiscoveryControls();
  }

  async function recommendProjects() {
    if (state.workflowBusy || !state.discovery) return;
    let query;
    try { query = discoveryQuery(); }
    catch (error) { showNotice("discovery-feedback", error.message, "error"); return; }
    const request = ++state.discoveryRequest, epoch = state.discoveryEpoch, signature = discoverySignature();
    state.discoveryPending = true;
    state.discoveryStale = true;
    state.projectReplacement = null;
    renderDiscovery();
    showNotice("discovery-feedback", "로컬 시작점의 기본 크기를 비교하고 있습니다. 조건을 바꾸면 이전 응답은 적용하지 않습니다.");
    try {
      const result = await api("/api/discovery", query, undefined, { current: () => request === state.discoveryRequest && epoch === state.discoveryEpoch && signature === discoverySignature() });
      if (request !== state.discoveryRequest || epoch !== state.discoveryEpoch || signature !== discoverySignature()) return;
      state.discoveryStale = false;
      state.discoveryMatches = result.matches || [];
      state.discoveryBrowsed = null;
      state.projectReplacement = null;
      renderDiscovery();
      showNotice("discovery-feedback", `${result.excluded_count || 0}개는 입력한 공간보다 커서 제외했습니다. 놓을 공간의 외곽 크기만 비교하며, 프린터 호환·실물 끼워맞춤은 확인하지 않습니다.`);
    } catch (error) {
      if (request === state.discoveryRequest && epoch === state.discoveryEpoch && signature === discoverySignature()) showNotice("discovery-feedback", `${error.message} 기존 결과와 제작안은 그대로입니다. 다시 찾아보세요.`, "error");
    } finally {
      if (request === state.discoveryRequest) { state.discoveryPending = false; updateDiscoveryControls(); }
    }
  }

  function modelGeometrySignature() {
    const template = state.templates.find(item => item.id === state.template);
    return JSON.stringify([state.template, state.projectSource, ...(template?.editable_fields || []).map(key => {
      const input = $(`parameter-${key}`);
      return [key, input.value, Boolean(input.validity?.badInput), input.validity?.valid !== false];
    })]);
  }

  function modelEditScope() {
    return JSON.stringify([modelGeometrySignature(), modelDraftSignature(), state.job?.id || null, state.connectionEpoch, state.storage?.path || null, $("model-edit-text").value, $("model-edit-mode").value]);
  }

  function validateEditParameters(parameters) {
    const defaults = { width: 120, depth: 80, height: 35, wall: 2, bottom: 2, dividers: 0, slots: 5, cable_diameter: 6, inset_diameter: 52, inset_depth: 2, fit_clearance: 0.3 };
    // Fields added later appear only in templates that use them (see schemas.LATER_FIELDS).
    const laterFields = { phone_stand: { lean_angle: 65, device_thickness: 12, lip_height: 12 }, name_tag: { text: "", text_size: 12, text_depth: 2, hole_diameter: 4 }, wall_hook: { lip_height: 12, hole_diameter: 4 }, keycap: { text: "", text_size: 12, text_depth: 2, key_units: 1 }, cup: { drain_hole: 0 } };
    const applicable = { tray: ["width", "depth", "height", "wall", "bottom", "dividers"], cable_comb: ["width", "depth", "height", "wall", "bottom", "slots", "cable_diameter", "fit_clearance"], magnet_frame: ["width", "depth", "height", "wall", "bottom", "inset_diameter", "inset_depth", "fit_clearance"], phone_stand: ["width", "depth", "height", "wall", "bottom", "lean_angle", "device_thickness", "lip_height", "fit_clearance"], name_tag: ["text", "text_size", "text_depth", "wall", "bottom", "hole_diameter"], wall_hook: ["width", "depth", "height", "wall", "bottom", "hole_diameter", "lip_height"], keycap: ["key_units", "text", "text_size", "text_depth", "height", "wall", "bottom", "fit_clearance"], cup: ["width", "height", "wall", "bottom", "drain_hole"] };
    const expected = { ...defaults, ...(laterFields[parameters?.template] || {}) };
    // Colours appear only when chosen (see schemas.COLOR_FIELDS); letters only on a name tag.
    const colorKeys = parameters && typeof parameters === "object" ? Object.keys(parameters).filter((key) => COLOR_PARAMETERS.has(key)) : [];
    for (const key of colorKeys) {
      if (!Object.hasOwn(PALETTE, parameters[key]) || (key === "accent_color" && parameters.template !== "name_tag")) throw new Error("수정 제안의 색 응답이 올바르지 않습니다.");
    }
    if (!parameters || typeof parameters !== "object" || Array.isArray(parameters) || !Object.hasOwn(applicable, parameters.template) || Object.keys(parameters).length !== Object.keys(expected).length + 1 + colorKeys.length || !Object.hasOwn(parameters, "template")) throw new Error("수정 제안의 전체 치수 응답을 확인할 수 없습니다.");
    for (const [key, neutral] of Object.entries(expected)) {
      const value = parameters[key];
      if (TEXT_PARAMETERS.has(key)) {
        if (!Object.hasOwn(parameters, key) || typeof value !== "string" || (!value.trim() && parameters.template !== "keycap") || value.length > (parameters.template === "keycap" ? 6 : fields[key].maxLength)) throw new Error("수정 제안의 글자 응답이 올바르지 않습니다.");
        continue;
      }
      if (!Object.hasOwn(parameters, key) || typeof value !== "number" || !Number.isFinite(value) || ((key === "dividers" || key === "slots") && !Number.isSafeInteger(value)) || (!applicable[parameters.template].includes(key) && value !== neutral)) throw new Error("수정 제안의 치수 응답이 올바르지 않습니다.");
      const definition = fields[key];
      if (definition && (value < definition.min || value > definition.max)) throw new Error("수정 제안의 치수 범위를 확인해 주세요.");
    }
    return [...applicable[parameters.template], ...colorKeys];
  }

  function parameterKeys(template) {
    // The eleven original fields for every template, plus later fields only where used.
    // Same order as the server's canonical fields (schemas.GeometryRequest).
    const later = { phone_stand: ["lean_angle", "device_thickness", "lip_height"], name_tag: ["text", "text_size", "text_depth", "hole_diameter"], wall_hook: ["lip_height", "hole_diameter"], keycap: ["text", "text_size", "text_depth", "key_units"], cup: ["drain_hole"] };
    return ["template", "width", "depth", "height", "wall", "bottom", "dividers", "slots", "cable_diameter", "inset_diameter", "inset_depth", "fit_clearance", ...(later[template] || [])];
  }

  function currentEditParameters() {
    const parameters = { template: state.template, width: 120, depth: 80, height: 35, wall: 2, bottom: 2, dividers: 0, slots: 5, cable_diameter: 6, inset_diameter: 52, inset_depth: 2, fit_clearance: 0.3 };
    if (state.template === "phone_stand") Object.assign(parameters, { lean_angle: 65, device_thickness: 12, lip_height: 12 });
    if (state.template === "name_tag") Object.assign(parameters, { text: "", text_size: 12, text_depth: 2, hole_diameter: 4 });
    if (state.template === "wall_hook") Object.assign(parameters, { lip_height: 12, hole_diameter: 4 });
    if (state.template === "keycap") Object.assign(parameters, { text: "", text_size: 12, text_depth: 2, key_units: 1 });
    if (state.template === "cup") Object.assign(parameters, { drain_hole: 0 });
    const template = state.templates.find(item => item.id === state.template);
    if (!template) throw new Error("수정할 템플릿을 먼저 선택해 주세요.");
    for (const key of template.editable_fields) {
      const input = $(`parameter-${key}`);
      if (!parameterInputComplete(input)) throw new Error("현재 치수 입력을 완성한 뒤 수정 제안을 요청해 주세요.");
      if (COLOR_PARAMETERS.has(key)) { if (input.value) parameters[key] = input.value; continue; }
      parameters[key] = TEXT_PARAMETERS.has(key) ? input.value.trim() : Number(input.value);
    }
    validateEditParameters(parameters);
    return parameters;
  }

  function modelEditParentJob(parameters) {
    const job = state.job;
    if (!job || !/^[a-f0-9]{32}$/.test(job.id) || job.result?.geometry_status !== "validated") return null;
    try {
      validateEditParameters(job.result.parameters);
      return Object.keys(parameters).every(key => parameters[key] === job.result.parameters[key]) ? job.id : null;
    } catch { return null; }
  }

  function validateModelEditResponse(response, context) {
    const fail = () => { throw new Error("수정 제안 응답을 현재 제작안과 일치하는지 확인할 수 없습니다. 입력은 유지했습니다. 다시 요청해 주세요."); };
    const exact = (value, keys) => Boolean(value && typeof value === "object" && !Array.isArray(value) && Object.keys(value).length === keys.length && keys.every(key => Object.hasOwn(value, key)));
    const hash = value => typeof value === "string" && /^[a-f0-9]{64}$/.test(value);
    if (response?.status !== "ready" || response.engine !== context.engine || response.capability !== "current_template_parameters_only" || typeof response.message !== "string" || !response.message.trim() || !Array.isArray(response.questions) || response.questions.length || !Array.isArray(response.assumptions) || response.assumptions.length || Object.hasOwn(response, "parameters")) fail();
    const review = response.review, selection = review?.selection;
    if (!exact(review, ["schema_version", "selection", "base_sha256", "parameters", "parameters_sha256", "changes", "review_sha256"]) || review.schema_version !== 1 || !hash(review.base_sha256) || !hash(review.parameters_sha256) || !hash(review.review_sha256) || !exact(selection, ["schema_version", "request_text", "base_parameters", "operations", "parent"]) || selection.schema_version !== 1 || selection.request_text !== context.text) fail();
    let editable;
    try { editable = validateEditParameters(review.parameters); validateEditParameters(selection.base_parameters); } catch { fail(); }
    // Colour keys follow the numeric and text keys, in the server's field order.
    const colorKeys = ["color", "accent_color"].filter((key) => editable.includes(key) || Object.hasOwn(context.base, key));
    const keys = [...parameterKeys(context.base.template), ...colorKeys];
    if (review.parameters.template !== context.base.template || keys.some(key => selection.base_parameters[key] !== context.base[key])) fail();
    if (context.parent) {
      const parent = selection.parent;
      if (!exact(parent, ["job_id", "parameters_sha256", "model_sha256", "manifest_sha256"]) || parent.job_id !== context.parent || !hash(parent.parameters_sha256) || !hash(parent.model_sha256) || !hash(parent.manifest_sha256) || parent.parameters_sha256 !== review.base_sha256) fail();
    } else if (selection.parent !== null) fail();
    const operations = selection.operations;
    if (!Array.isArray(operations) || !operations.length || operations.length > 12) fail();
    const seen = new Set();
    for (const operation of operations) {
      if (!exact(operation, ["field", "op", "value"]) || seen.has(operation.field) || !["set", "add"].includes(operation.op)) fail();
      if (COLOR_PARAMETERS.has(operation.field)) {
        if (operation.op !== "set" || typeof operation.value !== "string" || (operation.value && !Object.hasOwn(PALETTE, operation.value)) || (operation.field === "accent_color" && context.base.template !== "name_tag")) fail();
        seen.add(operation.field);
        if ((review.parameters[operation.field] ?? "") !== operation.value) fail();
        continue;
      }
      if (!editable.includes(operation.field)) fail();
      if (TEXT_PARAMETERS.has(operation.field)) {
        if (operation.op !== "set" || typeof operation.value !== "string") fail();
        seen.add(operation.field);
        if (review.parameters[operation.field] !== operation.value) fail();
        continue;
      }
      if (typeof operation.value !== "number" || !Number.isFinite(operation.value) || (["dividers", "slots"].includes(operation.field) && (operation.op !== "set" || !Number.isSafeInteger(operation.value)))) fail();
      seen.add(operation.field);
      if (operation.op === "set" && review.parameters[operation.field] !== operation.value) fail();
    }
    // Review consistency only: the server rederives operations and geometry before CAD.
    const valueOf = (parameters, key) => COLOR_PARAMETERS.has(key) ? (parameters[key] ?? "") : parameters[key];
    const expectedChanges = keys.slice(1).filter(key => valueOf(context.base, key) !== valueOf(review.parameters, key)).map(field => ({ field, before: valueOf(context.base, field), after: valueOf(review.parameters, field) }));
    if (!expectedChanges.length || expectedChanges.some(change => !seen.has(change.field)) || !Array.isArray(review.changes) || review.changes.length !== expectedChanges.length) fail();
    for (const [index, change] of review.changes.entries()) {
      const expected = expectedChanges[index];
      if (!exact(change, ["field", "before", "after"]) || change.field !== expected.field || change.before !== expected.before || change.after !== expected.after) fail();
    }
    return JSON.parse(JSON.stringify(review));
  }

  function renderModelEdit() {
    if (state.modelEditCandidate && state.modelEditCandidate.scope !== modelEditScope()) state.modelEditCandidate = null;
    const candidate = state.modelEditCandidate, busy = state.workflowBusy;
    $("model-edit-review").hidden = !candidate;
    $("model-edit-review").setAttribute("aria-busy", String(Boolean(state.modelEditPending)));
    $("model-edit-propose").disabled = busy || !state.token || !state.template;
    $("model-edit-propose").textContent = state.modelEditPending ? "새 요청으로 다시 제안" : "수정 제안 검토";
    $("model-edit-apply").disabled = busy || !state.token || !candidate;
    $("model-edit-cancel").disabled = busy;
    $("model-edit-changes").replaceChildren();
    if (candidate) {
      for (const change of candidate.review.changes) $("model-edit-changes").append(node("li", "", `${fieldNames[change.field] || change.field}: ${change.before} → ${change.after} ${fields[change.field]?.unit || "mm"}`));
    }
    $("model-edit-selected").hidden = !state.modelEditApplied;
    $("model-edit-selected").textContent = state.modelEditApplied ? `적용한 최신 수정: ${state.modelEditApplied.request_text} · 다음 생성에 기록됩니다. 치수를 직접 바꾸면 이 수정 선택은 해제됩니다.` : "";
  }

  function cancelModelEdit() {
    state.modelEditRequest = (state.modelEditRequest || 0) + 1;
    state.modelEditCandidate = null;
    state.modelEditPending = false;
    state.modelEditBusyRequest = null;
    renderModelEdit();
    hideNotice("model-edit-feedback");
  }

  function modelEditInputChanged() {
    state.modelEditRequest = (state.modelEditRequest || 0) + 1;
    state.modelEditCandidate = null;
    renderModelEdit();
  }

  function manualModelChanged() {
    state.modelEditApplied = null;
    state.modelEditAppliedSignature = null;
    cancelModelEdit();
    invalidateCurrentJob("치수가 바뀌었습니다. 새 모델을 생성하면 변경한 형상을 확인할 수 있습니다.");
  }

  async function planModelEdit() {
    if (state.workflowBusy || !state.token) return;
    state.modelEditCandidate = null;
    let base;
    try {
      base = currentEditParameters();
      if (!$("model-edit-text").value.trim() || $("model-edit-text").value.length > 4000) throw new Error("수정할 내용을 4000자 이내로 입력해 주세요.");
      if (!["templates", "llm"].includes($("model-edit-mode").value)) throw new Error("수정 제안 방식을 확인해 주세요.");
    } catch (error) { renderModelEdit(); showNotice("model-edit-feedback", error.message, "error"); return; }
    const request = state.modelEditRequest = (state.modelEditRequest || 0) + 1, scope = modelEditScope();
    const context = { base, text: $("model-edit-text").value, parent: modelEditParentJob(base), engine: $("model-edit-mode").value === "llm" ? "llm" : "template_rules" };
    const current = () => request === state.modelEditRequest && scope === modelEditScope();
    const payload = { text: context.text, mode: $("model-edit-mode").value, base_parameters: base };
    if (context.parent) payload.parent_job_id = context.parent;
    state.modelEditPending = true;
    state.modelEditBusyRequest = request;
    renderModelEdit();
    showNotice("model-edit-feedback", "현재 치수의 수정 제안을 요청하고 있습니다. 적용 전에는 제작안과 모델을 바꾸지 않습니다.");
    try {
      const response = await api("/api/model-edits/plan", payload, undefined, { current });
      if (!current()) return;
      if (response.status === "ready") {
        const review = validateModelEditResponse(response, context);
        state.modelEditCandidate = { review, scope };
        showNotice("model-edit-feedback", "바뀔 치수를 확인한 뒤 적용해 주세요. 모델 생성은 별도로 시작합니다.", "success");
        renderModelEdit();
        $("model-edit-review-heading").focus({ preventScroll: true });
      } else if (response.status === "needs_input" && !Object.hasOwn(response, "review") && !Object.hasOwn(response, "parameters") && response.engine === context.engine && response.capability === "current_template_parameters_only" && Array.isArray(response.questions) && response.questions.every(question => typeof question === "string")) {
        showNotice("model-edit-feedback", response.message || "수정할 치수를 더 구체적으로 알려주세요.", "info", response.questions);
      } else if (["open_profiles", "open_offers"].includes(response.action) && !response.review && !response.parameters) {
        showNotice("model-edit-feedback", response.message || "해당 작업 화면에서 요청을 이어가 주세요.");
        const view = response.action === "open_profiles" ? "profiles" : "offers";
        const button = node("button", "button button-secondary", `${pageNames[view]} 열기`);
        button.type = "button";
        button.addEventListener("click", () => changeView(view));
        $("model-edit-feedback").append(button);
      } else throw new Error("수정 제안 응답을 확인할 수 없습니다. 현재 입력은 유지했습니다.");
    } catch (error) { if (current()) showNotice("model-edit-feedback", error.message, "error"); }
    finally {
      if (state.modelEditBusyRequest === request) {
        state.modelEditPending = false;
        state.modelEditBusyRequest = null;
        renderModelEdit();
      }
    }
  }

  function applyModelEdit() {
    const candidate = state.modelEditCandidate;
    if (state.workflowBusy || !state.token || !candidate || candidate.scope !== modelEditScope()) { renderModelEdit(); return; }
    retainOutcomeDraft();
    state.modelEditApplied = candidate.review.selection;
    for (const change of candidate.review.changes) {
      $(`parameter-${change.field}`).value = String(change.after);
      state.parameters[change.field] = change.after;
    }
    state.modelEditAppliedSignature = modelGeometrySignature();
    cancelModelEdit();
    invalidateCurrentJob("검토한 치수 수정을 적용했습니다. CAD 모델을 생성하면 최신 수정과 원본 출처를 기록합니다.");
    showNotice("model-edit-feedback", "치수 수정을 적용했습니다. 다른 치수와 시작 설계는 유지했습니다. CAD 모델을 별도로 생성해 주세요.", "success");
    $("parameter-heading").focus({ preventScroll: true });
  }

  function renderModelEditRecord(id, record) {
    const area = typeof id === "string" ? $(id) : id;
    area.replaceChildren();
    area.hidden = !record;
    if (!record) return;
    area.append(node("h3", "", "기록된 최신 치수 수정"), node("p", "", record.selection.request_text));
    const changes = node("ul");
    for (const change of record.changes) changes.append(node("li", "", `${fieldNames[change.field] || change.field}: ${change.before} → ${change.after}`));
    area.append(changes, node("p", "muted", "사용자가 확인한 치수입니다. 전체 대화 이력이나 실물 출력 검증을 뜻하지 않습니다."));
    if (record.selection.parent) area.append(node("p", "source-path", `이전 모델 작업 ID: ${record.selection.parent.job_id}`));
  }

  function modelDraftSignature() {
    const template = state.templates.find((item) => item.id === state.template);
    return JSON.stringify([state.template, $("request-text").value, $("plan-mode").value, state.projectSource?.id || state.projectSource?.project_id, state.projectSource?.recipe_sha256, ...(template?.editable_fields || []).map((key) => {
      const input = $(`parameter-${key}`);
      return [key, input.value, Boolean(input.validity?.badInput)];
    })]);
  }

  function modelHasUnsavedChanges() {
    if (!state.template) return false;
    if (state.modelCleanSignature) return modelDraftSignature() !== state.modelCleanSignature;
    if (state.projectSource || $("request-text").value.trim()) return true;
    const template = state.templates.find((item) => item.id === state.template);
    return (template?.editable_fields || []).some((key) => {
      const input = $(`parameter-${key}`);
      return input.validity?.badInput || input.validity?.valid === false || (input.value === "" && !COLOR_PARAMETERS.has(key)) || String(input.value) !== String(template.defaults[key] ?? "");
    });
  }

  function slicerHasUnsavedChanges() {
    return studioHasUnsavedChanges() || state.slicerStaged || Object.keys(state.slicerPending || {}).length > 0 || $("slicer-json").value !== (state.slicerSavedText || "");
  }

  function outcomeHasUnsavedChanges() {
    if (!state.job) return false;
    const savedReasons = JSON.stringify(state.job.user_outcome?.reasons || []);
    const reasons = $("outcome-result").value === "failure" && typeof selectedOutcomeReasons === "function" ? JSON.stringify(selectedOutcomeReasons()) : "[]";
    return $("outcome-result").value !== (state.job.user_outcome?.result || "not_tested") || $("outcome-notes").value !== (state.job.user_outcome?.notes || "") || reasons !== savedReasons;
  }

  function hasPendingWork() {
    return Boolean(state.modelEditPending || state.modelEditCandidate) || state.retainedOutcomeDrafts.length > 0 || state.workflowBusy || state.workspaceBusy || state.offersPending || offersHaveUnsavedChanges() || modelHasUnsavedChanges() || slicerHasUnsavedChanges() || outcomeHasUnsavedChanges() || workspaceDirty();
  }

  function replacementSignature() {
    return JSON.stringify([modelDraftSignature(), state.job?.id, $("slicer-json").value, state.slicerContext, state.slicerStaged, studioContext(), $("outcome-result").value, $("outcome-notes").value]);
  }

  function cancelModelReplacement() {
    const previous = state.modelReplacement;
    state.modelReplacement = null;
    state.modelTransitionRequest += 1;
    $("model-replace-confirm").hidden = true;
    if (previous?.button?.isConnected) previous.button.focus({ preventScroll: true });
  }

  function newPlanHasPendingWork() {
    if (state.modelEditPending || state.modelEditCandidate || state.job || state.projectSource || state.modelEditApplied || state.retainedOutcomeDrafts.length || slicerHasUnsavedChanges() || outcomeHasUnsavedChanges()) return true;
    const template = state.templates.find(item => item.id === state.template);
    return (template?.editable_fields || []).some(key => {
      const input = $(`parameter-${key}`);
      return input.validity?.badInput || input.validity?.valid === false || input.value !== String(template.defaults[key] ?? "");
    });
  }

  function requestModelReplacement(action) {
    if (state.workflowBusy) return;
    cancelModelReplacement();
    cancelProjectApplication();
    if (action.kind === "plan" ? newPlanHasPendingWork() : (state.retainedOutcomeDrafts.length || modelHasUnsavedChanges() || slicerHasUnsavedChanges() || outcomeHasUnsavedChanges())) {
      state.modelReplacement = { ...action, signature: replacementSignature() };
      const titles = { history: "현재 제작안을 저장된 모델로 바꿀까요?", retry: "현재 제작안을 이 기록의 치수로 바꿀까요?", template: "현재 제작안을 다른 템플릿으로 바꿀까요?", reset: "현재 제작안을 기본 치수로 되돌릴까요?" };
      $("model-replace-title").textContent = titles[action.kind] || "현재 제작안을 바꿀까요?";
      $("model-replace-detail").textContent = `${action.title || "선택한 제작안"}을 준비합니다. 현재 치수와 미리보기·다운로드를 교체합니다. 저장하지 않은 출력 메모는 원래 작업과 저장 위치를 표시해 이 화면에 보관합니다. 생성해 둔 파일은 작업 기록에 남습니다.`;
      $("model-replace-confirm").hidden = false;
      updateWorkflowControls();
      $("model-replace-confirm").scrollIntoView?.({ block: "center", behavior: "auto" });
      $("model-confirm-replace").focus({ preventScroll: true });
      return;
    }
    performModelReplacement(action);
  }

  function confirmModelReplacement() {
    if (state.workflowBusy || !state.modelReplacement) return;
    const action = state.modelReplacement;
    if (action.signature !== replacementSignature()) {
      action.signature = replacementSignature();
      $("model-replace-detail").textContent = "확인 안내가 열린 뒤 편집 내용이 바뀌었습니다. 바뀐 현재 제작안을 교체하려면 한 번 더 확인해 주세요. 유지하면 모든 입력을 그대로 남깁니다.";
      return;
    }
    cancelModelReplacement();
    performModelReplacement(action);
  }

  function performModelReplacement(action) {
    if (state.workflowBusy) return;
    if (action.kind === "history" && action.job.result.template === "imported") {
      // An imported model has no template draft: keep the draft, show the job for slicing and sending.
      cancelModelReplacement();
      cancelModelEdit();
      renderJob(action.job);
      hideNotice("model-feedback");
      hideNotice("plan-feedback");
      changeView("models");
    } else if (action.kind === "history") {
      applyDraft(action.job.result.template, action.job.result.parameters, action.job.design_source || null);
      renderJob(action.job);
      hideNotice("model-feedback");
      hideNotice("plan-feedback");
      changeView("models");
    } else if (action.kind === "retry") {
      applyDraft(action.job.request.template, action.job.request, action.job.design_source || null);
      hideNotice("plan-feedback");
      showNotice("model-feedback", "저장된 요청의 치수를 준비했습니다. 치수를 확인한 뒤 새 모델을 생성해 주세요. 이전 중단·실패 기록은 그대로 남습니다.");
      changeView("models");
    } else if (action.kind === "plan") {
      applyDraft(action.result.parameters.template, action.result.parameters);
      showNotice("plan-feedback", action.result.message, "success", action.result.assumptions || []);
    } else if (action.kind === "paste") {
      applyDraft(action.template, action.parameters);
      hideNotice("plan-feedback");
      showNotice("parameter-share-feedback", "붙여 넣은 설정을 적용했습니다. 치수를 확인한 뒤 CAD 모델을 생성하세요.", "success");
    } else {
      applyDraft(action.template);
      hideNotice("plan-feedback");
      hideNotice("model-feedback");
      if (action.kind === "reset") toast("선택한 템플릿의 기본값을 적용했습니다.");
    }
    $("parameter-heading").focus({ preventScroll: true });
  }

  $("discovery-form").addEventListener("submit", (event) => { event.preventDefault(); recommendProjects(); });
  for (const axis of ["width", "depth", "height"]) $(`space-${axis}`).addEventListener("input", discoveryFiltersChanged);
  $("discovery-apply").addEventListener("click", requestProjectApplication);
  $("discovery-confirm-apply").addEventListener("click", confirmProjectApplication);
  $("discovery-cancel-apply").addEventListener("click", cancelProjectApplication);
  $("detach-source").addEventListener("click", detachProjectSource);

  function renderTemplates() {
    const list = $("template-cards");
    list.replaceChildren();
    state.templates.forEach((template, index) => {
      const button = node("button", "template-card");
      button.type = "button";
      button.disabled = state.workflowBusy;
      button.dataset.template = template.id;
      button.setAttribute("aria-pressed", String(template.id === state.template));
      button.classList.toggle("selected", template.id === state.template);
      const top = node("div", "template-topline");
      top.append(node("span", "template-index", `0${index + 1} / TEMPLATE`), node("span", "template-select", "✓"));
      button.append(top, node("strong", "", template.title), node("p", "", template.description));
      const defaults = template.defaults || {};
      button.append(node("span", "template-size", templateSizeText(defaults)));
      button.addEventListener("click", () => requestModelReplacement({ kind: "template", template: template.id, title: template.title, button }));
      list.append(button);
    });
  }

  function templateSizeText(defaults) {
    // A text-sized template has no fixed outer box; show its default text and letter size instead.
    if (typeof defaults.text === "string") return `기본 글자 “${defaults.text}” · 글자 크기 ${defaults.text_size} mm`;
    if (Number.isFinite(defaults.drain_hole)) return `지름 ${defaults.width} × 높이 ${defaults.height} mm · 기본 크기`;
    if ([defaults.width, defaults.depth, defaults.height].every(Number.isFinite)) return `${defaults.width} × ${defaults.depth} × ${defaults.height} mm · 기본 크기`;
    return "크기는 입력값에 맞춰 정해집니다";
  }

  function readParameter(input) {
    // Text fields stay strings; every other field is a number.
    if (COLOR_PARAMETERS.has(input.dataset.parameter)) return input.value;
    return TEXT_PARAMETERS.has(input.dataset.parameter) ? input.value.trim() : input.valueAsNumber;
  }

  function parameterInputComplete(input) {
    if (COLOR_PARAMETERS.has(input.dataset.parameter)) return input.value === "" || Object.hasOwn(PALETTE, input.value);
    if (TEXT_PARAMETERS.has(input.dataset.parameter)) return (input.value.trim().length > 0 || state.template === "keycap") && input.validity?.valid !== false;
    return Boolean(input.value.trim()) && !input.validity?.badInput && input.validity?.valid !== false && Number.isFinite(Number(input.value));
  }

  function parameterField(template, key) {
    const definition = fields[key];
    const unit = definition.unit ?? "mm";
    const container = node("div", "parameter-field");
    container.dataset.field = key;
    const labelText = templateFieldLabels[template.id]?.[key] || definition.label;
    const label = node("label", "", unit ? `${labelText} · ${unit}` : labelText);
    if (definition.kind === "color") return colorField(template, key, labelText);
    if (definition.kind === "text") {
      container.classList.add("parameter-text");
      const description = node("p", "parameter-desc", templateFieldDescriptions[template.id]?.[key] || fieldDescriptions[key] || "");
      description.id = `parameter-desc-${key}`;
      const input = node("input");
      input.id = `parameter-${key}`;
      input.name = key;
      input.type = "text";
      // A keycap legend is short and optional (a blank key).
      input.maxLength = template.id === "keycap" ? 6 : definition.maxLength;
      input.required = template.id !== "keycap";
      input.autocomplete = "off";
      input.value = state.parameters[key] ?? "";
      input.dataset.parameter = key;
      input.setAttribute("aria-describedby", description.id);
      label.htmlFor = input.id;
      container.append(label, description, input);
      return container;
    }
    const description = node("p", "parameter-desc", templateFieldDescriptions[template.id]?.[key] || fieldDescriptions[key] || "");
    description.id = `parameter-desc-${key}`;
    const input = node("input");
    input.id = `parameter-${key}`;
    input.name = key;
    input.type = "number";
    input.min = definition.min;
    input.max = definition.max;
    input.step = definition.unit === "개" ? "1" : definition.unit === "u" ? "0.25" : "any";
    input.required = true;
    input.value = state.parameters[key];
    input.dataset.parameter = key;
    label.htmlFor = input.id;
    const stepper = node("div", "parameter-stepper");
    const stepButton = (direction, text) => {
      const button = node("button", "step-button", text);
      button.type = "button";
      button.dataset.stepFor = key;
      button.dataset.direction = String(direction);
      button.setAttribute("aria-label", `${labelText} ${direction < 0 ? "줄이기" : "늘리기"} (${fieldNudges[key] || 1} ${unit})`);
      return button;
    };
    stepper.append(stepButton(-1, "−"), input, stepButton(1, "+"));
    const slider = node("input", "parameter-slider");
    slider.type = "range";
    slider.min = definition.min;
    slider.max = definition.max;
    slider.step = String(fieldNudges[key] || 1);
    slider.value = state.parameters[key];
    slider.dataset.sliderFor = key;
    slider.setAttribute("aria-label", `${labelText} 슬라이더`);
    slider.tabIndex = -1;  // the number field and +/- already cover keyboard use
    const help = node("small", "", `기본 ${template.defaults[key]} ${unit}`);
    help.id = `parameter-help-${key}`;
    input.setAttribute("aria-describedby", `${description.id} ${help.id}`);
    container.append(label, description, stepper, slider, help);
    return container;
  }

  function colorField(template, key, labelText) {
    // A hidden input keeps the shared read/compare paths; swatches only set its value.
    const container = node("div", "parameter-field parameter-color");
    container.dataset.field = key;
    const heading = node("span", "parameter-label", labelText);
    heading.id = `parameter-label-${key}`;
    const description = node("p", "parameter-desc", templateFieldDescriptions[template.id]?.[key] || fieldDescriptions[key] || "");
    const input = node("input");
    input.type = "hidden";
    input.id = `parameter-${key}`;
    input.name = key;
    input.value = state.parameters[key] ?? "";
    input.dataset.parameter = key;
    const swatches = node("div", "color-swatches");
    swatches.setAttribute("role", "radiogroup");
    swatches.setAttribute("aria-labelledby", heading.id);
    const options = [["", key === "accent_color" ? "받침과 같게" : "정하지 않음", null], ...Object.entries(PALETTE).map(([value, [name, hex]]) => [value, name, hex])];
    for (const [value, name, hex] of options) {
      const button = node("button", "color-swatch" + (hex ? "" : " color-none"));
      button.type = "button";
      button.dataset.colorFor = key;
      button.dataset.colorValue = value;
      button.setAttribute("role", "radio");
      button.setAttribute("aria-checked", String(input.value === value));
      button.setAttribute("aria-label", `${labelText} ${name}`);
      button.title = name;
      if (hex) button.style.setProperty("--swatch", hex);
      else button.textContent = name;
      swatches.append(button);
    }
    const chosen = node("small", "color-chosen", input.value ? PALETTE[input.value]?.[0] || input.value : (key === "accent_color" ? "글자도 받침 색으로 출력" : "필라멘트 색을 정하지 않았습니다"));
    chosen.id = `parameter-help-${key}`;
    container.append(heading, description, input, swatches, chosen);
    syncRadioGroup(swatches);
    return container;
  }

  function chooseColor(key, value) {
    const input = $(`parameter-${key}`);
    if (!input || input.disabled || (value && !Object.hasOwn(PALETTE, value))) return;
    input.value = value;
    for (const button of document.querySelectorAll(`[data-color-for="${key}"]`)) button.setAttribute("aria-checked", String(button.dataset.colorValue === value));
    const group = document.querySelector(`[data-color-for="${key}"]`)?.closest('[role="radiogroup"]');
    if (group) syncRadioGroup(group);
    const chosen = $(`parameter-help-${key}`);
    if (chosen) chosen.textContent = value ? PALETTE[value][0] : (key === "accent_color" ? "글자도 받침 색으로 출력" : "필라멘트 색을 정하지 않았습니다");
    input.dispatchEvent(new Event("input", { bubbles: true }));
  }

  // ---------------------------------------------------------------------------
  // Radio groups (colour swatches, store filters): one Tab stop, arrows move the choice.

  function syncRadioGroup(group) {
    const radios = [...group.querySelectorAll('[role="radio"]')].filter((radio) => !radio.hidden);
    const checked = radios.find((radio) => radio.getAttribute("aria-checked") === "true") || radios[0];
    for (const radio of radios) radio.tabIndex = radio === checked ? 0 : -1;
  }

  function radioGroupKey(event) {
    const radio = event.target.closest?.('[role="radio"]');
    const group = radio?.closest('[role="radiogroup"]');
    if (!radio || !group) return;
    const radios = [...group.querySelectorAll('[role="radio"]')].filter((item) => !item.hidden && !item.disabled);
    const index = radios.indexOf(radio);
    const moves = { ArrowRight: index + 1, ArrowDown: index + 1, ArrowLeft: index - 1, ArrowUp: index - 1, Home: 0, End: radios.length - 1 };
    if (!(event.key in moves) || index < 0) return;
    event.preventDefault();
    const next = radios[(moves[event.key] + radios.length) % radios.length];
    next.click();  // selection follows focus, as in a native radio group
    syncRadioGroup(group);
    next.focus();
  }

  function stepParameter(key, direction) {
    const input = $(`parameter-${key}`);
    const definition = fields[key];
    if (!input || !definition || input.disabled) return;
    const nudge = fieldNudges[key] || 1;
    const current = Number.isFinite(input.valueAsNumber) ? input.valueAsNumber : Number(state.parameters[key]);
    const decimals = (String(nudge).split(".")[1] || "").length;
    const next = Math.min(definition.max, Math.max(definition.min, Number((current + direction * nudge).toFixed(decimals))));
    input.value = String(next);
    input.dispatchEvent(new Event("input", { bubbles: true }));
  }

  function syncParameterSlider(key) {
    const input = $(`parameter-${key}`);
    const slider = document.querySelector(`[data-slider-for="${key}"]`);
    if (slider && input && Number.isFinite(input.valueAsNumber)) slider.value = String(input.valueAsNumber);
  }

  function currentParameterSnapshot() {
    const template = state.templates.find((item) => item.id === state.template);
    if (!template) throw new Error("템플릿을 먼저 선택해 주세요.");
    const parameters = {};
    for (const key of template.editable_fields) {
      const input = $(`parameter-${key}`);
      if (!input || !parameterInputComplete(input)) throw new Error("모든 치수를 올바르게 입력한 뒤 복사해 주세요.");
      if (COLOR_PARAMETERS.has(key)) { if (input.value) parameters[key] = input.value; continue; }
      parameters[key] = TEXT_PARAMETERS.has(key) ? input.value.trim() : Number(input.value);
    }
    return { format: PARAMETER_FORMAT, version: 1, template: template.id, title: template.title, parameters };
  }

  function parseParameterText(text) {
    let data;
    try { data = JSON.parse(String(text || "").trim()); } catch { throw new Error("붙여 넣은 내용이 복사한 설정 형식(JSON)이 아닙니다."); }
    if (!data || typeof data !== "object" || Array.isArray(data)) throw new Error("붙여 넣은 내용에서 설정을 찾지 못했습니다.");
    if (data.format !== undefined && data.format !== PARAMETER_FORMAT) throw new Error("이 앱에서 복사한 설정이 아닙니다.");
    const template = state.templates.find((item) => item.id === data.template);
    if (!template) throw new Error("붙여 넣은 설정의 템플릿을 이 버전에서 지원하지 않습니다.");
    const source = data.parameters && typeof data.parameters === "object" && !Array.isArray(data.parameters) ? data.parameters : data;
    const parameters = {};
    for (const [key, value] of Object.entries(source)) {
      if (["format", "version", "template", "title", "parameters"].includes(key)) continue;
      if (!template.editable_fields.includes(key)) throw new Error(`${fieldNames[key] || key}은(는) ${template.title}에서 쓰지 않는 치수입니다.`);
      const definition = fields[key];
      if (definition.kind === "color") {
        if (typeof value !== "string" || (value && !Object.hasOwn(PALETTE, value))) throw new Error(`${fieldNames[key] || key}은(는) ${Object.values(PALETTE).map(([name]) => name).join("·")} 중 하나여야 합니다.`);
        parameters[key] = value;
        continue;
      }
      if (definition.kind === "text") {
        if (typeof value !== "string" || !value.trim() || value.length > definition.maxLength) throw new Error(`${fieldNames[key] || key}은(는) 1~${definition.maxLength}자의 글자여야 합니다.`);
        parameters[key] = value.trim();
        continue;
      }
      if (typeof value !== "number" || !Number.isFinite(value) || value < definition.min || value > definition.max || (definition.unit === "개" && !Number.isInteger(value))) {
        throw new Error(`${fieldNames[key] || key} 값은 ${definition.min}~${definition.max}${definition.unit === "개" ? "개(정수)" : ` ${definition.unit || "mm"}`} 범위의 숫자여야 합니다.`);
      }
      parameters[key] = value;
    }
    if (!Object.keys(parameters).length) throw new Error("붙여 넣은 설정에 치수가 없습니다.");
    return { template, parameters };
  }

  async function copyParameters() {
    try {
      const text = JSON.stringify(currentParameterSnapshot());
      try {
        await navigator.clipboard.writeText(text);
        showNotice("parameter-share-feedback", "현재 템플릿과 치수를 복사했습니다. 다른 창이나 다음 작업에서 “붙여넣기”로 그대로 쓸 수 있습니다.", "success");
      } catch {
        // Clipboard access can be refused; try the selection-based copy, then let the user copy by hand.
        $("paste-heading").textContent = "복사할 설정";
        $("paste-apply").hidden = true;
        $("paste-text").value = text;
        $("paste-panel").hidden = false;
        $("paste-text").select();
        let copied = false;
        try { copied = document.execCommand("copy"); } catch { copied = false; }
        showNotice("parameter-share-feedback", copied ? "현재 템플릿과 치수를 복사했습니다. 아래 칸에도 같은 내용을 표시했습니다." : "브라우저가 클립보드 쓰기를 막았습니다. 아래 칸의 선택된 텍스트를 직접 복사하세요(Ctrl/⌘+C).", copied ? "success" : "warning");
      }
    } catch (error) { showNotice("parameter-share-feedback", error.message, "error"); }
  }

  function openPastePanel() {
    $("paste-heading").textContent = "복사한 설정 붙여넣기";
    $("paste-apply").hidden = false;
    $("paste-panel").hidden = false;
    $("paste-text").value = "";
    hideNotice("parameter-share-feedback");
    $("paste-text").focus();
  }

  function applyPastedParameters() {
    try {
      const { template, parameters } = parseParameterText($("paste-text").value);
      $("paste-panel").hidden = true;
      requestModelReplacement({ kind: "paste", template: template.id, parameters, title: `붙여 넣은 ${template.title} 설정`, button: $("paste-apply") });
    } catch (error) { showNotice("parameter-share-feedback", error.message, "error"); }
  }

  function applyDraft(templateId, parameters, source = null) {
    const template = state.templates.find((item) => item.id === templateId);
    if (!template) throw new Error("지원하지 않는 제작 템플릿입니다.");
    cancelModelReplacement();
    cancelModelEdit();
    state.modelEditApplied = null;
    state.modelEditAppliedSignature = null;
    state.modelCleanSignature = null;
    state.projectSource = source;
    state.projectReplacement = null;
    $("discovery-replace-confirm").hidden = true;
    renderProjectSource("draft-source", source);
    state.template = templateId;
    state.parameters = { ...template.defaults, template: templateId };
    for (const key of template.editable_fields) {
      if (parameters && Object.prototype.hasOwnProperty.call(parameters, key)) state.parameters[key] = parameters[key];
    }
    invalidateCurrentJob("제작안이 바뀌었습니다. 치수를 확인하고 새 모델을 생성해 주세요.");
    $("parameter-description").textContent = template.description;
    const grid = $("parameter-fields");
    grid.replaceChildren();
    const grouped = new Set(fieldGroups.flatMap(([, , keys]) => keys));
    // Colour comes last: it changes the print, not the shape.
    const groups = [...fieldGroups.filter(([id]) => id !== "color"), ["shape", "모양", template.editable_fields.filter((key) => !grouped.has(key))], ...fieldGroups.filter(([id]) => id === "color")];
    for (const [groupId, groupLabel, keys] of groups) {
      const present = keys.filter((key) => template.editable_fields.includes(key) && fields[key]);
      if (!present.length) continue;
      const group = node("fieldset", "parameter-group");
      group.dataset.group = groupId;
      group.append(node("legend", "", groupLabel));
      const groupGrid = node("div", "parameter-grid");
      for (const key of present) groupGrid.append(parameterField(template, key));
      group.append(groupGrid);
      grid.append(group);
    }
    renderTemplates();
    updateWorkflowControls();
  }

  $("model-form").addEventListener("input", (event) => {
    if (event.target.dataset.sliderFor) {
      const input = $(`parameter-${event.target.dataset.sliderFor}`);
      input.value = event.target.value;
      input.dispatchEvent(new Event("input", { bubbles: true }));
      return;
    }
    if (event.target.dataset.parameter) { syncParameterSlider(event.target.dataset.parameter); manualModelChanged(); }
  });
  $("model-form").addEventListener("click", (event) => {
    const swatch = event.target.closest("[data-color-for]");
    if (swatch) { chooseColor(swatch.dataset.colorFor, swatch.dataset.colorValue); return; }
    const button = event.target.closest("[data-step-for]");
    if (button) stepParameter(button.dataset.stepFor, Number(button.dataset.direction));
  });
  $("copy-parameters").addEventListener("click", copyParameters);
  $("paste-parameters").addEventListener("click", openPastePanel);
  $("paste-apply").addEventListener("click", applyPastedParameters);
  $("paste-cancel").addEventListener("click", () => { $("paste-panel").hidden = true; });

  $("reset-parameters").addEventListener("click", () => requestModelReplacement({ kind: "reset", template: state.template, title: "현재 템플릿의 기본 치수", button: $("reset-parameters") }));
  $("model-confirm-replace").addEventListener("click", confirmModelReplacement);
  $("model-cancel-replace").addEventListener("click", cancelModelReplacement);

  async function preparePlan() {
    if (state.workflowBusy) return;
    const signature = modelDraftSignature(), epoch = state.connectionEpoch;
    const current = () => signature === modelDraftSignature() && epoch === state.connectionEpoch;
    hideNotice("plan-feedback");
    try {
      const result = await withWorkflow($("plan-button"), "요청 해석 중", () => api("/api/plan", { text: $("request-text").value, mode: $("plan-mode").value }, undefined, { current }));
      if (!current()) return;
      if (result.status === "ready" && result.parameters) {
        requestModelReplacement({ kind: "plan", result, title: "요청에서 준비한 새 제작안", button: $("plan-button") });
      } else {
        showNotice("plan-feedback", result.message || "추가 정보가 필요합니다.", "info", (result.questions || []).filter((item) => item !== result.message));
        const view = { open_profiles: "profiles", open_offers: "offers" }[result.action];
        if (view) {
          const button = node("button", "button button-secondary", `${pageNames[view]} 열기`);
          button.type = "button";
          button.addEventListener("click", () => changeView(view));
          $("plan-feedback").append(button);
        }
      }
    } catch (error) { if (current() || (error.code === "connection_changed" && signature === modelDraftSignature())) showNotice("plan-feedback", error.message, "error"); }
  }

  $("model-edit-form").addEventListener("submit", event => { event.preventDefault(); planModelEdit(); });
  $("model-edit-apply").addEventListener("click", applyModelEdit);
  $("model-edit-cancel").addEventListener("click", cancelModelEdit);
  $("model-edit-text").addEventListener("input", modelEditInputChanged);
  $("model-edit-mode").addEventListener("change", modelEditInputChanged);
  $("request-text").addEventListener("input", modelEditInputChanged);
  $("plan-mode").addEventListener("change", modelEditInputChanged);

  $("plan-form").addEventListener("submit", (event) => { event.preventDefault(); preparePlan(); });

  $("plan-mode").addEventListener("change", () => {
    $("provider-note").textContent = $("plan-mode").value === "llm"
      ? "LLM 모드에서는 입력한 요청이 설정된 모델 서버로 전송됩니다. 지원 템플릿의 제작안만 받습니다."
      : "템플릿 모드는 지원하는 물건과 치수를 정해진 규칙으로 해석합니다.";
  });

  async function generateModel() {
    if (state.workflowBusy) return;
    if (!$("model-form").reportValidity()) return;
    hideNotice("model-feedback");
    const signature = modelDraftSignature();
    const parameters = { template: state.template };
    for (const input of document.querySelectorAll("[data-parameter]")) parameters[input.dataset.parameter] = readParameter(input);
    if (state.modelEditApplied && state.modelEditAppliedSignature === modelGeometrySignature()) parameters.model_edit = state.modelEditApplied;
    if (state.projectSource) parameters.project_selection = { id: state.projectSource.project_id || state.projectSource.id, recipe_sha256: state.projectSource.recipe_sha256 };
    try {
      await withWorkflow($("generate-button"), "CAD 생성 · 검증 중", async () => {
        const job = await api("/api/models", parameters, undefined, { current: () => signature === modelDraftSignature() });
        if (signature !== modelDraftSignature()) {
          invalidateCurrentJob("생성 중에 제작안이 바뀌었습니다. 생성한 파일은 작업 기록에서 확인하고, 현재 치수로 다시 생성해 주세요.");
          showNotice("model-feedback", "생성 중에 제작안이 바뀌었습니다. 생성한 파일은 작업 기록에서 확인할 수 있습니다. 현재 치수는 유지했습니다.");
          return;
        }
        renderJob(job);
        showNotice("model-feedback", "실제 CAD 모델과 파일을 생성했습니다. 오른쪽에서 형상과 검증 결과를 확인하세요.", "success");
        toast("모델 파일이 준비됐습니다.");
      });
    } catch (error) { showNotice("model-feedback", error.code === "model_edit_parent_changed" ? `${error.message} 현재 치수와 수정 선택은 유지했습니다. 이전 모델 기록을 확인한 뒤 수정 제안을 다시 검토해 주세요.` : error.status === 409 && error.code !== "resource_busy" && state.projectSource ? `${error.message} 현재 치수는 유지했습니다. 출처 연결을 해제하거나 새 시작점을 선택한 뒤 다시 생성해 주세요.` : error.message, "error"); }
  }

  $("model-form").addEventListener("submit", (event) => { event.preventDefault(); generateModel(); });

  function metric(label, value) {
    const item = node("div", "metric");
    item.append(node("span", "metric-label", label), node("strong", "metric-value", value));
    return item;
  }

  function localDownload(url) {
    if (typeof url !== "string") return null;
    try {
      const parsed = new URL(url, window.location.origin);
      return parsed.origin === window.location.origin && parsed.pathname.startsWith("/api/jobs/") ? parsed.href : null;
    } catch { return null; }
  }

  function renderDownloads(job) {
    syncPrintSend(job);
    const area = $("download-links");
    area.replaceChildren();
    const labels = { stl: "STL", step: "STEP", three_mf: "3MF 형상", color_three_mf: "색상 3MF (받침·글자 필라멘트 지정)", source: "Python 소스", manifest: "생성 기록", prepared_three_mf: "설정 포함 3MF", sliced_three_mf: "슬라이스 3MF", slice: "슬라이스 결과" };
    const files = { ...(job.artifacts || {}) };
    if (["running", "interrupted"].includes(job.latest_slice?.phase)) { delete files.prepared_three_mf; delete files.sliced_three_mf; delete files.slice; }
    if (job.bundle_url) files.bundle = job.bundle_url;
    labels.bundle = "전체 묶음";
    for (const [key, url] of Object.entries(files)) {
      const href = localDownload(url);
      if (!href || !labels[key]) continue;
      const link = node("a", "download-link", labels[key]);
      link.href = href;
      link.setAttribute("download", "");
      link.append(node("span", "", "↓"));
      area.append(link);
    }
  }

  const printabilityStatus = { ok: ["형상 점검 통과", "success"], review: ["확인할 점이 있어요", "warning"], needs_change: ["수정을 권해요", "error"] };
  const printabilityMarks = { pass: "✓", warn: "!", fail: "×" };

  function printerReportedNozzle() {
    const value = state.printerStatus?.connection?.state === "reporting" ? state.printerStatus.print?.nozzle?.diameter_mm : null;
    return [0.2, 0.4, 0.6, 0.8].includes(value) ? value : null;
  }

  function updatePrintabilityControls() {
    const pending = Boolean(state.printabilityPending);
    const reported = printerReportedNozzle();
    const current = Number($("printability-nozzle").value);
    // An imported mesh has no measured wall thickness, so a nozzle recheck changes nothing.
    const imported = state.job?.template === "imported";
    $("printability-nozzle").disabled = pending || !state.job || !state.token || imported;
    $("printability-run").disabled = pending || !state.job || !state.token || imported;
    const usePrinter = $("printability-use-printer");
    usePrinter.hidden = !reported || reported === current || !state.printabilityShown;
    usePrinter.disabled = pending;
    if (reported) usePrinter.textContent = `프린터가 보고한 ${reported} mm 노즐로 점검 →`;
  }

  async function recheckPrintability(nozzle) {
    const job = state.job;
    if (!job) return;
    const request = ++state.printabilityRequest;
    const previous = state.printabilityNozzle;
    state.printabilityPending = true;
    $("printability-nozzle").value = String(nozzle);
    hideNotice("printability-feedback");
    updatePrintabilityControls();
    try {
      const review = await api(`/api/jobs/${encodeURIComponent(job.id)}/printability`, { nozzle_mm: nozzle });
      if (request !== state.printabilityRequest || state.job?.id !== job.id) return;
      renderPrintability(review);
    } catch (error) {
      if (request !== state.printabilityRequest || state.job?.id !== job.id) return;
      $("printability-nozzle").value = String(previous);
      showNotice("printability-feedback", error.message, "error");
    } finally {
      if (request === state.printabilityRequest) { state.printabilityPending = false; updatePrintabilityControls(); }
    }
  }

  function journeySteps() {
    const job = state.job;
    const review = job && state.printabilityReview ? state.printabilityReview : job?.result?.printability;
    const dims = job?.result?.dimensions_mm;
    const reviewText = { ok: "점검 통과", review: "확인할 점 있음", needs_change: "수정 권장" }[review?.status];
    // Only a recorded prepared project or a successful slice counts; a reviewed plan,
    // a blocked plan or a failed run does not.
    const latest = job?.latest_slice;
    const prepared = Boolean(latest?.phase === "finished" && (latest.plan?.project_prepared === true || latest.execution?.status === "sliced"));
    const downloaded = Boolean(job && state.downloadedJobId === job.id);
    const outcome = job?.user_outcome?.result;
    const recorded = Boolean(outcome && outcome !== "not_tested");
    return [
      { id: "size", label: "치수 정하기", done: Boolean(job), detail: dims ? `${numberFormat.format(dims.x)} × ${numberFormat.format(dims.y)} × ${numberFormat.format(dims.z)} mm` : "시작점을 고르거나 치수 입력" },
      { id: "make", label: "만들기·점검", done: Boolean(job), attention: Boolean(job && review && review.status !== "ok"), detail: job ? (reviewText || "CAD 검증 완료") : "CAD 생성 전" },
      { id: "prepare", label: "출력 준비", done: prepared || downloaded, detail: prepared ? (latest.execution?.status === "sliced" ? "슬라이스 파일 있음" : "설정 포함 3MF 있음") : downloaded ? "3MF 내려받음" : job ? "3MF를 Studio에서 열기" : "모델을 먼저 만들기" },
      { id: "record", label: "결과 기록", done: recorded, detail: recorded ? (outcome === "success" ? "성공으로 기록" : "실패로 기록") : "출력 후 직접 기록" },
    ];
  }

  function journeyNext(steps) {
    const job = state.job;
    if (!job) return { text: "치수를 확인하고 CAD 모델을 만들어 보세요.", label: "치수 확인하러 가기", target: "parameter-heading" };
    // A warning is advice: once the user moves on (downloads or prepares), follow them.
    if (steps[1].attention && !steps[2].done) return { text: "형상 점검에서 확인할 점이 있어요. 고칠 치수를 바로 찾을 수 있습니다.", label: "점검 결과 보기", target: "printability-review" };
    if (!steps[2].done) return { text: "모델이 준비됐어요. 3MF를 내려받아 Bambu Studio에서 여세요.", label: "출력 방법 보기", target: "print-quickstart" };
    if (!steps[3].done) return { text: "출력했다면 결과를 남겨 두세요. 다음에 같은 조건으로 만들 때 참고합니다.", label: "결과 기록하기", target: "outcome-card", focus: "outcome-result" };
    return { text: "이 작업의 기록까지 마쳤어요. 고칠 점이 있으면 치수를 바꿔 다시 만드세요.", label: "치수 바꾸러 가기", target: "parameter-heading" };
  }

  function renderOutcomePrinterHint() {
    // A printer's finish/fail report is a hint for the user's own record, never the record itself.
    const hint = $("outcome-printer-hint");
    const kept = state.job?.printer_report;
    if (kept && ["FINISH", "FAILED"].includes(kept.state)) {
      const codes = (kept.codes || []).map((item) => item.code).join(", ");
      hint.textContent = `프린터 ${kept.serial || ""}가 ${dateTime(kept.observed_at)}에 이 작업의 ${kept.state === "FINISH" ? "출력 완료" : "출력 실패"}를 보고해 기록해 두었습니다${codes ? ` (코드 ${codes})` : ""}. 프린터 보고는 실물 확인이 아닙니다. 출력물을 직접 확인한 뒤 아래 결과를 골라 주세요.`;
      hint.hidden = false;
      return;
    }
    const status = state.printerStatus;
    const reported = status?.connection?.state === "reporting" ? status.print?.state : null;
    if (!state.job || !["FINISH", "FAILED"].includes(reported)) { hint.hidden = true; return; }
    const job = status.print.job_name ? ` (프린터의 작업 이름: ${status.print.job_name})` : "";
    const verdict = reported === "FINISH" ? "출력 완료" : "출력 실패";
    hint.textContent = `${dateTime(status.observed_at)}에 읽은 프린터 ${status.target?.serial || ""}의 상태: ${verdict} 보고${job}. 이 모델을 출력한 것이 맞는지, 실물을 직접 확인한 뒤 아래 결과를 골라 주세요. 자동으로 선택하지 않습니다.`;
    hint.hidden = false;
  }

  function renderJourney() {
    renderOutcomePrinterHint();
    const steps = journeySteps();
    const current = steps.findIndex((step, index) => !step.done || (step.attention && !steps[index + 1]?.done));
    $("journey-steps").replaceChildren(...steps.map((step, index) => {
      const item = node("li", `journey-step${step.done ? " is-done" : ""}${index === current ? " is-current" : ""}${step.attention ? " needs-attention" : ""}`);
      if (index === current) item.setAttribute("aria-current", "step");
      item.dataset.step = step.id;
      item.append(node("span", "journey-mark", step.attention ? "!" : step.done ? "✓" : String(index + 1)), node("span", "journey-label", step.label), node("span", "journey-detail", step.detail));
      return item;
    }));
    const next = journeyNext(steps);
    $("journey-next-text").textContent = next.text;
    const button = $("journey-next-button");
    button.textContent = `${next.label} →`;
    button.dataset.target = next.target;
    button.dataset.focus = next.focus || "";
  }

  function goToJourneyTarget() {
    const button = $("journey-next-button");
    const target = $(button.dataset.target);
    if (!target) return;
    target.scrollIntoView({ block: "start", behavior: "smooth" });
    const focus = button.dataset.focus ? $(button.dataset.focus) : target.matches("h1,h2,h3") ? target : null;
    if (focus) { if (!focus.hasAttribute("tabindex") && focus.matches("h1,h2,h3")) focus.setAttribute("tabindex", "-1"); focus.focus({ preventScroll: true }); }
  }

  function renderColorLegend(parts) {
    const list = $("preview-colors");
    const valid = Array.isArray(parts) ? parts.filter((part) => part && typeof part.label === "string") : [];
    list.hidden = !valid.length;
    list.replaceChildren(...valid.map((part) => {
      const item = node("li", "preview-color");
      const chip = node("span", "color-dot");
      chip.setAttribute("aria-hidden", "true");
      if (/^#[0-9a-f]{6}$/i.test(part.hex || "")) chip.style.setProperty("--swatch", part.hex);
      const grams = Number.isFinite(part.volume_mm3) ? ` · 약 ${numberFormat.format(part.volume_mm3 * 1.24 / 1000)} g(PLA, 꽉 찬 기준)` : "";
      item.append(chip, node("span", "", `${part.label}: ${part.name}${valid.length > 1 ? ` · 필라멘트 ${part.filament}` : ""}${grams}`));
      return item;
    }));
  }

  function renderPrintability(review) {
    state.printabilityReview = review && Array.isArray(review.items) ? review : null;
    const section = $("printability-review");
    if (!review || !Array.isArray(review.items)) {
      // Jobs saved before v0.10 have no stored review; offer an explicit check.
      state.printabilityShown = false;
      state.printabilityNozzle = 0.4;
      $("printability-nozzle").value = "0.4";
      setBadge("printability-status", "아직 점검 안 함");
      $("printability-basis").textContent = "이전 버전에서 만든 작업입니다. 노즐을 고르고 점검하면 저장된 형상으로 계산합니다.";
      $("printability-items").replaceChildren();
      $("printability-run").hidden = !state.job?.result?.mesh;
      section.hidden = !state.job?.result?.mesh;
      updatePrintabilityControls();
      renderJourney();
      return;
    }
    state.printabilityShown = true;
    state.printabilityNozzle = review.basis?.nozzle_mm ?? 0.4;
    $("printability-nozzle").value = String(state.printabilityNozzle);
    $("printability-run").hidden = true;
    const [label, tone] = printabilityStatus[review.status] || ["확인 필요", "neutral"];
    setBadge("printability-status", label, tone);
    $("printability-basis").textContent = review.basis?.note || "";
    $("printability-items").replaceChildren(...review.items.map((item) => {
      const row = node("li", `printability-item is-${item.status}`);
      row.dataset.check = item.id;
      const mark = node("span", "printability-mark", printabilityMarks[item.status] || "?");
      mark.setAttribute("aria-hidden", "true");
      const body = node("div", "printability-body");
      const head = node("div", "printability-row");
      head.append(node("strong", "", item.label), node("span", "printability-value", item.value));
      body.append(head, node("p", "", item.detail));
      if (item.advice) body.append(node("p", "printability-advice", item.advice));
      const input = item.field ? $(`parameter-${item.field}`) : null;
      if (item.id === "material" && Number.isFinite(item.grams)) {
        const compare = node("button", "text-button", "구매 비교에서 재료비 보기 →");
        compare.type = "button";
        compare.addEventListener("click", () => changeView("offers"));
        body.append(compare);
      }
      if (input && item.status !== "pass") {
        const fix = node("button", "text-button", "이 치수 고치기 →");
        fix.type = "button";
        fix.addEventListener("click", () => { input.scrollIntoView({ block: "center", behavior: "smooth" }); input.focus(); input.select?.(); });
        body.append(fix);
      }
      row.append(mark, body);
      return row;
    }));
    section.hidden = false;
    updatePrintabilityControls();
    renderJourney();
  }

  function renderJob(job) {
    const result = job.result;
    if (!result) throw new Error("작업에 모델 결과가 없습니다.");
    if (state.job?.id !== job.id) retainOutcomeDraft();
    cancelSlicerReads();
    state.job = job;
    state.studioRecorded = job.latest_slice?.plan?.kind === "studio_project" ? job.latest_slice.plan.project_source || null : null;
    state.studioSettingsRecorded = job.latest_slice?.plan?.settings_revision ?? null;
    state.studioSettingsRecordedReview = job.latest_slice?.plan?.settings_review ?? null;
    state.studioSavedIdentity = JSON.stringify([studioSourceIdentity(state.studioRecorded), studioSettingsIdentity(state.studioSettingsRecorded)]);
    renderProjectSource("generated-source", job.design_source);
    renderModelEditRecord("generated-model-edit", job.model_edit);
    state.slicePrepared = false;
    $("model-result").hidden = false;
    $("outcome-card").hidden = false;
    $("result-heading").textContent = (job.title || "모델 파일이 준비됐어요").replace(/\s+mm\b/g, "\u00a0mm");
    const dims = result.dimensions_mm || {};
    $("model-metrics").replaceChildren(
      metric("가로 × 세로 × 높이", `${numberFormat.format(dims.x)} × ${numberFormat.format(dims.y)} × ${numberFormat.format(dims.z)} mm`),
      metric(result.template === "imported" ? "메시 부피" : "CAD 체적", Number.isFinite(result.volume_mm3) ? `${numberFormat.format(result.volume_mm3 / 1000)} cm³` : "열린 메시 · 계산 안 함"),
      metric("형상 상태", result.geometry_status === "validated" ? "CAD 검증 완료" : result.geometry_status === "imported_mesh" ? "불러온 메시 · CAD 검증 아님" : "확인 필요")
    );
    const checkNames = { valid_cad: "형상 유효성", single_solid: "단일 솔리드", positive_volume: "양의 체적", requested_dimensions: "요청 치수", closed_preview_mesh: "닫힌 메시", original_verified: "원본 확인", placement_applied: "출력 방향 적용" };
    $("model-checks").replaceChildren(...(result.checks || []).map((check) => {
      const element = node("span", `check-item${check.passed ? "" : " failed"}`, checkNames[check.name] || check.name);
      element.title = check.detail || "";
      return element;
    }));
    $("model-warnings").replaceChildren(...(result.warnings || []).map((text) => node("p", "", text)));
    state.printabilityRequest += 1;
    state.printabilityPending = false;
    hideNotice("printability-feedback");
    renderPrintability(result.printability);
    renderDownloads(job);
    viewer.setMesh(result.mesh, job.title, result.template);
    renderColorLegend(result.color_parts);
    setBadge("preview-status", "실제 CAD 메시", "blue");
    $("preview-caption").textContent = "생성된 모델 · 드래그 또는 방향키로 조작";
    $("outcome-result").value = job.user_outcome?.result || "not_tested";
    $("outcome-notes").value = job.user_outcome?.notes || "";
    syncOutcomeReasons(job.user_outcome?.reasons || []);
    fillMeasurements(job.user_outcome);
    loadRecovery(job);
    loadAttempts(job);
    state.modelCleanSignature = modelDraftSignature();
    hideNotice("outcome-feedback");
    $("slice-result").replaceChildren();
    renderSliceComparison(job.slice_comparison);
    showNotice("slice-feedback", state.environment.available ? "전체 설정을 제공하고 실행 계획을 먼저 검토해 주세요." : "Bambu Studio를 사용할 수 없어 현재 환경에서는 슬라이싱을 실행할 수 없습니다.");
    if (job.latest_slice?.phase === "running") showNotice("slice-feedback", "이 기록의 슬라이싱 요청은 실행 중으로 저장되어 있습니다. 완료 여부는 작업 기록에서 다시 열어 확인해 주세요. 이전 슬라이스 파일을 현재 결과로 제공하지 않습니다.", "info");
    else if (job.latest_slice?.phase === "interrupted") showNotice("slice-feedback", "이전 슬라이싱은 완료 결과를 저장하기 전에 중단되었습니다. 설정을 다시 검토한 뒤 실행해 주세요. CAD 모델은 유지되며 이전 슬라이스 파일은 현재 결과로 제공하지 않습니다.", "warning");
    else if (job.latest_slice) renderSliceResult(job.latest_slice.plan || {}, job.latest_slice.execution, true);
    resetPrintSend(job);
    if (state.slicerStaged) resetSlicePreparation("선택 중인 설정 파일이 있습니다. 묶음을 만들거나 편집을 취소한 뒤 이 모델의 실행 계획을 검토해 주세요.");
    renderSlicerFiles();
    updateWorkflowControls();
  }

  // Workspace persistence has its own scope: typing may outlive a save, while
  // candidate selection, connection and storage changes invalidate its binding.
  function studioLibraryScope() {
    return JSON.stringify([state.connectionEpoch, state.storage?.path || null, state.studioWorkspaceEpoch || 0, studioSourceIdentity(state.studioApplied), studioSettingsIdentity(state.studioSettingsApplied), $("studio-library-kind").value, $("studio-library-list").value]);
  }

  function studioWorkspaceSnapshot() {
    if (!state.studioApplied?.supported || !studioSourceIdentity(state.studioApplied) || (state.studioSettingsApplied && (!studioSettingsIdentity(state.studioSettingsApplied) || state.studioSettingsApplied.revision?.source_id !== state.studioApplied.source_id))) throw new Error("사용할 원본과 설정을 먼저 선택해 주세요.");
    const source = state.studioApplied, revision = state.studioSettingsApplied?.revision;
    const draft = state.studioSettingsDraft == null ? null : { ...state.studioSettingsDraft };
    const keys = ["nozzle_temperature", "nozzle_temperature_initial_layer", "filament_flow_ratio", "filament_max_volumetric_speed", "bed_temperature", "bed_temperature_initial_layer"];
    if (draft && (Object.keys(draft).length !== 6 || keys.some(key => typeof draft[key] !== "string" || Array.from(draft[key]).length > 512))) throw new Error("초안은 여섯 항목의 정확한 문자열이며 항목마다 최대 512자까지 저장할 수 있습니다. 입력은 유지했습니다.");
    const snapshot = { schema_version: 1, source_id: source.source_id, settings_revision_id: revision?.revision_id || null, source_sha256: source.source.sha256, settings_sha256: source.settings_sha256, effective_settings_sha256: revision?.effective_settings_sha256 || source.settings_sha256, draft_values: draft };
    if (new TextEncoder().encode(JSON.stringify(snapshot)).byteLength > 16 * 1024) throw new Error("Studio 초안은 합계 16 KiB 이하여야 합니다. 입력은 유지했습니다.");
    return snapshot;
  }

  function studioWorkspaceSignature(snapshot = studioWorkspaceSnapshot(), title = $("studio-workspace-title").value.trim()) {
    // Canonical field order keeps exact values independent from JSON key order.
    const values = snapshot.draft_values;
    return JSON.stringify([title, snapshot.schema_version, snapshot.source_id, snapshot.settings_revision_id, snapshot.source_sha256, snapshot.settings_sha256, snapshot.effective_settings_sha256, values == null ? null : ["nozzle_temperature", "nozzle_temperature_initial_layer", "filament_flow_ratio", "filament_max_volumetric_speed", "bed_temperature", "bed_temperature_initial_layer"].map(key => values[key])]);
  }

  function studioWorkspaceDirty() {
    if (!state.studioApplied) return Boolean($("studio-workspace-title").value.trim());
    try { return studioWorkspaceSignature() !== state.studioWorkspaceSavedSignature; }
    catch { return true; }
  }

  function renderStudioLibrary() {
    const busy = Boolean(state.workflowBusy || state.bootstrapPending || state.studioWorkspaceBusy);
    const dirty = studioWorkspaceDirty();
    $("studio-workspace-status").textContent = state.studioWorkspaceId ? `저장 버전 ${state.studioWorkspaceRevision} · ${dirty ? "저장하지 않은 변경" : "저장됨"}` : "이름을 정해 CAD 없이도 저장할 수 있습니다.";
    for (const id of ["studio-workspace-save", "studio-workspace-copy"]) $(id).disabled = busy || !studioSourceCurrent() || Boolean(state.studioCandidate) || state.studioPending || state.studioSettingsPending;
    $("studio-workspace-delete").disabled = busy || !state.studioWorkspaceId || !studioSourceCurrent();
    $("studio-library-open").disabled = busy || !state.token || !$("studio-library-list").value || state.studioPending;
    $("studio-library-refresh").disabled = busy || !state.token || state.studioLibraryPending;
    $("studio-library-more").hidden = !state.studioLibraryCursor;
    $("studio-library-more").disabled = busy || state.studioLibraryPending;
    $("studio-library-kind").disabled = busy;
    $("studio-library-list").disabled = busy;
    const candidateArea = $("studio-workspace-candidate");
    const named = state.studioWorkspaceCandidate;
    candidateArea.replaceChildren();
    candidateArea.hidden = !named;
    if (named) {
      candidateArea.append(node("h4", "", `${named.record.title} · 저장 버전 ${named.record.revision} · 선택 전`), node("p", "field-help", named.record.snapshot.draft_values === null ? "저장한 별도 초안이 없습니다. 후보 선택 후 선택한 원본·편집 기록의 값으로 편집을 시작합니다." : "보관한 초안입니다. 미완성 입력도 그대로 복원하며 검토·적용 전에는 현재 CAD에 사용할 수 없습니다."));
      if (named.record.snapshot.draft_values !== null) candidateArea.append(node("pre", "", JSON.stringify(named.record.snapshot.draft_values, null, 2)));
    }
    const selected = (state.studioLibraryItems || []).find(item => item.id === $("studio-library-list").value);
    $("studio-library-detail").textContent = selected ? `${selected.summary || "기록된 입력"}${selected.detail ? ` · ${selected.detail}` : ""}${selected.metadata_status === "unreadable" ? " · 열어서 무결성을 확인해야 합니다." : ""}` : "목록은 보관된 입력의 설명입니다. 열 때 원본과 편집 기록을 다시 확인하며, 현재 입력은 후보 선택 전까지 유지합니다.";
  }

  async function loadStudioLibrary(more = false) {
    if (!state.token) return;
    const kind = $("studio-library-kind").value || "workspaces";
    if (!["workspaces", "sources", "revisions"].includes(kind)) return;
    const request = state.studioLibraryRequest = (state.studioLibraryRequest || 0) + 1;
    const scope = studioLibraryScope(), before = more ? state.studioLibraryCursor : null;
    const current = () => request === state.studioLibraryRequest && scope === studioLibraryScope();
    state.studioLibraryPending = true;
    renderStudioLibrary();
    try {
      const result = await api(`/api/studio-library?kind=${kind}&limit=25${before ? `&before=${encodeURIComponent(before)}` : ""}`, undefined, undefined, { current });
      if (!current()) return;
      if (!Array.isArray(result.items) || (result.next_cursor != null && !/^[a-f0-9]{32}$/.test(result.next_cursor))) throw new Error("보관함 목록 응답을 읽지 못했습니다.");
      state.studioLibraryItems = more ? [...(state.studioLibraryItems || []), ...result.items.filter(item => !(state.studioLibraryItems || []).some(old => old.id === item.id))] : result.items;
      state.studioLibraryCursor = result.next_cursor;
      const select = $("studio-library-list"), previous = select.value;
      const placeholder = node("option", "", state.studioLibraryItems.length ? "보관된 설정을 선택하세요" : "보관된 설정이 없습니다");
      placeholder.value = "";
      select.replaceChildren(placeholder, ...state.studioLibraryItems.map(item => {
        const option = node("option", "", `${item.title || "읽을 수 없는 기록"} · ${item.updated_at ? dateTime(item.updated_at) : "날짜 없음"} · ${(item.id || "").slice(0, 8)}${item.has_draft ? " · 초안 포함" : ""}${item.metadata_status === "unreadable" ? " · 확인 필요" : ""}`);
        option.value = item.id;
        return option;
      }));
      select.value = state.studioLibraryItems.some(item => item.id === previous) ? previous : "";
    } catch (error) { if (current()) showNotice("studio-library-feedback", `${error.message} 현재 입력은 유지했습니다.`, "error"); }
    finally { if (request === state.studioLibraryRequest) state.studioLibraryPending = false; renderStudioLibrary(); }
  }

  function validateStudioWorkspace(result) {
    const record = result?.workspace, source = result?.source, revision = result?.settings_revision, descriptor = result?.editor;
    const fail = () => { throw new Error("저장된 Studio 작업의 형식이나 원본 식별 정보가 일치하지 않습니다."); };
    const object = value => value && typeof value === "object" && !Array.isArray(value);
    const exact = (value, keys) => object(value) && Object.keys(value).length === keys.length && keys.every(key => Object.hasOwn(value, key));
    if (!exact(record, ["id", "title", "revision", "created_at", "updated_at", "snapshot"]) || !/^[a-f0-9]{32}$/.test(record.id) || typeof record.title !== "string" || record.title !== record.title.trim() || Array.from(record.title).length < 1 || Array.from(record.title).length > 120 || !Number.isSafeInteger(record.revision) || record.revision < 1 || record.revision >= Number.MAX_SAFE_INTEGER || [record.created_at, record.updated_at].some(value => typeof value !== "string" || !Number.isFinite(Date.parse(value)))) fail();
    const snapshot = record.snapshot;
    if (!exact(snapshot, ["schema_version", "source_id", "settings_revision_id", "source_sha256", "settings_sha256", "effective_settings_sha256", "draft_values"]) || snapshot.schema_version !== 1 || source?.supported !== true || !studioSourceIdentity(source) || snapshot.source_id !== source.source_id || snapshot.source_sha256 !== source.source.sha256 || snapshot.settings_sha256 !== source.settings_sha256) fail();
    if (snapshot.settings_revision_id === null ? revision !== null || snapshot.effective_settings_sha256 !== source.settings_sha256 : !studioSettingsIdentity(revision) || revision.revision?.revision_id !== snapshot.settings_revision_id || revision.revision.source_id !== source.source_id || revision.revision.effective_settings_sha256 !== snapshot.effective_settings_sha256 || studioSourceIdentity(revision.source) !== studioSourceIdentity(source)) fail();
    const keys = ["nozzle_temperature", "nozzle_temperature_initial_layer", "filament_flow_ratio", "filament_max_volumetric_speed", "bed_temperature", "bed_temperature_initial_layer"];
    if (!descriptor || descriptor.source_id !== source.source_id || descriptor.source_sha256 !== source.source.sha256 || descriptor.settings_sha256 !== source.settings_sha256 || !Array.isArray(descriptor.fields) || descriptor.fields.length !== 6 || !keys.every(key => descriptor.fields.filter(field => field.key === key && typeof field.value === "string").length === 1)) fail();
    if (snapshot.draft_values !== null && (!exact(snapshot.draft_values, keys) || keys.some(key => typeof snapshot.draft_values[key] !== "string" || Array.from(snapshot.draft_values[key]).length > 512))) fail();
    if (new TextEncoder().encode(JSON.stringify(snapshot)).byteLength > 16 * 1024) fail();
    const draft = snapshot.draft_values === null ? Object.fromEntries(descriptor.fields.map(field => [field.key, revision?.revision?.proposal?.values?.[field.key] ?? field.value])) : { ...snapshot.draft_values };
    if (keys.some(key => typeof draft[key] !== "string")) fail();
    return { record, source, revision, descriptor, draft, signature: studioWorkspaceSignature(snapshot, record.title) };
  }

  function studioLibrarySelectionChanged(kindChanged = false) {
    state.studioWorkspaceEpoch = (state.studioWorkspaceEpoch || 0) + 1;
    state.studioLibraryRequest = (state.studioLibraryRequest || 0) + 1;
    state.studioLibraryPending = false;
    if (kindChanged) {
      state.studioLibraryItems = [];
      state.studioLibraryCursor = null;
      $("studio-library-list").replaceChildren();
      $("studio-library-list").value = "";
      loadStudioLibrary();
    }
    renderStudioLibrary();
  }

  async function openStudioLibrary() {
    const id = $("studio-library-list").value, kind = $("studio-library-kind").value || "workspaces";
    if (!/^[a-f0-9]{32}$/.test(id) || !state.token || state.workflowBusy || state.studioWorkspaceBusy) return;
    invalidateStudioRequests();
    const context = studioContext(), scope = studioLibraryScope(), request = state.studioRequest;
    const current = () => scope === studioLibraryScope() && studioContextCurrent(context);
    state.studioPending = true;
    state.studioPendingName = "보관한 설정";
    renderStudioProject();
    try {
      const path = kind === "workspaces" ? `/api/studio-workspaces/${id}` : kind === "revisions" ? `/api/studio-settings-revisions/${id}` : `/api/studio-projects/${id}`;
      const result = await api(path, undefined, undefined, { current });
      if (!current()) return;
      const named = kind === "workspaces" ? validateStudioWorkspace(result) : null;
      const source = named ? named.source : kind === "revisions" ? result.source : result;
      const revision = named ? named.revision : kind === "revisions" ? result : null;
      if (!studioSourceIdentity(source) || typeof source.supported !== "boolean" || (revision && (!studioSettingsIdentity(revision) || revision.revision.source_id !== source.source_id || studioSourceIdentity(revision.source) !== studioSourceIdentity(source)))) throw new Error("보관한 원본 또는 편집 기록을 확인하지 못했습니다.");
      state.studioCandidate = source;
      state.studioSettingsCandidate = revision;
      state.studioWorkspaceCandidate = named;
      state.studioCandidateEpoch = state.connectionEpoch;
      state.studioCandidateStorage = state.storage?.path || null;
      showNotice("studio-library-feedback", named ? `‘${named.record.title}’을 후보로 확인했습니다. 후보를 직접 선택하면 보관한 초안도 함께 열립니다.` : "보관한 설정을 후보로 확인했습니다. 사용할 후보를 직접 선택해 주세요.");
    } catch (error) { if (current()) showNotice("studio-library-feedback", `${error.message} 현재 선택과 편집 내용은 유지했습니다.`, "error"); }
    // Selection scope gates applying results; request ownership gates releasing
    // pending controls, including when this completed open became stale.
    finally { if (request === state.studioRequest) { state.studioPending = false; state.studioPendingName = ""; } renderStudioProject(); }
  }

  async function saveStudioWorkspace(copy = false) {
    if (state.studioWorkspaceBusy || state.studioCandidate || state.studioPending || state.studioSettingsPending || state.workflowBusy || !studioSourceCurrent()) return;
    const scope = studioLibraryScope();
    const request = state.studioWorkspaceRequest = (state.studioWorkspaceRequest || 0) + 1;
    const current = () => request === state.studioWorkspaceRequest && scope === studioLibraryScope();
    try {
      const title = $("studio-workspace-title").value.trim();
      if (!title || Array.from(title).length > 120) throw new Error("Studio 작업 이름은 1자 이상 120자 이하로 입력해 주세요.");
      const snapshot = studioWorkspaceSnapshot(), signature = studioWorkspaceSignature(snapshot, title);
      const id = copy ? null : state.studioWorkspaceId;
      const payload = { title, snapshot, ...(id ? { expected_revision: state.studioWorkspaceRevision } : {}) };
      state.studioWorkspaceBusy = true;
      renderStudioLibrary();
      const descriptor = state.studioSettingsDescriptor || await api(`/api/studio-projects/${state.studioApplied.source_id}/settings`, undefined, undefined, { current });
      if (!current()) return;
      const record = await api(id ? `/api/studio-workspaces/${id}` : "/api/studio-workspaces", payload, id ? "PUT" : "POST", { current });
      if (!current()) return;
      // Validate the acknowledgement against submitted inputs, never current typing.
      const checked = validateStudioWorkspace({ workspace: record, source: state.studioApplied, settings_revision: state.studioSettingsApplied, editor: descriptor });
      if (checked.signature !== signature || (id && record.id !== id)) throw new Error("저장 응답이 요청한 입력과 일치하지 않습니다. 현재 입력은 유지했습니다.");
      state.studioWorkspaceId = record.id;
      state.studioWorkspaceRevision = record.revision;
      state.studioWorkspaceSavedSignature = signature;
      showNotice("studio-library-feedback", studioWorkspaceDirty() ? "요청한 초안을 저장했습니다. 저장 중 바뀐 입력은 한 번 더 저장해 주세요." : "Studio 원본 참조, 선택한 설정과 정확한 초안을 저장했습니다. CAD 없이 다시 열 수 있습니다.", "success");
    } catch (error) { if (current()) showNotice("studio-library-feedback", error.status === 409 && error.code !== "studio_workspace_integrity" ? "다른 탭에서 저장본을 변경했습니다. 현재 입력은 유지했습니다. 복사 저장하거나 목록에서 최신 저장본을 다시 열어 주세요." : `${error.message} 현재 입력은 유지했습니다.`, "error"); }
    finally { if (request === state.studioWorkspaceRequest) state.studioWorkspaceBusy = false; renderStudioLibrary(); }
  }

  async function deleteStudioWorkspace() {
    if (state.studioWorkspaceBusy || !state.studioWorkspaceId || !studioSourceCurrent()) return;
    if (!window.confirm("이 이름의 Studio 저장본을 삭제하시겠습니까? 보관한 원본, 편집 기록과 현재 입력은 남습니다.")) return;
    const id = state.studioWorkspaceId, scope = studioLibraryScope();
    const request = state.studioWorkspaceRequest = (state.studioWorkspaceRequest || 0) + 1;
    const current = () => request === state.studioWorkspaceRequest && scope === studioLibraryScope();
    state.studioWorkspaceBusy = true;
    renderStudioLibrary();
    try {
      await api(`/api/studio-workspaces/${id}`, { expected_revision: state.studioWorkspaceRevision }, "DELETE", { current });
      if (!current()) return;
      state.studioWorkspaceId = null;
      state.studioWorkspaceRevision = null;
      state.studioWorkspaceSavedSignature = null;
      showNotice("studio-library-feedback", "이름의 저장본을 삭제했습니다. 현재 입력과 원본·편집 기록은 유지했습니다.");
    } catch (error) { if (current()) showNotice("studio-library-feedback", `${error.message} 현재 입력은 유지했습니다. 최신 저장본을 다시 열거나 복사 저장해 주세요.`, "error"); }
    finally { if (request === state.studioWorkspaceRequest) state.studioWorkspaceBusy = false; renderStudioLibrary(); }
  }

  function studioSourceIdentity(inspection) {
    if (!inspection || !/^[a-f0-9]{32}$/.test(inspection.source_id || "") || !/^[a-f0-9]{64}$/.test(inspection.source?.sha256 || "") || !/^[a-f0-9]{64}$/.test(inspection.settings_sha256 || "")) return "";
    return JSON.stringify([inspection.source_id, inspection.source.sha256, inspection.settings_sha256]);
  }

  function studioModelSignature() {
    return JSON.stringify([state.job?.id || null, state.job?.artifacts?.three_mf || null, state.job?.result?.parameters || null, state.job?.result?.dimensions_mm || null]);
  }

  function studioContext() {
    return JSON.stringify([state.studioRequest, state.studioRevision, state.connectionEpoch, state.storage?.path || null, state.slicerContext, studioModelSignature(), studioSourceIdentity(state.studioApplied), studioSourceIdentity(state.studioCandidate), studioSourceIdentity(state.studioRecorded), studioSettingsIdentity(state.studioSettingsApplied), studioSettingsIdentity(state.studioSettingsCandidate), studioSettingsIdentity(state.studioSettingsRecorded)]);
  }

  function studioContextCurrent(context) {
    return context === studioContext();
  }

  function studioSourceCurrent() {
    return Boolean(state.token && state.studioApplied?.supported === true && studioSourceIdentity(state.studioApplied) && state.studioAppliedEpoch === state.connectionEpoch && state.studioAppliedStorage === (state.storage?.path || null) && (state.studioSettingsApplied == null || (studioSettingsIdentity(state.studioSettingsApplied) && state.studioSettingsApplied.revision?.source_id === state.studioApplied.source_id)));
  }

  function studioHasUnsavedChanges() {
    return Boolean(state.studioPending || state.studioSettingsPending || state.studioWorkspaceBusy || state.studioSettingsReview || state.studioCandidate || (state.studioWorkspaceSavedSignature ? studioWorkspaceDirty() : studioSettingsDirty() || $("studio-workspace-title").value.trim() || (state.studioApplied && JSON.stringify([studioSourceIdentity(state.studioApplied), studioSettingsIdentity(state.studioSettingsApplied)]) !== state.studioSavedIdentity)));
  }

  function invalidateStudioRequests() {
    state.studioRequest = (state.studioRequest || 0) + 1;
    state.studioRevision = (state.studioRevision || 0) + 1;
    state.studioPending = false;
    state.studioSettingsPending = false;
    state.studioSettingsReview = null;
    state.studioSettingsReviewContext = null;
    state.studioPendingName = "";
    state.studioSlicePrepared = false;
    state.studioPreparedSignature = null;
  }

  function studioSettingsIdentity(envelope) {
    const revision = envelope?.revision || envelope;
    if (!revision || !/^[a-f0-9]{32}$/.test(revision.revision_id || "") || !/^[a-f0-9]{32}$/.test(revision.source_id || "") || !/^[a-f0-9]{64}$/.test(revision.effective_settings_sha256 || "") || !/^[a-f0-9]{64}$/.test(revision.review_sha256 || "")) return "";
    return JSON.stringify([revision.revision_id, revision.source_id, revision.effective_settings_sha256, revision.review_sha256]);
  }

  function studioSettingsDirty() {
    if (!state.studioSettingsDraft || !state.studioSettingsDescriptor) return false;
    const values = state.studioSettingsApplied?.revision?.proposal?.values || {};
    return state.studioSettingsDescriptor.fields.some(field => state.studioSettingsDraft[field.key] !== (values[field.key] ?? field.value));
  }

  function renderStudioChanges(area, review, heading) {
    area.replaceChildren();
    area.hidden = !review;
    if (!review) return;
    area.append(node("h4", "", heading), node("p", "field-help", "사용자가 선택한 값입니다. 입력 형식과 범위 확인은 장비 적합성·제조사 권장·실물 출력 검증을 뜻하지 않습니다."));
    const list = node("ul", "studio-settings-changes");
    (review.changes || []).forEach(change => list.append(node("li", "", `${fieldNames[change.field] || change.field}: ${(change.before || []).join(" · ")} → ${(change.after || []).join(" · ")}`)));
    if (!review.changed_count) list.append(node("li", "", "원본과 수치가 같습니다. 원본 설정으로 돌아갈 수 있습니다."));
    area.append(list);
    (review.warnings || []).forEach(warning => area.append(node("p", "field-help", friendly(warning))));
  }

  function renderStudioSettings() {
    const busy = state.workflowBusy || state.bootstrapPending;
    $("studio-settings-open").hidden = !state.studioApplied;
    $("studio-settings-open").disabled = busy || !studioSourceCurrent() || Boolean(state.studioCandidate) || state.studioPending || state.studioSettingsPending;
    $("studio-settings-editor").hidden = !state.studioSettingsOpen;
    $("studio-settings-reset").hidden = !state.studioSettingsApplied;
    $("studio-settings-reset").disabled = busy || !studioSourceCurrent();
    $("studio-settings-review").disabled = busy || state.studioSettingsPending || !studioSourceCurrent() || Boolean(state.studioCandidate) || !state.studioSettingsDescriptor;
    $("studio-settings-apply").disabled = busy || state.studioSettingsPending || !state.studioSettingsReview || !studioContextCurrent(state.studioSettingsReviewContext);
    $("studio-settings-cancel").disabled = busy || !state.studioSettingsOpen;
    $("studio-settings-replace-choice").hidden = !state.studioSettingsReplace;
    $("studio-settings-replace").disabled = busy || !state.studioCandidate;
    renderStudioChanges($("studio-settings-differences"), state.studioSettingsReview, "검토한 차이 · 아직 적용하지 않았습니다");
    renderStudioChanges($("studio-settings-candidate"), state.studioSettingsCandidate?.review, "후보 설정의 차이 · 선택 전");
    renderStudioChanges($("studio-settings-applied"), state.studioSettingsApplied?.review, "현재 적용한 차이 · 사용자 선택값");
    renderStudioChanges($("studio-settings-recorded"), state.studioSettingsRecordedReview, "작업 기록의 원본 → 적용값");
    // Keep live text controls in place while typing, including incomplete numbers.
    const descriptor = state.studioSettingsDescriptor;
    const area = $("studio-settings-fields");
    if (area.dataset.descriptor !== descriptor?.source_sha256 || !area.children.length) {
      area.replaceChildren();
      area.dataset.descriptor = descriptor?.source_sha256 || "";
      for (const field of descriptor?.fields || []) {
        const label = node("label", "studio-settings-field");
        label.append(node("span", "", `${field.label} · ${field.unit || "비율"}`));
        const input = node("input");
        input.id = `studio-setting-${field.key}`;
        input.type = "text";
        input.inputMode = field.kind === "integer" ? "numeric" : "decimal";
        input.dataset.studioSetting = field.key;
        input.value = state.studioSettingsDraft?.[field.key] ?? field.value;
        input.addEventListener("input", () => editStudioSetting(field.key, input.value));
        label.append(input, node("small", "field-help", `원본 ${field.original} · ${field.kind === "integer" ? "정수" : "소수점 이하 최대 6자리"}, ${field.minimum}${field.exclusive_minimum ? " 초과" : " 이상"}–${field.maximum} 이하 · 최대 32자`));
        area.append(label);
      }
    }
    for (const label of area.children) {
      const input = Array.from(label.children).find(child => child.dataset?.studioSetting);
      if (input) { input.disabled = busy || !studioSourceCurrent() || Boolean(state.studioCandidate); const value = state.studioSettingsDraft?.[input.dataset.studioSetting]; if (value !== undefined && input.value !== value) input.value = value; }
    }
    $("studio-settings-plate").textContent = `원본 플레이트: ${descriptor?.source_summary?.plate_type || state.studioApplied?.summary?.plate_type || "기록 없음"} · 플레이트는 바꾸지 않습니다.`;
  }

  async function openStudioSettings() {
    if (!studioSourceCurrent() || state.workflowBusy || state.studioCandidate) return;
    invalidateStudioRequests();
    state.studioSettingsOpen = true;
    if (!state.studioSettingsDraft && state.studioSettingsDescriptor) state.studioSettingsDraft = Object.fromEntries(state.studioSettingsDescriptor.fields.map(field => [field.key, state.studioSettingsApplied?.revision?.proposal?.values?.[field.key] ?? field.value]));
    state.studioSettingsPending = true;
    const context = studioContext();
    renderStudioProject();
    try {
      const descriptor = await api(`/api/studio-projects/${state.studioApplied.source_id}/settings`, undefined, undefined, { current: () => studioContextCurrent(context) });
      if (!studioContextCurrent(context)) return;
      if (descriptor.source_sha256 !== state.studioApplied.source.sha256 || descriptor.settings_sha256 !== state.studioApplied.settings_sha256 || descriptor.source_id !== state.studioApplied.source_id || descriptor.fields?.length !== 6) throw new Error("현재 원본의 편집 항목을 확인하지 못했습니다.");
      state.studioSettingsDescriptor = descriptor;
      if (!state.studioSettingsDraft) state.studioSettingsDraft = Object.fromEntries(descriptor.fields.map(field => [field.key, state.studioSettingsApplied?.revision?.proposal?.values?.[field.key] ?? field.value]));
      hideNotice("studio-settings-feedback");
    } catch (error) { if (studioContextCurrent(context)) showNotice("studio-settings-feedback", `${error.message} 입력은 유지했습니다.`, "error"); }
    finally { if (studioContextCurrent(context)) state.studioSettingsPending = false; renderStudioProject(); }
  }

  function editStudioSetting(key, value) {
    if (!state.studioSettingsDraft || !state.studioSettingsDescriptor?.fields.some(field => field.key === key)) return;
    invalidateStudioRequests();
    state.studioSettingsDraft[key] = value;
    resetSlicePreparation("설정 입력이 바뀌었습니다. 차이를 검토하고 적용한 뒤 현재 CAD로 다시 준비해 주세요.");
    renderStudioProject();
  }

  async function reviewStudioSettings() {
    if (!studioSourceCurrent() || state.workflowBusy || state.studioCandidate || !state.studioSettingsDraft || !state.studioSettingsDescriptor) return;
    invalidateStudioRequests();
    const descriptor = state.studioSettingsDescriptor;
    const proposal = { source_sha256: descriptor.source_sha256, settings_sha256: descriptor.settings_sha256, values: { ...state.studioSettingsDraft } };
    state.studioSettingsPending = true;
    const context = studioContext();
    renderStudioProject();
    try {
      const review = await api(`/api/studio-projects/${state.studioApplied.source_id}/settings/review`, proposal, undefined, { current: () => studioContextCurrent(context) });
      if (!studioContextCurrent(context)) return;
      if (review.source_sha256 !== proposal.source_sha256 || review.settings_sha256 !== proposal.settings_sha256 || !/^[a-f0-9]{64}$/.test(review.review_sha256 || "")) throw new Error("현재 원본의 검토 결과를 확인하지 못했습니다.");
      state.studioSettingsReview = review;
      state.studioSettingsReviewContext = context;
      state.studioSettingsProposal = proposal;
      hideNotice("studio-settings-feedback");
    } catch (error) { if (studioContextCurrent(context)) showNotice("studio-settings-feedback", `${error.message} 입력 문자열 전체를 유지했습니다. 일부 값도 적용하지 않았습니다.`, "error"); }
    finally { if (studioContextCurrent(context)) state.studioSettingsPending = false; renderStudioProject(); }
  }

  async function applyStudioSettings() {
    if (state.workflowBusy || state.studioSettingsPending || !state.studioSettingsReview || !studioContextCurrent(state.studioSettingsReviewContext)) return;
    if (!state.studioSettingsReview.changed_count) { resetStudioSettings(); return; }
    const context = studioContext(), review = state.studioSettingsReview;
    state.studioSettingsPending = true;
    renderStudioProject();
    try {
      const envelope = await api(`/api/studio-projects/${state.studioApplied.source_id}/settings/revisions`, { ...state.studioSettingsProposal, review_sha256: review.review_sha256 }, undefined, { current: () => studioContextCurrent(context) });
      if (!studioContextCurrent(context)) return;
      if (!studioSettingsIdentity(envelope) || studioSourceIdentity(envelope.source) !== studioSourceIdentity(state.studioApplied) || envelope.revision.source_id !== state.studioApplied.source_id || envelope.revision.review_sha256 !== review.review_sha256 || envelope.revision.effective_settings_sha256 !== review.effective_settings_sha256) throw new Error("적용한 설정 기록의 식별 정보가 일치하지 않습니다.");
      invalidateStudioRequests();
      state.studioSettingsApplied = envelope;
      state.studioSettingsOpen = false;
      state.studioSettingsDraft = null;
      resetSlicePreparation("사용자가 선택한 설정을 적용했습니다. 현재 CAD에 설정을 담아 새로 준비해 주세요.");
      showNotice("studio-settings-feedback", "검토한 차이를 적용했습니다. 원본 프로젝트는 그대로 보관합니다.");
    } catch (error) { if (studioContextCurrent(context)) showNotice("studio-settings-feedback", `${error.message} 입력은 유지했습니다. 요청을 자동으로 반복하지 않습니다.`, "error"); }
    finally { if (studioContextCurrent(context)) state.studioSettingsPending = false; renderStudioProject(); }
  }

  function cancelStudioSettings() {
    invalidateStudioRequests();
    state.studioSettingsOpen = false;
    state.studioSettingsDraft = null;
    state.studioSettingsReplace = false;
    hideNotice("studio-settings-feedback");
    renderStudioProject();
  }

  function resetStudioSettings() {
    if (!studioSourceCurrent() || state.workflowBusy) return;
    cancelStudioSettings();
    state.studioSettingsApplied = null;
    resetSlicePreparation("원본 설정으로 돌아갔습니다. 현재 CAD에 다시 담아 주세요.");
    renderStudioProject();
  }

  function renderStudioSource(area, inspection, title, verified = false) {
    area.replaceChildren();
    area.hidden = !inspection;
    if (!inspection) return;
    const value = (item) => item === undefined || item === null || item === "" ? "기록 없음" : Array.isArray(item) ? item.join(" · ") : String(item);
    area.append(node("h4", "", title), node("p", "", inspection.source?.filename || "기록된 프로젝트"));
    const fields = [["프린터", "printer_model"], ["프린터 프리셋", "printer_preset"], ["노즐 지름 · mm", "nozzle_diameter"], ["플레이트", "plate_type"], ["기록된 출력 높이 · mm", "printable_height"], ["필라멘트", "filament_name"], ["재료 종류", "filament_type"], ["출력 공정", "process_preset"]];
    const list = node("dl", "studio-source-summary");
    for (const [label, key] of fields) {
      const row = node("div");
      row.append(node("dt", "", label), node("dd", "", value(inspection.summary?.[key])));
      list.append(row);
    }
    area.append(list, node("p", "", "프로젝트에 기록된 값입니다. 실제 장착 장비·제품 식별·출력 품질을 확인한 결과는 아닙니다."));
    if (inspection.issues?.length) {
      const issues = node("ul", "reason-list");
      inspection.issues.forEach((issue) => issues.append(node("li", "", issue.message || issue.code)));
      area.append(issues);
    }
    const details = node("details", "help-details");
    details.append(node("summary", "", "원본·버전·기록된 수치 확인"), node("pre", "", JSON.stringify({ source: inspection.source, producer: inspection.producer, settings_sha256: inspection.settings_sha256, recorded_settings: inspection.summary, warnings: inspection.warnings || [] }, null, 2)));
    area.append(details);
    const path = `/api/studio-projects/${inspection.source_id}/archive`;
    if (verified && studioSourceIdentity(inspection) && inspection.archive_url === path) {
      const link = node("a", "text-button", "보관한 원본 프로젝트 다운로드");
      link.href = path;
      link.setAttribute("download", "");
      area.append(link);
    }
  }

  function renderStudioProject() {
    const busy = state.workflowBusy || state.bootstrapPending;
    const candidate = state.studioCandidate;
    const candidateCurrent = Boolean(candidate && state.studioCandidateEpoch === state.connectionEpoch && state.studioCandidateStorage === (state.storage?.path || null));
    const appliedCurrent = studioSourceCurrent();
    renderStudioSource($("studio-project-candidate"), candidate, candidate?.supported ? "확인한 후보 · 아직 적용하지 않았습니다" : "이 후보의 지원 조건을 확인해 주세요", candidateCurrent);
    renderStudioSource($("studio-project-applied"), state.studioApplied, appliedCurrent ? "현재 선택한 프로젝트 설정" : "보관 중인 선택 · 원본 다시 확인 필요", appliedCurrent);
    renderStudioSource($("studio-project-recorded"), state.studioRecorded, "이 모델의 작업 기록에 남은 원본");
    $("studio-project-file").disabled = busy || !state.token;
    $("studio-project-candidate-actions").hidden = !candidate && !state.studioPending;
    $("studio-project-apply").disabled = busy || state.studioPending || !state.token || !candidateCurrent || candidate?.supported !== true;
    $("studio-project-apply").textContent = state.studioApplied || $("slicer-json").value ? "이 후보 설정 선택 · 기존 입력은 보관" : "이 프로젝트 설정 선택";
    $("studio-project-cancel").disabled = busy || (!candidate && !state.studioPending);
    const needsRevalidation = Boolean(candidate ? !candidateCurrent : state.studioApplied && !appliedCurrent);
    $("studio-project-revalidate").hidden = !needsRevalidation;
    $("studio-project-revalidate").disabled = busy || state.studioPending || !state.token || !needsRevalidation;
    $("studio-project-revalidate").textContent = candidate ? "후보 원본 다시 확인" : "선택한 원본 다시 확인";
    const canPrepare = Boolean(state.token && state.job?.result && appliedCurrent && !busy && !state.studioPending && !state.studioSettingsPending && !studioSettingsDirty() && !state.studioSettingsReview && !candidate);
    if (!$("prepare-studio-project").dataset.busy) $("prepare-studio-project").disabled = !canPrepare;
    if (!$("execute-studio-project").dataset.busy) $("execute-studio-project").disabled = !canPrepare || !state.environment.available || !state.studioSlicePrepared || !studioContextCurrent(state.studioPreparedSignature);
    $("studio-project-history-source").hidden = !studioSourceIdentity(state.studioRecorded);
    $("studio-project-history-source").disabled = busy || state.studioPending || !state.token || !studioSourceIdentity(state.studioRecorded);
    $("studio-project-status").textContent = state.studioPending ? `${state.studioPendingName || "원본"} 확인 중… 기존 선택은 유지합니다.` : candidate ? "후보를 확인한 뒤 선택하거나 취소하세요." : state.studioApplied ? appliedCurrent ? "선택한 설정을 현재 CAD에 사용할 수 있습니다." : "현재 연결에서 원본을 다시 확인하거나 파일을 다시 선택하세요." : "사용하던 Studio 프로젝트를 선택하세요.";
    $("studio-project-next").textContent = candidate ? "후보를 선택하기 전까지 기존 설정과 수동 JSON을 바꾸지 않습니다. 다른 재료 작업의 원본과 편집 내용도 유지합니다." : !state.studioApplied ? "프로젝트를 확인한 뒤 사용할 설정을 직접 선택합니다. 수동 JSON과 재료 편집 내용은 유지됩니다." : !appliedCurrent ? "저장 위치나 연결이 바뀌면 같은 원본인지 다시 확인해야 합니다. 이전 요청을 자동으로 반복하지 않습니다." : !state.job?.result ? "설정을 선택했습니다. 적용할 CAD 모델을 먼저 만들어 주세요." : "현재 CAD에 설정을 담은 뒤 파일을 내려받거나 지원되는 Studio에서 별도로 슬라이싱할 수 있습니다.";
    const download = $("studio-project-prepared-download");
    const prepared = state.job?.latest_slice?.plan;
    const settled = !["running", "interrupted"].includes(state.job?.latest_slice?.phase);
    const href = settled && appliedCurrent && prepared?.kind === "studio_project" && prepared.project_prepared && studioSourceIdentity(prepared.project_source) === studioSourceIdentity(state.studioApplied) && studioSettingsIdentity(prepared.settings_revision) === studioSettingsIdentity(state.studioSettingsApplied) && !studioSettingsDirty() ? localDownload(state.job?.artifacts?.prepared_three_mf) : null;
    download.hidden = !href;
    if (href) download.href = href; else download.removeAttribute("href");
    renderStudioSettings();
    renderStudioLibrary();
  }

  async function importStudioProject(input) {
    const file = input.files?.[0];
    if (!file || state.workflowBusy) return;
    input.value = "";
    invalidateStudioRequests();
    state.studioCandidate = null;
    state.studioWorkspaceCandidate = null;
    state.studioSettingsCandidate = null;
    state.studioSettingsReplace = false;
    state.studioCandidateEpoch = null;
    state.studioCandidateStorage = null;
    state.studioPending = true;
    state.studioPendingName = file.name;
    const request = state.studioRequest, context = studioContext();
    hideNotice("studio-project-feedback");
    renderStudioProject();
    try {
      if (!/\.3mf$/i.test(file.name) || file.name.length > 240) throw new Error("이름이 240자 이하인 Studio .3mf 프로젝트 파일을 선택해 주세요.");
      if (file.size > 16 * 1024 * 1024) throw new Error("Studio 프로젝트는 16 MiB 이하여야 합니다.");
      const bytes = new Uint8Array(await file.arrayBuffer());
      if (!studioContextCurrent(context)) return;
      if (!bytes.length || bytes.length > 16 * 1024 * 1024) throw new Error("읽은 프로젝트 파일의 크기는 1바이트 이상, 16 MiB 이하여야 합니다.");
      const chunks = [];
      for (let offset = 0; offset < bytes.length; offset += 32768) chunks.push(String.fromCharCode(...bytes.subarray(offset, offset + 32768)));
      const result = await api("/api/studio-projects/import", { filename: file.name, content_base64: btoa(chunks.join("")) }, undefined, { current: () => studioContextCurrent(context) });
      if (!studioContextCurrent(context)) return;
      if (!studioSourceIdentity(result) || typeof result.supported !== "boolean") throw new Error("서버의 프로젝트 원본 확인 응답을 읽지 못했습니다.");
      state.studioCandidate = result;
      state.studioCandidateEpoch = state.connectionEpoch;
      state.studioCandidateStorage = state.storage?.path || null;
      showNotice("studio-project-feedback", result.supported ? "원본과 기록된 설정을 확인했습니다. 사용할 후보를 직접 선택해 주세요." : "원본은 보관했지만 이 프로젝트의 설정은 현재 준비 경로에서 지원하지 않습니다. 아래 확인 사항을 살펴보세요.", result.supported ? "info" : "warning");
    } catch (error) {
      if (studioContextCurrent(context)) showNotice("studio-project-feedback", `${file.name}: ${error.message} 기존 선택과 편집 내용은 유지했습니다.`, "error");
    } finally {
      if (request === state.studioRequest) { state.studioPending = false; state.studioPendingName = ""; }
      renderStudioProject();
    }
  }

  function cancelStudioCandidate() {
    state.studioWorkspaceEpoch = (state.studioWorkspaceEpoch || 0) + 1;
    state.studioWorkspaceCandidate = null;
    invalidateStudioRequests();
    state.studioCandidate = null;
    state.studioSettingsCandidate = null;
    state.studioSettingsReplace = false;
    state.studioCandidateEpoch = null;
    state.studioCandidateStorage = null;
    $("studio-project-file").value = "";
    hideNotice("studio-project-feedback");
    renderStudioProject();
  }

  function applyStudioCandidate(replaceDraft = false) {
    const candidate = state.studioCandidate;
    if (state.workflowBusy || state.studioPending || !state.token || candidate?.supported !== true || !studioSourceIdentity(candidate) || state.studioCandidateEpoch !== state.connectionEpoch || state.studioCandidateStorage !== (state.storage?.path || null)) return;
    if (!replaceDraft && (studioSettingsDirty() || state.studioSettingsReview || state.studioSettingsPending)) { state.studioSettingsReplace = true; renderStudioProject(); return; }
    const settingsCandidate = state.studioSettingsCandidate;
    const workspaceCandidate = state.studioWorkspaceCandidate;
    if (settingsCandidate != null && (!studioSettingsIdentity(settingsCandidate) || settingsCandidate.revision?.source_id !== candidate.source_id)) {
      invalidateStudioRequests();
      showNotice("studio-project-feedback", "후보의 편집 설정 기록을 확인하지 못했습니다. 원본 설정으로 바꾸지 않았습니다. 이 기록의 설정을 다시 확인해 주세요.", "error");
      renderStudioProject();
      return;
    }
    let restored = null;
    if (workspaceCandidate) {
      try { restored = validateStudioWorkspace({ workspace: workspaceCandidate.record, source: candidate, settings_revision: settingsCandidate, editor: workspaceCandidate.descriptor }); }
      catch (error) { showNotice("studio-library-feedback", error.message, "error"); return; }
    }
    // Install the complete validated input state before rendering anything.
    invalidateStudioRequests();
    state.studioSettingsOpen = false;
    state.studioSettingsDraft = null;
    hideNotice("studio-settings-feedback");
    state.studioWorkspaceEpoch = (state.studioWorkspaceEpoch || 0) + 1;
    state.studioSettingsApplied = settingsCandidate || null;
    state.studioSettingsCandidate = null;
    state.studioSettingsDescriptor = null;
    cancelSlicerReads();
    state.studioApplied = candidate;
    state.studioAppliedEpoch = state.connectionEpoch;
    state.studioAppliedStorage = state.storage?.path || null;
    state.studioCandidate = null;
    state.studioSettingsCandidate = null;
    state.studioSettingsReplace = false;
    state.studioCandidateEpoch = null;
    state.studioCandidateStorage = null;
    state.studioSavedIdentity = null;
    state.studioWorkspaceId = workspaceCandidate?.record.id || null;
    state.studioWorkspaceRevision = workspaceCandidate?.record.revision || null;
    state.studioWorkspaceSavedSignature = null;
    state.studioWorkspaceCandidate = null;
    $("studio-workspace-title").value = workspaceCandidate?.record.title || "";
    if (workspaceCandidate) {
      state.studioSettingsDescriptor = restored.descriptor;
      state.studioSettingsDraft = restored.draft;
      state.studioSettingsOpen = true;
      // A null saved draft is persisted as null, though the visible editor is
      // initialized from the applied revision. Its equivalent baseline is clean.
      state.studioWorkspaceSavedSignature = studioWorkspaceSignature();
    }
    resetSlicePreparation("프로젝트 설정을 선택했습니다. 현재 CAD에 설정을 담아 새로 준비해 주세요. 수동 JSON과 재료 편집 내용은 유지했습니다.");
    showNotice("studio-project-feedback", settingsCandidate ? "검토했던 사용자 선택값을 포함한 설정을 선택했습니다. 현재 CAD에 설정을 담아 새로 준비해 주세요." : "선택한 원본의 전역 설정을 사용합니다. 아직 설정 포함 3MF 생성이나 슬라이싱을 실행하지 않았습니다.", "info");
    renderStudioProject();
  }

  async function revalidateStudioProject(recorded = false) {
    const mode = recorded ? "recorded" : state.studioCandidate ? "candidate" : "applied";
    const selected = mode === "recorded" ? state.studioRecorded : mode === "candidate" ? state.studioCandidate : state.studioApplied;
    const settings = mode === "recorded" ? state.studioSettingsRecorded : mode === "candidate" ? state.studioSettingsCandidate : state.studioSettingsApplied;
    const settingsIdentity = studioSettingsIdentity(settings);
    const identity = studioSourceIdentity(selected);
    if (!identity || state.workflowBusy || !state.token) return;
    const recordedReview = mode === "recorded" ? state.studioSettingsRecordedReview : settings?.review;
    if ((settings != null || recordedReview != null) && (!settingsIdentity || (settings.revision || settings).source_id !== selected.source_id)) {
      invalidateStudioRequests();
      showNotice("studio-project-feedback", "편집한 설정 기록의 식별 정보가 없거나 원본과 일치하지 않습니다. 기록과 기존 입력을 유지했으며 원본 설정으로 바꾸지 않았습니다. 저장한 설정 기록을 복구한 뒤 다시 확인해 주세요.", "error");
      renderStudioProject();
      return;
    }
    invalidateStudioRequests();
    state.studioPending = true;
    state.studioPendingName = selected.source.filename;
    const request = state.studioRequest, context = studioContext();
    renderStudioProject();
    try {
      const envelope = settingsIdentity ? await api(`/api/studio-settings-revisions/${(settings.revision || settings).revision_id}`, undefined, undefined, { current: () => studioContextCurrent(context) }) : null;
      const result = envelope ? envelope.source : await api(`/api/studio-projects/${selected.source_id}`, undefined, undefined, { current: () => studioContextCurrent(context) });
      if (!studioContextCurrent(context)) return;
      if (settingsIdentity && studioSettingsIdentity(envelope) !== settingsIdentity) throw new Error("저장한 설정 기록이 이전 선택과 일치하지 않습니다.");
      if (studioSourceIdentity(result) !== identity) throw new Error("현재 저장 위치의 원본 식별 정보가 이전 기록과 일치하지 않습니다. 파일을 다시 선택해 주세요.");
      if (mode === "applied") {
        state.studioSettingsApplied = envelope;
        state.studioApplied = result;
        state.studioAppliedEpoch = state.connectionEpoch;
        state.studioAppliedStorage = state.storage?.path || null;
      } else {
        if (mode === "recorded") state.studioWorkspaceCandidate = null;
        state.studioSettingsCandidate = envelope;
        state.studioCandidate = result;
        state.studioCandidateEpoch = state.connectionEpoch;
        state.studioCandidateStorage = state.storage?.path || null;
      }
      showNotice("studio-project-feedback", settingsIdentity ? mode === "applied" ? "원본과 저장한 사용자 선택값을 다시 확인했습니다. 현재 CAD에 설정을 담아 새로 준비해 주세요." : "기록의 원본과 사용자 선택값을 확인했습니다. 설정 차이를 살펴보고 후보를 직접 선택한 뒤 현재 CAD에 담아 주세요." : mode === "applied" ? "같은 원본임을 다시 확인했습니다. 현재 CAD에 설정을 담아 다시 준비해 주세요." : "기록과 같은 원본임을 확인했습니다. 후보를 직접 선택한 뒤 현재 CAD에 설정을 담아 주세요.", "info");
    } catch (error) {
      if (studioContextCurrent(context)) showNotice("studio-project-feedback", `${error.message} 기존 입력은 유지했습니다. 필요하면 원본 .3mf를 다시 선택해 주세요.`, "error");
    } finally {
      if (request === state.studioRequest) { state.studioPending = false; state.studioPendingName = ""; }
      renderStudioProject();
    }
  }

  async function runStudioSlice(execute) {
    const button = execute ? $("execute-studio-project") : $("prepare-studio-project");
    let context = null;
    try {
      if (!studioSourceCurrent() || state.studioCandidate || state.studioPending || state.studioSettingsPending || studioSettingsDirty() || state.studioSettingsReview || !state.job?.result) throw new Error("원본을 다시 확인하고 프로젝트 설정과 현재 CAD를 선택해 주세요.");
      if (execute && (!state.studioSlicePrepared || !studioContextCurrent(state.studioPreparedSignature) || !state.environment.available)) throw new Error("현재 원본과 CAD로 설정을 먼저 준비하고 지원되는 Studio 설치를 확인해 주세요.");
      await withWorkflow(button, execute ? "프로젝트 슬라이싱 중" : "CAD에 설정 담는 중", async () => {
        const sourceId = state.studioApplied.source_id, jobId = state.job.id;
        invalidateStudioRequests();
        resetSlicePreparation(execute ? "선택한 프로젝트와 현재 CAD로 슬라이싱하고 있습니다." : "원본의 전역 설정과 현재 CAD를 새 3MF에 담고 있습니다.");
        context = studioContext();
        const response = await api("/api/slice", { job_id: jobId, ...(state.studioSettingsApplied ? { studio_settings_revision_id: state.studioSettingsApplied.revision.revision_id } : { studio_project_id: sourceId }), execute }, undefined, { current: () => studioContextCurrent(context) });
        if (!studioContextCurrent(context)) return;
        state.studioSavedIdentity = JSON.stringify([studioSourceIdentity(state.studioApplied), studioSettingsIdentity(state.studioSettingsApplied)]);
        state.studioSlicePrepared = Boolean(response.plan?.ready) && !execute;
        state.studioPreparedSignature = state.studioSlicePrepared ? studioContext() : null;
        state.studioRecorded = response.plan?.project_source || null;
        state.studioSettingsRecorded = response.plan?.settings_revision ?? null;
        state.studioSettingsRecordedReview = response.plan?.settings_review ?? null;
        context = studioContext();
        state.studioPreparedSignature = state.studioSlicePrepared ? context : null;
        renderSliceResult(response.plan || {}, response.execution);
        try {
          const full = await api(`/api/jobs/${encodeURIComponent(jobId)}`, undefined, undefined, { current: () => studioContextCurrent(context) });
          if (!studioContextCurrent(context)) return;
          state.job = full;
          renderDownloads(full);
          state.studioPreparedSignature = state.studioSlicePrepared ? studioContext() : null;
        } catch (error) { if (studioContextCurrent(context)) toast("준비 결과는 받았지만 파일 목록을 불러오지 못했습니다. 작업 기록에서 확인해 주세요."); }
      });
    } catch (error) {
      if (context !== null && !studioContextCurrent(context)) return;
      state.studioSlicePrepared = false;
      state.studioPreparedSignature = null;
      showNotice("slice-feedback", error.message, "error");
    } finally { updateSliceControls(); }
  }

  function updateSliceControls() {
    if (typeof renderJourney === "function" && $("journey-steps")) renderJourney();
    const reading = Object.keys(state.slicerPending).length > 0;
    const busy = state.workflowBusy;
    const canPrepare = Boolean(state.token && state.job && state.environment.available && state.environment.cli_supported !== false && !busy && !state.slicerStaged && !reading);
    if (!$("prepare-slice").dataset.busy) $("prepare-slice").disabled = !canPrepare;
    if (!$("execute-slice").dataset.busy) $("execute-slice").disabled = !canPrepare || !state.slicePrepared;
    if (!$("compare-slices").dataset.busy) $("compare-slices").disabled = !canPrepare || !$("slicer-json").value.trim();
    $("probe-slicer").disabled = busy || !state.token || !state.environment.available;
    $("assemble-slicer").disabled = busy || reading || !state.slicerStaged;
    $("cancel-slicer-assembly").disabled = busy || (!reading && !state.slicerStaged);
    $("slicer-json").disabled = busy || state.slicerStaged || Boolean(state.slicerPending.bundle);
    $("slicer-file").disabled = busy || state.slicerStaged;
    for (const id of ["slicer-machine-file", "slicer-process-file", "slicer-filament-files", "slicer-plate"]) $(id).disabled = busy || Boolean(state.slicerPending.bundle);
    renderStudioProject();
  }

  function resetSlicePreparation(message) {
    state.slicePrepared = false;
    state.studioSlicePrepared = false;
    state.studioPreparedSignature = null;
    if (state.job) {
      const artifacts = { ...state.job.artifacts };
      delete artifacts.prepared_three_mf;
      delete artifacts.sliced_three_mf;
      delete artifacts.slice;
      state.job = { ...state.job, artifacts };
      renderDownloads(state.job);
    }
    $("slice-result").replaceChildren();
    if (message) showNotice("slice-feedback", message);
    updateSliceControls();
  }

  $("slicer-json").addEventListener("input", manualSlicerChanged);

  function renderPrintVolumeReview(report, recorded = false) {
    if (!report || report.schema_version !== 1) return null;
    const volumeFormat = new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 9 });
    const area = node("section", "print-volume-review");
    area.id = "print-volume-review";
    area.setAttribute("aria-labelledby", "print-volume-heading");
    const heading = node("h3", "", recorded ? "이 작업에 기록된 출력 크기 비교" : "현재 CAD와 기록된 출력 크기");
    heading.id = "print-volume-heading";
    const labels = { fits: "기록된 출력 공간과 크기 비교 완료", height_exceeded: "기록된 출력 높이 초과", needs_review: "배치 추가 확인 필요" };
    const status = node("span", `badge badge-${report.status === "fits" ? "blue" : "warning"}`, labels[report.status] || "크기 비교 결과 확인 필요");
    const header = node("div", "print-volume-heading");
    header.append(heading, status);
    area.append(header);
    if (recorded) area.append(node("p", "field-help", "이 모델 작업에 저장된 비교입니다. 현재 입력을 다시 비교한 결과가 아닙니다. 사용할 설정을 선택한 뒤 새로 준비해 주세요."));

    const table = node("table", "print-volume-comparison");
    table.append(node("caption", "", "가로·세로·높이 비교 · mm"));
    const head = node("thead"), headers = node("tr");
    for (const label of ["대상", "가로", "세로", "높이"]) {
      const cell = node("th", "", label);
      cell.scope = "col";
      headers.append(cell);
    }
    head.append(headers);
    const body = node("tbody");
    for (const [label, values] of [[recorded ? "기록된 CAD" : "현재 CAD", report.model_dimensions_mm], ["설정에 기록된 출력 공간", report.recorded_volume_mm]]) {
      const row = node("tr"), labelCell = node("th", "", label);
      labelCell.scope = "row";
      row.append(labelCell);
      for (const index of [0, 1, 2]) row.append(node("td", "", Number.isFinite(values?.[index]) ? volumeFormat.format(values[index]) : "미확인"));
      body.append(row);
    }
    table.append(head, body);
    const comparison = node("div", "table-wrap");
    comparison.append(table);
    area.append(comparison);

    const orientations = node("ul", "print-volume-orientations");
    for (const orientation of Array.isArray(report.orientations) ? report.orientations : []) {
      if (![0, 90].includes(orientation.rotation_degrees)) continue;
      const label = orientation.rotation_degrees === 0 ? "현재 방향 · 0°" : "가로·세로 회전 · 90°";
      orientations.append(node("li", "", `${label}: ${orientation.fits === true ? "크기 비교 통과" : "범위 내 배치 미확인"}`));
    }
    if (orientations.children.length) area.append(orientations);
    if (Array.isArray(report.issues) && report.issues.length) {
      const reasons = node("ul", "reason-list");
      for (const issue of report.issues) if (typeof issue?.message === "string") reasons.append(node("li", "", issue.message));
      area.append(reasons);
    }
    area.append(node("p", "field-help", "똑바로 세운 CAD 외곽 상자를 파일에 기록된 출력 공간과 비교했습니다. 실제 장착 장비와 실물 출력 가능 여부를 확인한 결과는 아닙니다."));
    if (report.status === "needs_review") area.append(node("p", "field-help", "다른 각도의 배치는 확인하지 않았습니다."));
    if (report.placement_applied === false) area.append(node("p", "field-help", "모델 크기는 그대로입니다. 회전이나 배치를 적용하지 않았습니다. Studio에서 실제 배치를 확인해 주세요."));
    if (Array.isArray(report.limitations) && report.limitations.length) {
      const details = node("details", "help-details");
      details.append(node("summary", "", "이 크기 비교의 범위"));
      const limitations = node("ul", "reason-list");
      for (const text of report.limitations) if (typeof text === "string") limitations.append(node("li", "", text));
      details.append(limitations);
      area.append(details);
    }
    if (!recorded) {
      const edit = node("button", "button button-secondary", "현재 치수 수정하기");
      edit.type = "button";
      edit.addEventListener("click", () => {
        $("parameter-heading").scrollIntoView?.({ block: "start", behavior: "auto" });
        $("parameter-heading").focus({ preventScroll: true });
      });
      area.append(edit);
    }
    return area;
  }

  function renderSliceResult(plan, execution, recorded = false) {
    const area = $("slice-result");
    area.replaceChildren();
    const volumeReview = renderPrintVolumeReview(plan.print_volume, recorded);
    if (volumeReview) area.append(volumeReview);
    if (execution) {
      const labels = { blocked: ["실행 조건 확인 필요", "warning"], failed: ["슬라이싱 실패", "error"], timed_out: ["슬라이싱 시간 초과", "warning"], sliced: ["슬라이스 파일 검증 완료", "success"], needs_review: ["슬라이스 결과 추가 확인 필요", "warning"] };
      const [title, tone] = labels[execution.status] || ["실행 결과 확인 필요", "info"];
      showNotice("slice-feedback", title, tone, (execution.checks || []).filter((check) => check.passed === false).map((check) => check.detail || check.message || check.name));
      const summary = node("div", "slicer-output");
      summary.append(node("h3", "", "실물 출력은 시작하지 않았습니다."));
      const seconds = execution.estimated_time_seconds;
      const grams = execution.filament_grams;
      summary.append(node("p", "", Number.isFinite(seconds) ? `슬라이서 예상 시간: ${numberFormat.format(seconds / 60)}분` : "출력 시간: 슬라이서에서 확인된 정보 없음"));
      summary.append(node("p", "", Number.isFinite(grams) ? `슬라이서 예상 사용량: ${numberFormat.format(grams)}g` : "재료 사용량: 슬라이서에서 확인된 정보 없음"));
      if (execution.bambu_version) summary.append(node("p", "", `확인한 Bambu Studio 버전: ${execution.bambu_version}`));
      if (execution.output_sha256) summary.append(node("p", "", `생성 파일 SHA-256: ${execution.output_sha256}`));
      area.append(summary);
      const details = node("details", "help-details");
      details.append(node("summary", "", "실행 기록과 검사 결과"), node("pre", "", JSON.stringify(execution, null, 2)));
      area.append(details);
    } else if (plan.kind === "studio_project" && plan.project_prepared) {
      const message = recorded ? "기록된 설정 포함 3MF가 있습니다. 원본을 다시 확인한 뒤 현재 CAD로 새로 준비해 주세요." : plan.ready ? "설정 포함 3MF를 준비했습니다. 파일을 내려받거나 지원되는 Studio에서 별도로 슬라이싱할 수 있습니다." : "설정 포함 3MF를 준비했습니다. 파일을 내려받아 Studio에서 열 수 있으며, 현재 환경의 로컬 슬라이싱 실행 조건은 별도로 확인해야 합니다.";
      showNotice("slice-feedback", message, "info", plan.diagnostics || []);
    } else {
      const message = recorded
        ? (plan.ready ? "저장된 실행 계획이 있습니다. 현재 전체 설정으로 다시 검토한 뒤 슬라이싱을 실행해 주세요." : "저장된 실행 계획은 준비되지 않았습니다. 아래 사항과 현재 설정을 확인해 주세요.")
        : (plan.ready ? "실행 계획을 준비했습니다. 설정을 확인한 뒤 슬라이싱을 실행할 수 있습니다." : "실행 계획을 준비하려면 아래 사항을 확인해 주세요.");
      showNotice("slice-feedback", message, plan.ready ? "success" : "warning", plan.diagnostics || []);
    }
    if (Array.isArray(plan.argv) && plan.argv.length) {
      const details = node("details", "help-details");
      details.append(node("summary", "", "고급 · 실행 계획 확인"), node("pre", "", JSON.stringify({ arguments: plan.argv, expected_settings: plan.expected_settings }, null, 2)));
      area.append(details);
    }
  }

  async function runSlice(execute) {
    const button = execute ? $("execute-slice") : $("prepare-slice");
    let context = null, submittedText = null;
    const current = () => context !== null && studioContextCurrent(context) && $("slicer-json").value === submittedText;
    try {
      if (state.slicerStaged || Object.keys(state.slicerPending).length) throw new Error("설정 파일을 선택 중입니다. 묶음을 만들거나 편집을 취소한 뒤 실행 계획을 검토해 주세요.");
      await withWorkflow(button, execute ? "슬라이싱 실행 중" : "전체 설정 검토 중", async () => {
        const jobId = state.job?.id;
        if (!jobId) throw new Error("먼저 현재 제작안의 모델을 생성해 주세요.");
        submittedText = $("slicer-json").value;
        const bundle = parseObject(submittedText, "슬라이서 전체 설정");
        cancelSlicerReads();
        resetSlicePreparation(execute ? "검토한 설정으로 슬라이싱하고 있습니다." : "전체 설정과 실행 계획을 검토하고 있습니다.");
        context = studioContext();
        const response = await api("/api/slice", { job_id: jobId, config_bundle: bundle, execute }, undefined, { current });
        if (!current()) return;
        state.slicerSavedText = submittedText;
        state.slicePrepared = Boolean(response.plan?.ready) && !execute;
        state.studioRecorded = null;
    state.studioSettingsRecorded = null;
    state.studioSettingsRecordedReview = null;
        state.studioSavedIdentity = null;
        renderSliceResult(response.plan || {}, response.execution);
        try {
          const full = await api(`/api/jobs/${encodeURIComponent(jobId)}`, undefined, undefined, { current });
          if (!current()) return;
          state.job = full;
          renderDownloads(full);
        } catch { if (current()) toast("검토 결과는 받았지만 파일 목록을 새로 불러오지 못했습니다. 작업 기록에서 다시 확인해 주세요."); }
      });
    } catch (error) {
      if (context !== null && !current()) return;
      state.slicePrepared = false;
      showNotice("slice-feedback", error.message, "error");
    }
    finally { updateSliceControls(); }
  }
  function renderSliceComparison(record) {
    const area = $("slice-compare");
    const rows = Array.isArray(record?.variants) ? record.variants : [];
    if (!rows.length) { area.hidden = true; area.replaceChildren(); return; }
    const base = rows.find((row) => row.id === "original" && Number.isFinite(row.minutes));
    const change = (value, reference, unit) => (Number.isFinite(value) && Number.isFinite(reference) && reference && value !== reference)
      ? ` (${value > reference ? "+" : ""}${Math.round((value - reference) / reference * 100)}%)` : "";
    const table = node("table", "");
    const head = node("tr", "");
    for (const title of ["설정", "예상 시간", "재료", "레이어", "서포트", ""]) head.append(node("th", "", title));
    table.append(head);
    for (const row of rows) {
      const line = node("tr", "");
      line.dataset.compareVariant = row.id;
      const name = node("td", "");
      const changed = Object.entries(row.overrides || {}).map(([key, value]) => `${({ layer_height: "레이어", sparse_infill_density: "채움", wall_loops: "벽", top_shell_layers: "윗면 층", bottom_shell_layers: "바닥 층" })[key] || key} ${value}`).join(" · ");
      name.append(node("strong", "", row.label), node("small", "", changed || row.description));
      line.append(name);
      if (row.status === "sliced") {
        line.append(node("td", "number", `${numberFormat.format(row.minutes)}분${change(row.minutes, base?.minutes)}`),
          node("td", "number", `${numberFormat.format(row.grams)} g${change(row.grams, base?.grams)}`),
          node("td", "number", row.layers ? numberFormat.format(row.layers) : "–"), node("td", "", row.support ? "있음" : "없음"));
        const cell = node("td", "");
        if (row.id !== "original") {
          const apply = node("button", "text-button", "이 설정 적용");
          apply.type = "button";
          apply.addEventListener("click", () => applySliceVariant(row));
          cell.append(apply);
        }
        line.append(cell);
      } else {
        const failed = node("td", "", `슬라이스하지 못함 · ${(row.diagnostics || [])[0] || row.status}`);
        failed.colSpan = 5;
        line.append(failed);
      }
      table.append(line);
    }
    area.replaceChildren(table, node("p", "field-help", record.scope || ""));
    area.hidden = false;
  }

  function applySliceVariant(row) {
    // Change only the listed process keys in the reviewed JSON; the person reviews and slices it as usual.
    let bundle;
    try { bundle = parseObject($("slicer-json").value, "슬라이서 전체 설정"); } catch (error) { showNotice("slice-feedback", error.message, "error"); return; }
    if (!bundle.process || typeof bundle.process !== "object") { showNotice("slice-feedback", "설정 JSON에 process가 없습니다.", "error"); return; }
    for (const [key, value] of Object.entries(row.overrides || {})) {
      const current = bundle.process[key];
      bundle.process[key] = Array.isArray(current) && current.length ? current.map(() => value) : value;
    }
    $("slicer-json").value = JSON.stringify(bundle, null, 2);
    $("slicer-json").dispatchEvent(new Event("input", { bubbles: true }));
    resetSlicePreparation(`“${row.label}” 설정을 설정 JSON에 넣었습니다. 바뀐 값: ${Object.entries(row.overrides || {}).map(([key, value]) => `${key}=${value}`).join(", ")}. 실행 계획을 다시 검토한 뒤 슬라이싱하세요.`);
    updateSliceControls();
  }

  async function compareSlices() {
    const button = $("compare-slices");
    try {
      if (state.slicerStaged || Object.keys(state.slicerPending).length) throw new Error("설정 파일을 선택 중입니다. 묶음을 만든 뒤 비교해 주세요.");
      await withWorkflow(button, "4가지 슬라이스 중", async () => {
        const jobId = state.job?.id;
        if (!jobId) throw new Error("먼저 모델을 준비해 주세요.");
        const bundle = parseObject($("slicer-json").value, "슬라이서 전체 설정");
        const job = await api("/api/slice/compare", { job_id: jobId, config_bundle: bundle });
        if (state.job?.id !== jobId) return;
        state.job = { ...state.job, slice_comparison: job.slice_comparison };
        renderSliceComparison(job.slice_comparison);
      });
    } catch (error) {
      showNotice("slice-feedback", error.message, "error");
    } finally { updateSliceControls(); }
  }
  $("compare-slices").addEventListener("click", compareSlices);

  $("prepare-slice").addEventListener("click", () => runSlice(false));
  $("execute-slice").addEventListener("click", () => runSlice(true));

  function cancelSlicerReads() {
    state.slicerContext += 1;
    state.slicerPending = {};
    invalidateStudioRequests();
  }

  function renderSlicerFiles() {
    for (const kind of ["machine", "process", "filaments"]) {
      const entries = kind === "filaments" ? state.slicerFiles.filaments : state.slicerFiles[kind] ? [state.slicerFiles[kind]] : [];
      const label = entries.map((entry, index) => `${kind === "filaments" ? `${index + 1}. ` : ""}${entry.filename} · ${entry.profile.name} (${entry.profile.type})`).join("\n");
      $(`slicer-${kind}-summary`).textContent = `${label || "선택한 파일 없음"}${state.slicerPending[kind] ? "\n새 파일 읽는 중…" : ""}`;
    }
    const reading = Object.keys(state.slicerPending).length > 0;
    $("slicer-helper-status").textContent = reading ? "파일 읽기가 끝나면 묶음을 만들 수 있습니다." : state.slicerStaged ? "선택을 편집 중입니다. 이전 실행 계획은 해제되었습니다." : state.slicerFiles.machine ? "묶음을 만들었습니다. 아래 JSON과 실행 계획을 확인하세요." : "파일과 플레이트를 선택하세요.";
    updateSliceControls();
  }

  function slicerBundle(files = state.slicerFiles) {
    return { source: "user_export", plate_type: $("slicer-plate").value, machine: files.machine?.profile || {}, process: files.process?.profile || {}, filaments: files.filaments.map((entry) => entry.profile) };
  }

  function checkSlicerBundleSize(bundle) {
    const request = { job_id: state.job?.id || "0".repeat(32), config_bundle: bundle, execute: false };
    if (new TextEncoder().encode(JSON.stringify(request)).byteLength > 8 * 1024 * 1024) throw new Error("설정 묶음을 포함한 전체 요청은 8 MiB 이하여야 합니다. 기존 입력과 선택한 파일은 유지했습니다.");
  }

  async function readSlicerFiles(kind, input) {
    const files = Array.from(input.files || []);
    if (!files.length || !["machine", "process", "filaments"].includes(kind)) return;
    input.value = "";
    const context = state.slicerContext;
    const request = (state.slicerRequests[kind] || 0) + 1;
    state.slicerRequests[kind] = request;
    state.slicerPending[kind] = request;
    state.slicerStaged = true;
    resetSlicePreparation("설정 파일을 선택하고 있습니다. 묶음을 만들거나 편집을 취소한 뒤 다시 검토해 주세요.");
    renderSlicerFiles();
    hideNotice("slicer-helper-feedback");
    try {
      const maximum = kind === "filaments" ? 16 : 1;
      if (files.length > maximum) throw new Error(kind === "filaments" ? "필라멘트 파일은 1~16개를 선택해 주세요." : "이 종류의 설정 파일은 하나만 선택해 주세요.");
      if (files.some((file) => file.size > 8 * 1024 * 1024) || files.reduce((sum, file) => sum + file.size, 0) > 8 * 1024 * 1024) throw new Error("선택한 JSON 파일의 합계는 8 MiB 이하여야 합니다.");
      const expectedType = kind === "filaments" ? "filament" : kind;
      const imported = await Promise.all(files.map(async (file) => {
        const profile = parseObject(await file.text(), file.name);
        if (typeof profile.name !== "string" || !profile.name.trim() || profile.type !== expectedType) throw new Error(`${file.name}: name과 type=${expectedType}가 있는 Bambu 전체 설정 파일을 선택해 주세요. 재료 검토 보고서는 사용할 수 없습니다.`);
        return { filename: file.name, profile };
      }));
      if (context !== state.slicerContext || request !== state.slicerRequests[kind]) return;
      const candidate = { ...state.slicerFiles, [kind]: kind === "filaments" ? imported : imported[0] };
      checkSlicerBundleSize(slicerBundle(candidate));
      state.slicerFiles = candidate;
      showNotice("slicer-helper-feedback", `${imported.length}개 파일을 선택했습니다. 전체 설정의 지원 여부는 묶음을 만든 뒤 실행 계획에서 확인합니다.`);
    } catch (error) {
      if (context === state.slicerContext && request === state.slicerRequests[kind]) showNotice("slicer-helper-feedback", error.message, "error");
    } finally {
      if (context === state.slicerContext && request === state.slicerRequests[kind]) delete state.slicerPending[kind];
      renderSlicerFiles();
    }
  }

  function changeSlicerPlate() {
    state.slicerStaged = true;
    resetSlicePreparation("플레이트 선택을 바꿨습니다. 설정 묶음을 다시 만든 뒤 실행 계획을 검토해 주세요.");
    renderSlicerFiles();
  }

  function assembleSlicerBundle() {
    if (state.workflowBusy || Object.keys(state.slicerPending).length) throw new Error("진행 중인 작업과 파일 읽기가 끝난 뒤 묶음을 만들어 주세요.");
    const plates = ["Cool Plate", "Engineering Plate", "High Temp Plate", "Textured PEI Plate", "Supertack Plate"];
    if (!plates.includes($("slicer-plate").value)) throw new Error("이번 출력에서 사용할 플레이트를 직접 선택해 주세요.");
    if (!state.slicerFiles.machine || !state.slicerFiles.process || state.slicerFiles.filaments.length < 1) throw new Error("프린터·출력 공정 파일과 필라멘트 파일 1개 이상을 선택해 주세요.");
    const bundle = slicerBundle();
    checkSlicerBundleSize(bundle);
    $("slicer-json").value = JSON.stringify(bundle, null, 2);
    state.slicerStaged = false;
    cancelSlicerReads();
    resetSlicePreparation("선택한 파일과 플레이트로 묶음을 만들었습니다. 설정과 실행 계획을 검토해 주세요.");
    renderSlicerFiles();
    showNotice("slicer-helper-feedback", "파일의 값을 그대로 묶었습니다. 설정 검증이나 슬라이싱을 완료한 것은 아닙니다.", "success");
    return bundle;
  }

  function cancelSlicerAssembly() {
    cancelSlicerReads();
    state.slicerFiles = { machine: null, process: null, filaments: [] };
    state.slicerStaged = false;
    $("slicer-plate").value = "";
    for (const id of ["slicer-machine-file", "slicer-process-file", "slicer-filament-files"]) $(id).value = "";
    resetSlicePreparation("파일 선택을 취소했습니다. 기존 전체 구성 JSON을 유지했으며 실행 계획은 다시 검토해야 합니다.");
    renderSlicerFiles();
    hideNotice("slicer-helper-feedback");
  }

  function manualSlicerChanged() {
    cancelSlicerReads();
    state.slicerFiles = { machine: null, process: null, filaments: [] };
    state.slicerStaged = false;
    $("slicer-plate").value = "";
    resetSlicePreparation("전체 설정이 바뀌었습니다. 설정과 실행 계획을 다시 검토해 주세요.");
    renderSlicerFiles();
    hideNotice("slicer-helper-feedback");
  }

  async function readSlicerBundle(input) {
    const file = input.files?.[0];
    if (!file) return;
    input.value = "";
    cancelSlicerReads();
    const context = state.slicerContext;
    state.slicerPending.bundle = true;
    resetSlicePreparation("전체 구성 파일을 읽고 있습니다. 완료 후 실행 계획을 다시 검토해 주세요.");
    renderSlicerFiles();
    try {
      if (file.size > 8 * 1024 * 1024) throw new Error("8 MiB 이하의 전체 구성 JSON 파일을 선택해 주세요.");
      const text = await file.text();
      const bundle = parseObject(text, file.name);
      if (context !== state.slicerContext) return;
      checkSlicerBundleSize(bundle);
      $("slicer-json").value = text;
      manualSlicerChanged();
      toast(`${file.name} 파일을 불러왔습니다. 실행 계획을 검토해 주세요.`);
    } catch (error) {
      if (context === state.slicerContext) showNotice("slice-feedback", error.message, "error");
    } finally {
      if (context === state.slicerContext) delete state.slicerPending.bundle;
      renderSlicerFiles();
    }
  }

  function renderSlicerEnvironment() {
    const environment = state.environment;
    const available = Boolean(environment.available);
    const supported = environment.cli_supported;
    setBadge("environment-badge", available ? "Bambu Studio 감지됨" : "슬라이서 사용 불가", available ? "blue" : "neutral");
    setBadge("slicer-status", !available ? "현재 환경에서 사용 불가" : supported === true ? "CLI 기능 확인됨" : supported === false ? "CLI 실행 조건 확인 필요" : "실행 파일 감지됨", supported === true ? "blue" : supported === false ? "warning" : "neutral");
    $("slicer-description").textContent = available
      ? "실행 파일을 찾았습니다. 설치된 슬라이서 확인을 누르면 버전과 필요한 명령줄 기능을 확인합니다. 모델과 전체 설정의 슬라이싱은 별도 단계입니다."
      : "Bambu Studio 실행 파일을 찾지 못했습니다. 프로젝트 설정 확인, 현재 CAD에 설정을 담은 3MF 생성과 다운로드는 사용할 수 있습니다. 로컬 슬라이싱은 Studio 설치·실행 경로를 설정한 뒤 다시 연결해 주세요.";
    const details = [];
    if (environment.path) details.push(`실행 파일: ${environment.path}`);
    if (supported !== undefined) {
      details.push(`확인한 버전: ${environment.version || "확인하지 못함"}`);
      details.push(`확인한 명령줄 옵션: ${(environment.capabilities || []).join(", ") || "확인하지 못함"}`);
    }
    details.push(...(environment.diagnostics || []));
    if (details.length) showNotice("slicer-probe-feedback", supported === true ? "필요한 명령줄 기능을 확인했습니다. 실제 슬라이스 파일과 실물 출력은 별도 검증이 필요합니다." : supported === false ? "필요한 명령줄 기능을 확인하지 못했습니다." : "설치 환경에서 확인한 정보", supported === false ? "warning" : "info", details);
    else hideNotice("slicer-probe-feedback");
    updateSliceControls();
  }

  async function probeSlicer() {
    if (!state.environment.available) return;
    try {
      await withWorkflow($("probe-slicer"), "슬라이서 확인 중", async () => {
        resetSlicePreparation("설치된 슬라이서의 명령줄 기능을 확인하고 있습니다. 기존 실행 계획은 다시 검토해야 합니다.");
        state.environment = { ...state.environment, cli_supported: undefined, version: null, capabilities: [], diagnostics: [] };
        renderSlicerEnvironment();
        const environment = await api("/api/slicer/probe", {});
        state.environment = environment;
        renderSlicerEnvironment();
      });
    } catch (error) { showNotice("slicer-probe-feedback", error.message, "error"); }
    finally { updateSliceControls(); }
  }
  $("profile-file").addEventListener("change", (event) => importProfileFiles(event.target));
  $("profile-archive").addEventListener("change", (event) => importProfileArchive(event.target));
  $("slicer-file").addEventListener("change", (event) => readSlicerBundle(event.target));
  $("slicer-machine-file").addEventListener("change", (event) => readSlicerFiles("machine", event.target));
  $("slicer-process-file").addEventListener("change", (event) => readSlicerFiles("process", event.target));
  $("slicer-filament-files").addEventListener("change", (event) => readSlicerFiles("filaments", event.target));
  $("slicer-plate").addEventListener("change", changeSlicerPlate);
  $("assemble-slicer").addEventListener("click", () => {
    try { assembleSlicerBundle(); }
    catch (error) { showNotice("slicer-helper-feedback", error.message, "error"); }
  });
  $("cancel-slicer-assembly").addEventListener("click", cancelSlicerAssembly);
  $("probe-slicer").addEventListener("click", probeSlicer);
  $("studio-library-kind").addEventListener("change", () => studioLibrarySelectionChanged(true));
  $("studio-library-list").addEventListener("change", () => studioLibrarySelectionChanged());
  $("studio-library-refresh").addEventListener("click", () => loadStudioLibrary());
  $("studio-library-more").addEventListener("click", () => loadStudioLibrary(true));
  $("studio-library-open").addEventListener("click", openStudioLibrary);
  $("studio-workspace-title").addEventListener("input", renderStudioLibrary);
  $("studio-workspace-save").addEventListener("click", () => saveStudioWorkspace());
  $("studio-workspace-copy").addEventListener("click", () => saveStudioWorkspace(true));
  $("studio-workspace-delete").addEventListener("click", deleteStudioWorkspace);
  $("studio-settings-open").addEventListener("click", openStudioSettings);
  $("studio-settings-review").addEventListener("click", reviewStudioSettings);
  $("studio-settings-apply").addEventListener("click", applyStudioSettings);
  $("studio-settings-cancel").addEventListener("click", cancelStudioSettings);
  $("studio-settings-reset").addEventListener("click", resetStudioSettings);
  $("studio-settings-replace").addEventListener("click", () => applyStudioCandidate(true));
  $("studio-settings-keep").addEventListener("click", cancelStudioCandidate);
  $("studio-project-file").addEventListener("change", (event) => importStudioProject(event.target));
  $("studio-project-cancel").addEventListener("click", cancelStudioCandidate);
  $("studio-project-apply").addEventListener("click", () => applyStudioCandidate());
  $("studio-project-revalidate").addEventListener("click", () => revalidateStudioProject(false));
  $("studio-project-history-source").addEventListener("click", () => revalidateStudioProject(true));
  $("prepare-studio-project").addEventListener("click", () => runStudioSlice(false));
  $("execute-studio-project").addEventListener("click", () => runStudioSlice(true));

  // ---------------------------------------------------------------------------
  // After a failed print: the person's reasons, and reviewable next steps.

  function setFailureReasons(reasons) {
    state.failureReasons = reasons && typeof reasons === "object" ? reasons : {};
    $("outcome-reason-list").replaceChildren(...Object.entries(state.failureReasons).map(([code, label]) => {
      const item = node("label", "outcome-reason");
      const box = node("input");
      box.type = "checkbox";
      box.value = code;
      box.dataset.outcomeReason = code;
      item.append(box, node("span", "", label));
      return item;
    }));
    syncOutcomeReasons(state.job?.user_outcome?.reasons || []);
  }

  function selectedOutcomeReasons() {
    return [...document.querySelectorAll("[data-outcome-reason]")].filter((box) => box.checked).map((box) => box.value);
  }

  function syncOutcomeReasons(reasons) {
    const wanted = new Set(Array.isArray(reasons) ? reasons : []);
    for (const box of document.querySelectorAll("[data-outcome-reason]")) box.checked = wanted.has(box.value);
    $("outcome-reasons").hidden = $("outcome-result").value !== "failure";
  }

  async function loadRecovery(job) {
    const area = $("outcome-recovery");
    const reasons = job?.user_outcome?.result === "failure" ? job.user_outcome.reasons || [] : [];
    if (!job || (!reasons.length && job.printer_report?.state !== "FAILED")) { area.hidden = true; area.replaceChildren(); return; }
    const request = state.recoveryRequest = (state.recoveryRequest || 0) + 1;
    try {
      const plan = await api(`/api/jobs/${encodeURIComponent(job.id)}/recovery`);
      if (request !== state.recoveryRequest || state.job?.id !== job.id) return;
      renderRecovery(plan);
    } catch (error) {
      if (request === state.recoveryRequest) { area.hidden = false; area.replaceChildren(node("p", "field-help", error.message)); }
    }
  }

  function renderRecovery(plan) {
    const area = $("outcome-recovery");
    const items = Array.isArray(plan?.items) ? plan.items : [];
    area.replaceChildren(node("h3", "", "다음에 바꿔 볼 것"), ...items.map((item) => {
      const block = node("div", "recovery-item");
      block.dataset.reason = item.reason;
      block.append(node("strong", "", item.label));
      const list = node("ul", "");
      for (const action of item.actions || []) list.append(node("li", "", action));
      block.append(list);
      if (item.lookup_url) {
        // Bambu Lab's own HMS search; the code meaning is never inferred here.
        const link = node("a", "", "Bambu Lab HMS 코드 검색 열기 ↗");
        link.href = item.lookup_url;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        block.append(link);
      }
      if (item.model_edit?.text) {
        const changes = (item.model_edit.changes || []).map((change) => `${fieldNames[change.field] || change.field} ${change.before} → ${change.after}`).join(", ");
        const button = node("button", "button button-secondary", `모델 수정 검토: ${changes}`);
        button.type = "button";
        button.dataset.recoveryEdit = item.model_edit.text;
        button.addEventListener("click", () => proposeRecoveryEdit(item.model_edit.text));
        block.append(button);
      }
      return block;
    }), node("p", "field-help", plan?.scope || ""));
    area.hidden = !items.length;
  }

  async function loadAttempts(job) {
    // Only a model edited from an earlier one has a history worth showing.
    const area = $("outcome-attempts");
    if (!job?.id || !job.model_edit?.selection?.parent) { area.hidden = true; area.replaceChildren(); return; }
    const request = state.attemptsRequest = (state.attemptsRequest || 0) + 1;
    try {
      const history = await api(`/api/jobs/${encodeURIComponent(job.id)}/attempts`);
      if (request !== state.attemptsRequest || state.job?.id !== job.id) return;
      renderAttempts(history, job.id);
    } catch (error) {
      if (request === state.attemptsRequest) { area.hidden = false; area.replaceChildren(node("p", "field-help", error.message)); }
    }
  }

  function attemptFacts(attempt) {
    const attemptResults = { success: "성공", failure: "실패", not_tested: "출력 안 함" };
    const facts = [];
    const outcome = attempt.user_outcome;
    if (outcome?.result) {
      const reasons = (outcome.reasons || []).map((code) => state.failureReasons?.[code] || code);
      facts.push(`직접 기록: ${attemptResults[outcome.result] || outcome.result}${reasons.length ? ` (${reasons.join(", ")})` : ""}`);
    }
    const report = attempt.printer_report;
    if (report?.state) facts.push(`프린터 보고: ${report.state === "FAILED" ? "실패" : report.state === "FINISH" ? "완료" : report.state}${report.codes?.length ? ` · ${report.codes.join(", ")}` : ""}`);
    if (!facts.length) facts.push(attempt.sent_to_printer ? "프린터로 보냄 · 결과 기록 없음" : attempt.sliced ? "슬라이스함 · 결과 기록 없음" : "결과 기록 없음");
    return facts.join(" · ");
  }

  function attemptSliceText(attempt, attempts) {
    // What the verified slice plan recorded; compared with the nearest earlier successful slice.
    const labels = { printer_model: "프린터", nozzle_diameter: "노즐", curr_bed_type: "출력판", layer_height: "레이어 높이",
      initial_layer_print_height: "첫 레이어 높이", wall_loops: "벽 루프", top_shell_layers: "윗면 층", bottom_shell_layers: "바닥 층",
      sparse_infill_density: "채움 밀도", outer_wall_speed: "바깥 벽 속도", inner_wall_speed: "안쪽 벽 속도", sparse_infill_speed: "채움 속도",
      initial_layer_speed: "첫 레이어 속도", filament_settings_id: "필라멘트 프로필", filament_type: "재료", filament_flow_ratio: "유량 비율",
      filament_max_volumetric_speed: "최대 체적 속도", nozzle_temperature: "노즐 온도", nozzle_temperature_initial_layer: "첫 레이어 노즐 온도",
      hot_plate_temp: "베드 온도(고온판)", hot_plate_temp_initial_layer: "첫 레이어 베드 온도(고온판)", textured_plate_temp: "베드 온도(텍스처판)",
      textured_plate_temp_initial_layer: "첫 레이어 베드 온도(텍스처판)", cool_plate_temp: "베드 온도(쿨판)", cool_plate_temp_initial_layer: "첫 레이어 베드 온도(쿨판)",
      eng_plate_temp: "베드 온도(엔지니어링판)", eng_plate_temp_initial_layer: "첫 레이어 베드 온도(엔지니어링판)" };
    const show = (value) => value === undefined || value === null ? "없음" : Array.isArray(value) ? value.join(" / ") : String(value);
    const settings = attempt.slice_settings;
    if (!settings) return "";
    const comparison = attempt.slice_changes;
    if (comparison) {
      const number = attempts.findIndex((item) => item.job_id === comparison.compared_with) + 1;
      const where = number > 0 ? `${number}번째 시도` : "이전 시도";
      const changes = comparison.changes || [];
      if (!changes.length) return `슬라이스 설정: ${where}와 같음`;
      return `슬라이스 설정 변경(${where} 대비): ${changes.map((change) => `${labels[change.key] || change.key} ${show(change.before)} → ${show(change.after)}`).join(", ")}`;
    }
    const summary = ["filament_type", "nozzle_diameter", "layer_height", "nozzle_temperature"].filter((key) => key in settings)
      .map((key) => `${labels[key]} ${show(settings[key])}`);
    return summary.length ? `슬라이스 설정: ${summary.join(" · ")}` : "";
  }

  function renderAttempts(history, currentId) {
    const area = $("outcome-attempts");
    const attempts = Array.isArray(history?.attempts) ? [...history.attempts].reverse() : [];
    if (attempts.length < 2) { area.hidden = true; area.replaceChildren(); return; }
    const attemptStops = { missing: "더 이전 모델 기록은 이 PC에 없습니다.", unreadable: "더 이전 모델 기록을 읽을 수 없습니다(원본 파일은 보존).",
      limit: "최근 시도까지만 보여줍니다.", cycle: "기록 연결이 반복되어 여기서 멈췄습니다." };
    const list = node("ol", "");
    attempts.forEach((attempt, index) => {
      const item = node("li", "");
      item.dataset.attempt = attempt.job_id;
      if (attempt.job_id === currentId) item.setAttribute("aria-current", "true");
      item.append(node("strong", "", `${index + 1}번째 · ${dateTime(attempt.created_at)}`), node("span", "attempt-facts", attemptFacts(attempt)));
      const sliceText = attemptSliceText(attempt, attempts);
      if (sliceText) item.append(node("span", "attempt-changes", sliceText));
      const changes = attempt.changes_from_parent?.changes || [];
      if (changes.length) {
        const text = changes.map((change) => `${fieldNames[change.field] || change.field} ${change.before} → ${change.after}`).join(", ");
        item.append(node("span", "attempt-changes", `이전 시도에서 바꾼 점: ${text}`));
      }
      list.append(item);
    });
    const parts = [node("h3", "", "출력 시도 이력"), list];
    if (attemptStops[history.stopped]) parts.push(node("p", "field-help", attemptStops[history.stopped]));
    parts.push(node("p", "field-help", "각 시도에 기록된 결과, 검증된 슬라이스 계획의 설정, 검토해 적용한 치수 변경만 보여줍니다. 원인을 추정하지 않습니다."));
    area.replaceChildren(...parts);
    area.hidden = false;
  }

  function proposeRecoveryEdit(text) {
    // Reuse the reviewed edit flow: the person still checks and applies the change.
    const input = $("model-edit-text");
    // The sentence is written for the rule engine; never hand it to an external model.
    if ($("model-edit-mode").value !== "templates") $("model-edit-mode").value = "templates";
    input.value = text;
    input.dispatchEvent(new Event("input", { bubbles: true }));
    $("model-edit-panel")?.scrollIntoView({ behavior: "smooth", block: "center" });
    $("model-edit-propose").click();
  }

  // ---------------------------------------------------------------------------
  // Caliper measurements of printed samples (user-measured, compared with the CAD size).

  function collectMeasurements() {
    const samples = [];
    for (const row of document.querySelectorAll("[data-measure-row]")) {
      const inputs = [...row.querySelectorAll("[data-measure]")];
      const filled = inputs.filter((input) => input.value.trim() !== "");
      if (!filled.length) continue;
      if (filled.length !== 3 || inputs.some((input) => !Number.isFinite(Number(input.value)) || Number(input.value) <= 0)) {
        throw new Error(`샘플 ${row.dataset.measureRow}의 가로·세로·높이를 모두 0보다 큰 숫자로 적어 주세요.`);
      }
      samples.push(Object.fromEntries(inputs.map((input) => [input.dataset.measure, Number(input.value)])));
    }
    const toleranceText = $("outcome-tolerance").value.trim();
    const tolerance = toleranceText === "" ? null : Number(toleranceText);
    if (tolerance !== null && !samples.length) throw new Error("허용 오차는 실측값과 함께 적어 주세요.");
    return { samples, tolerance };
  }

  function fillMeasurements(outcome) {
    const samples = Array.isArray(outcome?.measurements) ? outcome.measurements : [];
    for (const row of document.querySelectorAll("[data-measure-row]")) {
      const sample = samples[Number(row.dataset.measureRow) - 1];
      for (const input of row.querySelectorAll("[data-measure]")) input.value = sample ? String(sample[input.dataset.measure]) : "";
    }
    $("outcome-tolerance").value = Number.isFinite(outcome?.tolerance_mm) ? String(outcome.tolerance_mm) : "";
    if (samples.length && $("outcome-measure")) $("outcome-measure").open = true;
    renderMeasurementReview(outcome?.measurement_review);
  }

  function renderMeasurementReview(review) {
    const area = $("outcome-measure-review");
    if (!review || !Array.isArray(review.rows)) { area.hidden = true; area.replaceChildren(); return; }
    const labels = { within: ["허용 오차 안", "success"], outside: ["허용 오차 밖", "warning"], not_judged: ["허용 오차 미지정", "neutral"] };
    const [label, tone] = labels[review.status] || ["판정 없음", "neutral"];
    const head = node("div", "measure-head");
    const badge = node("span", `badge badge-${tone}`, label);
    head.append(node("h3", "", `실측 ${review.samples}개 · CAD 치수와 비교`), badge);
    const table = node("table", "measure-table");
    const header = node("tr", "");
    for (const text of ["", "CAD", "평균 차이", "최대 차이", "샘플 간 편차"]) header.append(node("th", "", text));
    table.append(header);
    const sign = (value) => `${value > 0 ? "+" : ""}${numberFormat.format(value)}`;
    for (const [axis, name] of [["x", "가로 X"], ["y", "세로 Y"], ["z", "높이 Z"]]) {
      const data = review.axes?.[axis];
      if (!data) continue;
      const row = node("tr", "");
      row.append(node("th", "", name), node("td", "", `${numberFormat.format(data.expected)} mm`), node("td", "", `${sign(data.mean_deviation)} mm`),
        node("td", "", `${numberFormat.format(data.max_abs_deviation)} mm`), node("td", "", `${numberFormat.format(data.spread)} mm`));
      table.append(row);
    }
    area.replaceChildren(head, table, ...(review.notes || []).map((note) => node("p", "field-help", note)), node("p", "field-help", review.scope || ""));
    area.hidden = false;
  }

  $("outcome-result").addEventListener("change", () => { $("outcome-reasons").hidden = $("outcome-result").value !== "failure"; });
  $("outcome-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!state.job) return;
    try {
      await withWorkflow($("save-outcome"), "기록 중", async () => {
        const jobId = state.job.id;
        const result = $("outcome-result").value;
        const measured = collectMeasurements();
        const job = await api(`/api/jobs/${encodeURIComponent(jobId)}/outcome`, { result, notes: $("outcome-notes").value, reasons: result === "failure" ? selectedOutcomeReasons() : [],
          measurements: measured.samples.length ? measured.samples : null, tolerance_mm: measured.tolerance });
        state.job = job;
        renderMeasurementReview(job.user_outcome?.measurement_review);
        loadRecovery(job);
        loadAttempts(job);
        showNotice("outcome-feedback", "직접 보고한 출력 결과를 기록했습니다. CAD 검증 상태와 별도로 보관합니다.", "success");
        renderJourney();
      });
    } catch (error) { showNotice("outcome-feedback", error.message, "error"); }
  });

  function profileName(profile) {
    const settings = profile && Object.hasOwn(profile, "settings") ? profile.settings : profile;
    return settings && typeof settings.name === "string" ? settings.name : "";
  }

  function sameJson(first, second) {
    if (first === second) return true;
    if (!first || !second || typeof first !== "object" || typeof second !== "object" || Array.isArray(first) !== Array.isArray(second)) return false;
    if (Array.isArray(first)) return first.length === second.length && first.every((value, index) => sameJson(value, second[index]));
    const keys = Object.keys(first);
    return keys.length === Object.keys(second).length && keys.every((key) => Object.hasOwn(second, key) && sameJson(first[key], second[key]));
  }

  function profileDocument(entry, profile = entry.profile) {
    return { filename: entry.filename, profile, ...(entry.origin ? { origin: { ...entry.origin } } : {}) };
  }

  function profileSetupFields() {
    return { printer_model: "setup-printer-model", printer_preset: "setup-printer-preset", nozzle_diameter: "setup-nozzle", plate_type: "setup-plate", extruder: "setup-extruder", feed_mode: "setup-feed", material_id: "setup-material", material_identity_status: "setup-identity" };
  }

  function captureProfileSnapshot() {
    if (state.profileDocuments[state.profileTarget]) state.profileDocuments[state.profileTarget].draftText = $("profile-json").value;
    return {
      schema_version: 1,
      documents: state.profileDocuments.map((entry) => ({ ...profileDocument(entry), draft_text: entry.draftText })),
      target_index: state.profileTarget,
      profile_text: state.profileDocuments.length ? "" : $("profile-json").value,
      setup: Object.fromEntries(Object.entries(profileSetupFields()).map(([name, id]) => [name, $(id).value])),
    };
  }

  function workspaceSignature() {
    return JSON.stringify({ title: $("workspace-title").value.trim(), snapshot: captureProfileSnapshot() });
  }

  function workspaceDirty() {
    return Object.keys(state.guidedEdits).length > 0 || workspaceSignature() !== state.workspaceSavedSignature;
  }

  function markWorkspaceChanged() {
    state.workspaceEdits += 1;
    updateWorkspaceStatus();
  }

  function updateWorkspaceStatus() {
    const pending = Object.keys(state.guidedEdits).length > 0;
    const dirty = workspaceDirty();
    setBadge("workspace-status", pending ? "편집값 적용 필요" : dirty ? "저장하지 않은 변경" : state.workspaceId ? "저장됨" : "새 작업", dirty ? "warning" : "neutral");
    $("workspace-detail").textContent = state.workspaceId
      ? `현재 작업 · ${state.workspaceId.slice(0, 8)} · 저장 버전 ${state.workspaceRevision}${dirty ? " · 현재 변경 내용은 아직 저장되지 않았습니다." : " · 원본과 편집본을 함께 보관했습니다."}`
      : "이름을 정해 저장하면 새로고침 후에도 다시 열 수 있습니다. 저장은 이 PC의 앱 데이터에만 적용됩니다.";
    for (const id of ["workspace-save", "workspace-save-copy"]) $(id).disabled = state.workspaceBusy || !state.token;
    $("workspace-open").disabled = state.workspaceBusy || !$("workspace-list").value;
    $("workspace-delete").disabled = state.workspaceBusy || !state.workspaceId;
    $("workspace-new").disabled = state.workspaceBusy;
    $("workspace-refresh").disabled = state.workspaceBusy;
    $("workspace-list").disabled = state.workspaceBusy;
    $("profile-guided-actions").hidden = !pending;
    for (const id of ["profile-json", "profile-target", "profile-file", "profile-archive", "profile-adopt", "profile-clear", "profile-remove", "profile-restore", ...Object.values(profileSetupFields())]) {
      if (!$("review-profile").dataset.busy) $(id).disabled = pending;
    }
    document.querySelectorAll(".guided-remove").forEach((button) => { button.disabled = pending || Boolean($("review-profile").dataset.busy); });
  }

  async function loadWorkspaces() {
    const request = ++state.workspaceListRequest;
    try {
      const result = await api("/api/profile-workspaces", undefined, undefined, { current: () => request === state.workspaceListRequest });
      if (request !== state.workspaceListRequest) return;
      state.workspaces = result.workspaces || [];
      const select = $("workspace-list");
      const previous = select.value || state.workspaceId;
      const placeholder = node("option", "", state.workspaces.length ? "저장된 작업을 선택하세요" : "아직 저장된 작업이 없습니다");
      placeholder.value = "";
      select.replaceChildren(placeholder, ...state.workspaces.map((record) => {
        const option = node("option", "", `${record.title} · ${record.document_count}개 파일 · ${dateTime(record.updated_at)}`);
        option.value = record.id;
        return option;
      }));
      select.value = state.workspaces.some((record) => record.id === previous) ? previous : "";
      updateWorkspaceStatus();
    } catch (error) {
      if (request === state.workspaceListRequest) showNotice("workspace-feedback", `저장된 작업 목록을 불러오지 못했습니다. ${error.message}`, "error");
    }
  }

  async function saveWorkspace(copy = false) {
    if (state.workspaceBusy) return;
    const epoch = state.workspaceEpoch;
    try {
      applyGuidedEdits();
      const title = $("workspace-title").value.trim();
      if (!title) throw new Error("저장할 작업 이름을 입력해 주세요.");
      const snapshot = captureProfileSnapshot();
      const payload = { title, snapshot };
      const signature = JSON.stringify(payload);
      if (new TextEncoder().encode(signature).byteLength > 8 * 1024 * 1024) throw new Error("저장할 원본과 편집본의 합계는 8 MiB 이하여야 합니다. 현재 내용은 입력창에 유지했습니다.");
      const id = copy ? null : state.workspaceId;
      if (id) payload.expected_revision = state.workspaceRevision;
      state.workspaceBusy = true;
      updateWorkspaceStatus();
      hideNotice("workspace-feedback");
      const record = await api(id ? `/api/profile-workspaces/${encodeURIComponent(id)}` : "/api/profile-workspaces", payload, id ? "PUT" : "POST", { current: () => epoch === state.workspaceEpoch });
      if (epoch !== state.workspaceEpoch) return;
      state.workspaceId = record.id;
      state.workspaceRevision = record.revision;
      state.workspaceSavedSignature = signature;
      $("workspace-list").value = record.id;
      await loadWorkspaces();
      if (epoch === state.workspaceEpoch) {
        const changed = workspaceDirty();
        showNotice("workspace-feedback", changed ? "요청한 내용을 저장했습니다. 저장 중에 편집한 내용이 남아 있으니 한 번 더 저장해 주세요." : "원본, 편집본과 사용 조건을 이 PC에 저장했습니다.", changed ? "info" : "success");
      }
    } catch (error) {
      if (epoch === state.workspaceEpoch) showNotice("workspace-feedback", error.status === 409 && error.code !== "workspace_integrity" ? "다른 탭에서 이 작업을 변경했습니다. 현재 편집은 유지했습니다. 다른 이름으로 저장하거나 저장된 작업을 다시 열어 최신 내용을 확인하세요." : error.message, "error");
    } finally {
      state.workspaceBusy = false;
      updateWorkspaceStatus();
    }
  }

  function restoreWorkspace(record) {
    const snapshot = record?.snapshot;
    const fail = () => { throw new Error("저장된 재료 작업의 형식을 확인하지 못했습니다. 현재 입력은 유지했습니다."); };
    const object = value => value && typeof value === "object" && !Array.isArray(value);
    const exact = (value, keys) => object(value) && Object.keys(value).length === keys.length && keys.every(key => Object.hasOwn(value, key));
    const setupKeys = Object.keys(profileSetupFields());
    if (!exact(snapshot, ["schema_version", "documents", "target_index", "profile_text", "setup"]) || snapshot.schema_version !== 1 || !Array.isArray(snapshot.documents) || snapshot.documents.length > 64 || !Number.isInteger(snapshot.target_index) || snapshot.target_index < 0 || snapshot.target_index >= Math.max(1, snapshot.documents.length) || typeof snapshot.profile_text !== "string" || (snapshot.documents.length && snapshot.profile_text !== "") || !exact(snapshot.setup, setupKeys) || setupKeys.some(key => typeof snapshot.setup[key] !== "string" || Array.from(snapshot.setup[key]).length > 512) || !["unknown", "ambiguous", "exact"].includes(snapshot.setup.material_identity_status)) fail();
    if (!record || typeof record.title !== "string" || Array.from(record.title.trim()).length > 120 || (record.id !== null && (!/^[a-f0-9]{32}$/.test(record.id) || !record.title.trim() || !Number.isSafeInteger(record.revision) || record.revision < 1 || record.revision >= Number.MAX_SAFE_INTEGER))) fail();
    for (const entry of snapshot.documents) {
      if (!object(entry) || !exact(entry, Object.hasOwn(entry, "origin") ? ["filename", "profile", "draft_text", "origin"] : ["filename", "profile", "draft_text"]) || typeof entry.filename !== "string" || !entry.filename.trim() || Array.from(entry.filename).length > 240 || !object(entry.profile) || typeof entry.draft_text !== "string") fail();
      if (Object.hasOwn(entry, "origin")) {
        const origin = entry.origin;
        if (!exact(origin, ["type", "archive_name", "archive_sha256", "member_path", "member_sha256"]) || origin.type !== "bambu_preset_archive" || typeof origin.archive_name !== "string" || !origin.archive_name.trim() || Array.from(origin.archive_name).length > 240 || typeof origin.member_path !== "string" || !origin.member_path.trim() || Array.from(origin.member_path).length > 240 || !/^[a-f0-9]{64}$/.test(origin.archive_sha256) || !/^[a-f0-9]{64}$/.test(origin.member_sha256)) fail();
      }
    }
    const pending = [[snapshot, 0]];
    while (pending.length) {
      const [value, depth] = pending.pop();
      if (depth > 64 || (typeof value === "number" && (!Number.isFinite(value) || (Number.isInteger(value) && !Number.isSafeInteger(value))))) fail();
      if (value && typeof value === "object") pending.push(...Object.values(value).map(child => [child, depth + 1]));
    }
    const copied = JSON.parse(JSON.stringify(snapshot));
    if (new TextEncoder().encode(JSON.stringify(copied)).byteLength > 8 * 1024 * 1024 || new TextEncoder().encode(JSON.stringify(copied.documents.map(entry => profileDocument(entry)))).byteLength > 2 * 1024 * 1024) fail();
    const documents = copied.documents.map(entry => ({ ...profileDocument(entry), draftText: entry.draft_text }));
    const text = documents.length ? documents[copied.target_index].draftText : copied.profile_text;
    const setup = setupKeys.map(name => [profileSetupFields()[name], copied.setup[name]]);
    // All restoration values are validated and allocated before the first mutation.
    state.workspaceEpoch += 1;
    state.workspaceEdits += 1;
    state.profileImport += 1;
    state.guidedEdits = {};
    state.profileDocuments = documents;
    state.profileTarget = snapshot.target_index;
    $("profile-json").value = text;
    for (const [id, value] of setup) $(id).value = value;
    $("workspace-title").value = record.title;
    state.workspaceId = record.id;
    state.workspaceRevision = record.revision;
    invalidateProfile();
    renderProfileLibrary();
    renderGuidedEditor();
    state.workspaceSavedSignature = workspaceSignature();
    updateWorkspaceStatus();
  }

  async function openWorkspace() {
    if (state.workspaceBusy) return;
    const id = $("workspace-list").value;
    if (!id) return;
    if (workspaceDirty() && !window.confirm("저장하지 않은 변경 내용이 있습니다. 현재 편집을 버리고 저장된 작업을 여시겠습니까?")) return;
    const epoch = state.workspaceEpoch, edits = state.workspaceEdits;
    state.workspaceBusy = true;
    updateWorkspaceStatus();
    try {
      const record = await api(`/api/profile-workspaces/${encodeURIComponent(id)}`, undefined, undefined, { current: () => epoch === state.workspaceEpoch && edits === state.workspaceEdits });
      if (epoch !== state.workspaceEpoch || edits !== state.workspaceEdits) {
        showNotice("workspace-feedback", "불러오는 동안 편집한 내용이 있어 현재 작업을 유지했습니다. 저장된 작업을 열려면 다시 눌러 주세요.");
        return;
      }
      restoreWorkspace(record);
      showNotice("workspace-feedback", "저장된 원본과 편집본을 열었습니다. 프로필 검토하기로 현재 조건을 다시 확인해 주세요.", "success");
    } catch (error) {
      if (epoch === state.workspaceEpoch) showNotice("workspace-feedback", error.message, "error");
    } finally { state.workspaceBusy = false; updateWorkspaceStatus(); }
  }

  function newWorkspace() {
    if (state.workspaceBusy) return;
    if (workspaceDirty() && !window.confirm("저장하지 않은 변경 내용이 있습니다. 현재 편집을 버리고 새 작업을 시작하시겠습니까?")) return;
    restoreWorkspace({ id: null, revision: null, title: "", snapshot: {
      schema_version: 1, documents: [], target_index: 0, profile_text: "",
      setup: Object.fromEntries(Object.keys(profileSetupFields()).map((name) => [name, name === "material_identity_status" ? "unknown" : ""])),
    } });
    $("workspace-list").value = "";
    hideNotice("workspace-feedback");
    updateWorkspaceStatus();
  }

  async function deleteWorkspace() {
    if (state.workspaceBusy || !state.workspaceId) return;
    if (!window.confirm("이 작업의 저장본을 삭제하시겠습니까? 편집 중인 내용은 입력창에 남으며, 삭제한 저장본은 다시 열 수 없습니다.")) return;
    const id = state.workspaceId, epoch = state.workspaceEpoch;
    state.workspaceBusy = true;
    updateWorkspaceStatus();
    try {
      await api(`/api/profile-workspaces/${encodeURIComponent(id)}`, { expected_revision: state.workspaceRevision }, "DELETE", { current: () => epoch === state.workspaceEpoch });
      if (epoch === state.workspaceEpoch && id === state.workspaceId) {
        state.workspaceId = null;
        state.workspaceRevision = null;
        state.workspaceSavedSignature = null;
        state.workspaceEpoch += 1;
        $("workspace-list").value = "";
        showNotice("workspace-feedback", "저장본을 삭제했습니다. 편집 중인 내용은 남아 있으며 새로 저장할 수 있습니다.");
      }
      await loadWorkspaces();
    } catch (error) {
      if (epoch === state.workspaceEpoch) showNotice("workspace-feedback", error.status === 409 ? "다른 탭에서 저장본을 변경해 삭제하지 않았습니다. 최신 작업을 다시 열어 확인해 주세요. 현재 편집은 유지했습니다." : error.message, "error");
    } finally { state.workspaceBusy = false; updateWorkspaceStatus(); }
  }

  function guidedFieldDefinitions() {
    const fields = [
      { field: "nozzle_temperature", unit: "°C", positive: true },
      { field: "nozzle_temperature_initial_layer", unit: "°C", positive: true },
      { field: "filament_flow_ratio", unit: "비율", positive: true },
      { field: "filament_max_volumetric_speed", unit: "mm³/s", positive: true },
    ];
    const plateFields = { "Textured PEI Plate": "textured_plate_temp", "Smooth PEI Plate": "hot_plate_temp", "High Temp Plate": "hot_plate_temp", "Smooth PEI Plate / High Temp Plate": "hot_plate_temp", "Engineering Plate": "eng_plate_temp", "Cool Plate": "cool_plate_temp", "Bambu Cool Plate SuperTack": "supertack_plate_temp" };
    const plate = plateFields[$("setup-plate").value.trim()];
    if (plate) fields.push({ field: plate, unit: "°C", positive: false }, { field: `${plate}_initial_layer`, unit: "°C", positive: false });
    return fields;
  }

  function numericSetting(value, text, positive) {
    const input = text.trim();
    if (!input || !/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/.test(input)) throw new Error("빈 값은 설정에 적용하지 않습니다. 숫자를 입력하거나 편집 취소를 눌러 주세요.");
    const number = Number(input);
    if (!Number.isFinite(number) || (Number.isInteger(number) && !Number.isSafeInteger(number)) || (positive ? number <= 0 : number < 0)) throw new Error(positive ? "유한한 양수를 입력해 주세요." : "유한한 0 이상의 숫자를 입력해 주세요.");
    if (value === undefined) return [input];
    const multiple = Array.isArray(value);
    if (multiple && value.length !== 1) throw new Error("여러 값의 배열은 압출기 대응을 확인한 뒤 JSON에서 편집해 주세요.");
    const original = multiple ? value[0] : value;
    if (typeof original !== "string" && typeof original !== "number") throw new Error("이 값의 형식은 간편 편집을 지원하지 않습니다. JSON에서 확인해 주세요.");
    const updated = typeof original === "number" ? number : input;
    return multiple ? [updated] : updated;
  }

  function profileSettings(profile) {
    const settings = Object.hasOwn(profile, "settings") ? profile.settings : profile;
    if (!settings || typeof settings !== "object" || Array.isArray(settings)) throw new Error("settings는 JSON 객체여야 합니다.");
    return settings;
  }

  function evidenceFieldDefinitions() {
    return [
      { group: "scope", field: "printer_model", label: "프린터 모델" },
      { group: "scope", field: "printer_preset", label: "프린터 프리셋" },
      { group: "scope", field: "nozzle_diameter", label: "노즐 지름 · mm", numeric: true },
      { group: "scope", field: "plate_type", label: "플레이트 종류", list: "plate-types" },
      { group: "scope", field: "extruder", label: "압출기 식별자" },
      { group: "scope", field: "feed_mode", label: "필라멘트 공급 방식" },
      { group: "scope", field: "material_id", label: "재료 제품 식별자" },
      { group: "source", field: "authority", label: "출처 구분", list: "profile-source-authorities", placeholder: "예: manufacturer · user · community" },
      { group: "source", field: "publisher", label: "발행처" },
      { group: "source", field: "url", label: "원문 URL", placeholder: "확인한 원문 주소 그대로" },
      { group: "source", field: "retrieved_at", label: "원문 확인 시각", placeholder: "확인한 날짜·시각 그대로" },
    ];
  }

  function stageGuidedInput(field, input) {
    const source = state.guidedSources[field];
    if (!source?.editable) return;
    source.invalid = Boolean(input.validity?.badInput);
    if (input.value === source.initial && !source.invalid) delete state.guidedEdits[field];
    else state.guidedEdits[field] = input.value;
    hideNotice("profile-guided-feedback");
    invalidateProfile();
    markWorkspaceChanged();
  }

  function renderEvidenceEditor(profile) {
    const details = $("profile-evidence");
    details.hidden = !profile;
    const definitions = evidenceFieldDefinitions();
    const counts = [];
    for (const [group, title] of [["scope", "이 프로필의 적용 범위"], ["source", "출처 기록"]]) {
      const area = $(`profile-evidence-${group}`);
      area.replaceChildren();
      if (!profile) continue;
      const heading = node("h4", "", title);
      heading.id = `evidence-${group}-heading`;
      area.append(heading);
      if (group === "source") area.append(node("p", "field-help", "입력한 출처 기록입니다. 발행처 인증이나 실제 출력 검증을 뜻하지 않습니다."));
      const value = Object.hasOwn(profile, "settings") && Object.hasOwn(profile, group) ? profile[group] : {};
      if (!value || typeof value !== "object" || Array.isArray(value)) {
        area.append(node("p", "field-help", "기존 근거가 JSON 객체 형식이 아닙니다. 이 내용은 그대로 보존하며, JSON 편집창에서 확인해 주세요."), node("pre", "evidence-original", JSON.stringify(value)));
        counts.push(`${group === "scope" ? "적용 범위" : "출처"} 형식 확인 필요`);
        continue;
      }
      const fields = definitions.filter((definition) => definition.group === group);
      counts.push(`${group === "scope" ? "적용 범위" : "출처"} ${fields.filter((definition) => Object.hasOwn(value, definition.field)).length}/${fields.length}`);
      const grid = node("div", "guided-fields");
      for (const definition of fields) {
        const field = definition.field, key = `${group}.${field}`;
        const own = Object.hasOwn(value, field), original = own ? value[field] : undefined;
        const scalar = Array.isArray(original) && original.length === 1 ? original[0] : original;
        let editable = !own || typeof original === "string";
        if (own && definition.numeric) {
          try { numericSetting(original, String(scalar), false); editable = true; }
          catch { editable = false; }
        }
        const row = node("div", "guided-field");
        row.dataset.evidence = key;
        const label = node("label", "", definition.label);
        const input = node("input");
        input.id = `evidence-${group}-${field}`;
        input.type = definition.numeric && editable ? "number" : "text";
        if (definition.numeric && editable) input.step = "any";
        if (definition.list) input.setAttribute("list", definition.list);
        if (definition.placeholder) input.placeholder = definition.placeholder;
        if (field === "url") input.inputMode = "url";
        input.value = editable && own ? String(scalar) : "";
        input.disabled = !editable;
        input.dataset.guided = key;
        const helpId = `evidence-help-${group}-${field}`;
        input.setAttribute("aria-describedby", helpId);
        label.htmlFor = input.id;
        label.append(input);
        const help = node("p", "field-help", !editable ? "이 값의 형식은 간편 편집을 지원하지 않습니다. JSON에서 확인해 주세요." : own ? "선택한 파일에 명시된 근거" : "근거 없음 · 확인한 내용만 입력하세요.");
        help.id = helpId;
        row.append(label, help);
        if (!editable) row.append(node("pre", "evidence-original", JSON.stringify(original)));
        state.guidedSources[key] = { kind: "evidence", group, field, numeric: Boolean(definition.numeric), value: original, editable, initial: input.value, label: definition.label };
        input.addEventListener("input", () => stageGuidedInput(key, input));
        grid.append(row);
      }
      area.append(grid);
    }
    $("profile-evidence-summary").textContent = `프로필의 적용 범위와 출처${counts.length ? ` · ${counts.join(" · ")}` : ""}`;
  }

  function renderGuidedEditor() {
    state.guidedSources = {};
    state.guidedEdits = {};
    const area = $("profile-guided-fields");
    area.replaceChildren();
    renderEvidenceEditor(null);
    $("profile-adopt").hidden = state.profileDocuments.length > 0;
    hideNotice("profile-guided-feedback");
    if (!state.profileDocuments.length) {
      $("profile-guided-help").textContent = "파일을 가져오거나 입력한 JSON을 파일 모음에 추가하면 주요 설정을 편집할 수 있습니다.";
      updateWorkspaceStatus();
      return;
    }
    let profile, settings;
    try { profile = parseObject($("profile-json").value, "선택한 프로필"); settings = profileSettings(profile); }
    catch (error) {
      $("profile-guided-help").textContent = `${error.message} 편집 중인 JSON은 그대로 저장할 수 있습니다.`;
      updateWorkspaceStatus();
      return;
    }
    const resolved = state.profileReport?.status === "resolved" ? state.profileReport : null;
    const definitions = guidedFieldDefinitions();
    $("profile-guided-help").textContent = `선택한 파일에만 값을 적용합니다. 상속값은 검토 후 표시하며, 부모 파일은 유지합니다.${definitions.length === 4 ? " 베드 온도는 사용 조건에서 플레이트를 선택하면 표시됩니다." : ""}`;
    for (const definition of definitions) {
      const { field, unit, positive } = definition;
      const own = Object.hasOwn(settings, field);
      const inherited = !own && resolved && Object.hasOwn(resolved.resolved_profile.settings, field);
      const value = own ? settings[field] : inherited ? resolved.resolved_profile.settings[field] : undefined;
      const pendingParent = !own && !resolved && Boolean(settings.inherits);
      const scalar = Array.isArray(value) && value.length === 1 ? value[0] : value;
      let editable = !pendingParent, description = own ? "선택한 파일에 명시" : inherited ? `상속값 · ${resolved.field_sources[field]?.filename || "부모 파일"}` : pendingParent ? "프로필 검토 후 상속값을 확인하세요." : "값 없음 · 입력하면 문자열 배열로 추가합니다.";
      if (value !== undefined) {
        try { numericSetting(value, String(scalar), false); }
        catch { editable = false; description = "여러 옵션 또는 숫자가 아닌 값입니다. JSON에서 확인해 주세요."; }
      }
      const row = node("div", "guided-field");
      row.dataset.field = field;
      const label = node("label", "", `${fieldNames[field] || field} · ${unit}`);
      const input = node("input");
      input.id = `guided-${field}`;
      input.type = "number";
      input.step = "any";
      input.value = editable && value !== undefined ? String(scalar) : "";
      input.disabled = !editable;
      input.dataset.guided = field;
      input.setAttribute("aria-describedby", `guided-help-${field}`);
      label.htmlFor = input.id;
      label.append(input);
      const help = node("p", "field-help", description);
      help.id = `guided-help-${field}`;
      state.guidedSources[field] = { value, positive, editable, initial: input.value };
      input.addEventListener("input", () => stageGuidedInput(field, input));
      row.append(label, help);
      if (own) {
        const remove = node("button", "text-button guided-remove", "이 파일의 값 제거");
        remove.type = "button";
        remove.setAttribute("aria-label", `${fieldNames[field] || field}의 이 파일 값 제거`);
        remove.addEventListener("click", () => removeGuidedOverride(field));
        row.append(remove);
      }
      area.append(row);
    }
    renderEvidenceEditor(profile);
    updateWorkspaceStatus();
  }

  function applyGuidedEdits() {
    const edits = Object.entries(state.guidedEdits);
    if (!edits.length) return;
    const entry = state.profileDocuments[state.profileTarget];
    if (!entry) throw new Error("편집할 파일을 먼저 선택해 주세요.");
    let profile = parseObject($("profile-json").value, entry.filename);
    const settings = profileSettings(profile);
    const replacements = edits.map(([field, text]) => {
      const source = state.guidedSources[field];
      if (!source?.editable) throw new Error("이 설정은 JSON에서 확인해 주세요.");
      try {
        if (source.invalid) throw new Error("완전한 숫자를 입력하거나 편집 취소를 눌러 주세요.");
        if (source.kind === "evidence") {
          const group = Object.hasOwn(profile, "settings") && Object.hasOwn(profile, source.group) ? profile[source.group] : {};
          if (!group || typeof group !== "object" || Array.isArray(group)) throw new Error("이 근거의 기존 형식은 JSON에서 확인해 주세요.");
          const present = Object.hasOwn(group, source.field), original = group[source.field];
          const remove = text === "";
          let value;
          if (!remove) {
            value = source.numeric ? numericSetting(present ? original : undefined, text, true) : text;
            if (source.numeric && !present) value = Number(value[0]);
          }
          return { kind: "evidence", group: source.group, field: source.field, remove, value, changed: remove ? present : !present || !sameJson(original, value) };
        }
        const value = numericSetting(Object.hasOwn(settings, field) ? settings[field] : source.value, text, source.positive);
        return { kind: "setting", field, value, changed: !Object.hasOwn(settings, field) || !sameJson(settings[field], value) };
      } catch (error) { throw new Error(`${source.label || fieldNames[field] || field}: ${error.message}`); }
    });
    const changes = replacements.filter((replacement) => replacement.changed);
    if (changes.some((replacement) => replacement.kind === "evidence") && !Object.hasOwn(profile, "settings")) profile = { settings: profile };
    for (const replacement of changes) {
      if (replacement.kind === "setting") profileSettings(profile)[replacement.field] = replacement.value;
      else {
        if (!Object.hasOwn(profile, replacement.group)) profile[replacement.group] = {};
        if (replacement.remove) delete profile[replacement.group][replacement.field];
        else profile[replacement.group][replacement.field] = replacement.value;
      }
    }
    if (changes.length) {
      entry.draftText = JSON.stringify(profile, null, 2);
      $("profile-json").value = entry.draftText;
    }
    state.guidedEdits = {};
    invalidateProfile();
    markWorkspaceChanged();
    renderProfileLibrary();
    renderGuidedEditor();
    showNotice("profile-guided-feedback", "선택한 파일의 편집본에 적용했습니다. 프로필을 다시 검토하고 작업을 저장해 주세요.", "success");
  }

  function removeGuidedOverride(field) {
    if (Object.keys(state.guidedEdits).length) return;
    try {
      const entry = state.profileDocuments[state.profileTarget];
      if (!entry) return;
      const profile = parseObject($("profile-json").value, entry.filename);
      delete profileSettings(profile)[field];
      entry.draftText = JSON.stringify(profile, null, 2);
      $("profile-json").value = entry.draftText;
      invalidateProfile();
      markWorkspaceChanged();
      renderGuidedEditor();
      showNotice("profile-guided-feedback", "선택한 파일의 명시값을 제거했습니다. 상속될 값이 있는지 다시 검토해 주세요.");
    } catch (error) { showNotice("profile-guided-feedback", error.message, "error"); }
  }

  function adoptProfileText() {
    if (state.profileDocuments.length) return;
    try {
      const profile = parseObject($("profile-json").value, "입력한 프로필");
      if (new TextEncoder().encode(JSON.stringify([{ filename: "pasted-filament.json", profile }])).byteLength > 2 * 1024 * 1024) throw new Error("보관할 원본 JSON 합계는 2 MiB 이하여야 합니다. 입력한 내용은 유지했습니다.");
      state.profileDocuments = [{ filename: "pasted-filament.json", profile, draftText: $("profile-json").value }];
      state.profileTarget = 0;
      invalidateProfile();
      markWorkspaceChanged();
      renderProfileLibrary();
      renderGuidedEditor();
      showNotice("profile-feedback", "지금 입력한 JSON을 비교 원본으로 보관했습니다. 출처나 실제 측정을 인증한 것은 아닙니다.");
    } catch (error) { showNotice("profile-feedback", error.message, "error"); }
  }

  function removeProfileDocument() {
    if (!state.profileDocuments[state.profileTarget]) return;
    if (!window.confirm("선택한 파일을 이 작업의 파일 모음에서 제거하시겠습니까? 다른 파일과 PC의 원본 파일은 유지됩니다.")) return;
    state.profileDocuments.splice(state.profileTarget, 1);
    state.profileTarget = Math.max(0, Math.min(state.profileTarget, state.profileDocuments.length - 1));
    $("profile-json").value = state.profileDocuments[state.profileTarget]?.draftText || "";
    state.profileImport += 1;
    invalidateProfile();
    markWorkspaceChanged();
    renderProfileLibrary();
    renderGuidedEditor();
  }

  function restoreProfileOriginal() {
    const entry = state.profileDocuments[state.profileTarget];
    if (!entry) return;
    if (entry.draftText !== JSON.stringify(entry.profile, null, 2) && !window.confirm("선택한 파일의 편집 내용을 버리고 가져온 원본으로 되돌리시겠습니까?")) return;
    entry.draftText = JSON.stringify(entry.profile, null, 2);
    $("profile-json").value = entry.draftText;
    invalidateProfile();
    markWorkspaceChanged();
    renderProfileLibrary();
    renderGuidedEditor();
  }

  function invalidateProfile() {
    state.profileRevision += 1;
    state.profileReport = null;
    if (state.profileDownloadUrl) URL.revokeObjectURL(state.profileDownloadUrl);
    state.profileDownloadUrl = null;
    $("profile-download").removeAttribute("href");
    ["profile-result", "profile-resolution", "profile-download"].forEach((id) => { $(id).hidden = true; });
    hideNotice("profile-feedback");
  }

  function renderProfileLibrary() {
    $("profile-library").hidden = state.profileDocuments.length === 0;
    const select = $("profile-target");
    select.replaceChildren(...state.profileDocuments.map((entry, index) => {
      let name = profileName(entry.profile);
      try { name = profileName(JSON.parse(entry.draftText)); } catch { /* Keep the last imported name while JSON is being edited. */ }
      const option = node("option", "", `${name || "이름 미확인"} · ${entry.filename}`);
      option.value = String(index);
      return option;
    }));
    select.value = String(state.profileTarget);
    $("profile-library-summary").textContent = `${state.profileDocuments.length}개 파일 · 선택한 JSON을 아래에서 편집할 수 있습니다. 원본은 보고서에 함께 보존합니다.`;
    renderProfileOrigin();
  }

  function renderProfileOrigin() {
    const origin = state.profileDocuments[state.profileTarget]?.origin;
    $("profile-origin").hidden = !origin;
    const fields = $("profile-origin-fields");
    fields.replaceChildren();
    if (!origin) return;
    for (const [label, value] of [["내보내기 파일", origin.archive_name], ["파일 안의 경로", origin.member_path], ["내보내기 파일 SHA-256", origin.archive_sha256], ["원본 JSON 파일 SHA-256", origin.member_sha256]]) {
      fields.append(node("dt", "", label), node("dd", "", value));
    }
  }

  function beginProfileImport() {
    markWorkspaceChanged();
    return { id: ++state.profileImport, revision: state.profileRevision, epoch: state.workspaceEpoch };
  }

  function currentProfileImport(request) {
    return request.id === state.profileImport && request.revision === state.profileRevision && request.epoch === state.workspaceEpoch;
  }

  function appendProfileDocuments(imported) {
    // Build a complete candidate without touching accepted inputs or reports.
    // An unfinished existing draft is valid workspace input, even though it
    // cannot yet be reviewed. Only incoming originals need to parse here.
    const documents = state.profileDocuments.map((entry, index) => index === state.profileTarget && entry.draftText !== $("profile-json").value ? { ...entry, draftText: $("profile-json").value } : entry);
    let adopted = false, duplicates = 0, added = 0;
    if (!documents.length && $("profile-json").value.trim()) {
      let profile;
      try { profile = parseObject($("profile-json").value, "입력 중인 JSON 초안"); }
      catch { throw new Error("입력 중인 JSON 초안이 아직 완성되지 않았습니다. 내용을 완성하거나 작업으로 저장한 뒤 새 작업에서 가져와 주세요. 현재 초안은 유지했습니다."); }
      documents.push({ filename: "pasted-filament.json", profile, draftText: $("profile-json").value });
      adopted = true;
    }
    for (const candidate of imported) {
      if (typeof candidate.filename !== "string" || !candidate.filename.trim() || candidate.filename.length > 240) throw new Error("파일 이름과 내부 경로는 1~240자로 지정해 주세요.");
      const draftText = candidate.draftText;
      const profile = parseObject(draftText, candidate.filename);
      if (!sameJson(profile, candidate.profile)) throw new Error(`${candidate.filename}: 가져온 원본과 JSON 내용이 일치하지 않습니다.`);
      if (documents.some((entry) => sameJson(entry.profile, profile))) { duplicates += 1; continue; }
      const name = profileName(profile);
      const conflict = name && documents.find((entry) => {
        if (profileName(entry.profile) === name) return true;
        try { return profileName(parseObject(entry.draftText, entry.filename)) === name; }
        catch { return false; }
      });
      if (conflict) throw new Error(`‘${name}’ 이름이 ${conflict.filename}의 원본 또는 편집본과 겹치지만 내용이 다릅니다. 추가하지 않았습니다. 사용할 파일을 확인하고 기존 파일을 제거하거나 서로 다른 이름으로 다시 가져오세요.`);
      documents.push({ ...profileDocument(candidate, profile), draftText });
      added += 1;
    }
    if (documents.length > 64) throw new Error("파일 모음은 최대 64개입니다. 필요한 파일만 남긴 뒤 다시 가져와 주세요.");
    const bytes = (value) => new TextEncoder().encode(JSON.stringify(value)).byteLength;
    if (bytes(documents.map((entry) => profileDocument(entry))) > 2 * 1024 * 1024) throw new Error("보관할 원본 JSON 합계는 2 MiB 이하여야 합니다. 필요한 파일만 남긴 뒤 다시 가져와 주세요.");
    // Count serialized draft strings and their filename/origin framing. This
    // conservative limit keeps exact unfinished text without reparsing it.
    const drafts = documents.map((entry) => ({ filename: entry.filename, draft_text: entry.draftText, ...(entry.origin ? { origin: entry.origin } : {}) }));
    if (bytes(drafts) > 2 * 1024 * 1024) throw new Error("편집 문자열과 파일 정보의 합계는 2 MiB 이하여야 합니다. 현재 편집 내용은 유지했습니다.");
    if (!added && !adopted) return { added, duplicates, adopted };
    const hadDocuments = state.profileDocuments.length > 0;
    state.profileDocuments = documents;
    if (!hadDocuments) state.profileTarget = 0;
    $("profile-json").value = documents[state.profileTarget].draftText;
    invalidateProfile();
    markWorkspaceChanged();
    renderProfileLibrary();
    renderGuidedEditor();
    return { added, duplicates, adopted };
  }

  function profileImportSummary(result) {
    return `${result.added ? `${result.added}개 파일을 추가했습니다.` : "새로 추가할 파일이 없습니다."}${result.adopted ? " 입력 중인 JSON은 첫 번째 파일로 함께 보관했습니다." : ""}${result.duplicates ? ` 원본 내용이 같은 ${result.duplicates}개 파일은 이미 있어 건너뛰었습니다. 기존 편집본과 가져오기 정보는 유지했습니다.` : ""}${result.added || result.adopted ? " 검토 대상을 확인하고 프로필 검토하기를 누르세요." : ""}`;
  }

  async function importProfileFiles(input) {
    const files = Array.from(input.files || []);
    if (!files.length) return;
    input.value = "";
    const request = beginProfileImport();
    showNotice("profile-feedback", "JSON 파일을 읽고 있습니다. 현재 파일 모음은 유지합니다.");
    try {
      if (files.length > 64) throw new Error("한 번에 가져올 JSON 파일은 최대 64개입니다.");
      if (files.reduce((sum, file) => sum + file.size, 0) > 2 * 1024 * 1024) throw new Error("가져올 JSON 파일의 합계는 2 MiB 이하여야 합니다.");
      const imported = await Promise.all(files.map(async (file) => {
        if (!file.name.trim() || file.name.length > 240) throw new Error("파일명은 1~240자로 지정해 주세요. 파일 이름을 줄인 뒤 다시 추가할 수 있습니다.");
        const draftText = await file.text();
        const profile = parseObject(draftText, file.name);
        return { filename: file.name, profile, draftText };
      }));
      if (!currentProfileImport(request)) return;
      showNotice("profile-feedback", profileImportSummary(appendProfileDocuments(imported)));
    } catch (error) {
      if (currentProfileImport(request)) showNotice("profile-feedback", `${error.message} 현재 파일 모음과 입력은 유지했습니다.`, "error");
    }
  }

  async function importProfileArchive(input) {
    const file = input.files?.[0];
    if (!file) return;
    input.value = "";
    const request = beginProfileImport();
    showNotice("profile-feedback", "Studio 내보내기 파일을 읽고 있습니다. 현재 파일 모음은 유지합니다.");
    try {
      if (file.size > 4 * 1024 * 1024) throw new Error("Studio 내보내기 파일은 4 MiB 이하여야 합니다.");
      const bytes = new Uint8Array(await file.arrayBuffer());
      if (!currentProfileImport(request)) return;
      const chunks = [];
      for (let offset = 0; offset < bytes.length; offset += 32768) chunks.push(String.fromCharCode(...bytes.subarray(offset, offset + 32768)));
      const result = await api("/api/profiles/import-archive", { filename: file.name, content_base64: btoa(chunks.join("")) }, undefined, { current: () => currentProfileImport(request) });
      if (!currentProfileImport(request)) return;
      const imported = result.documents.map((entry) => ({ ...profileDocument(entry), draftText: typeof entry.draft_text === "string" ? entry.draft_text : JSON.stringify(entry.profile, null, 2) }));
      const summary = appendProfileDocuments(imported);
      const ignored = result.ignored_members || [];
      const details = [...(result.warnings || []), ...ignored.map((entry) => `${entry.path} · ${entry.reason}`)];
      showNotice("profile-feedback", `${profileImportSummary(summary)}${ignored.length ? ` 재료 프로필 이외의 ${ignored.length}개 항목은 추가하지 않았습니다.` : ""}`, "info", details);
    } catch (error) {
      if (currentProfileImport(request)) showNotice("profile-feedback", `${error.message} 현재 파일 모음과 입력은 유지했습니다.`, "error");
    }
  }

  function selectProfileTarget() {
    if (state.profileDocuments[state.profileTarget]) state.profileDocuments[state.profileTarget].draftText = $("profile-json").value;
    const index = Number($("profile-target").value);
    if (!Number.isInteger(index) || !state.profileDocuments[index]) return;
    state.profileTarget = index;
    $("profile-json").value = state.profileDocuments[index].draftText;
    invalidateProfile();
    renderProfileLibrary();
    renderGuidedEditor();
    markWorkspaceChanged();
  }

  function clearProfileLibrary() {
    invalidateProfile();
    state.profileImport += 1;
    state.profileDocuments = [];
    state.profileTarget = 0;
    renderProfileLibrary();
    renderGuidedEditor();
    markWorkspaceChanged();
    showNotice("profile-feedback", "파일 모음을 비웠습니다. 선택했던 JSON은 입력창에 남아 있으며 단일 프로필로 검토할 수 있습니다.");
  }

  async function reviewProfile() {
    let revision = state.profileRevision;
    try {
      applyGuidedEdits();
      invalidateProfile();
      revision = state.profileRevision;
      await withBusy($("review-profile"), "프로필 검토 중", async () => {
        const profile = parseObject($("profile-json").value, "필라멘트 프로필");
        const setup = {};
        document.querySelectorAll(".setup-grid [name]").forEach((input) => {
          setup[input.name] = input.name === "nozzle_diameter" && input.value !== "" ? input.valueAsNumber : input.value.trim();
        });
        if (state.profileDocuments.length) {
          state.profileDocuments[state.profileTarget].draftText = $("profile-json").value;
          const documents = state.profileDocuments.map((entry) => profileDocument(entry, parseObject(entry.draftText, entry.filename)));
          const targetName = profileName(profile);
          if (!targetName.trim()) throw new Error("선택한 프로필의 name에 정확한 이름이 필요합니다. 이름 필드는 소문자 name으로 입력해 주세요.");
          const originals = state.profileDocuments.map((entry) => profileDocument(entry));
          const edited = documents.filter((entry, index) => !sameJson(entry.profile, originals[index].profile)).map((entry) => entry.filename);
          const result = await api("/api/profiles/resolve", { documents, target_name: targetName, setup, baseline: { documents: originals, target_name: profileName(state.profileDocuments[state.profileTarget].profile) } }, undefined, { current: () => revision === state.profileRevision });
          if (revision !== state.profileRevision) return;
          renderProfileResolution({ ...result, setup, imported_documents: result.imported_documents || originals, edited_filenames: edited });
          if (result.review) renderProfile(result.review);
        } else {
          const result = await api("/api/profiles/review", { profile, setup }, undefined, { current: () => revision === state.profileRevision });
          if (revision === state.profileRevision) renderProfile(result);
        }
      });
      if (revision === state.profileRevision) renderGuidedEditor();
    } catch (error) {
      if (revision === state.profileRevision) showNotice("profile-feedback", error.message, "error");
    } finally { updateWorkspaceStatus(); }
  }

  function renderProfileEvidenceChanges(edit) {
    const area = $("profile-evidence-changes");
    area.replaceChildren();
    const changes = edit?.evidence_status === "compared" ? edit.evidence_changes || [] : [];
    $("profile-evidence-review").hidden = !changes.length;
    $("profile-evidence-review-help").textContent = changes.length ? `선택한 파일의 근거 정보 ${changes.length}곳이 원본과 다릅니다. 입력한 기록의 변경이며, 발행처 인증이나 실제 출력 검증을 뜻하지 않습니다.` : "";
    if (!changes.length) return;
    const definitions = evidenceFieldDefinitions();
    const table = node("table", "profile-evidence-table");
    table.setAttribute("aria-label", "선택한 프로필 근거의 원본과 편집본 비교");
    const head = node("thead"), headings = node("tr");
    for (const label of ["근거 항목", "가져온 원본", "현재 편집본"]) {
      const heading = node("th", "", label);
      heading.scope = "col";
      headings.append(heading);
    }
    head.append(headings);
    const body = node("tbody");
    for (const change of changes) {
      const row = node("tr");
      row.dataset.evidencePath = change.path;
      const definition = definitions.find((item) => `${item.group}.${item.field}` === change.path);
      const heading = node("th", "", definition ? `${definition.group === "scope" ? "적용 범위" : "출처"} · ${definition.label}` : change.path);
      heading.scope = "row";
      if (definition) heading.append(node("small", "", change.path));
      row.append(heading, node("td", "evidence-value", change.before_present ? JSON.stringify(change.before) : "항목 없음"), node("td", "evidence-value", change.after_present ? JSON.stringify(change.after) : "항목 없음"));
      body.append(row);
    }
    table.append(head, body);
    area.append(table);
  }

  function renderProfileResolution(result) {
    state.profileReport = result;
    $("profile-resolution").hidden = false;
    const statuses = { resolved: ["명시된 설정 연결 확인", "success"], needs_input: ["상속 파일 필요", "warning"], blocked: ["해석 조건 확인 필요", "warning"] };
    const [label, tone] = statuses[result.status] || ["해석 결과 확인 필요", "neutral"];
    setBadge("profile-resolution-status", label, tone);
    $("profile-resolution-issues").replaceChildren(...(result.issues || []).map((issue) => node("li", "", issue.message || issue.code)));
    $("profile-chain").replaceChildren(...(result.chain || []).map((entry, index) => {
      const item = node("li");
      item.append(node("strong", "", `${index + 1}. ${entry.name}`), node("small", "", entry.filename));
      const hash = node("small", "", `JSON SHA-256 · ${(entry.sha256 || "").slice(0, 12)}…`);
      hash.title = entry.sha256 || "";
      item.append(hash);
      return item;
    }));
    $("profile-resolution-warnings").replaceChildren(...(result.warnings || []).map((warning) => node("p", "", friendly(warning))));
    const edit = result.edit_review;
    renderProfileEvidenceChanges(edit);
    hideNotice("profile-edit-review");
    if (edit?.status === "changed") showNotice("profile-edit-review", `가져온 원본과 달라진 설정 ${edit.changed_fields.length}개가 있습니다. 수정값은 사용자의 변경으로 구분합니다.${edit.validation_invalidated ? " 이전 검증 보고는 이 변경값에 적용하지 않습니다." : ""}`, "info", edit.changed_fields.map((field) => fieldNames[field] || field));
    else if (edit?.status === "baseline_unresolved") showNotice("profile-edit-review", "원본의 상속을 확인하지 못해 변경 전후의 유효값을 비교할 수 없습니다. 이전 검증 보고를 현재 값의 근거로 사용하지 않습니다.", "warning");
    const entries = Object.entries(result.field_sources || {});
    const area = $("profile-fields");
    area.replaceChildren();
    if (entries.length) {
      const table = node("table", "profile-fields-table");
      const head = node("thead");
      const headings = node("tr");
      ["설정", "명시된 값", "값의 출처"].forEach((title) => headings.append(node("th", "", title)));
      head.append(headings);
      const body = node("tbody");
      for (const [field, source] of entries) {
        const row = node("tr");
        row.dataset.field = field;
        const heading = node("th", "", fieldNames[field] || field);
        heading.scope = "row";
        if (fieldNames[field]) heading.append(node("small", "", field));
        const value = result.resolved_profile?.settings?.[field];
        const cell = node("td", "", JSON.stringify(value));
        const origin = node("td", "", source.preset_name);
        origin.append(node("small", "", source.filename), node("small", "", source.inherited ? "부모에서 상속" : "선택한 프로필에 명시"));
        if (source.edited === true) origin.append(node("small", "", "원본과 다른 사용자 수정값"));
        if (source.history?.length > 1) {
          const details = node("details");
          details.append(node("summary", "", `덮어쓰기 기록 ${source.history.length}건`));
          const list = node("ol");
          source.history.forEach((assignment) => list.append(node("li", "", `${assignment.preset_name} (${assignment.filename}) · ${JSON.stringify(assignment.value)}`)));
          details.append(list);
          origin.append(details);
        }
        row.append(heading, cell, origin);
        body.append(row);
      }
      table.append(head, body);
      area.append(table);
    }
    const serialized = JSON.stringify(result, null, 2);
    $("profile-resolution-report").textContent = serialized;
    if (state.profileDownloadUrl) URL.revokeObjectURL(state.profileDownloadUrl);
    state.profileDownloadUrl = URL.createObjectURL(new Blob([serialized], { type: "application/json" }));
    $("profile-download").href = state.profileDownloadUrl;
    $("profile-download").hidden = false;
  }

  $("profile-form").addEventListener("submit", (event) => { event.preventDefault(); reviewProfile(); });
  $("profile-form").addEventListener("input", (event) => {
    if (event.target.id === "profile-file" || event.target.id === "profile-archive" || event.target.id === "profile-target" || event.target.dataset.guided) return;
    if (event.target.id === "profile-json" && state.profileDocuments[state.profileTarget]) state.profileDocuments[state.profileTarget].draftText = $("profile-json").value;
    invalidateProfile();
    markWorkspaceChanged();
    renderGuidedEditor();
  });
  $("profile-target").addEventListener("change", selectProfileTarget);
  $("profile-clear").addEventListener("click", clearProfileLibrary);
  $("profile-adopt").addEventListener("click", adoptProfileText);
  $("profile-remove").addEventListener("click", removeProfileDocument);
  $("profile-restore").addEventListener("click", restoreProfileOriginal);
  $("profile-guided-apply").addEventListener("click", () => {
    try { applyGuidedEdits(); }
    catch (error) { showNotice("profile-guided-feedback", error.message, "error"); }
  });
  $("profile-guided-cancel").addEventListener("click", () => { renderGuidedEditor(); markWorkspaceChanged(); });
  $("workspace-title").addEventListener("input", markWorkspaceChanged);
  $("workspace-list").addEventListener("change", updateWorkspaceStatus);
  $("workspace-save").addEventListener("click", () => saveWorkspace(false));
  $("workspace-save-copy").addEventListener("click", () => saveWorkspace(true));
  $("workspace-open").addEventListener("click", openWorkspace);
  $("workspace-refresh").addEventListener("click", loadWorkspaces);
  $("workspace-new").addEventListener("click", newWorkspace);
  $("workspace-delete").addEventListener("click", deleteWorkspace);
  window.addEventListener("beforeunload", (event) => {
    if (hasPendingWork()) { event.preventDefault(); event.returnValue = ""; }
  });
  window.addEventListener("pagehide", () => { if (state.profileDownloadUrl) URL.revokeObjectURL(state.profileDownloadUrl); });

  function renderProfile(result) {
    $("profile-result").hidden = false;
    const decisions = { blocked: ["준비 중단", "error"], needs_input: ["정보 입력 필요", "warning"], needs_evidence: ["근거 확인 필요", "warning"], ready_to_prepare: ["프로필 준비 가능", "success"] };
    const [label, tone] = decisions[result.decision] || ["판정 확인 필요", "neutral"];
    setBadge("profile-decision", label, tone);
    const compatibilities = { supported: "입력 조건 일치", unsupported: "조건 불일치", unknown: "확인하지 못함" };
    const validations = { unverified: "검증 미확인", stale: "재확인 필요", reported_validated: "동일 조건의 검증 보고 있음" };
    $("profile-summary").replaceChildren(metric("호환 조건 검토", compatibilities[result.compatibility] || "확인하지 못함"), metric("입력된 출처 구분", result.source_authority === "unknown" ? "출처 미확인" : result.source_authority), metric("실물 검증 정보", validations[result.validation_status] || result.validation_status));
    const area = $("profile-reasons");
    area.replaceChildren();
    if (result.reasons?.length) {
      const list = node("ul", "reason-list");
      result.reasons.forEach((reason) => list.append(node("li", "", friendly(reason.message))));
      area.append(list);
    } else area.append(node("p", "muted compact", "제공한 정보에서 이 검사기의 준비 조건을 만족했습니다. 전체 슬라이서 구성과 실제 출력은 별도 검증이 필요합니다."));
    if (result.missing_fields?.length) area.append(node("p", "missing-label", `추가 확인 항목: ${result.missing_fields.map(friendly).join(" · ")}`));
    $("profile-warnings").replaceChildren(...(result.warnings || []).map((text) => node("p", "", friendly(text))));
    const table = node("table");
    const body = node("tbody");
    for (const [key, value] of Object.entries(result.effective_settings || {})) {
      const row = node("tr");
      const heading = node("th", "", fieldNames[key] || key);
      heading.scope = "row";
      const cell = node("td", "", typeof value === "object" ? JSON.stringify(value) : String(value));
      if (fieldNames[key]) cell.append(node("small", "", key));
      row.append(heading, cell);
      body.append(row);
    }
    table.append(body);
    $("effective-settings").replaceChildren(table);
    $("profile-report").textContent = JSON.stringify(result, null, 2);
  }

  const printerNozzleTypes = { stainless_steel: "스테인리스강", hardened_steel: "경화강", tungsten_carbide: "텅스텐 카바이드", brass: "황동" };
  const printerConnectionTones = { reporting: "success", certificate_changed: "error", access_rejected: "warning" };

  function printerTarget() {
    return {
      host: $("printer-host").value.trim(),
      serial: $("printer-serial").value.trim().toUpperCase(),
      access_code: $("printer-access-code").value,
    };
  }

  function printerPinKey(target) { return `${target.host}|${target.serial}`; }

  function updatePrinterControls() {
    const busy = Boolean($("printer-check").dataset.busy || $("printer-discover").dataset.busy);
    const target = printerTarget();
    $("printer-check").disabled = !state.token || busy || !target.host || !target.serial || !target.access_code;
    $("printer-discover").disabled = !state.token || busy;
    $("printer-unpin").hidden = !state.printerPins[printerPinKey(target)];
  }

  function selectPrinterDevice(device) {
    $("printer-host").value = device.host;
    $("printer-serial").value = device.serial;
    state.printerStatus = null;
    $("printer-result").hidden = true;
    hideNotice("printer-feedback");
    setBadge("printer-status-badge", "아직 확인 전");
    updatePrinterControls();
    $("printer-access-code").focus();
  }

  function renderPrinterDevices(result) {
    const area = $("printer-devices");
    const devices = Array.isArray(result?.devices) ? result.devices : [];
    area.replaceChildren();
    if (result?.state === "listen_unavailable") {
      showNotice("printer-discover-feedback", "이 PC에서 프린터 알림을 들을 수 없습니다. 다른 앱(예: Bambu Studio)이 같은 포트를 사용 중일 수 있습니다. IP와 시리얼을 직접 입력하세요.", "warning");
      return;
    }
    if (!devices.length) {
      showNotice("printer-discover-feedback", `${result?.seconds ?? 4}초 동안 응답한 프린터가 없습니다. 같은 네트워크인지 확인하거나 IP와 시리얼을 직접 입력하세요.`, "info");
      return;
    }
    showNotice("printer-discover-feedback", `${devices.length}대의 프린터 알림을 받았습니다. 알림 내용은 프린터가 스스로 보낸 정보이며 아직 접속을 확인하지 않았습니다.`, "info");
    for (const device of devices) {
      const item = node("div", "printer-device");
      const model = device.model_name ? `${device.model_name} (${device.model_code})` : device.model_code ? `알 수 없는 기종 코드 ${device.model_code}` : "기종 미보고";
      item.append(node("strong", "", device.name || device.serial), node("span", "field-help", `${model} · ${device.host} · ${device.serial}`));
      const details = [];
      if (device.connection_mode) details.push(`연결 방식 보고: ${device.connection_mode}`);
      if (device.firmware) details.push(`펌웨어 보고: ${device.firmware}`);
      if (device.location_matches_sender === false) details.push("알림의 주소와 보낸 주소가 다릅니다");
      if (details.length) item.append(node("span", "field-help", details.join(" · ")));
      const choose = node("button", "button button-secondary", "이 프린터 선택");
      choose.type = "button";
      choose.addEventListener("click", () => selectPrinterDevice(device));
      item.append(choose);
      area.append(item);
    }
  }

  function printerNumber(value, unit) {
    return typeof value === "number" && Number.isFinite(value) ? `${numberFormat.format(value)}${unit}` : "보고되지 않음";
  }

  function printerTemperature(current, target) {
    if (typeof current !== "number") return "보고되지 않음";
    return typeof target === "number" && target > 0 ? `${printerNumber(current, "°C")} / 목표 ${printerNumber(target, "°C")}` : printerNumber(current, "°C");
  }

  function renderPrinterStatus(result) {
    const connection = result?.connection || {};
    const area = $("printer-result");
    area.replaceChildren();
    area.classList.remove("is-stale");
    area.removeAttribute("aria-hidden");
    const reporting = connection.state === "reporting";
    setBadge("printer-status-badge", reporting ? (result.print?.state_label || "상태 보고됨") : "상태를 받지 못함", printerConnectionTones[connection.state] || "neutral");
    showNotice("printer-feedback", connection.detail || "확인 결과를 해석하지 못했습니다.", reporting ? "info" : printerConnectionTones[connection.state] || "warning");
    const certificate = result?.certificate;
    if (certificate?.sha256) {
      const label = !certificate.pinned ? "처음 확인한 인증서" : certificate.matches_pin ? "고정한 인증서와 일치" : "고정한 인증서와 다름 · 이번에 받은 인증서";
      area.append(node("p", "field-help", `${label} · SHA-256 ${certificate.sha256.slice(0, 16)}… · 발급 기관은 확인하지 않았습니다.`));
    }
    if (!reporting) { area.hidden = !certificate?.sha256; return; }
    const status = result.print || {};
    const progress = typeof status.progress_percent === "number" ? `${status.progress_percent}%` : "보고되지 않음";
    const layers = typeof status.layer === "number" && typeof status.total_layers === "number" ? `${status.layer} / ${status.total_layers}` : "보고되지 않음";
    if (typeof status.progress_percent === "number") {
      const bar = node("progress", "printer-progress");
      bar.max = 100;
      bar.value = status.progress_percent;
      bar.setAttribute("aria-label", `프린터 보고 진행률 ${status.progress_percent}%`);
      area.append(bar);
    }
    const grid = node("div", "metric-grid printer-metrics");
    grid.append(
      metric("프린터 보고 상태", status.state_label || "보고되지 않음"),
      metric("진행률", progress),
      metric("남은 시간 보고", typeof status.remaining_minutes === "number" ? `${status.remaining_minutes}분` : "보고되지 않음"),
      metric("레이어", layers),
      metric("노즐", printerTemperature(status.temperatures_c?.nozzle, status.temperatures_c?.nozzle_target)),
      metric("베드", printerTemperature(status.temperatures_c?.bed, status.temperatures_c?.bed_target)),
    );
    area.append(grid);
    const identity = result.identity || {};
    const facts = [`시리얼 ${result.target?.serial} 주제로 보고 수신`];
    if (identity.product_name) facts.push(`제품 보고: ${identity.product_name}`);
    if (identity.firmware) facts.push(`펌웨어 보고: ${identity.firmware}`);
    if (status.nozzle?.diameter_mm) facts.push(`노즐 보고: ${status.nozzle.diameter_mm} mm${status.nozzle.type ? ` · ${printerNozzleTypes[status.nozzle.type] || status.nozzle.type}` : ""}`);
    if (status.job_name) facts.push(`작업: ${status.job_name}`);
    area.append(node("p", "field-help", facts.join(" · ")));
    if (status.error_code || (status.hms || []).length) {
      const codes = (status.hms || []).map((entry) => `HMS ${entry.hms_code}`);
      if (status.error_code) codes.unshift(`오류 코드 ${status.error_code_hex}`);
      area.append(node("p", "notice notice-warning", `프린터가 보고한 알림: ${codes.join(", ")}. 코드의 의미는 프린터 화면이나 제조사 안내에서 확인하세요.`));
    }
    const slots = (status.material_slots || []).filter((slot) => !slot.empty);
    if (slots.length) {
      const list = node("ul", "printer-slots");
      for (const slot of slots) {
        const where = slot.unit === "external" ? "외부 스풀" : `AMS ${Number(slot.unit) + 1} · 슬롯 ${Number(slot.slot) + 1}`;
        const item = node("li", "");
        if (slot.color) {
          const swatch = node("span", "printer-swatch");
          // CSSOM assignment is permitted by the page CSP; the value is a validated hex colour.
          swatch.style.backgroundColor = `#${slot.color.slice(0, 6)}`;
          swatch.setAttribute("aria-hidden", "true");
          item.append(swatch);
        }
        item.append(node("span", "", `${where}: ${[slot.product || slot.material || "재료 미보고", slot.filament_id, slot.color ? `#${slot.color}` : null].filter(Boolean).join(" · ")}`));
        list.append(item);
      }
      area.append(node("p", "field-help", "프린터에 등록된 재료 정보(사용자가 설정한 값일 수 있음):"), list);
    }
    area.append(node("p", "field-help", `확인 시각 ${dateTime(result.observed_at)} · ${result.scope || ""}`));
    area.hidden = false;
  }

  async function discoverPrinters() {
    try {
      await withBusy($("printer-discover"), "찾는 중", async () => {
        updatePrinterControls();
        showNotice("printer-discover-feedback", "4초 동안 프린터 알림을 기다리고 있습니다.", "info");
        renderPrinterDevices(await api("/api/printers/discover", { seconds: 4 }));
      });
    } catch (error) { showNotice("printer-discover-feedback", error.message, "error"); }
    finally { updatePrinterControls(); }
  }

  async function checkPrinterStatus() {
    const target = printerTarget();
    if (!target.host || !target.serial || !target.access_code) return;
    const key = printerPinKey(target);
    const body = { ...target };
    if (state.printerPins[key]) body.pinned_certificate_sha256 = state.printerPins[key];
    const request = ++state.printerRequest;
    try {
      await withBusy($("printer-check"), "상태 읽는 중", async () => {
        updatePrinterControls();
        const result = await api("/api/printers/status", body);
        if (request !== state.printerRequest || printerPinKey(printerTarget()) !== key) return;
        // Pin the first certificate that produced a real report for this page session.
        if (result.connection?.state === "reporting" && result.certificate?.sha256 && !state.printerPins[key]) state.printerPins[key] = result.certificate.sha256;
        state.printerStatus = result;
        renderPrinterStatus(result);
        rememberPrinter({ host: body.host, serial: body.serial }, result);
        if (typeof updatePrintabilityControls === "function") updatePrintabilityControls();
      });
    } catch (error) {
      if (request === state.printerRequest) showNotice("printer-feedback", error.message, error.code === "printer_busy" ? "warning" : "error");
    } finally { updatePrinterControls(); }
  }

  function printerInputChanged() {
    state.printerRequest += 1;
    if (state.printerStatus) {
      state.printerStatus = null;
      $("printer-result").classList.add("is-stale");
      $("printer-result").setAttribute("aria-hidden", "true");
      showNotice("printer-feedback", "입력이 바뀌었습니다. 흐리게 표시한 아래 값은 이전 대상의 확인 결과이며 현재 입력의 상태가 아닙니다. 다시 읽어 주세요.", "warning");
      setBadge("printer-status-badge", "입력이 바뀌어 다시 확인 필요");
    }
    updatePrinterControls();
  }

  function clearPrinterPin() {
    const target = printerTarget();
    delete state.printerPins[printerPinKey(target)];
    storeSavedPrinters(loadSavedPrinters().map((item) => item.host === target.host && item.serial === target.serial ? { ...item, pin: null } : item));
    showNotice("printer-feedback", "이 프린터의 고정 인증서를 해제했습니다. 다음 확인에서 받은 인증서가 다시 고정됩니다. 프린터를 교체했거나 초기화한 경우에만 해제하세요.", "warning");
    updatePrinterControls();
  }

  // ---------------------------------------------------------------------------
  // Remembered printers: a per-browser convenience (host, serial, certificate pin).
  // Access codes are never written here. Storage may be unavailable; everything still works.

  const PRINTER_STORE_KEY = "ppa.printers.v1";

  function loadSavedPrinters() {
    try {
      const raw = JSON.parse(window.localStorage.getItem(PRINTER_STORE_KEY) || "[]");
      if (!Array.isArray(raw)) return [];
      return raw.filter((item) => item && typeof item.host === "string" && typeof item.serial === "string"
        && /^[0-9A-Z]{8,32}$/.test(item.serial) && item.host.length <= 64
        && (item.pin === undefined || item.pin === null || /^[a-f0-9]{64}$/.test(item.pin))).slice(0, 8)
        .map((item) => ({ host: item.host, serial: item.serial, pin: item.pin || null, label: typeof item.label === "string" ? item.label.slice(0, 60) : "", saved_at: typeof item.saved_at === "string" ? item.saved_at : "" }));
    } catch { return []; }
  }

  function storeSavedPrinters(items) {
    // Only these fields are ever written; an access code cannot reach storage.
    const clean = items.slice(0, 8).map(({ host, serial, pin, label, saved_at }) => ({ host, serial, pin: pin || null, label: label || "", saved_at: saved_at || "" }));
    try { window.localStorage.setItem(PRINTER_STORE_KEY, JSON.stringify(clean)); return true; } catch { return false; }
  }

  function rememberPrinter(target, result) {
    if (!$("printer-remember").checked || result?.connection?.state !== "reporting" || !result.certificate?.sha256) return;
    const label = result.identity?.product_name || "";
    const items = loadSavedPrinters().filter((item) => !(item.host === target.host && item.serial === target.serial));
    items.unshift({ host: target.host, serial: target.serial, pin: result.certificate.sha256, label, saved_at: new Date().toISOString() });
    storeSavedPrinters(items);
    renderSavedPrinters();
  }

  function forgetPrinter(host, serial) {
    storeSavedPrinters(loadSavedPrinters().filter((item) => !(item.host === host && item.serial === serial)));
    delete state.printerPins[`${host}|${serial}`];
    renderSavedPrinters();
    updatePrinterControls();
  }

  function renderSavedPrinters() {
    const items = loadSavedPrinters();
    for (const item of items) if (item.pin && !state.printerPins[`${item.host}|${item.serial}`]) state.printerPins[`${item.host}|${item.serial}`] = item.pin;
    $("printer-saved").hidden = !items.length;
    $("printer-saved-list").replaceChildren(...items.map((item) => {
      const group = node("span", "saved-printer");
      // Name it by what the person entered; the printer-reported product name is only a hint.
      const choose = node("button", "purpose-button", `${item.host} · …${item.serial.slice(-4)}`);
      choose.type = "button";
      choose.title = `${item.serial}${item.label ? ` · 프린터 보고: ${item.label}` : ""}${item.pin ? " · 인증서 고정됨" : ""}`;
      choose.addEventListener("click", () => {
        $("printer-host").value = item.host;
        $("printer-serial").value = item.serial;
        $("printer-remember").checked = true;
        printerInputChanged();
        $("printer-access-code").focus();
      });
      const remove = node("button", "text-button", "삭제");
      remove.type = "button";
      remove.setAttribute("aria-label", `${item.host} 기억 삭제`);
      remove.addEventListener("click", () => forgetPrinter(item.host, item.serial));
      group.append(choose, remove);
      return group;
    }));
  }

  function restoreSavedPrinter() {
    const items = loadSavedPrinters();
    renderSavedPrinters();
    if (items.length && !$("printer-host").value && !$("printer-serial").value) {
      $("printer-host").value = items[0].host;
      $("printer-serial").value = items[0].serial;
      $("printer-remember").checked = true;
    }
  }

  // ---------------------------------------------------------------------------
  // Following a started print: re-read the printer's own report on a fixed interval.

  // Each read asks the printer for its full state; P1/A1 integrations warn against frequent full pushes,
  // so progress is re-read every five minutes (and on request), without the version query.
  const PRINT_FOLLOW_SECONDS = 300;
  const PRINT_FOLLOW_LIMIT_MS = 12 * 60 * 60 * 1000;

  function stopPrintFollow(message) {
    if (state.printFollow?.timer) clearTimeout(state.printFollow.timer);
    if (state.printFollow) state.printFollow.timer = null;
    if (state.printFollow) state.printFollow.active = false;
    if (message && $("print-follow-status")) $("print-follow-status").textContent = message;
    if (message) updatePrintControls(null);
    if ($("print-follow-stop")) $("print-follow-stop").hidden = true;
    if ($("print-follow-refresh")) $("print-follow-refresh").hidden = true;
  }

  function renderPrintFollow(printing, observedAt) {
    const area = $("print-follow");
    if (!area) return;
    const percent = Number.isFinite(printing?.progress_percent) ? printing.progress_percent : null;
    const bar = $("print-follow-bar");
    bar.style.width = `${percent ?? 0}%`;
    bar.parentElement.setAttribute("aria-valuenow", String(percent ?? 0));
    const parts = [printing?.state_label || "보고되지 않음"];
    if (percent !== null) parts.push(`${percent}%`);
    if (printing?.state === "RUNNING" && Number.isFinite(printing?.remaining_minutes)) parts.push(`남은 시간 약 ${printing.remaining_minutes}분`);
    if (Number.isFinite(printing?.layer) && Number.isFinite(printing?.total_layers)) parts.push(`레이어 ${printing.layer}/${printing.total_layers}`);
    if (printing?.error_code_hex) parts.push(`오류 ${printing.error_code_hex}`);
    $("print-follow-text").textContent = parts.join(" · ");
    updatePrintControls(printing?.state);
    $("print-follow-status").textContent = `${dateTime(observedAt)} 프린터 보고 · ${Math.round(PRINT_FOLLOW_SECONDS / 60)}분마다 다시 읽습니다.`;
  }

  function updatePrintControls(printerState) {
    // Offer only commands the printer's reported state allows (see printer_send.CONTROL_FROM).
    const allowed = { pause: ["RUNNING"], resume: ["PAUSE"], stop: ["PREPARE", "SLICING", "RUNNING", "PAUSE"] };
    const pending = state.printControlPending;
    for (const action of Object.keys(allowed)) {
      const button = $(`print-control-${action}`);
      if (!button) continue;
      button.hidden = !allowed[action].includes(printerState);
      // A stop never waits behind a pending pause or resume.
      button.disabled = Boolean(pending) && (action !== "stop" || pending === "stop");
    }
    if (!allowed.stop.includes(printerState) && $("print-stop-confirm")) $("print-stop-confirm").hidden = true;
  }

  function askPrintStop() {
    $("print-stop-confirm").hidden = false;
    $("print-stop-yes").focus();
  }

  async function sendPrintControl(action) {
    const follow = state.printFollow;
    const target = currentPrinterTarget();
    const pin = state.printerPins[`${target.host}|${target.serial}`];
    if (!follow || (state.printControlPending && (action !== "stop" || state.printControlPending === "stop"))) return;
    if (!pin || !target.access_code) {
      $("print-control-feedback").textContent = "프린터 액세스 코드와 확인한 인증서가 있어야 제어할 수 있습니다.";
      return;
    }
    state.printControlPending = action;
    $("print-stop-confirm").hidden = true;
    updatePrintControls(follow.lastState);
    const labels = { pause: "일시정지", resume: "재개", stop: "정지" };
    $("print-control-feedback").textContent = `${labels[action]} 명령을 보내는 중…`;
    try {
      const result = await api("/api/printers/print/control", { ...target, pinned_certificate_sha256: pin, action,
        stop_confirmed: action === "stop", job_id: state.job?.id || null });
      $("print-control-feedback").textContent = result.detail || "";
      if (result.printer) { follow.lastState = result.printer.state; renderPrintFollow(result.printer, result.finished_at || new Date().toISOString()); }
      if (action === "stop" && result.status === "applied") {
        stopPrintFollow("출력을 정지했습니다. 출력판을 비우고, 필요하면 결과를 기록해 주세요.");
        showNotice("print-send-feedback", "프린터가 정지 뒤 상태를 보고했습니다.", "warning");
      }
    } catch (error) {
      $("print-control-feedback").textContent = error.message;
    } finally {
      if (state.printControlPending === action) state.printControlPending = false;
      updatePrintControls(state.printFollow?.lastState);
    }
  }

  async function pollPrintFollow() {
    const follow = state.printFollow;
    if (!follow?.active) return;
    if (Date.now() - follow.startedAt > PRINT_FOLLOW_LIMIT_MS) { stopPrintFollow("12시간이 지나 자동 갱신을 멈췄습니다. 프린터 상태 화면에서 다시 읽을 수 있습니다."); return; }
    const target = currentPrinterTarget();
    if (target.host !== follow.host || target.serial !== follow.serial || !target.access_code) {
      stopPrintFollow("프린터 입력이 바뀌었거나 액세스 코드가 없어 자동 갱신을 멈췄습니다.");
      return;
    }
    const body = { ...target, include_version: false };
    if (follow.jobId) body.job_id = follow.jobId;
    if (state.printerPins[`${target.host}|${target.serial}`]) body.pinned_certificate_sha256 = state.printerPins[`${target.host}|${target.serial}`];
    if (follow.timer) { clearTimeout(follow.timer); follow.timer = null; }
    try {
      const result = await api("/api/printers/status", body);
      if (state.printFollow !== follow || !follow.active) return;
      if (result.connection?.state !== "reporting") {
        $("print-follow-status").textContent = `${result.connection?.detail || "프린터 보고를 받지 못했습니다."} 다음 주기에 다시 시도합니다.`;
      } else {
        follow.lastState = result.print?.state;
        renderPrintFollow(result.print, result.observed_at);
        if (result.job_link?.recorded && result.job_link.report) linkPrinterReport(follow.jobId, result.job_link.report);
        const state_ = result.print?.state;
        const sameJob = !follow.jobName || result.print?.job_name === follow.jobName;
        // A finished, failed or idle printer is no longer running this job, whatever name it reports.
        if (["FINISH", "FAILED", "IDLE"].includes(state_)) {
          const done = !sameJob ? `프린터가 “${result.print?.state_label || state_}” 상태이며 이 작업 이름을 보고하지 않았습니다. 프린터 화면을 확인하고 결과를 기록해 주세요.`
            : state_ === "FINISH" ? "프린터가 완료를 보고했습니다. 출력물을 확인하고 아래에 결과를 기록해 주세요." : state_ === "FAILED" ? "프린터가 실패를 보고했습니다. 프린터 화면을 확인하고 결과를 기록해 주세요." : "프린터가 대기 상태로 돌아갔습니다.";
          stopPrintFollow(done);
          showNotice("print-send-feedback", done, state_ === "FINISH" ? "success" : "warning");
          return;
        }
      }
    } catch (error) {
      if (state.printFollow !== follow) return;
      $("print-follow-status").textContent = `${error.message} 다음 주기에 다시 시도합니다.`;
    }
    if (follow.active) follow.timer = setTimeout(pollPrintFollow, PRINT_FOLLOW_SECONDS * 1000);
  }

  function linkPrinterReport(jobId, report) {
    // The server kept the printer's report on the job; show it without touching unsaved outcome drafts.
    if (!jobId || state.job?.id !== jobId) return;
    state.job = { ...state.job, printer_report: report };
    renderOutcomePrinterHint();
    loadRecovery(state.job);
    loadAttempts(state.job);
  }

  function startPrintFollow(result) {
    stopPrintFollow();
    const target = currentPrinterTarget();
    const area = node("div", "print-follow");
    area.id = "print-follow";
    const track = node("div", "print-follow-track");
    track.setAttribute("role", "progressbar");
    track.setAttribute("aria-valuemin", "0");
    track.setAttribute("aria-valuemax", "100");
    track.setAttribute("aria-label", "출력 진행률");
    const bar = node("div", "print-follow-bar");
    bar.id = "print-follow-bar";
    track.append(bar);
    const text = node("p", "print-follow-text", "진행 상황을 기다리는 중");
    text.id = "print-follow-text";
    const status = node("small", "field-help", "");
    status.id = "print-follow-status";
    const refresh = node("button", "text-button", "지금 다시 읽기");
    refresh.id = "print-follow-refresh";
    refresh.type = "button";
    refresh.addEventListener("click", () => { if (state.printFollow?.active) pollPrintFollow(); });
    const stop = node("button", "text-button", "자동 갱신 멈추기");
    stop.id = "print-follow-stop";
    stop.type = "button";
    stop.addEventListener("click", () => stopPrintFollow("자동 갱신을 멈췄습니다."));
    const controls = node("div", "button-row print-control-row");
    controls.id = "print-control";
    for (const [action, label, kind] of [["pause", "일시정지", "button-secondary"], ["resume", "재개", "button-secondary"], ["stop", "정지…", "button-danger"]]) {
      const button = node("button", `button ${kind}`, label);
      button.type = "button";
      button.id = `print-control-${action}`;
      button.hidden = true;
      button.addEventListener("click", () => action === "stop" ? askPrintStop() : sendPrintControl(action));
      controls.append(button);
    }
    const confirm = node("div", "print-stop-confirm");
    confirm.id = "print-stop-confirm";
    confirm.hidden = true;
    const confirmText = node("p", "", "출력을 정지하면 되돌릴 수 없습니다. 지금 정지할까요?");
    const confirmYes = node("button", "button button-danger", "네, 정지합니다");
    confirmYes.type = "button";
    confirmYes.id = "print-stop-yes";
    confirmYes.addEventListener("click", () => sendPrintControl("stop"));
    const confirmNo = node("button", "button button-secondary", "취소");
    confirmNo.type = "button";
    confirmNo.addEventListener("click", () => { $("print-stop-confirm").hidden = true; });
    confirm.append(confirmText, confirmYes, confirmNo);
    const controlFeedback = node("p", "field-help", "");
    controlFeedback.id = "print-control-feedback";
    controlFeedback.setAttribute("role", "status");
    area.append(node("h3", "", "출력 진행"), track, text, status, controls, confirm, controlFeedback, refresh, stop);
    $("print-send-result").append(area);
    state.printFollow = { active: true, timer: null, startedAt: Date.now(), host: target.host, serial: target.serial, jobName: result.subtask || result.printer?.job_name || null, jobId: state.job?.id || null };
    state.printFollow.lastState = result.printer?.state || null;
    if (result.printer) renderPrintFollow(result.printer, result.finished_at || new Date().toISOString());
    state.printFollow.timer = setTimeout(pollPrintFollow, PRINT_FOLLOW_SECONDS * 1000);
  }

  // ---------------------------------------------------------------------------
  // Sending the verified slice to a LAN printer. Review first (single-use token),
  // then an explicit confirmation; every send is recorded on the job.

  function printSendReady(job) {
    return Boolean(job?.artifacts?.sliced_three_mf) && job.latest_slice?.execution?.status === "sliced" && !["running", "interrupted"].includes(job.latest_slice?.phase);
  }

  function resetPrintSend(job) {
    stopPrintFollow();
    state.printSendIdentity = printSendReady(job) ? `${job.id}|${job.artifacts.sliced_three_mf}` : null;
    state.printSendRequest = (state.printSendRequest || 0) + 1;
    state.printSend = { jobId: job?.id || null, review: null, expiresAt: 0, pending: false, result: null };
    $("print-send-card").hidden = !printSendReady(job);
    $("print-send-slots").hidden = true;
    $("print-send-slots").replaceChildren();
    $("print-send-summary").hidden = true;
    $("print-send-result").hidden = true;
    $("print-send-confirm").checked = false;
    hideNotice("print-send-feedback");
    setBadge("print-send-badge", "확인 전");
    updatePrintSendControls();
  }

  function currentPrinterTarget() {
    // Shared with the printer status view; absent only in isolated controller checks.
    return typeof printerTarget === "function" ? printerTarget() : { host: "", serial: "", access_code: "" };
  }

  function syncPrintSend(job) {
    // Keep a review only while it is for the same job and the same verified slice file.
    const identity = printSendReady(job) ? `${job.id}|${job.artifacts.sliced_three_mf}` : null;
    if (identity !== (state.printSendIdentity ?? null)) {
      state.printSendIdentity = identity;
      resetPrintSend(job);
    }
  }

  function printSendTarget() {
    const target = currentPrinterTarget();
    const body = { ...target };
    const key = `${target.host}|${target.serial}`;
    if (state.printerPins?.[key]) body.pinned_certificate_sha256 = state.printerPins[key];
    return body;
  }

  function updatePrintSendControls() {
    const send = state.printSend || {};
    const target = currentPrinterTarget();
    const hasTarget = Boolean(target.host && target.serial && target.access_code);
    $("print-send-target").textContent = hasTarget ? `보낼 프린터: ${target.host} · ${target.serial}` : "프린터 상태 화면에서 IP 주소·시리얼·LAN 액세스 코드를 먼저 입력하세요. 액세스 코드는 저장하지 않습니다.";
    const live = Boolean(send.review?.review_token) && Date.now() < send.expiresAt && send.jobId === state.job?.id;
    $("print-send-review").disabled = !state.token || send.pending || !hasTarget || !printSendReady(state.job);
    $("print-send-confirm").disabled = !live || send.pending;
    if (!live) $("print-send-confirm").checked = false;
    $("print-send-start").disabled = !live || send.pending || !$("print-send-confirm").checked;
  }

  function printSendSlotChoice() {
    const selects = [...document.querySelectorAll("[data-print-slot]")];
    if (!selects.length) return null;
    return selects.map((select) => select.value === "external" ? "external" : Number(select.value));
  }

  function renderPrintSendSlots(review) {
    const area = $("print-send-slots");
    const filaments = review.summary?.filaments || [];
    const previous = printSendSlotChoice();
    const slots = (review.material_slots || []).filter((slot) => Number.isInteger(slot.unit) && Number.isInteger(slot.slot) && !slot.empty);
    area.replaceChildren(node("p", "field-help", "슬라이스한 필라멘트마다 프린터에 꽂힌 위치를 고르세요."));
    filaments.forEach((filament, index) => {
      const label = node("label", "print-send-slot");
      const swatch = node("span", "color-dot");
      if (/^#[0-9a-f]{6}$/i.test(filament.color || "")) swatch.style.setProperty("--swatch", filament.color);
      label.append(swatch, node("span", "", `필라멘트 ${filament.id}${filament.type ? ` · ${filament.type}` : ""}${Number.isFinite(filament.used_g) ? ` · ${numberFormat.format(filament.used_g)} g` : ""}`));
      const select = node("select");
      select.dataset.printSlot = String(index);
      select.append(node("option", "", "선택하세요"));
      select.firstChild.value = "";
      for (const slot of slots) {
        const option = node("option", "", `AMS ${slot.unit + 1} · ${slot.slot + 1}번 칸 · ${slot.material || "재료 미보고"}${slot.color ? ` · #${slot.color.slice(0, 6)}` : ""}`);
        option.value = String(slot.unit * 4 + slot.slot);
        select.append(option);
      }
      if (filaments.length === 1) {
        const external = node("option", "", "외부 스풀");
        external.value = "external";
        select.append(external);
      }
      if (previous && previous[index] !== undefined) select.value = String(previous[index]);
      label.append(select);
      area.append(label);
    });
    area.hidden = !filaments.length;
  }

  function renderPrintSendSummary(review) {
    const area = $("print-send-summary");
    area.replaceChildren();
    const summary = review.summary || {};
    const printer = review.printer || {};
    const rows = [
      ["모델", review.job_title || "현재 모델"],
      ["확인 당시 프린터", printer.state_label || "보고되지 않음"],
      ["기종", `슬라이스 ${review.printer_model?.sliced_name || review.printer_model?.sliced_code || "미기록"} · 프린터 보고 ${review.printer_model?.reported_product || "없음"}`],
      ["노즐", Number.isFinite(printer.nozzle?.diameter_mm) ? `${printer.nozzle.diameter_mm} mm (슬라이스 ${summary.nozzle_diameters || "미기록"} mm)` : `슬라이스 ${summary.nozzle_diameters || "미기록"} mm`],
      ["예상 시간", Number.isFinite(summary.prediction_seconds) ? `${numberFormat.format(summary.prediction_seconds / 60)}분` : "기록 없음"],
      ["예상 재료", Number.isFinite(summary.weight_g) ? `${numberFormat.format(summary.weight_g)} g` : "기록 없음"],
      ["파일", `${review.filename} · ${numberFormat.format(review.file_bytes / 1024)} KB`],
    ];
    if (review.mapping) rows.push(["필라멘트 위치", review.mapping.slots.map((slot) => `필라멘트 ${slot.filament} → ${slot.location}`).join(", ")]);
    const list = node("dl", "print-send-facts");
    for (const [name, value] of rows) list.append(node("dt", "", name), node("dd", "", value));
    area.append(list);
    if (review.problems?.length) {
      const problems = node("ul", "print-send-problems");
      for (const problem of review.problems) problems.append(node("li", "", problem));
      area.append(node("h3", "", "보낼 수 없는 이유"), problems);
    }
    if (review.warnings?.length) {
      const warnings = node("ul", "print-send-warnings");
      for (const warning of review.warnings) warnings.append(node("li", "", warning));
      area.append(node("h3", "", "확인할 점"), warnings);
    }
    area.append(node("p", "field-help", review.requirements || ""));
    area.hidden = false;
  }

  async function reviewPrintSend() {
    const job = state.job;
    if (!printSendReady(job)) return;
    const request = ++state.printSendRequest;
    state.printSend = { ...state.printSend, jobId: job.id, review: null, expiresAt: 0, pending: true, result: null };
    $("print-send-result").hidden = true;
    updatePrintSendControls();
    try {
      await withBusy($("print-send-review"), "프린터 확인 중", async () => {
        const review = await api("/api/printers/print/review", { ...printSendTarget(), job_id: job.id, slots: printSendSlotChoice() });
        if (request !== state.printSendRequest || state.job?.id !== job.id) return;
        state.printSend.review = review;
        state.printSend.expiresAt = review.review_token ? Date.now() + Math.max(0, (review.expires_in_seconds || 0) - 5) * 1000 : 0;
        renderPrintSendSlots(review);
        renderPrintSendSummary(review);
        if (review.ready) {
          setBadge("print-send-badge", "보낼 준비 됨", "success");
          showNotice("print-send-feedback", `확인을 마쳤습니다. ${Math.round((review.expires_in_seconds || 0) / 60)}분 안에 출력판을 확인하고 시작하세요.`, "success");
          if (state.printSend.expiresAt) setTimeout(() => updatePrintSendControls(), state.printSend.expiresAt - Date.now() + 50);
        } else {
          setBadge("print-send-badge", "보낼 수 없음", "warning");
          showNotice("print-send-feedback", review.problems?.[0] || "보낼 조건을 확인하지 못했습니다.", "warning");
        }
      });
    } catch (error) {
      if (request === state.printSendRequest) showNotice("print-send-feedback", error.message, error.code === "printer_busy" ? "warning" : "error");
    } finally {
      if (request === state.printSendRequest) state.printSend.pending = false;
      updatePrintSendControls();
    }
  }

  async function startPrintSend() {
    const send = state.printSend;
    if (!send?.review?.review_token || Date.now() >= send.expiresAt || !$("print-send-confirm").checked) return;
    const token = send.review.review_token;
    send.review = { ...send.review, review_token: null };  // a review starts at most one print
    send.pending = true;
    const request = ++state.printSendRequest;
    updatePrintSendControls();
    try {
      await withBusy($("print-send-start"), "올리고 시작하는 중", async () => {
        const result = await api("/api/printers/print/start", { review_token: token, access_code: currentPrinterTarget().access_code, bed_clear_confirmed: true });
        if (request !== state.printSendRequest) return;
        state.printSend.result = result;
        renderPrintSendResult(result);
        if (result.status === "started") startPrintFollow({ ...result, subtask: state.printSend.review?.subtask });
      });
    } catch (error) {
      if (request === state.printSendRequest) showNotice("print-send-feedback", error.message, "error");
    } finally {
      if (request === state.printSendRequest) state.printSend.pending = false;
      $("print-send-confirm").checked = false;
      updatePrintSendControls();
    }
  }

  function renderPrintSendResult(result) {
    const tones = { started: ["프린터가 출력 시작을 보고함", "success", "success"], unconfirmed: ["시작 보고를 받지 못함", "warning", "warning"],
      rejected: ["프린터가 거부함", "error", "error"], blocked: ["보내지 않음", "warning", "warning"], failed: ["보내기 실패", "error", "error"] };
    const [label, badge, notice] = tones[result.status] || ["결과 확인 필요", "warning", "warning"];
    setBadge("print-send-badge", label, badge);
    showNotice("print-send-feedback", result.detail || label, notice);
    const area = $("print-send-result");
    const stages = result.stages || {};
    const list = node("ol", "print-send-stages");
    for (const [key, text] of [["printer_ready", "프린터 대기 상태 확인"], ["uploaded", "파일 올리기"], ["command_sent", "시작 명령 보내기"], ["printer_reported_start", "프린터의 출력 시작 보고"]]) {
      const item = node("li", stages[key] ? "is-done" : "is-pending", `${stages[key] ? "✓" : "–"} ${text}`);
      list.append(item);
    }
    const reported = result.printer;
    const latest = reported ? node("p", "print-send-latest", `시작 직후 프린터가 보고한 상태: ${reported.state_label || "보고되지 않음"}${Number.isFinite(reported.progress_percent) ? ` · ${reported.progress_percent}%` : ""}${reported.error_code_hex ? ` · 오류 ${reported.error_code_hex}` : ""}`) : null;
    area.replaceChildren(list, ...(latest ? [latest] : []), node("p", "field-help", `${result.scope || ""} 진행 상황은 프린터 상태 화면에서 다시 읽을 수 있습니다.`));
    area.hidden = false;
  }

  $("print-send-printer").addEventListener("click", () => changeView("printers"));
  $("print-send-review").addEventListener("click", reviewPrintSend);
  $("print-send-start").addEventListener("click", startPrintSend);
  $("print-send-confirm").addEventListener("change", updatePrintSendControls);
  $("print-send-slots").addEventListener("change", () => {
    // A different slot choice needs a fresh review.
    state.printSendRequest += 1;
    if (state.printSend?.review?.review_token) { state.printSend.review = { ...state.printSend.review, review_token: null }; setBadge("print-send-badge", "다시 확인 필요"); }
    updatePrintSendControls();
  });
  for (const id of ["printer-host", "printer-serial", "printer-access-code"]) $(id).addEventListener("input", () => {
    if (state.printSend?.review?.review_token) { state.printSend.review = { ...state.printSend.review, review_token: null }; setBadge("print-send-badge", "다시 확인 필요"); }
    updatePrintSendControls();
  });

  // ---------------------------------------------------------------------------
  // New version check: only when asked; nothing is downloaded or installed.

  async function checkForUpdate() {
    const button = $("update-check");
    const result = $("update-result");
    try {
      await withBusy(button, "확인 중", async () => {
        const update = await api("/api/updates/check", {});
        result.replaceChildren(node("span", "", `${update.detail} 현재 ${update.current_version}${update.latest_version ? ` · 최신 ${update.latest_version}` : ""}${update.published_at ? ` (${dateTime(update.published_at)} 게시)` : ""}. `));
        if (update.status === "update_available") {
          for (const [label, url] of [["릴리스 보기", update.release_url], ["업데이트·검증 안내", update.update_guide]]) {
            const link = node("a", "", `${label} ↗`);
            try { const parsed = new URL(url); if (parsed.protocol !== "https:") continue; link.href = parsed.href; } catch { continue; }
            link.target = "_blank";
            link.rel = "noopener noreferrer";
            result.append(link, document.createTextNode(" "));
          }
        }
      });
    } catch (error) { result.textContent = error.message; }
  }

  $("update-check").addEventListener("click", checkForUpdate);
  document.addEventListener("keydown", radioGroupKey);
  $("printer-discover").addEventListener("click", discoverPrinters);
  restoreSavedPrinter();
  $("printer-form").addEventListener("submit", (event) => { event.preventDefault(); return checkPrinterStatus(); });
  $("printer-form").addEventListener("input", printerInputChanged);
  $("printer-unpin").addEventListener("click", clearPrinterPin);

  function renderOfferRows() {
    const container = $("offer-rows");
    for (let index = 1; index <= 3; index += 1) {
      const row = node("div", "offer-row");
      row.dataset.offer = index;
      row.append(node("span", "offer-index", `0${index}`));
      const definitions = [
        { key: "name", label: "상품명", placeholder: `비교할 상품 ${index}`, type: "text" },
        { key: "price", label: "상품 가격", placeholder: "확인한 가격", type: "number", min: "0" },
        { key: "grams", label: "중량 · g", placeholder: "순중량", type: "number", min: "0.01" },
        { key: "shipping", label: "배송비", placeholder: "미확인 시 비워두기", type: "number", min: "0" },
      ];
      definitions.forEach((definition) => {
        const label = node("label", "", definition.label);
        const input = node("input");
        input.type = definition.type;
        input.id = `offer-${index}-${definition.key}`;
        input.dataset.offerField = definition.key;
        input.placeholder = definition.placeholder;
        input.setAttribute("aria-label", `상품 ${index} ${definition.label}`);
        if (definition.type === "number") { input.min = definition.min; input.step = "any"; }
        else input.maxLength = 120;
        label.htmlFor = input.id;
        label.append(input);
        row.append(label);
      });
      container.append(row);
    }
  }

  function offersSignature() {
    return JSON.stringify([$("offer-currency").value, ...Array.from(document.querySelectorAll("[data-offer]")).map((row) => [row.dataset.offer, ...Array.from(row.querySelectorAll("[data-offer-field]")).map((input) => [input.dataset.offerField, input.value, Boolean(input.validity?.badInput), input.validity?.valid !== false])])]);
  }

  function offersHaveUnsavedChanges() {
    return $("offer-currency").value !== "KRW" || Array.from(document.querySelectorAll("[data-offer]")).some((row) => Array.from(row.querySelectorAll("[data-offer-field]")).some((input) => input.value !== "" || input.validity?.badInput || input.validity?.valid === false));
  }

  function offersInputChanged() {
    state.offersRevision += 1;
    $("offers-result").hidden = true;
    if (state.offersPending) showNotice("offers-feedback", "비교 중에 조건이 바뀌었습니다. 현재 입력은 유지했습니다. 새 조건으로 다시 비교해 주세요.", "info");
    else hideNotice("offers-feedback");
  }

  async function compareOffers() {
    if (state.offersPending) return;
    const revision = ++state.offersRevision, signature = offersSignature();
    const current = () => revision === state.offersRevision && signature === offersSignature();
    hideNotice("offers-feedback");
    $("offers-result").hidden = true;
    try {
      const offers = [];
      for (const row of document.querySelectorAll("[data-offer]")) {
        const inputs = Array.from(row.querySelectorAll("[data-offer-field]"));
        if (inputs.some((input) => input.validity?.badInput || input.validity?.valid === false)) throw new Error(`상품 ${row.dataset.offer}의 입력값을 완성하고 표시된 범위를 확인해 주세요.`);
        const values = Object.fromEntries(inputs.map((input) => [input.dataset.offerField, input.value.trim()]));
        if (Object.values(values).every((value) => value === "")) continue;
        if (!values.name || values.price === "" || values.grams === "") throw new Error(`상품 ${row.dataset.offer}의 이름, 가격, 중량을 모두 입력해 주세요.`);
        offers.push({ name: values.name, currency: $("offer-currency").value, price: Number(values.price), grams: Number(values.grams), shipping: values.shipping === "" ? null : Number(values.shipping) });
      }
      if (!offers.length) throw new Error("비교할 상품을 하나 이상 입력해 주세요.");
      state.offersPending = true;
      await withBusy($("compare-offers"), "단가 계산 중", async () => {
        const result = await api("/api/offers/compare", { offers }, undefined, { current });
        if (current()) { state.offersResult = result; renderOffers(result); }
      });
    } catch (error) { if (current()) showNotice("offers-feedback", error.message, "error"); }
    finally { state.offersPending = false; }
  }

  $("offers-form").addEventListener("submit", (event) => { event.preventDefault(); return compareOffers(); });
  $("offers-form").addEventListener("input", offersInputChanged);
  $("offer-currency").addEventListener("change", offersInputChanged);

  function money(value, currency) {
    if (!Number.isFinite(value)) return "미확인";
    return new Intl.NumberFormat("ko-KR", { style: "currency", currency, maximumFractionDigits: currency === "KRW" || currency === "JPY" ? 0 : 2 }).format(value);
  }

  // ---------------------------------------------------------------------------
  // Where to buy: a dated, curated directory. Links open the store; nothing is fetched from it.

  function setStoreGuide(guide) {
    const valid = guide && Array.isArray(guide.stores) && Array.isArray(guide.materials);
    state.storeGuide = valid ? guide : null;
    state.storeFilter = state.storeFilter || { material: "all", kind: "all", query: "" };
    $("store-guide").hidden = !valid;
    if (!valid) return;
    $("store-guide-checked").textContent = `판매처 안내 · ${guide.checked_on} 확인`;
    const chip = (group, value, label) => {
      const button = node("button", "purpose-button", label);
      button.type = "button";
      button.dataset.storeFilter = group;
      button.dataset.value = value;
      button.setAttribute("role", "radio");
      return button;
    };
    $("store-material-filters").replaceChildren(chip("material", "all", "모든 재료"), ...guide.materials.map((material) => chip("material", material, material)));
    const kinds = [["all", "모든 판매처"], ["bambu", "Bambu 정품"], ...Object.entries(guide.kinds || {})];
    $("store-kind-filters").replaceChildren(...kinds.map(([value, label]) => chip("kind", value, label)));
    $("store-guide-scope").textContent = `${guide.scope || ""}${guide.excluded?.length ? ` 운영 종료가 확인된 ${guide.excluded.map((item) => item.name).join(", ")}은(는) 목록에서 뺐습니다.` : ""}`;
    renderStoreGuide();
  }

  function storeMatches(store, filter) {
    if (filter.material !== "all" && !(store.materials || []).includes(filter.material)) return false;
    if (filter.kind === "bambu" && !store.bambu) return false;
    if (!["all", "bambu"].includes(filter.kind) && !(store.kinds || []).includes(filter.kind)) return false;
    const query = filter.query.trim().toLowerCase();
    if (!query) return true;
    const haystack = [store.name, store.sells, store.note, ...(store.materials || [])].join(" ").toLowerCase();
    const aliases = { 뱀부: "bambu", 뱀부랩: "bambu", 폴리메이커: "polymaker", 크리얼리티: "creality", 애니큐빅: "anycubic" };
    return haystack.includes(query) || Boolean(aliases[query] && haystack.includes(aliases[query]));
  }

  function storeLink(link) {
    // Only http(s) links from the curated list; a new tab without the opener.
    const anchor = node("a", "store-link", `${link.label} ↗`);
    try {
      const url = new URL(link.url);
      if (!["http:", "https:"].includes(url.protocol)) return null;
      anchor.href = url.href;
    } catch { return null; }
    anchor.target = "_blank";
    anchor.rel = "noopener noreferrer";
    return anchor;
  }

  function renderStoreGuide() {
    const guide = state.storeGuide;
    if (!guide) return;
    const filter = state.storeFilter;
    for (const button of document.querySelectorAll("[data-store-filter]")) {
      button.setAttribute("aria-checked", String(filter[button.dataset.storeFilter] === button.dataset.value));
    }
    for (const id of ["store-material-filters", "store-kind-filters"]) syncRadioGroup($(id));
    const matches = guide.stores.filter((store) => storeMatches(store, filter));
    $("store-guide-count").textContent = matches.length ? `${matches.length}곳 · 운영을 확인한 ${guide.stores.length}곳 중` : "조건에 맞는 판매처가 없습니다. 재료나 판매처 종류를 바꿔 보세요.";
    $("store-guide-list").replaceChildren(...matches.map((store) => {
      const item = node("li", "store-item");
      item.dataset.store = store.id;
      const head = node("div", "store-head");
      head.append(node("strong", "", store.name));
      const tags = node("div", "store-tags");
      if (store.bambu) tags.append(node("span", "store-tag store-tag-bambu", "Bambu 정품"));
      for (const kind of store.kinds || []) tags.append(node("span", "store-tag", guide.kinds?.[kind] || kind));
      head.append(tags);
      const links = node("div", "store-links");
      for (const link of store.urls || []) { const anchor = storeLink(link); if (anchor) links.append(anchor); }
      item.append(head, node("p", "store-sells", store.sells || ""));
      if (store.note) item.append(node("p", "store-note", store.note));
      item.append(node("p", "store-materials", (store.materials || []).join(" · ")), links,
        node("small", "store-evidence", `확인 ${guide.checked_on} · ${store.evidence || ""}`));
      return item;
    }));
    const unconfirmed = guide.unconfirmed || [];
    $("store-guide-unconfirmed").hidden = !unconfirmed.length;
    $("store-guide-unconfirmed-summary").textContent = `운영을 확인하지 못한 곳 ${unconfirmed.length}곳`;
    $("store-guide-unconfirmed-list").replaceChildren(...unconfirmed.map((store) => {
      const item = node("li", "", `${store.name} — ${store.reason || ""} `);
      for (const link of store.urls || []) { const anchor = storeLink(link); if (anchor) item.append(anchor); }
      return item;
    }));
  }

  $("store-guide").addEventListener("click", (event) => {
    const button = event.target.closest("[data-store-filter]");
    if (!button || !state.storeFilter) return;
    state.storeFilter[button.dataset.storeFilter] = button.dataset.value;
    renderStoreGuide();
  });
  $("store-search").addEventListener("input", (event) => {
    if (!state.storeFilter) return;
    state.storeFilter.query = event.target.value;
    renderStoreGuide();
  });

  function renderOffers(result) {
    $("offers-result").hidden = false;
    const area = $("offer-comparison");
    area.replaceChildren();
    for (const [currency, offers] of Object.entries(result.groups || {})) {
      const wrap = node("div", "table-wrap");
      const table = node("table", "offer-result-table");
      const head = node("thead");
      const headings = node("tr");
      const material = currentModelMaterial();
      ["상품", "중량", "상품 + 배송비", "배송비 포함 kg당 비용", ...(material ? [`현재 모델 재료비 상한 · ${numberFormat.format(material.grams)} g`] : [])].forEach((label) => { const th = node("th", "", label); th.scope = "col"; headings.append(th); });
      head.append(headings);
      table.append(head);
      const body = node("tbody");
      offers.forEach((offer, index) => {
        const row = node("tr");
        const product = node("td", "", offer.name);
        const unit = node("td", offer.price_per_kg !== null && index === 0 ? "offer-best" : "", offer.price_per_kg === null ? "배송비 미확인" : `${money(offer.price_per_kg, currency)} / kg`);
        if (offer.price_per_kg !== null && index === 0 && offers.filter((item) => item.price_per_kg !== null).length > 1) unit.append(node("small", "", "입력한 조건 중 최소 단가"));
        if (offer.price_per_kg === null) unit.append(node("small", "", `배송비 제외 ${money(offer.product_price_per_kg, currency)} / kg`));
        row.append(product, node("td", "", `${numberFormat.format(offer.grams)} g`), node("td", "", offer.delivered_total === null ? `${money(offer.price, currency)} + 미확인` : money(offer.delivered_total, currency)), unit);
        if (material) {
          const perKg = offer.price_per_kg ?? offer.product_price_per_kg;
          const cost = node("td", "offer-model-cost", `${money(perKg * material.grams / 1000, currency)}`);
          if (offer.price_per_kg === null) cost.append(node("small", "", "배송비 제외 금액"));
          row.append(cost);
        }
        body.append(row);
      });
      table.append(body);
      wrap.append(table);
      area.append(wrap);
    }
    $("offer-notice").textContent = result.notice || "사용자가 입력한 조건으로 계산했습니다. 실시간 가격은 확인하지 않았습니다.";
    const material = currentModelMaterial();
    const note = $("offer-model-note");
    note.hidden = !material;
    if (material) note.textContent = `재료비 상한은 지금 만든 “${material.title}”을 속 100% PLA로 채웠을 때의 무게(약 ${numberFormat.format(material.grams)} g) 기준입니다. 실제 사용량은 속채움·지지대 설정에 따라 보통 더 적으니 슬라이서 결과를 보세요.`;
  }

  function renderSetupPrinterFill() {
    // Offer values the printer reported, for empty fields only. They describe what the
    // printer says is installed, so the user is asked to confirm them.
    const area = $("setup-printer-fill");
    const status = state.printerStatus;
    if (status?.connection?.state !== "reporting") { area.hidden = true; return; }
    const product = status.identity?.product_name;
    const nozzle = status.print?.nozzle?.diameter_mm;
    const slots = (status.print?.material_slots || []).filter((slot) => !slot.empty && slot.filament_id);
    const actions = $("setup-printer-fill-actions");
    actions.replaceChildren();
    $("setup-printer-fill-status").textContent = "";
    const fill = (id, value) => {
      const input = $(id);
      if (input.value.trim() || value === null || value === undefined) return false;
      input.value = String(value);
      input.dispatchEvent(new Event("input", { bubbles: true }));
      return true;
    };
    if (product || nozzle) {
      const button = node("button", "button button-secondary", "프린터 모델·노즐 채우기");
      button.type = "button";
      button.addEventListener("click", () => {
        const filled = [fill("setup-printer-model", product) && "프린터 모델", fill("setup-nozzle", nozzle) && "노즐 지름"].filter(Boolean);
        $("setup-printer-fill-status").textContent = filled.length ? `프린터가 보고한 ${filled.join("·")}을 빈 칸에 채웠습니다. 실제 장착 상태와 같은지 확인하세요.` : "이미 입력한 값은 바꾸지 않았습니다.";
      });
      actions.append(button);
    }
    for (const slot of slots.slice(0, 5)) {
      const where = slot.unit === "external" ? "외부 스풀" : `AMS ${Number(slot.unit) + 1}·슬롯 ${Number(slot.slot) + 1}`;
      const button = node("button", "text-button", `${where}: ${slot.product || slot.material || "재료"} (${slot.filament_id}) 사용`);
      button.type = "button";
      button.addEventListener("click", () => {
        const done = fill("setup-material", slot.filament_id);
        $("setup-printer-fill-status").textContent = done ? `${where}에 등록된 재료 식별자 ${slot.filament_id}를 채웠습니다. 프린터에 사용자가 설정한 값이므로 실제 스풀과 맞는지 확인하세요.` : "재료 식별자 칸에 이미 값이 있어 바꾸지 않았습니다.";
      });
      actions.append(button);
    }
    $("setup-printer-fill-text").textContent = `프린터 ${status.target?.serial || ""} 상태(${dateTime(status.observed_at)})에서 읽은 값을 비어 있는 칸에만 채울 수 있습니다.`;
    area.hidden = !actions.children.length;
  }

  function renderOffersModelHint() {
    const material = currentModelMaterial();
    $("offers-model-hint").hidden = !material;
    if (material) $("offers-model-hint").textContent = `지금 만든 “${material.title}”은 속을 100% 채워도 PLA 약 ${numberFormat.format(material.grams)} g입니다. 상품을 넣고 비교하면 이 모델 하나의 재료비 상한도 함께 계산합니다.`;
  }

  function currentModelMaterial() {
    const item = state.job?.result?.printability?.items?.find((entry) => entry.id === "material");
    return item && Number.isFinite(item.grams) && item.grams > 0 ? { grams: item.grams, title: state.job.title || "현재 모델" } : null;
  }

  function dateTime(value) {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? "시간 정보 없음" : new Intl.DateTimeFormat("ko-KR", { dateStyle: "medium", timeStyle: "short" }).format(date);
  }

  function updateHistoryControls() {
    $("history-more").hidden = !state.historyCursor;
    $("history-more").disabled = state.historyPending || !state.historyCursor;
    $("history-more").textContent = state.historyPending ? "불러오는 중" : "이전 기록 더 보기";
    $("history-list").setAttribute("aria-busy", String(Boolean(state.historyPending)));
    $("history-summary").textContent = state.historyPending ? `${state.historyItems.length}개 기록을 유지하며 목록을 불러오고 있습니다.` : state.historyLoaded ? `${state.historyItems.length}개 기록을 표시합니다.${state.historyCursor ? " 이전 기록을 더 불러올 수 있습니다." : " 현재 목록의 마지막 기록입니다."}` : "작업 기록을 아직 불러오지 않았습니다.";
  }

  async function openHistoryJob(job, button) {
    if (state.workflowBusy) return;
    const request = ++state.modelTransitionRequest;
    const signature = replacementSignature();
    let full;
    try {
      await withWorkflow(button, "불러오는 중", async () => {
        full = await api(`/api/jobs/${encodeURIComponent(job.id)}`, undefined, undefined, { current: () => request === state.modelTransitionRequest && signature === replacementSignature() });
      });
      if (request !== state.modelTransitionRequest || signature !== replacementSignature()) {
        if (request === state.modelTransitionRequest) showNotice("history-feedback", "불러오는 동안 제작안이 바뀌어 현재 편집을 유지했습니다. 원하는 기록을 다시 열어 주세요.");
        return;
      }
      if (!full.result) {
        const reasons = (full.events || []).filter((entry) => ["generation_failed", "generation_interrupted"].includes(entry.type)).map((entry) => entry.message);
        const messages = { failed: "모델 생성에 실패한 기록입니다. 원인을 확인한 뒤 저장된 치수로 다시 준비할 수 있습니다.", interrupted: "서버가 끝나기 전에 생성이 완료되지 않은 기록입니다. 부분 파일을 출력 가능한 모델로 제공하지 않습니다.", unreadable: "이 작업 기록을 읽을 수 없습니다. 원본 파일은 보존했습니다. 저장 위치에서 백업과 기록을 확인해 주세요." };
        showNotice("history-feedback", messages[full.status] || "이 작업에는 아직 생성된 모델이 없습니다.", full.status === "generating" ? "info" : "warning", reasons);
        if (full.request && state.templates.some((template) => template.id === full.request.template) && ["failed", "interrupted"].includes(full.status)) {
          const retry = node("button", "button button-secondary", "저장된 치수로 다시 준비");
          retry.type = "button";
          retry.addEventListener("click", () => requestModelReplacement({ kind: "retry", job: full, title: full.title, button: retry }));
          $("history-feedback").append(retry);
        }
        return;
      }
      requestModelReplacement({ kind: "history", job: full, title: full.title, button });
    } catch (error) {
      if (request === state.modelTransitionRequest && signature === replacementSignature()) showNotice("history-feedback", error.message, "error");
    }
  }

  function historyMatches(job) {
    const outcome = job.user_outcome?.result;
    if (state.historyFilter === "success") return outcome === "success";
    if (state.historyFilter === "failure") return outcome === "failure";
    if (state.historyFilter === "unrecorded") return !outcome || outcome === "not_tested";
    return true;
  }

  function historyFacts(job) {
    // Short facts that distinguish records with the same title.
    const parameters = job.summary?.parameters || {};
    const facts = Object.entries(parameters).map(([key, value]) => {
      const definition = fields[key];
      const label = templateFieldLabels[job.template]?.[key] || definition?.label || key;
      return `${label} ${numberFormat.format(value)}${definition?.unit === "개" ? "개" : definition?.unit || " mm"}`;
    });
    const slice = { sliced: "슬라이스 완료", needs_review: "슬라이스 확인 필요", failed: "슬라이스 실패", blocked: "슬라이스 차단", prepared: "설정 포함 3MF 준비", planned: "실행 계획 검토", running: "슬라이스 기록 실행 중", interrupted: "슬라이스 중단" }[job.summary?.slice];
    if (slice) facts.push(slice);
    return facts;
  }

  function setHistoryFilter(filter) {
    state.historyFilter = filter;
    document.querySelectorAll("[data-history-filter]").forEach((button) => button.setAttribute("aria-pressed", String(button.dataset.historyFilter === filter)));
    renderHistory();
  }

  function renderHistory() {
    const container = $("history-list");
    container.replaceChildren();
    if (!state.historyItems.length) {
      if (!state.historyLoaded) return;
      const empty = node("div", "history-empty");
      const button = node("button", "button button-secondary", "첫 모델 만들기 →");
      button.type = "button";
      button.addEventListener("click", () => changeView("models"));
      empty.append(node("h3", "", "아직 만들어 둔 모델이 없어요"), node("p", "", "모델을 생성하면 실제 파일과 검증 상태가 이곳에 기록됩니다."), button);
      container.append(empty);
      return;
    }
    const visible = state.historyItems.filter(historyMatches);
    if (state.historyFilter !== "all") {
      const more = state.historyCursor ? " 이전 기록을 더 불러오면 함께 거릅니다." : "";
      container.append(node("p", "history-filter-note", `불러온 ${state.historyItems.length}개 중 ${visible.length}개가 조건에 맞습니다.${more}`));
    }
    if (!visible.length) {
      const empty = node("div", "history-empty");
      empty.append(node("h3", "", "조건에 맞는 기록이 없어요"), node("p", "", "출력한 뒤 모델을 열어 결과를 기록하면 여기에서 찾을 수 있습니다."));
      container.append(empty);
      return;
    }
    visible.forEach((job) => {
      const card = node("article", "history-item");
      card.dataset.jobId = job.id;
      const title = node("div");
      title.append(node("h3", "", job.title || "생성한 모델"), node("p", "", dateTime(job.created_at)));
      const facts = historyFacts(job);
      if (facts.length) title.append(node("p", "history-facts", facts.join(" · ")));
      const notes = typeof job.user_outcome?.notes === "string" ? job.user_outcome.notes.trim() : "";
      if (notes) title.append(node("p", "history-notes", `메모: ${notes.length > 80 ? `${notes.slice(0, 80)}…` : notes}`));
      if (job.model_edit) {
        const edit = node("div", "history-model-edit");
        edit.id = `history-model-edit-${job.id}`;
        title.append(edit);
        renderModelEditRecord(edit, job.model_edit);
      }
      if (job.diagnostic) title.append(node("p", "history-diagnostic", job.diagnostic));
      const statuses = node("div", "history-statuses");
      const warning = ["failed", "interrupted", "unreadable"].includes(job.status);
      const statusLabel = { geometry_validated: "CAD 검증 완료", failed: "모델 생성 실패", generating: "모델 생성 중", interrupted: "생성 중단 · 완료 결과 없음", unreadable: "기록 읽기 확인 필요" }[job.status] || friendly(job.status || "상태 미확인");
      statuses.append(node("span", `badge badge-${warning ? "warning" : job.status === "geometry_validated" ? "blue" : "neutral"}`, statusLabel));
      const outcome = job.user_outcome?.result;
      statuses.append(node("span", `badge badge-${outcome === "success" ? "success" : outcome === "failure" ? "warning" : "neutral"}`, outcome === "success" ? "출력 성공 · 사용자 보고" : outcome === "failure" ? "출력 실패 · 사용자 보고" : "실물 출력 미기록"));
      const review = job.summary?.printability;
      if (review) statuses.append(node("span", `badge badge-${review === "ok" ? "success" : review === "review" ? "warning" : "error"}`, review === "ok" ? "형상 점검 통과" : review === "review" ? "점검 확인할 점" : "점검 수정 권장"));
      const open = node("button", "button button-secondary", warning ? "기록 보기 ↗" : "열기 ↗");
      open.type = "button";
      open.disabled = state.workflowBusy;
      open.addEventListener("click", () => openHistoryJob(job, open));
      card.append(node("span", "history-icon", "CAD"), title, statuses, open);
      container.append(card);
    });
  }

  async function loadHistory(more = false) {
    if (more && (!state.historyCursor || state.historyPending)) return;
    const request = ++state.historyRequest;
    const cursor = more ? state.historyCursor : null;
    state.historyPending = true;
    hideNotice("history-feedback");
    updateHistoryControls();
    try {
      const result = await api(`/api/jobs?limit=20${cursor ? `&before=${encodeURIComponent(cursor)}` : ""}`, undefined, undefined, { current: () => request === state.historyRequest });
      if (request !== state.historyRequest) return;
      const records = more ? [...state.historyItems, ...(result.jobs || [])] : result.jobs || [];
      state.historyItems = Array.from(new Map(records.map((record) => [record.id, record])).values());
      state.historyCursor = result.next_cursor || null;
      state.historyLoaded = true;
      renderHistory();
    } catch (error) {
      if (request === state.historyRequest) showNotice("history-feedback", `${error.message}${state.historyLoaded ? " 이미 불러온 기록은 유지했습니다. 다시 불러올 수 있습니다." : " 기록을 다시 불러와 주세요."}`, "error");
    } finally {
      if (request === state.historyRequest) { state.historyPending = false; updateHistoryControls(); }
    }
  }
  $("refresh-history").addEventListener("click", () => loadHistory());
  $("history-more").addEventListener("click", () => loadHistory(true));

  class MeshViewer {
    constructor(canvas, ids = {}) {
      this.canvas = canvas;
      // Element ids of the surrounding stage; the import check reuses the viewer with its own.
      this.ids = { stage: "preview-stage", empty: "preview-empty", tools: "preview-tools", previousToggle: "preview-previous-toggle",
        previousLabel: "preview-previous-label", viewButtons: "[data-preview-view]", ...ids };
      this.context = canvas.getContext("2d", { willReadFrequently: true });
      this.mesh = null;
      this.yaw = 0.62;
      this.elevation = 0.62;
      this.zoom = 1;
      this.showDimensions = true;
      this.showOverhangs = true;
      this.showPrevious = true;
      this.previous = null;
      this.lastMesh = null;
      this.pending = false;
      this.drag = null;
      new ResizeObserver(() => this.requestDraw()).observe(this.element("stage"));
      canvas.addEventListener("pointerdown", (event) => {
        if (event.button !== 0) return;
        this.drag = { x: event.clientX, y: event.clientY };
        canvas.setPointerCapture(event.pointerId);
        canvas.classList.add("dragging");
      });
      canvas.addEventListener("pointermove", (event) => {
        if (!this.drag) return;
        this.yaw += (event.clientX - this.drag.x) * 0.009;
        this.elevation = Math.max(0, Math.min(Math.PI / 2, this.elevation + (event.clientY - this.drag.y) * 0.008));
        this.markView("custom");
        this.drag = { x: event.clientX, y: event.clientY };
        this.requestDraw();
      });
      const endDrag = () => { this.drag = null; canvas.classList.remove("dragging"); };
      canvas.addEventListener("pointerup", endDrag);
      canvas.addEventListener("pointercancel", endDrag);
      canvas.addEventListener("lostpointercapture", endDrag);
      canvas.addEventListener("wheel", (event) => { event.preventDefault(); this.changeZoom(event.deltaY > 0 ? 0.9 : 1.1); }, { passive: false });
      canvas.addEventListener("keydown", (event) => {
        if (!["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "+", "=", "-", "0"].includes(event.key)) return;
        event.preventDefault();
        this.markView("custom");
        if (event.key === "ArrowLeft") this.yaw -= 0.12;
        if (event.key === "ArrowRight") this.yaw += 0.12;
        if (event.key === "ArrowUp") this.elevation = Math.min(Math.PI / 2, this.elevation + 0.1);
        if (event.key === "ArrowDown") this.elevation = Math.max(0, this.elevation - 0.1);
        if (["+", "="].includes(event.key)) this.changeZoom(1.15);
        if (event.key === "-") this.changeZoom(1 / 1.15);
        if (event.key === "0") this.reset();
        this.requestDraw();
      });
    }

    faceColor(index) {
      // Chosen filament colours, else the neutral preview blue.
      const parts = this.mesh.parts;
      if (!Array.isArray(parts) || !parts.length) return [124, 160, 230];
      const part = parts[this.mesh.face_parts?.[index] ?? 0] || parts[0];
      return MeshViewer.rgb(part.hex) || [124, 160, 230];
    }

    static rgb(hex) {
      const match = /^#([0-9a-f]{6})$/i.exec(hex || "");
      if (!match) return null;
      // Keep very light and very dark filaments readable under the shading.
      return [0, 2, 4].map((offset) => Math.min(225, Math.max(48, parseInt(match[1].slice(offset, offset + 2), 16))));
    }

    setMesh(mesh, title, template = null) {
      if (!mesh?.vertices?.length || !mesh.faces?.length || !this.context) {
        this.element("empty").hidden = false;
        this.canvas.hidden = true;
        this.element("tools").hidden = true;
        return;
      }
      // Keep the model shown just before as a labelled outline for comparison.
      const earlier = this.mesh || this.lastMesh;
      const bounds = MeshViewer.bounds(mesh);
      // Compare only with the same kind of object; another template is not "the previous version".
      if (earlier && earlier !== mesh && template && template === this.template && MeshViewer.signature(earlier) !== MeshViewer.signature(mesh)) {
        this.previous = { mesh: earlier, edges: MeshViewer.featureEdges(earlier), bounds: MeshViewer.bounds(earlier), title: this.title };
      } else if (earlier !== mesh) {
        this.previous = null;
      }
      this.mesh = mesh;
      this.title = title;
      this.template = template;
      this.lastMesh = null;
      const [mins, maxs] = bounds;
      this.floor = mins[2];
      this.mins = mins;
      this.maxs = maxs;
      this.frame();
      this.featureEdges = MeshViewer.featureEdges(mesh);
      this.renderPreviousControl(this.previous, bounds);
      this.canvas.hidden = false;
      this.canvas.setAttribute("aria-label", `${title || "생성한 모델"}. 방향키로 회전, 더하기와 빼기로 확대, 0으로 기본 시점.`);
      this.element("empty").hidden = true;
      this.element("tools").hidden = false;
      this.reset();
    }

    static signature(mesh) {
      // Same-size models can still differ (for example a changed angle), so
      // compare vertex count and per-axis coordinate sums, not only the box.
      const sums = [0, 0, 0];
      mesh.vertices.forEach((point) => point.forEach((value, axis) => { sums[axis] += value; }));
      return JSON.stringify([mesh.vertices.length, mesh.faces.length, ...sums.map((value) => Math.round(value * 1000))]);
    }

    static bounds(mesh) {
      const mins = [Infinity, Infinity, Infinity], maxs = [-Infinity, -Infinity, -Infinity];
      mesh.vertices.forEach((point) => point.forEach((value, axis) => { mins[axis] = Math.min(mins[axis], value); maxs[axis] = Math.max(maxs[axis], value); }));
      return [mins, maxs];
    }

    frame() {
      // Frame the union of the current and (when shown) previous model.
      const mins = [...this.mins], maxs = [...this.maxs];
      if (this.previous && this.showPrevious) this.previous.bounds[0].forEach((value, axis) => {
        mins[axis] = Math.min(mins[axis], value); maxs[axis] = Math.max(maxs[axis], this.previous.bounds[1][axis]);
      });
      this.center = mins.map((value, axis) => (value + maxs[axis]) / 2);
      this.extents = mins.map((value, axis) => maxs[axis] - value);
      this.radius = Math.hypot(...this.extents) / 2 || 1;
    }

    renderPreviousControl(previous, currentBounds) {
      this.element("previousToggle").hidden = !previous;
      if (!previous) return;
      const size = ([mins, maxs]) => mins.map((value, axis) => numberFormat.format(Math.round((maxs[axis] - value) * 10) / 10)).join(" × ");
      const before = size(previous.bounds);
      this.element("previousLabel").textContent = currentBounds && before === size(currentBounds) ? "이전 모델 · 같은 크기" : `이전 ${before} mm`;
    }

    forgetPrevious() {
      this.lastMesh = null;
      this.previous = null;
      this.renderPreviousControl(null);
    }

    clear() {
      if (this.mesh) this.lastMesh = this.mesh;
      this.mesh = null;
      this.drag = null;
      this.canvas.hidden = true;
      this.canvas.classList.remove("dragging");
      if (this.context) this.context.clearRect(0, 0, this.canvas.width, this.canvas.height);
      this.element("empty").hidden = false;
      this.element("tools").hidden = true;
    }

    reset() { this.setView("iso"); }

    static featureEdges(mesh) {
      // Draw only creases (> 25° between neighbouring triangles) and open
      // boundaries, so tessellation diagonals on flat or curved faces stay hidden.
      const normals = mesh.faces.map((face) => {
        const [a, b, c] = face.map((index) => mesh.vertices[index]);
        const u = b.map((value, axis) => value - a[axis]), v = c.map((value, axis) => value - a[axis]);
        const n = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]];
        const length = Math.hypot(...n) || 1;
        return n.map((value) => value / length);
      });
      const owners = new Map();
      mesh.faces.forEach((face, faceIndex) => face.forEach((start, corner) => {
        const end = face[(corner + 1) % 3];
        const key = start < end ? `${start}:${end}` : `${end}:${start}`;
        if (!owners.has(key)) owners.set(key, []);
        owners.get(key).push(faceIndex);
      }));
      const edges = [];
      const crease = Math.cos(25 * Math.PI / 180);
      for (const [key, faces] of owners) {
        const keep = faces.length !== 2 || normals[faces[0]].reduce((sum, value, axis) => sum + value * normals[faces[1]][axis], 0) < crease;
        if (keep) edges.push(key.split(":").map(Number));
      }
      return edges;
    }

    setView(name) {
      const views = { iso: [0.62, 0.62], front: [0, 0], top: [0, Math.PI / 2], side: [Math.PI / 2, 0] };
      const [yaw, elevation] = views[name] || views.iso;
      this.yaw = yaw; this.elevation = elevation; this.zoom = 1;
      this.markView(name in views ? name : "iso");
      this.requestDraw();
    }

    element(key) {
      // A missing optional element (e.g. no "previous model" toggle) is ignored.
      return (this.ids[key] && $(this.ids[key])) || { hidden: true, textContent: "", style: {} };
    }

    markView(name) {
      this.view = name;
      document.querySelectorAll(this.ids.viewButtons).forEach((button) => button.setAttribute("aria-pressed", String(button.dataset.previewView === name)));
    }

    setOption(name, value) { this[name] = value; if (name === "showPrevious" && this.mesh) this.frame(); this.requestDraw(); }
    changeZoom(factor) { this.zoom = Math.max(0.45, Math.min(2.8, this.zoom * factor)); this.requestDraw(); }
    requestDraw() {
      if (this.pending) return;
      this.pending = true;
      window.requestAnimationFrame(() => { this.pending = false; this.draw(); });
    }

    draw() {
      if (!this.mesh || !this.context || this.canvas.hidden) return;
      const width = this.canvas.clientWidth, height = this.canvas.clientHeight;
      if (!width || !height) return;
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      this.canvas.width = Math.round(width * dpr);
      this.canvas.height = Math.round(height * dpr);
      const ctx = this.context;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, width, height);
      const cy = Math.cos(this.yaw), sy = Math.sin(this.yaw), ce = Math.cos(this.elevation), se = Math.sin(this.elevation);
      const scale = Math.min(width, height) * 0.34 * this.zoom / this.radius;
      const distance = this.radius * 4;
      const project = (point) => {
        const x = point[0] - this.center[0], y = point[1] - this.center[1], z = point[2] - this.center[2];
        // Right-handed view: the camera sits on the -Y side at yaw 0 (CAD "front"),
        // so the top view shows +Y up and text reads normally.
        const right = cy * x - sy * y, forward = -(sy * x + cy * y);
        const vertical = ce * z - se * forward, depth = se * z + ce * forward;
        const perspective = distance / (distance - depth);
        return [width / 2 + right * scale * perspective, height / 2 - vertical * scale * perspective, depth];
      };
      const span = Math.max(this.extents[0], this.extents[1]) * 0.8;
      ctx.lineWidth = 0.6;
      ctx.strokeStyle = "#dfe7f2";
      for (let index = -5; index <= 5; index += 1) {
        const offset = index * span / 5;
        const lines = [
          [[this.center[0] - span, this.center[1] + offset, this.floor], [this.center[0] + span, this.center[1] + offset, this.floor]],
          [[this.center[0] + offset, this.center[1] - span, this.floor], [this.center[0] + offset, this.center[1] + span, this.floor]],
        ];
        lines.forEach(([start, end]) => { const a = project(start), b = project(end); ctx.beginPath(); ctx.moveTo(a[0], a[1]); ctx.lineTo(b[0], b[1]); ctx.stroke(); });
      }
      // Average-depth triangle sorting cannot correctly display concave parts.
      // Rasterize with a per-pixel reciprocal-depth buffer so pockets and walls
      // remain visible exactly where the generated CAD mesh places them.
      const points = this.mesh.vertices.map((vertex) => {
        const point = project(vertex);
        return [point[0] * dpr, point[1] * dpr, 1 / (distance - point[2])];
      });
      const pixelWidth = this.canvas.width, pixelHeight = this.canvas.height;
      const raster = ctx.getImageData(0, 0, pixelWidth, pixelHeight);
      const pixels = raster.data;
      const depths = new Float32Array(pixelWidth * pixelHeight);
      for (let faceIndex = 0; faceIndex < this.mesh.faces.length; faceIndex += 1) {
        const face = this.mesh.faces[faceIndex];
        const [a, b, c] = face.map((index) => points[index]);
        const denominator = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1]);
        if (Math.abs(denominator) < 1e-9) continue;
        const minX = Math.max(0, Math.floor(Math.min(a[0], b[0], c[0])));
        const maxX = Math.min(pixelWidth - 1, Math.ceil(Math.max(a[0], b[0], c[0])));
        const minY = Math.max(0, Math.floor(Math.min(a[1], b[1], c[1])));
        const maxY = Math.min(pixelHeight - 1, Math.ceil(Math.max(a[1], b[1], c[1])));
        const [pa, pb, pc] = face.map((index) => this.mesh.vertices[index]);
        const u = pb.map((value, axis) => value - pa[axis]), v = pc.map((value, axis) => value - pa[axis]);
        const normal = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]];
        const magnitude = Math.hypot(...normal) || 1;
        const n = normal.map((value) => value / magnitude);
        // Camera-relative lighting: rotate the normal like project() does, then light
        // from the viewer's upper left so every view keeps readable face contrast.
        const viewRight = cy * n[0] - sy * n[1], viewForward = -(sy * n[0] + cy * n[1]);
        const viewUp = ce * n[2] - se * viewForward, viewDepth = se * n[2] + ce * viewForward;
        const key = Math.max(0, -0.38 * viewRight + 0.52 * viewUp + 0.76 * viewDepth);
        const rim = Math.max(0, 0.55 * viewRight + 0.25 * viewUp + 0.4 * viewDepth);
        const shade = Math.min(1.12, 0.6 + key * 0.42 + rim * 0.12);
        const overhangFace = this.showOverhangs && n[2] < -0.7072 && Math.min(pa[2], pb[2], pc[2]) > this.floor + 1e-6;
        const base = overhangFace ? [240, 128, 80] : this.faceColor(faceIndex);
        const color = base.map((value) => Math.round(Math.min(255, value * shade)));
        const inverse = 1 / denominator;
        for (let y = minY; y <= maxY; y += 1) {
          for (let x = minX; x <= maxX; x += 1) {
            const first = ((b[1] - c[1]) * (x + 0.5 - c[0]) + (c[0] - b[0]) * (y + 0.5 - c[1])) * inverse;
            const second = ((c[1] - a[1]) * (x + 0.5 - c[0]) + (a[0] - c[0]) * (y + 0.5 - c[1])) * inverse;
            const third = 1 - first - second;
            if (first < -1e-7 || second < -1e-7 || third < -1e-7) continue;
            const depth = first * a[2] + second * b[2] + third * c[2];
            const index = y * pixelWidth + x;
            if (depth <= depths[index]) continue;
            depths[index] = depth;
            const offset = index * 4;
            pixels[offset] = color[0]; pixels[offset + 1] = color[1]; pixels[offset + 2] = color[2]; pixels[offset + 3] = 255;
          }
        }
      }
      // Crease edges: depth-tested against the same buffer so hidden edges stay hidden.
      for (const [startIndex, endIndex] of this.featureEdges || []) {
        const a = points[startIndex], b = points[endIndex];
        const steps = Math.ceil(Math.max(Math.abs(b[0] - a[0]), Math.abs(b[1] - a[1])));
        for (let step = 0; step <= steps; step += 1) {
          const t = steps ? step / steps : 0;
          const x = Math.round(a[0] + (b[0] - a[0]) * t), y = Math.round(a[1] + (b[1] - a[1]) * t);
          if (x < 0 || y < 0 || x >= pixelWidth || y >= pixelHeight) continue;
          const depth = a[2] + (b[2] - a[2]) * t;
          const index = y * pixelWidth + x;
          if (depth < depths[index] * (1 - 2e-4)) continue;
          const offset = index * 4;
          pixels[offset] = 38; pixels[offset + 1] = 56; pixels[offset + 2] = 96; pixels[offset + 3] = 255;
        }
      }
      ctx.putImageData(raster, 0, 0);
      if (this.previous && this.showPrevious) {
        // Previous model: dashed grey outline drawn over everything and never
        // shaded, so it cannot be mistaken for the current CAD.
        ctx.save();
        ctx.setLineDash([5, 4]);
        ctx.strokeStyle = "rgba(71, 85, 105, 0.7)";
        ctx.lineWidth = 1.2;
        ctx.beginPath();
        for (const [start, end] of this.previous.edges) {
          const a = project(this.previous.mesh.vertices[start]), b = project(this.previous.mesh.vertices[end]);
          ctx.moveTo(a[0], a[1]); ctx.lineTo(b[0], b[1]);
        }
        ctx.stroke();
        ctx.restore();
      }
      if (this.showDimensions) this.drawDimensions(ctx, project);
      const origin = [31, height - 31];
      const axes = [["X", cy, se * sy, "#bb8391"], ["Y", -sy, se * cy, "#79a190"], ["Z", 0, ce, "#7898c8"]];
      ctx.font = "9px sans-serif";
      axes.forEach(([label, x, y, color]) => {
        const end = [origin[0] + x * 20, origin[1] - y * 20];
        ctx.strokeStyle = color; ctx.lineWidth = 1.3; ctx.beginPath(); ctx.moveTo(...origin); ctx.lineTo(...end); ctx.stroke();
        ctx.fillStyle = color; ctx.fillText(label, end[0] + 3, end[1] - 3);
      });
    }
  }

  MeshViewer.prototype.drawDimensions = function drawDimensions(ctx, project) {
    const [x0, y0, z0] = this.mins, [x1, y1, z1] = this.maxs;
    const pad = this.radius * 0.12;
    const format = (value) => `${numberFormat.format(Math.round(value * 10) / 10)} mm`;
    // In project(), a larger forward value (−(sin(yaw)·x + cos(yaw)·y)) is closer to the
    // viewer. Use the nearest box edges and push each line outward from the part.
    const nearY = Math.cos(this.yaw) >= 0 ? y0 : y1, outY = nearY === y1 ? pad : -pad;
    const nearX = Math.sin(this.yaw) >= 0 ? x0 : x1, outX = nearX === x1 ? pad : -pad, farX = nearX === x1 ? x0 : x1;
    // Depth components of the X, Y and Z axes (see project()); an axis pointing
    // almost straight at the viewer has no readable length on screen.
    const ce = Math.cos(this.elevation);
    const facing = [ce * Math.sin(this.yaw), ce * Math.cos(this.yaw), Math.sin(this.elevation)];
    const lines = [
      [[x0, nearY + outY, z0], [x1, nearY + outY, z0], x1 - x0, facing[0]],
      [[nearX + outX, y0, z0], [nearX + outX, y1, z0], y1 - y0, facing[1]],
      [[farX - outX, nearY + outY, z0], [farX - outX, nearY + outY, z1], z1 - z0, facing[2]],
    ].filter((line) => Math.abs(line[3]) < 0.9);
    ctx.save();
    ctx.font = "600 11px Pretendard, 'Apple SD Gothic Neo', sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    for (const [start, end, length] of lines) {
      const a = project(start), b = project(end);
      if (Math.hypot(b[0] - a[0], b[1] - a[1]) < 24) continue;
      ctx.strokeStyle = "#e0662f"; ctx.lineWidth = 1.2;
      ctx.beginPath(); ctx.moveTo(a[0], a[1]); ctx.lineTo(b[0], b[1]); ctx.stroke();
      const angle = Math.atan2(b[1] - a[1], b[0] - a[0]);
      for (const [point, direction] of [[a, 1], [b, -1]]) {
        ctx.beginPath();
        ctx.moveTo(point[0], point[1]);
        ctx.lineTo(point[0] + direction * 6 * Math.cos(angle - 0.4), point[1] + direction * 6 * Math.sin(angle - 0.4));
        ctx.moveTo(point[0], point[1]);
        ctx.lineTo(point[0] + direction * 6 * Math.cos(angle + 0.4), point[1] + direction * 6 * Math.sin(angle + 0.4));
        ctx.stroke();
      }
      const label = format(length), mid = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
      const widthText = ctx.measureText(label).width + 10;
      ctx.fillStyle = "#fffffff0"; ctx.strokeStyle = "#f2b79c"; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.roundRect(mid[0] - widthText / 2, mid[1] - 9, widthText, 18, 5); ctx.fill(); ctx.stroke();
      ctx.fillStyle = "#b5481b"; ctx.fillText(label, mid[0], mid[1] + 0.5);
    }
    ctx.restore();
  };

  $("journey-next-button").addEventListener("click", goToJourneyTarget);
  document.querySelectorAll("[data-history-filter]").forEach((button) => button.addEventListener("click", () => setHistoryFilter(button.dataset.historyFilter)));
  renderJourney();
  $("download-links").addEventListener("click", (event) => {
    // Remember only that this page offered the file and it was clicked; not that it was printed.
    const link = event.target.closest("a");
    if (link && state.job && /3MF/.test(link.textContent)) { state.downloadedJobId = state.job.id; renderJourney(); }
  });
  $("printability-nozzle").addEventListener("change", (event) => recheckPrintability(Number(event.target.value)));
  $("printability-run").addEventListener("click", () => recheckPrintability(Number($("printability-nozzle").value)));
  $("printability-use-printer").addEventListener("click", () => { const nozzle = printerReportedNozzle(); if (nozzle) recheckPrintability(nozzle); });

  const viewer = new MeshViewer($("model-canvas"));
  document.querySelectorAll("[data-preview-view]").forEach((button) => button.addEventListener("click", () => viewer.setView(button.dataset.previewView)));
  $("preview-dimensions").addEventListener("change", (event) => viewer.setOption("showDimensions", event.target.checked));
  $("preview-overhangs").addEventListener("change", (event) => viewer.setOption("showOverhangs", event.target.checked));
  $("preview-previous").addEventListener("change", (event) => viewer.setOption("showPrevious", event.target.checked));
  $("zoom-in").addEventListener("click", () => viewer.changeZoom(1.15));
  $("zoom-out").addEventListener("click", () => viewer.changeZoom(1 / 1.15));
  $("reset-view").addEventListener("click", () => viewer.reset());

  // ---------------------------------------------------------------------------
  // Imported model check: originals stay unchanged; a placement is a rotation and move only.

  const importViewer = new MeshViewer($("import-canvas"), { stage: "import-stage", empty: "import-empty", tools: "import-tools",
    previousToggle: null, previousLabel: null, viewButtons: "[data-import-view]" });
  $("import-zoom-in").addEventListener("click", () => importViewer.changeZoom(1.15));
  $("import-zoom-out").addEventListener("click", () => importViewer.changeZoom(1 / 1.15));
  $("import-reset-view").addEventListener("click", () => importViewer.reset());
  const IMPORT_MAX_BYTES = 32 * 1024 * 1024;
  const importStatus = { ok: ["점검 통과", "success"], review: ["확인할 점 있음", "warning"], needs_change: ["바꿔야 할 점 있음", "error"] };

  function updateImportControls() {
    const file = $("import-file").files?.[0];
    $("import-submit").disabled = !state.token || !file || Boolean(state.importPending);
  }

  function placedPreview(preview, rotation) {
    // Rotate the sampled preview like the server does, then sit it on the bed, centred.
    const turned = preview.vertices.map(([x, y, z]) => rotation.map((row) => row[0] * x + row[1] * y + row[2] * z));
    const mins = [0, 1, 2].map((axis) => Math.min(...turned.map((point) => point[axis])));
    const maxs = [0, 1, 2].map((axis) => Math.max(...turned.map((point) => point[axis])));
    const shift = [(mins[0] + maxs[0]) / 2, (mins[1] + maxs[1]) / 2, mins[2]];
    return { vertices: turned.map((point) => point.map((value, axis) => value - shift[axis])), faces: preview.faces };
  }

  function importOrientationText(item) {
    const size = item.size_mm;
    return `돌출부 ${(item.overhang_mm2 / 100).toFixed(1)} cm² · 바닥 접촉 ${(item.contact_mm2 / 100).toFixed(1)} cm² · ${numberFormat.format(size.x)} × ${numberFormat.format(size.y)} × ${numberFormat.format(size.z)} mm`;
  }

  function renderImportReview(review) {
    const tone = { pass: "success", warn: "warning", fail: "error" };
    const word = { pass: "통과", warn: "확인", fail: "바꿔야 함" };
    $("import-review").replaceChildren(...(review?.items || []).map((item) => {
      const row = node("div", "import-review-item");
      row.dataset.importReview = item.id;
      row.append(node("span", `badge badge-${tone[item.status] || "neutral"}`, word[item.status] || item.status),
        node("strong", "", `${item.label} · ${item.value}`), node("small", "", item.advice ? `${item.detail} ${item.advice}` : item.detail));
      return row;
    }));
  }

  function selectImportOrientation(id) {
    const result = state.importResult;
    const item = result?.orientations?.find((entry) => entry.id === id);
    if (!item) return;
    state.importSelected = id;
    for (const button of document.querySelectorAll("[data-import-orientation]")) button.setAttribute("aria-checked", String(Number(button.dataset.importOrientation) === id));
    const [label, tone] = importStatus[item.review.status] || ["점검 결과", "neutral"];
    setBadge("import-status", label, tone);
    renderImportReview(item.review);
    // No template: switching placements is not a "previous model" to outline.
    importViewer.setMesh(placedPreview(result.preview, item.rotation), result.filename, null);
    $("import-caption").textContent = `${item.label}${item.recommended ? " (추천)" : ""}${result.preview.sampled ? " · 미리보기는 삼각형 일부만 표시" : ""}`;
    $("import-download").href = `/api/imports/${encodeURIComponent(result.import_id)}/oriented?orientation=${id}`;
    $("import-make-job").disabled = !state.token || Boolean(state.importJobPending);
  }

  function renderImport(result) {
    state.importResult = result;
    $("import-result").hidden = false;
    const facts = result.facts;
    $("import-facts").textContent = `${result.filename} · ${result.format.toUpperCase()} · 삼각형 ${numberFormat.format(facts.triangles)}개 · ${facts.closed ? "닫힌 메시" : "열린 메시"}${facts.volume_mm3 ? ` · 부피 ${numberFormat.format(facts.volume_mm3 / 1000)} cm³` : ""}${result.build_items > 1 ? ` · 개체 ${result.build_items}개를 한 판으로 봄` : ""}`;
    $("import-scope").textContent = result.scope || "";
    $("import-source").href = result.source_url;
    $("import-orientations").replaceChildren(...result.orientations.slice(0, 6).map((item, index) => {
      const button = node("button", "import-orientation");
      button.type = "button";
      button.setAttribute("role", "radio");
      button.dataset.importOrientation = String(item.id);
      button.append(node("span", "import-rank", String(index + 1)), node("strong", "", `${item.label}${item.recommended ? " · 추천" : ""}${item.id === result.original_id ? " · 파일에 저장된 방향" : ""}`), node("span", "", importOrientationText(item)));
      button.addEventListener("click", () => selectImportOrientation(item.id));
      return button;
    }));
    selectImportOrientation(result.recommended_id);
    setBadge("import-badge", "점검 완료", "success");
  }

  async function submitImport(event) {
    event?.preventDefault();
    const file = $("import-file").files?.[0];
    if (!file || state.importPending) return;
    const request = state.importRequest = (state.importRequest || 0) + 1;
    state.importPending = true;
    updateImportControls();
    hideNotice("import-feedback");
    setBadge("import-badge", "불러오는 중", "info");
    try {
      if (!/\.(stl|3mf)$/i.test(file.name) || file.name.length > 120) throw new Error("이름이 120자 이하인 .stl 또는 .3mf 파일을 선택해 주세요.");
      if (!file.size || file.size > IMPORT_MAX_BYTES) throw new Error("모델 파일은 1바이트 이상, 32 MiB 이하여야 합니다.");
      const bytes = new Uint8Array(await file.arrayBuffer());
      const chunks = [];
      for (let offset = 0; offset < bytes.length; offset += 32768) chunks.push(String.fromCharCode(...bytes.subarray(offset, offset + 32768)));
      const result = await api("/api/imports", { filename: file.name, content_base64: btoa(chunks.join("")) });
      if (request !== state.importRequest) return;
      renderImport(result);
      loadRecentImports();
    } catch (error) {
      if (request === state.importRequest) {
        setBadge("import-badge", "불러오지 못함", "error");
        showNotice("import-feedback", error.message, "error");
      }
    } finally {
      if (request === state.importRequest) state.importPending = false;
      updateImportControls();
    }
  }

  async function openImport(importId) {
    const request = state.importRequest = (state.importRequest || 0) + 1;
    try {
      const result = await api(`/api/imports/${encodeURIComponent(importId)}`);
      if (request === state.importRequest) { renderImport(result); hideNotice("import-feedback"); }
    } catch (error) {
      if (request === state.importRequest) showNotice("import-feedback", error.message, "error");
    }
  }

  async function loadRecentImports() {
    if (!state.token) return;
    try {
      const { imports } = await api("/api/imports?limit=10");
      $("import-recent").hidden = !imports.length;
      $("import-recent-list").replaceChildren(...imports.map((item) => {
        const row = node("li", "");
        if (item.unreadable) { row.textContent = "읽을 수 없는 기록(원본 보존)"; return row; }
        const button = node("button", "", `${item.filename} · ${dateTime(item.created_at)}`);
        button.type = "button";
        button.addEventListener("click", () => openImport(item.import_id));
        row.append(button);
        return row;
      }));
    } catch {
      $("import-recent").hidden = true;
    }
  }

  async function makeImportJob() {
    const result = state.importResult;
    if (!result || state.importJobPending || state.importSelected === undefined) return;
    if (state.workflowBusy) return;
    state.importJobPending = true;
    $("import-make-job").disabled = true;
    try {
      const job = await api(`/api/imports/${encodeURIComponent(result.import_id)}/jobs`, { orientation: state.importSelected });
      requestModelReplacement({ kind: "history", job, title: job.title, button: $("import-make-job") });
      // Unsaved model work asks first; that question is on the model screen.
      if (state.modelReplacement) changeView("models");
      showNotice("import-feedback", "작업을 만들었습니다. 모델 만들기 화면의 슬라이싱·프린터로 보내기·결과 기록을 이어서 쓸 수 있습니다.", "success");
    } catch (error) {
      showNotice("import-feedback", error.message, "error");
    } finally {
      state.importJobPending = false;
      $("import-make-job").disabled = !state.token || !state.importResult;
    }
  }

  $("import-make-job").addEventListener("click", makeImportJob);
  $("import-file").addEventListener("change", updateImportControls);
  $("import-form").addEventListener("submit", submitImport);

  function renderRetainedOutcomes() {
    const area = $("retained-outcome-notes");
    area.replaceChildren();
    area.hidden = !state.retainedOutcomeDrafts.length;
    if (area.hidden) return;
    area.append(node("h3", "", "저장하지 않은 이전 출력 메모"), node("p", "", "제작안이나 저장 위치를 바꿀 때 입력 중이던 내용을 이 화면에 보관했습니다. 원래 작업에 옮기거나 복사한 뒤 보관을 해제하세요. 새 모델에 자동으로 연결하거나 저장하지 않습니다."));
    const labels = { success: "출력 성공 · 입력 중", failure: "출력 실패 · 입력 중", not_tested: "출력 미실시 · 입력 중" };
    for (const draft of state.retainedOutcomeDrafts) {
      const details = node("details", "help-details");
      details.open = true;
      details.append(node("summary", "", draft.title || "이전 작업의 출력 메모"), node("p", "", `원래 저장 위치: ${draft.storage_path}`), node("p", "", `작업 ID: ${draft.job_id} · ${labels[draft.result] || draft.result}`), node("pre", "", draft.notes || "텍스트 메모 없음"));
      if (draft.reasons?.length) details.append(node("p", "", `고른 실패 원인: ${draft.reasons.map((code) => state.failureReasons?.[code] || code).join(", ")}`));
      const dismiss = node("button", "button button-secondary", "메모를 옮겼어요 · 보관 해제");
      dismiss.type = "button";
      dismiss.addEventListener("click", () => {
        state.retainedOutcomeDrafts = state.retainedOutcomeDrafts.filter((item) => item !== draft);
        renderRetainedOutcomes();
      });
      details.append(dismiss);
      area.append(details);
    }
  }

  function retainOutcomeDraft(storagePath = state.storage?.path || "저장 위치 미확인") {
    if (!outcomeHasUnsavedChanges()) return;
    const draft = { job_id: state.job.id, title: state.job.title, storage_path: storagePath, result: $("outcome-result").value, notes: $("outcome-notes").value,
      reasons: $("outcome-result").value === "failure" && typeof selectedOutcomeReasons === "function" ? selectedOutcomeReasons() : [] };
    if (!state.retainedOutcomeDrafts.some(item => JSON.stringify(item) === JSON.stringify(draft))) state.retainedOutcomeDrafts.push(draft);
    renderRetainedOutcomes();
  }

  function detachPreviousStorage(previousPath) {
    retainOutcomeDraft(previousPath);
    state.modelEditApplied = null;
    state.modelEditAppliedSignature = null;
    cancelModelEdit();
    const hadWorkspace = Boolean(state.workspaceId) || workspaceDirty();
    state.studioWorkspaceEpoch = (state.studioWorkspaceEpoch || 0) + 1;
    state.studioWorkspaceId = null;
    state.studioWorkspaceRevision = null;
    state.studioWorkspaceSavedSignature = null;
    state.studioWorkspaceCandidate = null;
    state.studioLibraryItems = [];
    state.studioLibraryCursor = null;
    $("studio-library-list").replaceChildren();
    $("studio-library-list").value = "";
    cancelSlicerReads();
    state.job = null;
    state.slicePrepared = false;
    state.studioRecorded = null;
    state.studioSettingsRecorded = null;
    state.studioSettingsRecordedReview = null;
    state.studioSavedIdentity = null;
    state.slicerSavedText = "";
    state.modelCleanSignature = null;
    viewer.clear();
    renderColorLegend(null);
    viewer.forgetPrevious();  // a model from another storage is not this one's previous version
    state.offersResult = null;
    renderProjectSource("generated-source", null);
    $("model-result").hidden = true;
    $("outcome-card").hidden = true;
    $("download-links").replaceChildren();
    $("slice-result").replaceChildren();
    setBadge("preview-status", "저장 위치 변경 · 다시 생성 필요");
    $("preview-caption").textContent = "현재 치수는 유지했습니다. 이전 모델은 원래 저장 위치의 작업 기록에서 확인하세요.";
    $("preview-empty").querySelector("h3").textContent = "새 저장 위치에서 모델을 만들어 주세요";
    $("preview-empty").querySelector("p").textContent = "이전에 생성한 파일은 원래 폴더에서 확인해 주세요. 입력한 치수와 시작 설계는 유지했습니다.";
    state.workspaceEpoch += 1;
    state.workspaceEdits += 1;
    state.profileImport += 1;
    state.workspaceId = null;
    state.workspaceRevision = null;
    state.workspaceSavedSignature = hadWorkspace ? null : workspaceSignature();
    state.workspaces = [];
    const placeholder = node("option", "", "새 저장 위치의 작업을 불러오는 중입니다");
    placeholder.value = "";
    $("workspace-list").replaceChildren(placeholder);
    $("workspace-list").value = "";
    state.historyItems = [];
    state.historyCursor = null;
    state.historyLoaded = false;
    renderHistory();
    updateHistoryControls();
    renderSlicerFiles();
    showNotice("storage-change-notice", "저장 위치가 바뀌었습니다. 현재 치수, 요청과 재료 편집 내용은 유지했습니다. 이전 결과와 저장본은 원래 폴더의 기록에서 확인하세요. 이전 폴더에 연결된 다운로드와 저장본 연결은 해제했으며, 현재 재료 편집은 새 위치에 새 작업으로 저장할 수 있습니다.", "warning");
    $("storage-change-notice").append(node("p", "", `이전 저장 위치: ${previousPath}`), node("p", "", `현재 저장 위치: ${state.storage.path}`));
    showNotice("model-feedback", "저장 위치가 바뀌어 이전 모델의 다운로드 연결을 해제했습니다. 현재 치수로 새 모델을 생성하거나 원래 폴더의 기록을 확인해 주세요.", "info");
    showNotice("slice-feedback", "새 저장 위치에서 현재 치수의 모델을 생성한 뒤 슬라이싱 설정을 다시 검토해 주세요.", "info");
  }

  async function bootstrap() {
    const request = ++state.bootstrapRequest;
    const previousStoragePath = state.storage?.path;
    state.connectionEpoch += 1;
    cancelModelEdit();
    invalidateStudioRequests();
    state.slicePrepared = false;
    if (state.job) showNotice("slice-feedback", "연결을 다시 확인합니다. 현재 입력은 유지하며 실행 계획은 새로 준비해야 합니다. 처리 중이던 요청의 결과는 작업 기록에서 확인해 주세요.", "info");
    cancelModelReplacement();
    state.historyRequest += 1;
    state.historyPending = false;
    state.workspaceListRequest += 1;
    updateHistoryControls();
    state.bootstrapPending = true;
    state.connectionState = "connecting";
    state.token = null;
    renderConnection();
    updateWorkflowControls();
    state.discoveryEpoch += 1;
    state.discoveryRequest += 1;
    state.discoveryPending = false;
    if (state.discovery) { state.discoveryStale = true; renderDiscovery(); }
    $("bootstrap-error").hidden = true;
    try {
      const data = await api("/api/bootstrap", undefined, undefined, { current: () => request === state.bootstrapRequest });
      if (request !== state.bootstrapRequest) return;
      state.token = data.session_token;
      state.connectionState = "connected";
      state.storage = data.storage || null;
      if (typeof previousStoragePath === "string" && typeof state.storage?.path === "string" && previousStoragePath !== state.storage.path) detachPreviousStorage(previousStoragePath);
      renderConnection();
      state.templates = data.templates || [];
      state.environment = data.environment || {};
      state.provider = data.provider || {};
      const name = data.app?.name || "3D Printer Agent";
      $("brand-name").textContent = name.replace(/^3D\s+/i, "");
      document.title = `${name} · 로컬 작업 공간`;
      $("app-version").textContent = data.app?.version ? `Version ${data.app.version}` : "버전 정보 없음";
      renderSlicerEnvironment();
      updateImportControls();
      const editLlmOption = $("model-edit-mode").querySelector('option[value="llm"]');
      editLlmOption.disabled = !state.provider.configured;
      editLlmOption.textContent = state.provider.configured ? "LLM 모드 · 설정 있음" : "LLM 모드 · 미설정";
      const llmOption = $("plan-mode").querySelector('option[value="llm"]');
      llmOption.disabled = !state.provider.configured;
      llmOption.textContent = state.provider.configured ? "LLM 모드 · 설정 있음" : "LLM 모드 · 미설정";
      $("provider-note").textContent = state.provider.configured
        ? `LLM ${state.provider.model || "모델"} 설정이 있습니다. 실제 연결과 응답은 요청 시 확인합니다. 기본은 템플릿 모드입니다.`
        : "LLM은 아직 설정되지 않았습니다. 템플릿 모드로 지원하는 물건과 치수를 해석할 수 있습니다.";
      if (!state.template && state.templates.length) applyDraft(state.templates[0].id);
      else renderTemplates();
      setDiscoveryCatalog(data.discovery, Boolean(state.discovery));
      setStoreGuide(data.store_guide);
      setFailureReasons(data.failure_reasons);
      ["plan-button", "review-profile", "compare-offers"].forEach((id) => { $(id).disabled = false; });
      updateWorkflowControls();
      updateWorkspaceStatus();
      // The connection is established once bootstrap succeeds. Saved-list loads are
      // secondary and must not keep the reconnect control busy if they stall.
      state.bootstrapPending = false;
      renderConnection();
      updateWorkspaceStatus();
      await loadWorkspaces();
      await loadStudioLibrary();
    } catch (error) {
      if (request !== state.bootstrapRequest) return;
      $("bootstrap-error").hidden = false;
      $("bootstrap-error-detail").textContent = error.message;
      state.connectionState = "disconnected";
      state.token = null;
      renderConnection();
    } finally {
      if (request === state.bootstrapRequest) { state.bootstrapPending = false; renderConnection(); updateWorkflowControls(); updateWorkspaceStatus(); }
    }
  }
  $("reconnect-button").addEventListener("click", bootstrap);
  $("retry-bootstrap").addEventListener("click", bootstrap);
  renderOfferRows();
  state.workspaceSavedSignature = workspaceSignature();
  renderGuidedEditor();
  bootstrap();
})();
