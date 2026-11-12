(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const state = { token: null, templates: [], template: null, parameters: {}, environment: {}, provider: {}, job: null, slicePrepared: false, workflowBusy: false };
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

  async function api(path, body) {
    const options = { method: body === undefined ? "GET" : "POST", credentials: "same-origin", cache: "no-store", headers: {} };
    if (body !== undefined) {
      if (!state.token) throw new Error("작업 공간에 연결한 뒤 다시 시도해 주세요.");
      options.headers["Content-Type"] = "application/json";
      options.headers["X-Session-Token"] = state.token;
      options.body = JSON.stringify(body);
    }
    let response;
    try { response = await fetch(path, options); }
    catch { throw new Error("로컬 서버에 연결하지 못했습니다. 서버가 실행 중인지 확인해 주세요."); }
    let data;
    try { data = await response.json(); }
    catch { throw new Error(`서버 응답을 읽지 못했습니다. (HTTP ${response.status})`); }
    if (!response.ok) throw new Error(friendly(errorMessage(data.detail || data.message)));
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
    $("save-outcome").disabled = busy || !state.job;
    updateSliceControls();
  }

  function invalidateCurrentJob(message) {
    if (!state.job) return;
    state.job = null;
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
    let parsed;
    try { parsed = JSON.parse(value); }
    catch { throw new Error(`${label}의 JSON 문법을 확인해 주세요. 중괄호와 따옴표가 맞아야 합니다.`); }
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
      button.addEventListener("click", () => { applyDraft(template.id); hideNotice("plan-feedback"); hideNotice("model-feedback"); });
      list.append(button);
    });
  }

  function applyDraft(templateId, parameters) {
    const template = state.templates.find((item) => item.id === templateId);
    if (!template) throw new Error("지원하지 않는 제작 템플릿입니다.");
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

  $("reset-parameters").addEventListener("click", () => { applyDraft(state.template); hideNotice("plan-feedback"); toast("선택한 템플릿의 기본값을 적용했습니다."); });

  $("plan-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    hideNotice("plan-feedback");
    try {
      await withWorkflow($("plan-button"), "요청 해석 중", async () => {
        const result = await api("/api/plan", { text: $("request-text").value, mode: $("plan-mode").value });
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
  });

  $("plan-mode").addEventListener("change", () => {
    $("provider-note").textContent = $("plan-mode").value === "llm"
      ? "LLM 모드에서는 입력한 요청이 설정된 모델 서버로 전송됩니다. 지원 템플릿의 제작안만 받습니다."
      : "템플릿 모드는 지원하는 물건과 치수를 정해진 규칙으로 해석합니다.";
  });

  $("model-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!$("model-form").reportValidity()) return;
    hideNotice("model-feedback");
    const parameters = { template: state.template };
    for (const input of document.querySelectorAll("[data-parameter]")) parameters[input.dataset.parameter] = input.valueAsNumber;
    try {
      await withWorkflow($("generate-button"), "CAD 생성 · 검증 중", async () => {
        const job = await api("/api/models", parameters);
        renderJob(job);
        showNotice("model-feedback", "실제 CAD 모델과 파일을 생성했습니다. 오른쪽에서 형상과 검증 결과를 확인하세요.", "success");
        toast("모델 파일이 준비됐습니다.");
      });
    } catch (error) { showNotice("model-feedback", error.message, "error"); }
  });

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
    state.job = job;
    state.slicePrepared = false;
    $("model-result").hidden = false;
    $("outcome-card").hidden = false;
    $("result-heading").textContent = job.title || "모델 파일이 준비됐어요";
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
    hideNotice("outcome-feedback");
    $("slice-result").replaceChildren();
    showNotice("slice-feedback", state.environment.available ? "전체 설정을 제공하고 실행 계획을 먼저 검토해 주세요." : "Bambu Studio를 사용할 수 없어 현재 환경에서는 슬라이싱을 실행할 수 없습니다.");
    if (job.latest_slice) renderSliceResult(job.latest_slice.plan || {}, job.latest_slice.execution, true);
    updateWorkflowControls();
  }

  function updateSliceControls() {
    const canPrepare = Boolean(state.token && state.job && state.environment.available && !state.workflowBusy);
    if (!$("prepare-slice").dataset.busy) $("prepare-slice").disabled = !canPrepare;
    if (!$("execute-slice").dataset.busy) $("execute-slice").disabled = !canPrepare || !state.slicePrepared;
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

  $("slicer-json").addEventListener("input", () => resetSlicePreparation("전체 설정이 바뀌었습니다. 설정과 실행 계획을 다시 검토해 주세요."));

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
      await withWorkflow(button, execute ? "슬라이싱 실행 중" : "전체 설정 검토 중", async () => {
        const jobId = state.job?.id;
        if (!jobId) throw new Error("먼저 현재 제작안의 모델을 생성해 주세요.");
        const bundle = parseObject($("slicer-json").value, "슬라이서 전체 설정");
        resetSlicePreparation(execute ? "검토한 설정으로 슬라이싱하고 있습니다." : "전체 설정과 실행 계획을 검토하고 있습니다.");
        const response = await api("/api/slice", { job_id: jobId, config_bundle: bundle, execute });
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

  async function readFile(input, textarea, feedbackId) {
    const file = input.files[0];
    if (!file) return;
    try {
      if (file.size > 2 * 1024 * 1024) throw new Error("2MB 이하의 JSON 파일을 선택해 주세요.");
      const text = await file.text();
      if (input.disabled) throw new Error("진행 중인 요청이 끝난 뒤 파일을 다시 선택해 주세요.");
      textarea.value = text;
      textarea.dispatchEvent(new Event("input", { bubbles: true }));
      toast(`${file.name} 파일을 불러왔습니다. 검토 버튼을 눌러 확인하세요.`);
    } catch (error) { showNotice(feedbackId, error.message, "error"); }
  }
  $("profile-file").addEventListener("change", (event) => readFile(event.target, $("profile-json"), "profile-feedback"));
  $("slicer-file").addEventListener("change", (event) => readFile(event.target, $("slicer-json"), "slice-feedback"));

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

  $("profile-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    hideNotice("profile-feedback");
    try {
      await withBusy($("review-profile"), "프로필 검토 중", async () => {
        const profile = parseObject($("profile-json").value, "필라멘트 프로필");
        const setup = {};
        document.querySelectorAll(".setup-grid [name]").forEach((input) => {
          setup[input.name] = input.name === "nozzle_diameter" && input.value !== "" ? input.valueAsNumber : input.value.trim();
        });
        renderProfile(await api("/api/profiles/review", { profile, setup }));
      });
    } catch (error) { showNotice("profile-feedback", error.message, "error"); }
  });
  $("profile-form").addEventListener("input", () => { $("profile-result").hidden = true; });

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

  async function loadHistory() {
    hideNotice("history-feedback");
    const container = $("history-list");
    container.replaceChildren(node("p", "muted", "작업 기록을 불러오는 중입니다."));
    try {
      const result = await api("/api/jobs");
      container.replaceChildren();
      if (!result.jobs?.length) {
        const empty = node("div", "history-empty");
        const button = node("button", "button button-secondary", "첫 모델 만들기 →");
        button.type = "button";
        button.addEventListener("click", () => changeView("models"));
        empty.append(node("h3", "", "아직 만들어 둔 모델이 없어요"), node("p", "", "모델을 생성하면 실제 파일과 검증 상태가 이곳에 기록됩니다."), button);
        container.append(empty);
        return;
      }
      result.jobs.forEach((job) => {
        const card = node("article", "history-item");
        const title = node("div");
        title.append(node("h3", "", job.title || "생성한 모델"), node("p", "", dateTime(job.created_at)));
        const statuses = node("div", "history-statuses");
        const statusLabel = { geometry_validated: "CAD 검증 완료", failed: "모델 생성 실패", generating: "모델 생성 중" }[job.status] || friendly(job.status || "상태 미확인");
        statuses.append(node("span", `badge badge-${job.status === "failed" ? "warning" : job.status === "geometry_validated" ? "blue" : "neutral"}`, statusLabel));
        const outcome = job.user_outcome?.result;
        statuses.append(node("span", `badge badge-${outcome === "success" ? "success" : outcome === "failure" ? "warning" : "neutral"}`, outcome === "success" ? "출력 성공 · 사용자 보고" : outcome === "failure" ? "출력 실패 · 사용자 보고" : "실물 출력 미기록"));
        const open = node("button", "button button-secondary", job.status === "failed" ? "기록 보기 ↗" : "열기 ↗");
        open.type = "button";
        open.disabled = state.workflowBusy;
        open.addEventListener("click", async () => {
          try {
            await withWorkflow(open, "불러오는 중", async () => {
              const full = await api(`/api/jobs/${encodeURIComponent(job.id)}`);
              if (!full.result) {
                const reasons = (full.events || []).filter((entry) => entry.type === "generation_failed").map((entry) => entry.message);
                showNotice("history-feedback", full.status === "failed" ? "모델 생성에 실패한 기록입니다. 원인을 확인하고 치수를 조정해 다시 생성할 수 있습니다." : "이 작업에는 아직 생성된 모델이 없습니다.", full.status === "failed" ? "warning" : "info", reasons);
                return;
              }
              applyDraft(full.result.template, full.result.parameters);
              renderJob(full);
              hideNotice("model-feedback");
              hideNotice("plan-feedback");
              changeView("models");
            });
          } catch (error) { showNotice("history-feedback", error.message, "error"); }
        });
        card.append(node("span", "history-icon", "CAD"), title, statuses, open);
        container.append(card);
      });
    } catch (error) { container.replaceChildren(); showNotice("history-feedback", error.message, "error"); }
  }
  $("refresh-history").addEventListener("click", loadHistory);

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

  async function bootstrap() {
    $("bootstrap-error").hidden = true;
    try {
      const data = await api("/api/bootstrap");
      state.token = data.session_token;
      state.templates = data.templates || [];
      state.environment = data.environment || {};
      state.provider = data.provider || {};
      const name = data.app?.name || "3D Printer Agent";
      $("brand-name").textContent = name.replace(/^3D\s+/i, "");
      document.title = `${name} · 로컬 작업 공간`;
      $("app-version").textContent = data.app?.version ? `Version ${data.app.version}` : "버전 정보 없음";
      const available = Boolean(state.environment.available);
      setBadge("environment-badge", available ? "Bambu Studio 감지됨" : "슬라이서 사용 불가", available ? "blue" : "neutral");
      setBadge("slicer-status", available ? "실행 파일 감지됨" : "현재 환경에서 사용 불가", available ? "blue" : "neutral");
      $("slicer-description").textContent = available
        ? "Bambu Studio 실행 파일을 찾았습니다. 모델과 전체 설정을 검토한 뒤 슬라이싱을 준비할 수 있습니다."
        : "현재 환경에서 Bambu Studio를 사용할 수 없습니다. 생성한 파일은 내려받을 수 있고, 이곳의 슬라이싱 실행은 비활성화되어 있습니다.";
      if (!available && state.environment.diagnostics?.length) showNotice("slice-feedback", "환경 확인 사항", "info", state.environment.diagnostics);
      const llmOption = $("plan-mode").querySelector('option[value="llm"]');
      llmOption.disabled = !state.provider.configured;
      llmOption.textContent = state.provider.configured ? "LLM 모드 · 설정 있음" : "LLM 모드 · 미설정";
      $("provider-note").textContent = state.provider.configured
        ? `LLM ${state.provider.model || "모델"} 설정이 있습니다. 실제 연결과 응답은 요청 시 확인합니다. 기본은 템플릿 모드입니다.`
        : "LLM은 아직 설정되지 않았습니다. 템플릿 모드로 지원하는 물건과 치수를 해석할 수 있습니다.";
      if (!state.template && state.templates.length) applyDraft(state.templates[0].id);
      else renderTemplates();
      ["plan-button", "review-profile", "compare-offers"].forEach((id) => { $(id).disabled = false; });
      updateWorkflowControls();
    } catch (error) {
      $("bootstrap-error").hidden = false;
      $("bootstrap-error-detail").textContent = error.message;
      setBadge("environment-badge", "서버 연결 확인 필요", "warning");
    }
  }
  $("retry-bootstrap").addEventListener("click", bootstrap);
  renderOfferRows();
  bootstrap();
})();
