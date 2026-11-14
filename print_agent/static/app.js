(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const state = { retainedOutcomeDrafts: [], connectionState: "connecting", connectionEpoch: 0, bootstrapPending: false, storage: null, modelCleanSignature: null, modelReplacement: null, modelTransitionRequest: 0, slicerSavedText: "", historyItems: [], historyLoaded: false, historyRequest: 0, historyPending: false, historyCursor: null, discovery: null, discoveryPurpose: "all", discoveryMatches: [], discoveryBrowsed: null, discoveryPending: false, discoveryStale: false, discoveryRequest: 0, discoveryEpoch: 0, discoveryRevision: 0, projectSource: null, projectReplacement: null, bootstrapRequest: 0, token: null, templates: [], template: null, parameters: {}, environment: {}, provider: {}, job: null, slicePrepared: false, workflowBusy: false, slicerFiles: { machine: null, process: null, filaments: [] }, slicerStaged: false, slicerContext: 0, slicerRequests: {}, slicerPending: {}, profileDocuments: [], profileTarget: 0, profileRevision: 0, profileImport: 0, profileReport: null, profileDownloadUrl: null, guidedEdits: {}, guidedSources: {}, workspaceId: null, workspaceRevision: null, workspaceSavedSignature: null, workspaceEpoch: 0, workspaceEdits: 0, workspaceListRequest: 0, workspaceBusy: false, workspaces: [] };
  const pageNames = { models: "모델 만들기", profiles: "재료 설정", offers: "구매 비교", history: "작업 기록" };
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
  };
  const fieldNames = {
    ...Object.fromEntries(Object.entries(fields).map(([key, value]) => [key, value.label])),
    printer_model: "프린터 모델", printer_preset: "프린터 프리셋", nozzle_diameter: "노즐 지름",
    plate_type: "플레이트 종류", extruder: "압출기", feed_mode: "공급 방식", material_id: "재료 제품 식별자",
    material_identity_status: "제품 식별 상태", nozzle_temperature: "노즐 온도",
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
    updateConnectionActions();
  }

  function connectionFailed(message) {
    state.connectionEpoch += 1;
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
    $("save-outcome").disabled = busy || !state.token || !state.job;
    updateSliceControls();
    updateDiscoveryControls();
    $("model-confirm-replace").disabled = busy || !state.modelReplacement;
    $("model-cancel-replace").disabled = busy;
  }

  function invalidateCurrentJob(message) {
    cancelSlicerReads();
    renderSlicerFiles();
    if (!state.job) return;
    state.job = null;
    renderProjectSource("generated-source", null);
    state.slicePrepared = false;
    viewer.clear();
    $("model-result").hidden = true;
    $("outcome-card").hidden = true;
    $("download-links").replaceChildren();
    $("slice-result").replaceChildren();
    setBadge("preview-status", "새 제작안 · 생성 전");
    $("preview-caption").textContent = "변경한 제작안은 아직 모델에 반영되지 않았습니다.";
    $("preview-empty").querySelector("h3").textContent = "새 제작안으로 다시 만들어 주세요";
    $("preview-empty").querySelector("p").textContent = "이전에 생성한 파일은 작업 기록에서 다시 열 수 있습니다.";
    showNotice("model-feedback", message);
    showNotice("slice-feedback", "현재 제작안의 모델을 생성한 뒤 슬라이싱을 준비할 수 있습니다.");
    updateWorkflowControls();
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
    if (name === "models") viewer.requestDraw();
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
      art.append(shape);
      const size = project.parameters || {};
      button.append(art, node("strong", "project-title", project.title), node("span", "project-description", project.description), node("span", "project-size", `${size.width} × ${size.depth} × ${size.height} mm`));
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
      return input.validity?.badInput || input.validity?.valid === false || input.value === "" || input.value !== String(state.parameters[key]);
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
      return input.validity?.badInput || input.validity?.valid === false || input.value === "" || String(input.value) !== String(template.defaults[key]);
    });
  }

  function slicerHasUnsavedChanges() {
    return state.slicerStaged || Object.keys(state.slicerPending || {}).length > 0 || $("slicer-json").value !== (state.slicerSavedText || "");
  }

  function outcomeHasUnsavedChanges() {
    return Boolean(state.job) && ($("outcome-result").value !== (state.job.user_outcome?.result || "not_tested") || $("outcome-notes").value !== (state.job.user_outcome?.notes || ""));
  }

  function hasPendingWork() {
    return state.retainedOutcomeDrafts.length > 0 || state.workflowBusy || state.workspaceBusy || modelHasUnsavedChanges() || slicerHasUnsavedChanges() || outcomeHasUnsavedChanges() || workspaceDirty();
  }

  function replacementSignature() {
    return JSON.stringify([modelDraftSignature(), state.job?.id, $("slicer-json").value, state.slicerContext, state.slicerStaged, $("outcome-result").value, $("outcome-notes").value]);
  }

  function cancelModelReplacement() {
    const previous = state.modelReplacement;
    state.modelReplacement = null;
    state.modelTransitionRequest += 1;
    $("model-replace-confirm").hidden = true;
    if (previous?.button?.isConnected) previous.button.focus({ preventScroll: true });
  }

  function requestModelReplacement(action) {
    if (state.workflowBusy) return;
    cancelModelReplacement();
    cancelProjectApplication();
    if (modelHasUnsavedChanges() || slicerHasUnsavedChanges() || outcomeHasUnsavedChanges()) {
      state.modelReplacement = { ...action, signature: replacementSignature() };
      const titles = { history: "현재 제작안을 저장된 모델로 바꿀까요?", retry: "현재 제작안을 이 기록의 치수로 바꿀까요?", template: "현재 제작안을 다른 템플릿으로 바꿀까요?", reset: "현재 제작안을 기본 치수로 되돌릴까요?" };
      $("model-replace-title").textContent = titles[action.kind] || "현재 제작안을 바꿀까요?";
      $("model-replace-detail").textContent = `${action.title || "선택한 제작안"}을 준비합니다. 저장하지 않은 치수와 출력 메모가 바뀔 수 있으며, 현재 미리보기와 다운로드는 교체됩니다. 생성해 둔 파일은 작업 기록에 남습니다.`;
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
    if (action.kind === "history") {
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
      button.append(node("span", "template-size", `${defaults.width} × ${defaults.depth} × ${defaults.height} mm · 기본 크기`));
      button.addEventListener("click", () => requestModelReplacement({ kind: "template", template: template.id, title: template.title, button }));
      list.append(button);
    });
  }

  function applyDraft(templateId, parameters, source = null) {
    const template = state.templates.find((item) => item.id === templateId);
    if (!template) throw new Error("지원하지 않는 제작 템플릿입니다.");
    cancelModelReplacement();
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
    for (const key of template.editable_fields) {
      const definition = fields[key];
      if (!definition) continue;
      const container = node("div", "parameter-field");
      const label = node("label", "", `${definition.label} · ${definition.unit || "mm"}`);
      const input = node("input");
      input.id = `parameter-${key}`;
      input.name = key;
      input.type = "number";
      input.min = definition.min;
      input.max = definition.max;
      input.step = definition.unit === "개" ? "1" : "any";
      input.required = true;
      input.value = state.parameters[key];
      input.dataset.parameter = key;
      label.htmlFor = input.id;
      const help = node("small", "", `기본 ${template.defaults[key]} ${definition.unit || "mm"}`);
      help.id = `parameter-help-${key}`;
      input.setAttribute("aria-describedby", help.id);
      container.append(label, input, help);
      grid.append(container);
    }
    renderTemplates();
    updateWorkflowControls();
  }

  $("model-form").addEventListener("input", (event) => {
    if (event.target.dataset.parameter) invalidateCurrentJob("치수가 바뀌었습니다. 새 모델을 생성하면 변경한 형상을 확인할 수 있습니다.");
  });

  $("reset-parameters").addEventListener("click", () => requestModelReplacement({ kind: "reset", template: state.template, title: "현재 템플릿의 기본 치수", button: $("reset-parameters") }));
  $("model-confirm-replace").addEventListener("click", confirmModelReplacement);
  $("model-cancel-replace").addEventListener("click", cancelModelReplacement);

  async function preparePlan() {
    if (state.workflowBusy) return;
    const signature = modelDraftSignature();
    hideNotice("plan-feedback");
    try {
      await withWorkflow($("plan-button"), "요청 해석 중", async () => {
        const result = await api("/api/plan", { text: $("request-text").value, mode: $("plan-mode").value }, undefined, { current: () => signature === modelDraftSignature() });
        if (signature !== modelDraftSignature()) return;
        if (result.status === "ready" && result.parameters) {
          applyDraft(result.parameters.template, result.parameters);
          showNotice("plan-feedback", result.message, "success", result.assumptions || []);
          $("parameter-heading").focus({ preventScroll: true });
          if (result.engine === "llm") $("provider-note").textContent = "설정된 LLM에서 제작안을 받았습니다. 치수를 확인한 뒤 모델을 생성하세요.";
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
      });
    } catch (error) { showNotice("plan-feedback", error.message, "error"); }
  }

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
    for (const input of document.querySelectorAll("[data-parameter]")) parameters[input.dataset.parameter] = input.valueAsNumber;
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
    } catch (error) { showNotice("model-feedback", error.status === 409 && error.code !== "resource_busy" && state.projectSource ? `${error.message} 현재 치수는 유지했습니다. 출처 연결을 해제하거나 새 시작점을 선택한 뒤 다시 생성해 주세요.` : error.message, "error"); }
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
    const area = $("download-links");
    area.replaceChildren();
    const labels = { stl: "STL", step: "STEP", three_mf: "3MF 형상", source: "Python 소스", manifest: "생성 기록", sliced_three_mf: "슬라이스 3MF", slice: "슬라이스 결과" };
    const files = { ...(job.artifacts || {}) };
    if (["running", "interrupted"].includes(job.latest_slice?.phase)) { delete files.sliced_three_mf; delete files.slice; }
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

  function renderJob(job) {
    const result = job.result;
    if (!result) throw new Error("작업에 모델 결과가 없습니다.");
    cancelSlicerReads();
    state.job = job;
    renderProjectSource("generated-source", job.design_source);
    state.slicePrepared = false;
    $("model-result").hidden = false;
    $("outcome-card").hidden = false;
    $("result-heading").textContent = (job.title || "모델 파일이 준비됐어요").replace(/\s+mm\b/g, "\u00a0mm");
    const dims = result.dimensions_mm || {};
    $("model-metrics").replaceChildren(
      metric("가로 × 세로 × 높이", `${numberFormat.format(dims.x)} × ${numberFormat.format(dims.y)} × ${numberFormat.format(dims.z)} mm`),
      metric("CAD 체적", `${numberFormat.format(result.volume_mm3 / 1000)} cm³`),
      metric("형상 상태", result.geometry_status === "validated" ? "CAD 검증 완료" : "확인 필요")
    );
    const checkNames = { valid_cad: "형상 유효성", single_solid: "단일 솔리드", positive_volume: "양의 체적", requested_dimensions: "요청 치수", closed_preview_mesh: "닫힌 메시" };
    $("model-checks").replaceChildren(...(result.checks || []).map((check) => {
      const element = node("span", `check-item${check.passed ? "" : " failed"}`, checkNames[check.name] || check.name);
      element.title = check.detail || "";
      return element;
    }));
    $("model-warnings").replaceChildren(...(result.warnings || []).map((text) => node("p", "", text)));
    renderDownloads(job);
    viewer.setMesh(result.mesh, job.title);
    setBadge("preview-status", "실제 CAD 메시", "blue");
    $("preview-caption").textContent = "생성된 모델 · 드래그 또는 방향키로 조작";
    $("outcome-result").value = job.user_outcome?.result || "not_tested";
    $("outcome-notes").value = job.user_outcome?.notes || "";
    state.modelCleanSignature = modelDraftSignature();
    hideNotice("outcome-feedback");
    $("slice-result").replaceChildren();
    showNotice("slice-feedback", state.environment.available ? "전체 설정을 제공하고 실행 계획을 먼저 검토해 주세요." : "Bambu Studio를 사용할 수 없어 현재 환경에서는 슬라이싱을 실행할 수 없습니다.");
    if (job.latest_slice?.phase === "running") showNotice("slice-feedback", "이 기록의 슬라이싱 요청은 실행 중으로 저장되어 있습니다. 완료 여부는 작업 기록에서 다시 열어 확인해 주세요. 이전 슬라이스 파일을 현재 결과로 제공하지 않습니다.", "info");
    else if (job.latest_slice?.phase === "interrupted") showNotice("slice-feedback", "이전 슬라이싱은 완료 결과를 저장하기 전에 중단되었습니다. 설정을 다시 검토한 뒤 실행해 주세요. CAD 모델은 유지되며 이전 슬라이스 파일은 현재 결과로 제공하지 않습니다.", "warning");
    else if (job.latest_slice) renderSliceResult(job.latest_slice.plan || {}, job.latest_slice.execution, true);
    if (state.slicerStaged) resetSlicePreparation("선택 중인 설정 파일이 있습니다. 묶음을 만들거나 편집을 취소한 뒤 이 모델의 실행 계획을 검토해 주세요.");
    renderSlicerFiles();
    updateWorkflowControls();
  }

  function updateSliceControls() {
    const reading = Object.keys(state.slicerPending).length > 0;
    const busy = state.workflowBusy;
    const canPrepare = Boolean(state.token && state.job && state.environment.available && state.environment.cli_supported !== false && !busy && !state.slicerStaged && !reading);
    if (!$("prepare-slice").dataset.busy) $("prepare-slice").disabled = !canPrepare;
    if (!$("execute-slice").dataset.busy) $("execute-slice").disabled = !canPrepare || !state.slicePrepared;
    $("probe-slicer").disabled = busy || !state.token || !state.environment.available;
    $("assemble-slicer").disabled = busy || reading || !state.slicerStaged;
    $("cancel-slicer-assembly").disabled = busy || (!reading && !state.slicerStaged);
    $("slicer-json").disabled = busy || state.slicerStaged || Boolean(state.slicerPending.bundle);
    $("slicer-file").disabled = busy || state.slicerStaged;
    for (const id of ["slicer-machine-file", "slicer-process-file", "slicer-filament-files", "slicer-plate"]) $(id).disabled = busy || Boolean(state.slicerPending.bundle);
  }

  function resetSlicePreparation(message) {
    state.slicePrepared = false;
    if (state.job) {
      const artifacts = { ...state.job.artifacts };
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

  function renderSliceResult(plan, execution, recorded = false) {
    const area = $("slice-result");
    area.replaceChildren();
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
    try {
      if (state.slicerStaged || Object.keys(state.slicerPending).length) throw new Error("설정 파일을 선택 중입니다. 묶음을 만들거나 편집을 취소한 뒤 실행 계획을 검토해 주세요.");
      await withWorkflow(button, execute ? "슬라이싱 실행 중" : "전체 설정 검토 중", async () => {
        const jobId = state.job?.id;
        if (!jobId) throw new Error("먼저 현재 제작안의 모델을 생성해 주세요.");
        const submittedText = $("slicer-json").value;
        const bundle = parseObject(submittedText, "슬라이서 전체 설정");
        resetSlicePreparation(execute ? "검토한 설정으로 슬라이싱하고 있습니다." : "전체 설정과 실행 계획을 검토하고 있습니다.");
        const response = await api("/api/slice", { job_id: jobId, config_bundle: bundle, execute });
        state.slicerSavedText = submittedText;
        state.slicePrepared = Boolean(response.plan?.ready) && !execute;
        renderSliceResult(response.plan || {}, response.execution);
        try { state.job = await api(`/api/jobs/${encodeURIComponent(jobId)}`); renderDownloads(state.job); }
        catch { toast("검토 결과는 받았지만 파일 목록을 새로 불러오지 못했습니다. 작업 기록에서 다시 확인해 주세요."); }
      });
    } catch (error) { state.slicePrepared = false; showNotice("slice-feedback", error.message, "error"); }
    finally { updateSliceControls(); }
  }
  $("prepare-slice").addEventListener("click", () => runSlice(false));
  $("execute-slice").addEventListener("click", () => runSlice(true));

  function cancelSlicerReads() {
    state.slicerContext += 1;
    state.slicerPending = {};
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
      : "Bambu Studio 실행 파일을 찾지 못했습니다. 설치·실행 경로를 설정한 뒤 앱을 다시 열어 주세요. 설정 묶음 작성과 모델 파일 다운로드는 사용할 수 있습니다.";
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

  $("outcome-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!state.job) return;
    try {
      await withWorkflow($("save-outcome"), "기록 중", async () => {
        const jobId = state.job.id;
        const job = await api(`/api/jobs/${encodeURIComponent(jobId)}/outcome`, { result: $("outcome-result").value, notes: $("outcome-notes").value });
        state.job = job;
        showNotice("outcome-feedback", "직접 보고한 출력 결과를 기록했습니다. CAD 검증 상태와 별도로 보관합니다.", "success");
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
      if (epoch === state.workspaceEpoch) showNotice("workspace-feedback", error.status === 409 ? "다른 탭에서 이 작업을 변경했습니다. 현재 편집은 유지했습니다. 다른 이름으로 저장하거나 저장된 작업을 다시 열어 최신 내용을 확인하세요." : error.message, "error");
    } finally {
      state.workspaceBusy = false;
      updateWorkspaceStatus();
    }
  }

  function restoreWorkspace(record) {
    const snapshot = record.snapshot;
    state.workspaceEpoch += 1;
    state.workspaceEdits += 1;
    state.profileImport += 1;
    state.guidedEdits = {};
    state.profileDocuments = snapshot.documents.map((entry) => ({ ...profileDocument(entry), draftText: entry.draft_text }));
    state.profileTarget = snapshot.target_index;
    $("profile-json").value = state.profileDocuments.length ? state.profileDocuments[state.profileTarget].draftText : snapshot.profile_text;
    for (const [name, id] of Object.entries(profileSetupFields())) $(id).value = snapshot.setup[name];
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
      documents: [], target_index: 0, profile_text: "",
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

  $("offers-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    hideNotice("offers-feedback");
    try {
      const offers = [];
      for (const row of document.querySelectorAll("[data-offer]")) {
        const values = Object.fromEntries(Array.from(row.querySelectorAll("[data-offer-field]")).map((input) => [input.dataset.offerField, input.value.trim()]));
        if (Object.values(values).every((value) => value === "")) continue;
        if (!values.name || values.price === "" || values.grams === "") throw new Error(`상품 ${row.dataset.offer}의 이름, 가격, 중량을 모두 입력해 주세요.`);
        offers.push({ name: values.name, currency: $("offer-currency").value, price: Number(values.price), grams: Number(values.grams), shipping: values.shipping === "" ? null : Number(values.shipping) });
      }
      if (!offers.length) throw new Error("비교할 상품을 하나 이상 입력해 주세요.");
      await withBusy($("compare-offers"), "단가 계산 중", async () => renderOffers(await api("/api/offers/compare", { offers })));
    } catch (error) { showNotice("offers-feedback", error.message, "error"); }
  });
  $("offers-form").addEventListener("input", () => { $("offers-result").hidden = true; });
  $("offer-currency").addEventListener("change", () => { $("offers-result").hidden = true; });

  function money(value, currency) {
    if (!Number.isFinite(value)) return "미확인";
    return new Intl.NumberFormat("ko-KR", { style: "currency", currency, maximumFractionDigits: currency === "KRW" || currency === "JPY" ? 0 : 2 }).format(value);
  }

  function renderOffers(result) {
    $("offers-result").hidden = false;
    const area = $("offer-comparison");
    area.replaceChildren();
    for (const [currency, offers] of Object.entries(result.groups || {})) {
      const wrap = node("div", "table-wrap");
      const table = node("table", "offer-result-table");
      const head = node("thead");
      const headings = node("tr");
      ["상품", "중량", "상품 + 배송비", "배송비 포함 kg당 비용"].forEach((label) => { const th = node("th", "", label); th.scope = "col"; headings.append(th); });
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
        body.append(row);
      });
      table.append(body);
      wrap.append(table);
      area.append(wrap);
    }
    $("offer-notice").textContent = result.notice || "사용자가 입력한 조건으로 계산했습니다. 실시간 가격은 확인하지 않았습니다.";
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
    state.historyItems.forEach((job) => {
      const card = node("article", "history-item");
      const title = node("div");
      title.append(node("h3", "", job.title || "생성한 모델"), node("p", "", dateTime(job.created_at)));
      if (job.diagnostic) title.append(node("p", "history-diagnostic", job.diagnostic));
      const statuses = node("div", "history-statuses");
      const warning = ["failed", "interrupted", "unreadable"].includes(job.status);
      const statusLabel = { geometry_validated: "CAD 검증 완료", failed: "모델 생성 실패", generating: "모델 생성 중", interrupted: "생성 중단 · 완료 결과 없음", unreadable: "기록 읽기 확인 필요" }[job.status] || friendly(job.status || "상태 미확인");
      statuses.append(node("span", `badge badge-${warning ? "warning" : job.status === "geometry_validated" ? "blue" : "neutral"}`, statusLabel));
      const outcome = job.user_outcome?.result;
      statuses.append(node("span", `badge badge-${outcome === "success" ? "success" : outcome === "failure" ? "warning" : "neutral"}`, outcome === "success" ? "출력 성공 · 사용자 보고" : outcome === "failure" ? "출력 실패 · 사용자 보고" : "실물 출력 미기록"));
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
    constructor(canvas) {
      this.canvas = canvas;
      this.context = canvas.getContext("2d", { willReadFrequently: true });
      this.mesh = null;
      this.yaw = 0.62;
      this.elevation = 0.62;
      this.zoom = 1;
      this.pending = false;
      this.drag = null;
      new ResizeObserver(() => this.requestDraw()).observe($("preview-stage"));
      canvas.addEventListener("pointerdown", (event) => {
        if (event.button !== 0) return;
        this.drag = { x: event.clientX, y: event.clientY };
        canvas.setPointerCapture(event.pointerId);
        canvas.classList.add("dragging");
      });
      canvas.addEventListener("pointermove", (event) => {
        if (!this.drag) return;
        this.yaw += (event.clientX - this.drag.x) * 0.009;
        this.elevation = Math.max(0.06, Math.min(1.48, this.elevation + (event.clientY - this.drag.y) * 0.008));
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
        if (event.key === "ArrowLeft") this.yaw -= 0.12;
        if (event.key === "ArrowRight") this.yaw += 0.12;
        if (event.key === "ArrowUp") this.elevation = Math.min(1.48, this.elevation + 0.1);
        if (event.key === "ArrowDown") this.elevation = Math.max(0.06, this.elevation - 0.1);
        if (["+", "="].includes(event.key)) this.changeZoom(1.15);
        if (event.key === "-") this.changeZoom(1 / 1.15);
        if (event.key === "0") this.reset();
        this.requestDraw();
      });
    }

    setMesh(mesh, title) {
      if (!mesh?.vertices?.length || !mesh.faces?.length || !this.context) {
        $("preview-empty").hidden = false;
        this.canvas.hidden = true;
        $("preview-tools").hidden = true;
        return;
      }
      this.mesh = mesh;
      const mins = [Infinity, Infinity, Infinity], maxs = [-Infinity, -Infinity, -Infinity];
      mesh.vertices.forEach((point) => point.forEach((value, axis) => { mins[axis] = Math.min(mins[axis], value); maxs[axis] = Math.max(maxs[axis], value); }));
      this.center = mins.map((value, axis) => (value + maxs[axis]) / 2);
      this.extents = mins.map((value, axis) => maxs[axis] - value);
      this.radius = Math.hypot(...this.extents) / 2 || 1;
      this.floor = mins[2];
      this.canvas.hidden = false;
      this.canvas.setAttribute("aria-label", `${title || "생성한 모델"}. 방향키로 회전, 더하기와 빼기로 확대, 0으로 기본 시점.`);
      $("preview-empty").hidden = true;
      $("preview-tools").hidden = false;
      this.reset();
    }

    clear() {
      this.mesh = null;
      this.drag = null;
      this.canvas.hidden = true;
      this.canvas.classList.remove("dragging");
      if (this.context) this.context.clearRect(0, 0, this.canvas.width, this.canvas.height);
      $("preview-empty").hidden = false;
      $("preview-tools").hidden = true;
    }

    reset() { this.yaw = 0.62; this.elevation = 0.62; this.zoom = 1; this.requestDraw(); }
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
        const right = cy * x - sy * y, forward = sy * x + cy * y;
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
      for (const face of this.mesh.faces) {
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
        const light = Math.max(-0.6, Math.min(1, (-0.35 * normal[0] - 0.45 * normal[1] + 0.82 * normal[2]) / magnitude));
        const shade = 0.87 + light * 0.24;
        const color = [Math.round(112 * shade), Math.round(153 * shade), Math.round(224 * shade)];
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
      ctx.putImageData(raster, 0, 0);
      const origin = [31, height - 31];
      const axes = [["X", cy, -se * sy, "#bb8391"], ["Y", -sy, -se * cy, "#79a190"], ["Z", 0, ce, "#7898c8"]];
      ctx.font = "9px sans-serif";
      axes.forEach(([label, x, y, color]) => {
        const end = [origin[0] + x * 20, origin[1] - y * 20];
        ctx.strokeStyle = color; ctx.lineWidth = 1.3; ctx.beginPath(); ctx.moveTo(...origin); ctx.lineTo(...end); ctx.stroke();
        ctx.fillStyle = color; ctx.fillText(label, end[0] + 3, end[1] - 3);
      });
    }
  }

  const viewer = new MeshViewer($("model-canvas"));
  $("zoom-in").addEventListener("click", () => viewer.changeZoom(1.15));
  $("zoom-out").addEventListener("click", () => viewer.changeZoom(1 / 1.15));
  $("reset-view").addEventListener("click", () => viewer.reset());

  function renderRetainedOutcomes() {
    const area = $("retained-outcome-notes");
    area.replaceChildren();
    area.hidden = !state.retainedOutcomeDrafts.length;
    if (area.hidden) return;
    area.append(node("h3", "", "저장하지 않은 이전 출력 메모"), node("p", "", "저장 위치를 바꿀 때 입력 중이던 내용을 이 화면에 보관했습니다. 원래 작업에 옮기거나 복사한 뒤 보관을 해제하세요. 새 모델에 자동으로 연결하거나 저장하지 않습니다."));
    const labels = { success: "출력 성공 · 입력 중", failure: "출력 실패 · 입력 중", not_tested: "출력 미실시 · 입력 중" };
    for (const draft of state.retainedOutcomeDrafts) {
      const details = node("details", "help-details");
      details.open = true;
      details.append(node("summary", "", draft.title || "이전 작업의 출력 메모"), node("p", "", `원래 저장 위치: ${draft.storage_path}`), node("p", "", `작업 ID: ${draft.job_id} · ${labels[draft.result] || draft.result}`), node("pre", "", draft.notes || "텍스트 메모 없음"));
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

  function detachPreviousStorage(previousPath) {
    if (outcomeHasUnsavedChanges()) {
      state.retainedOutcomeDrafts.push({ job_id: state.job.id, title: state.job.title, storage_path: previousPath, result: $("outcome-result").value, notes: $("outcome-notes").value });
      renderRetainedOutcomes();
    }
    const hadWorkspace = Boolean(state.workspaceId) || workspaceDirty();
    cancelSlicerReads();
    state.job = null;
    state.slicePrepared = false;
    state.slicerSavedText = "";
    state.modelCleanSignature = null;
    viewer.clear();
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
      const llmOption = $("plan-mode").querySelector('option[value="llm"]');
      llmOption.disabled = !state.provider.configured;
      llmOption.textContent = state.provider.configured ? "LLM 모드 · 설정 있음" : "LLM 모드 · 미설정";
      $("provider-note").textContent = state.provider.configured
        ? `LLM ${state.provider.model || "모델"} 설정이 있습니다. 실제 연결과 응답은 요청 시 확인합니다. 기본은 템플릿 모드입니다.`
        : "LLM은 아직 설정되지 않았습니다. 템플릿 모드로 지원하는 물건과 치수를 해석할 수 있습니다.";
      if (!state.template && state.templates.length) applyDraft(state.templates[0].id);
      else renderTemplates();
      setDiscoveryCatalog(data.discovery, Boolean(state.discovery));
      ["plan-button", "review-profile", "compare-offers"].forEach((id) => { $(id).disabled = false; });
      updateWorkflowControls();
      updateWorkspaceStatus();
      await loadWorkspaces();
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
