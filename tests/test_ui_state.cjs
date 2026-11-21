// Controller state checks using DOM doubles; this is not a browser/layout test.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync('print_agent/static/app.js', 'utf8');
const names = ['newPlanHasPendingWork','retainOutcomeDraft','renderRetainedOutcomes','detachPreviousStorage','updateConnectionActions','renderConnection','connectionFailed','modelHasUnsavedChanges','slicerHasUnsavedChanges','outcomeHasUnsavedChanges','hasPendingWork','replacementSignature','cancelModelReplacement','requestModelReplacement','confirmModelReplacement','performModelReplacement','updateHistoryControls','openHistoryJob','renderHistory','errorMessage','api','node','friendly','showNotice','hideNotice','setBadge','withBusy','withWorkflow','updateWorkflowControls','invalidateCurrentJob','applyDraft','metric','localDownload','renderDownloads','renderJob','updateSliceControls','renderSliceResult','resetSlicePreparation','parseObject','runSlice','dateTime','loadHistory','cancelSlicerReads','renderSlicerFiles','slicerBundle','checkSlicerBundleSize','readSlicerFiles','changeSlicerPlate','assembleSlicerBundle','cancelSlicerAssembly','manualSlicerChanged','readSlicerBundle','renderSlicerEnvironment','probeSlicer','discoverySignature','discoveryQuery','discoveryFiltersChanged','setDiscoveryCatalog','renderDiscovery','renderProjectDetail','renderProjectSource','updateDiscoveryControls','browseProject','draftHasChanges','requestProjectApplication','confirmProjectApplication','cancelProjectApplication','applyProject','detachProjectSource','recommendProjects','modelDraftSignature','preparePlan','generateModel','bootstrap'];
const studioNames = ['studioSourceIdentity','studioModelSignature','studioContext','studioContextCurrent','studioSourceCurrent','studioHasUnsavedChanges','invalidateStudioRequests','renderStudioSource','renderStudioProject','importStudioProject','cancelStudioCandidate','applyStudioCandidate','revalidateStudioProject','runStudioSlice','studioSettingsIdentity','studioSettingsDirty','renderStudioSettings','openStudioSettings','editStudioSetting','reviewStudioSettings','applyStudioSettings','cancelStudioSettings','resetStudioSettings','renderStudioChanges'];
names.push(...studioNames);
names.push('renderPrintVolumeReview','readParameter','parameterInputComplete','parameterField','stepParameter','syncParameterSlider','currentParameterSnapshot','parseParameterText','copyParameters','openPastePanel','applyPastedParameters','renderSetupPrinterFill','currentModelMaterial','renderOffersModelHint','renderOutcomePrinterHint','historyMatches','historyFacts','setHistoryFilter','renderPrintability','printerReportedNozzle','updatePrintabilityControls','recheckPrintability','journeySteps','journeyNext','renderJourney','goToJourneyTarget','templateSizeText','renderColorLegend','colorField','chooseColor','printSendReady','resetPrintSend','printSendTarget','updatePrintSendControls','printSendSlotChoice','renderPrintSendSlots','renderPrintSendSummary','reviewPrintSend','startPrintSend','renderPrintSendResult','currentPrinterTarget','syncPrintSend','setStoreGuide','storeMatches','storeLink','renderStoreGuide','loadSavedPrinters','storeSavedPrinters','rememberPrinter','forgetPrinter','renderSavedPrinters','stopPrintFollow','renderPrintFollow','pollPrintFollow','linkPrinterReport','startPrintFollow','updatePrintControls','askPrintStop','sendPrintControl','setFailureReasons','selectedOutcomeReasons','syncOutcomeReasons','loadRecovery','renderRecovery','proposeRecoveryEdit','checkForUpdate','syncRadioGroup','radioGroupKey','collectMeasurements','fillMeasurements','renderMeasurementReview','loadAttempts','attemptFacts','attemptSliceText','renderAttempts','projectSizeText','updateImportControls','placedPreview','importOrientationText','renderSliceComparison','applySliceVariant','loadInventory','spoolLabel','renderInventory','spoolFormValues','editSpool','resetSpoolForm','saveSpool','spoolAction','renderOutcomeSpool','useSpoolForJob','setGlossary','glossaryTerm','glossaryMatches','renderGlossary','renderOnboarding','showGlossaryTerm','enhanceTerms','openTerm','closeTerm','welcomeDismissed','renderWelcome','dismissWelcome','slotPosition','sendChoicePosition','positionLabel','spoolInSlot','materialBase','renderPrinterSlotLinks','linkSpoolToSlot','renderPrintSendSpools','sentSpoolForJob');
const editNames = ['parameterKeys','modelGeometrySignature','modelEditScope','currentEditParameters','modelEditParentJob','validateEditParameters','validateModelEditResponse','renderModelEdit','cancelModelEdit','modelEditInputChanged','manualModelChanged','planModelEdit','applyModelEdit','renderModelEditRecord'];
names.push(...editNames.filter(name => new RegExp('^  (?:async )?function '+name+'\\(', 'm').test(source)));
const libraryNames = ['studioLibraryScope','studioWorkspaceSnapshot','studioWorkspaceSignature','studioWorkspaceDirty','renderStudioLibrary','loadStudioLibrary','validateStudioWorkspace','openStudioLibrary','saveStudioWorkspace','deleteStudioWorkspace','studioLibrarySelectionChanged'];
names.push(...libraryNames.filter(name => new RegExp('^  (?:async )?function '+name+'\\(', 'm').test(source)));
class Element {
  constructor() { this.children=[]; this.dataset={}; this.disabled=false; this.hidden=false; this.value=''; this._text=''; this.attributes={}; this.style={setProperty(name,value){this[name]=value;}}; this.listeners={}; this.classList={add(){},remove(){},toggle(){}}; }
  set textContent(value) { this._text=String(value); this.children=[]; }
  get textContent() { return this._text + this.children.map(x=>x.textContent || '').join(' '); }
  append(...nodes) { this.children.push(...nodes); }
  replaceChildren(...nodes) { this._text=''; this.children=nodes; }
  setAttribute(name,value) { this.attributes[name]=value; }
  getAttribute(name) { return Object.hasOwn(this.attributes,name) ? this.attributes[name] : null; }
  removeAttribute(name) { delete this.attributes[name]; }
  querySelector() { return new Element(); }
  querySelectorAll(selector) {
    // Enough for role lookups: walk descendants and match [role="..."].
    const role = /\[role="([^"]+)"\]/.exec(selector)?.[1];
    const found = [];
    const walk = (node) => { for (const child of node.children || []) { if (child instanceof Element) { if (!role || child.attributes.role === role) found.push(child); walk(child); } } };
    walk(this);
    return found;
  }
  addEventListener(name,callback) { this.listeners[name]=callback; }
  focus() {}
  checkValidity() { return !this.validity || this.validity.valid !== false; }
  reportValidity() { return this.checkValidity(); }
}
function fixture() {
  const ids = new Map();
  const $ = id => { if (!ids.has(id)) ids.set(id,new Element()); return ids.get(id); };
  const context = {
    $, console, URL, Intl, Number, Math, JSON, Object, Array, String, Error, Blob, TextEncoder, Uint8Array, btoa, Event:class { constructor(type){ this.type=type; } },
    state:{offersResult:null,historyFilter:'all',downloadedJobId:null,printabilityReview:null,printabilityRequest:0,printabilityPending:false,printabilityNozzle:0.4,printabilityShown:false,printerStatus:null,offersRevision:0,offersPending:false,retainedOutcomeDrafts:[],connectionState:'connected',connectionEpoch:0,bootstrapPending:false,storage:null,modelCleanSignature:null,modelReplacement:null,modelTransitionRequest:0,slicerSavedText:'',historyItems:[],historyLoaded:false,historyRequest:0,historyPending:false,historyCursor:null,token:'test-token',templates:[{id:'tray',defaults:{width:120},editable_fields:['width'],description:'Tray'},{id:'cable_comb',defaults:{width:80},editable_fields:['width'],description:'Cable'}],template:'tray',parameters:{width:120},environment:{available:true},job:null,slicePrepared:false,workflowBusy:false,slicerFiles:{machine:null,process:null,filaments:[]},slicerStaged:false,slicerContext:0,slicerRequests:{},slicerPending:{},discovery:null,discoveryPurpose:'all',discoveryMatches:[],discoveryBrowsed:null,discoveryPending:false,discoveryRequest:0,discoveryEpoch:0,discoveryRevision:0,projectSource:null,projectReplacement:null,bootstrapRequest:0},
    fields:{width:{label:'width',min:10,max:500,step:0.1}},fieldNames:{},numberFormat:new Intl.NumberFormat('en'),
    document:{createElement:()=>new Element(),querySelectorAll:()=>[],querySelector:()=>null},window:{location:{origin:'http://localhost'},setTimeout,clearTimeout,confirm:()=>true},
    viewer:{setMesh(){},clear(){this.mesh=null;},forgetPrevious(){this.forgotten=true;},mesh:'old'},workspaceDirty(){return false;},renderTemplates(){},toast(){},updateWorkspaceStatus(){},loadWorkspaces:async()=>{},
  };
  $('parameter-width').value='120';$('outcome-result').value='not_tested';$('offer-currency').value='KRW';
  vm.createContext(context);
  for (const name of ['printabilityStatus','printabilityMarks','templateFieldLabels']) vm.runInContext(new RegExp('^  const '+name+' = .*$','m').exec(source)[0],context);
  // Multi-line editing-panel constants are evaluated from their declaration to the closing brace.
  for (const name of ['fieldDescriptions','PALETTE']) { const start=source.indexOf('  const '+name+' = {'); vm.runInContext(source.slice(start, source.indexOf('\n  };', start)+5), context); }
  for (const name of ['templateFieldDescriptions','fieldNudges','fieldGroups','PARAMETER_FORMAT','TEXT_PARAMETERS','COLOR_PARAMETERS','STRING_PARAMETERS']) vm.runInContext(new RegExp('^  const '+name+' = .*$','m').exec(source)[0],context);
  for (const name of names) {
    const match = new RegExp('^  (?:async )?function '+name+'\\(', 'm').exec(source);
    if (!match) throw new Error('Missing controller function: '+name);
    const tail=source.slice(match.index), end=/\n  \}(?=\n|$)/.exec(tail);
    vm.runInContext(tail.slice(0,end.index+4),context);
  }
  // Load actual offer event wiring as well as its controller functions.
  vm.runInContext(source.slice(source.indexOf('  function renderOfferRows()'),source.indexOf('  function dateTime(')),context);
  Object.assign(context.state,{studioSettingsOpen:false,studioSettingsDescriptor:null,studioSettingsDraft:null,studioSettingsReview:null,studioSettingsReviewContext:null,studioSettingsPending:false,studioSettingsApplied:null,studioSettingsCandidate:null,studioSettingsRecorded:null,studioSettingsRecordedReview:null,studioRequest:0,studioRevision:0,studioPending:false,studioCandidate:null,studioCandidateEpoch:null,studioCandidateStorage:null,studioApplied:null,studioAppliedEpoch:null,studioAppliedStorage:null,studioRecorded:null,studioSlicePrepared:false,studioPreparedSignature:null,studioSavedIdentity:null});
  return context;
}
function printerFixture() {
  const c=fixture();
  Object.assign(c.state,{printerPins:{},printerStatus:null,printerRequest:0});
  vm.runInContext(/^  const printerNozzleTypes = .*$/m.exec(source)[0],c);
  vm.runInContext(/^  const printerConnectionTones = .*$/m.exec(source)[0],c);
  for(const name of ['printerTarget','printerPinKey','updatePrinterControls','selectPrinterDevice','renderPrinterDevices','printerNumber','printerTemperature','renderPrinterStatus','discoverPrinters','checkPrinterStatus','printerInputChanged','clearPrinterPin','metric','dateTime']) {
    const match=new RegExp('^  (?:async )?function '+name+'\\(', 'm').exec(source);
    if(!match)throw new Error('Missing printer controller function: '+name);
    const tail=source.slice(match.index),end=/\n  \}(?=\n|$)/.exec(tail);
    vm.runInContext(tail.slice(0,end.index+4),c);
  }
  c.$('printer-host').value='192.168.0.20';c.$('printer-serial').value='01s00test000001';c.$('printer-access-code').value='SECRET-CODE';
  return c;
}
function printerReport(overrides={}) {
  return {schema_version:1,observed_at:'2026-11-16T00:00:00Z',target:{host:'192.168.0.20',serial:'01S00TEST000001',port:8883},
    connection:{state:'reporting',detail:'프린터가 현재 상태를 보고했습니다.'},certificate:{sha256:'a'.repeat(64),issuer_verified:false,pinned:false,matches_pin:null},
    identity:{product_name:'Bambu Lab P1S',firmware:'01.08.00.00',modules:[]},
    print:{state:'RUNNING',state_label:'출력 중',progress_percent:42,remaining_minutes:37,layer:51,total_layers:120,error_code:0,hms:[{hms_code:'0700_8000_0002_0001'}],
      temperatures_c:{nozzle:219.6,nozzle_target:220,bed:55,bed_target:55,chamber:null},nozzle:{diameter_mm:0.4,type:'stainless_steel'},
      material_slots:[{unit:0,slot:0,material:'PLA',product:'PLA Basic',color:'FFFFFFFF',filament_id:'GFA00'},{unit:0,slot:1,empty:true}]},
    scope:'읽기 전용',...overrides};
}
function profileFixture() {
  const context=fixture();
  Object.assign(context.state,{profileDocuments:[],profileTarget:0,profileRevision:0,profileImport:0,profileReport:null,profileDownloadUrl:null,guidedEdits:{},guidedSources:{},workspaceId:null,workspaceRevision:null,workspaceSavedSignature:null,workspaceEpoch:0,workspaceEdits:0,workspaceListRequest:0,workspaceBusy:false,workspaces:[]});
  for(const name of ['profileName','sameJson','profileDocument','invalidateProfile','renderProfileLibrary','renderProfileOrigin','beginProfileImport','currentProfileImport','appendProfileDocuments','profileImportSummary','importProfileFiles','importProfileArchive','selectProfileTarget','clearProfileLibrary','reviewProfile','renderProfileResolution','renderProfileEvidenceChanges','profileSetupFields','captureProfileSnapshot','workspaceSignature','workspaceDirty','markWorkspaceChanged','updateWorkspaceStatus','loadWorkspaces','saveWorkspace','restoreWorkspace','openWorkspace','newWorkspace','deleteWorkspace','guidedFieldDefinitions','numericSetting','profileSettings','evidenceFieldDefinitions','stageGuidedInput','renderEvidenceEditor','renderGuidedEditor','applyGuidedEdits','removeGuidedOverride','adoptProfileText','removeProfileDocument','restoreProfileOriginal']) {
    const match=new RegExp('^  (?:async )?function '+name+'\\(', 'm').exec(source);
    if(!match)throw new Error('Missing profile controller function: '+name);
    const tail=source.slice(match.index),end=/\n  \}(?=\n|$)/.exec(tail);
    vm.runInContext(tail.slice(0,end.index+4),context);
  }
  context.$('setup-identity').value='unknown';
  context.state.workspaceSavedSignature=context.workspaceSignature();
  return context;
}
function offersFixture() {
  const c=profileFixture(),rows=[];
  for(let index=1;index<=3;index++) {
    const row=new Element();row.dataset.offer=String(index);
    const fields=['name','price','grams','shipping'].map(key=>{const input=c.$(`offer-${index}-${key}`);input.dataset.offerField=key;return input;});
    row.querySelectorAll=()=>fields;row.append(...fields);rows.push(row);
  }
  c.document.querySelectorAll=selector=>selector==='[data-offer]'?rows:[];
  c.$('compare-offers').form={elements:[...rows.flatMap(row=>row.children),c.$('offer-currency'),c.$('compare-offers')]};
  c.$('offers-result').hidden=true;c.$('offers-feedback').hidden=true;
  c.submitOffers=()=>c.$('offers-form').listeners.submit({preventDefault(){}});
  c.editOffer=(id,value,validity)=>{c.$(id).value=value;if(validity)c.$(id).validity=validity;c.$('offers-form').listeners.input();};
  c.fillOffer=()=>{c.$('offer-1-name').value='Current product';c.$('offer-1-price').value='1000';c.$('offer-1-grams').value='1000';};
  c.exitIsProtected=()=>{
    let handler,prevented=false;c.window.addEventListener=(name,callback)=>{if(name==='beforeunload')handler=callback;};
    const start=source.indexOf('  window.addEventListener("beforeunload"'),end=source.indexOf('  window.addEventListener("pagehide"',start);
    vm.runInContext(source.slice(start,end),c);handler({preventDefault(){prevented=true;}});return prevented;
  };
  return c;
}
const offerReply = (name='Compared product',currency='KRW') => ({groups:{[currency]:[{name,price:1000,grams:1000,shipping:null,delivered_total:null,price_per_kg:null,product_price_per_kg:1000}]},notice:'User-entered comparison; not saved.'});
const plain = value => JSON.parse(JSON.stringify(value));
const workspaceRecord = (snapshot, overrides={}) => ({id:'a'.repeat(32),title:'Saved filament',revision:1,created_at:'2026-11-13T00:00:00Z',updated_at:'2026-11-13T00:00:00Z',document_count:snapshot.documents.length,snapshot,...overrides});
const archiveOrigin = () => ({type:'bambu_preset_archive',archive_name:'synthetic.bbsflmt',archive_sha256:'a'.repeat(64),member_path:'Example/Child.json',member_sha256:'b'.repeat(64)});
const archiveResult = () => {
  const draft_text=' {\n "name": "Child", "filament_settings_id": ["Child"], "inherits": "Missing parent", "nozzle_temperature": ["215"]\n}\n';
  return {schema_version:1,archive:{filename:'synthetic.bbsflmt',sha256:'a'.repeat(64),format:'bbsflmt'},documents:[{filename:'Example/Child.json',profile:JSON.parse(draft_text),draft_text,origin:archiveOrigin()}],ignored_members:[{path:'printer/Printer.json',reason:'프린터 설정'}],warnings:['사용자가 제공한 파일입니다.']};
};
const archiveInput = () => ({files:[{name:'synthetic.bbsflmt',size:3,arrayBuffer:async()=>new Uint8Array([80,75,3]).buffer}],value:'synthetic.bbsflmt'});
function findElement(element, predicate) {
  if(predicate(element))return element;
  for(const child of element.children || []) {const found=findElement(child,predicate);if(found)return found;}
}
function guidedInput(context, key) {
  const input=['profile-guided-fields','profile-evidence-scope','profile-evidence-source']
    .map(id=>findElement(context.$(id),element=>element.dataset.guided===key)).find(Boolean);
  assert(input,`The selected profile exposes an input for ${key}`);
  return input;
}
function editGuided(context, key, value) {
  const input=guidedInput(context,key);assert.equal(input.disabled,false,`${key} is editable`);
  input.value=value;input.listeners.input();
  return input;
}
function selectedProfile(context, profile, origin) {
  const draftText=` ${JSON.stringify(profile)}\n`;
  context.state.profileDocuments=[{filename:'selected.json',profile,draftText,...(origin?{origin}: {})}];
  context.$('profile-json').value=draftText;
  context.renderGuidedEditor();
  context.state.workspaceSavedSignature=context.workspaceSignature();
  return draftText;
}
const project = (id='idea') => ({id,title:'Idea title',template:'tray',purpose:'organization',parameters:{template:'tray',width:90,depth:60,height:18},description:'Original idea',reason:'Useful',measurements:['Measure'],limits:['Not tested'],recipe_sha256:'a'.repeat(64),source:{kind:'repository_original',repository:'https://github.com/uulab-official/3d-printer-agent',path:'print_agent/geometry.py',creator:'uulab-official',license:'MIT'}});
const job = () => ({
  id:'job-a',title:'Tray',artifacts:{stl:'/api/jobs/job-a/files/stl',sliced_three_mf:'/api/jobs/job-a/files/sliced_three_mf'},
  result:{template:'tray',parameters:{width:120},dimensions_mm:{x:120,y:80,z:35},volume_mm3:45072,geometry_status:'validated',checks:[],warnings:[],mesh:{vertices:[],faces:[]}},
  latest_slice:null,user_outcome:null,
});
const studioInspection = (id='a'.repeat(32), overrides={}) => ({schema_version:1,source_id:id,archive_url:`/api/studio-projects/${id}/archive`,source:{filename:'Studio 원본.3mf',bytes:3,sha256:'c'.repeat(64)},producer:{application:'BambuStudio-02.09.01.70',format_version:'1',settings_version:'02.09.01.70'},settings_sha256:'d'.repeat(64),summary:{printer_model:'Fixture Printer',printer_preset:'Fixture Printer 0.4',process_preset:'Fixture process',nozzle_diameter:'0.4',plate_type:'Textured PEI Plate',filament_name:'Fixture filament',filament_type:'PLA',nozzle_temperature:'215',nozzle_temperature_initial_layer:'220',bed_temperature:'55',bed_temperature_initial_layer:'55',filament_flow_ratio:'0.98',filament_max_volumetric_speed:'12'},supported:true,issues:[],warnings:['프로젝트의 기록이며 실제 장착 상태는 확인하지 않았습니다.'],...overrides});
const studioInput = (name='Studio 원본.3mf') => ({files:[{name,size:3,arrayBuffer:async()=>new Uint8Array([80,75,3]).buffer}],value:name});
function studioApplied(c, inspection=studioInspection()) {
  c.state.studioApplied=inspection;c.state.studioAppliedEpoch=c.state.connectionEpoch;c.state.studioAppliedStorage=c.state.storage?.path || null;
}
const studioDescriptor=()=>({schema_version:1,source_id:'a'.repeat(32),source_sha256:'c'.repeat(64),settings_sha256:'d'.repeat(64),source_summary:studioInspection().summary,warnings:[],fields:['nozzle_temperature','nozzle_temperature_initial_layer','filament_flow_ratio','filament_max_volumetric_speed','bed_temperature','bed_temperature_initial_layer'].map(key=>({key,native_key:key,label:key,unit:'',kind:'integer',original:studioInspection().summary[key],value:studioInspection().summary[key],minimum:1,maximum:360,exclusive_minimum:false}))});
const studioReview=()=>({schema_version:1,source_id:'a'.repeat(32),source_sha256:'c'.repeat(64),settings_sha256:'d'.repeat(64),effective_settings_sha256:'f'.repeat(64),review_sha256:'1'.repeat(64),values:{nozzle_temperature:'216'},changes:[{field:'nozzle_temperature',native_key:'nozzle_temperature',before:['215'],after:['216']}],changed_count:1,provenance:'user_selected',effective_summary:{...studioInspection().summary,nozzle_temperature:'216'}});
const studioEnvelope=(id='e'.repeat(32))=>({source:studioInspection(),review:studioReview(),revision:{schema_version:1,revision_id:id,source_id:'a'.repeat(32),effective_settings_sha256:'f'.repeat(64),review_sha256:'1'.repeat(64),proposal:{source_sha256:'c'.repeat(64),settings_sha256:'d'.repeat(64),values:{nozzle_temperature:'216'}},changes:studioReview().changes,provenance:'user_selected'}});
const studioNamed=(edited=false,draft=null)=>({source:studioInspection(),settings_revision:edited?studioEnvelope():null,editor:studioDescriptor(),workspace:{id:'b'.repeat(32),title:'Saved Studio',revision:2,created_at:'2026-11-15T00:00:00Z',updated_at:'2026-11-15T00:00:00Z',snapshot:{schema_version:1,source_id:'a'.repeat(32),settings_revision_id:edited?'e'.repeat(32):null,source_sha256:'c'.repeat(64),settings_sha256:'d'.repeat(64),effective_settings_sha256:edited?'f'.repeat(64):'d'.repeat(64),draft_values:draft}}});
const editBase=()=>({template:'tray',width:150,depth:90,height:30,wall:2,bottom:2,dividers:2,slots:5,cable_diameter:6,inset_diameter:52,inset_depth:2,fit_clearance:0.3});
function editFixture() {
  const c=fixture(),base=editBase(),editable=['width','depth','height','wall','bottom','dividers'];
  c.state.templates=[{id:'tray',defaults:base,editable_fields:editable,description:'tray'}];c.state.parameters=base;c.state.projectSource=project();c.state.storage={path:'/original'};
  for(const key of editable){c.$(`parameter-${key}`).value=String(base[key]);c.$(`parameter-${key}`).valueAsNumber=base[key];}
  c.$('model-edit-text').value='높이를 5mm 늘려줘';c.$('model-edit-mode').value='templates';
  c.document.querySelectorAll=selector=>selector==='[data-parameter]'?editable.map(key=>Object.assign(c.$(`parameter-${key}`),{dataset:{parameter:key}})):[];
  return c;
}
const editReply=(parent=null)=>({status:'ready',engine:'template_rules',capability:'current_template_parameters_only',message:'review',questions:[],assumptions:[],review:{schema_version:1,selection:{schema_version:1,request_text:'높이를 5mm 늘려줘',base_parameters:editBase(),operations:[{field:'height',op:'add',value:5}],parent},base_sha256:'1'.repeat(64),parameters:{...editBase(),height:35},parameters_sha256:'2'.repeat(64),changes:[{field:'height',before:30,after:35}],review_sha256:'3'.repeat(64)}});
const printVolumeReport = (overrides={}) => ({
  schema_version:1,status:'needs_review',can_prepare:false,scope:'upright_bounding_box_0_90',
  model_dimensions_mm:[120,80,35],recorded_volume_mm:[100,100,200],
  orientations:[{rotation_degrees:0,fits:false},{rotation_degrees:90,fits:false}],
  placement_mm:null,rotation_degrees:null,placement_applied:false,
  issues:[{code:'placement_unconfirmed',message:'가로 120 mm인 현재 CAD의 0°·90° 배치를 기록된 100 × 100 mm 공간에서 확인하지 못했습니다.'}],
  limitations:['브림과 서포트에 필요한 공간은 비교하지 않았습니다.'],tolerance_mm:0.000001,
  model_sha256:'a'.repeat(64),settings_sha256:'b'.repeat(64),...overrides,
});
(async()=>{
  let failed=0,passed=0;
  async function check(name,test) {
    let deadline;
    try { await Promise.race([Promise.resolve().then(test),new Promise((_,reject)=>{deadline=setTimeout(()=>reject(new Error('Controller check timed out')),5000);})]); passed++; console.log('PASS',name); }
    catch(error) { failed++; console.log('FAIL',name,error.message); }
    finally { clearTimeout(deadline); }
  }
  await check('Blocked size preparation displays the actual CAD, recorded volume and limited orientation results',()=>{
    const c=fixture(),report=printVolumeReport();
    c.renderSliceResult({kind:'studio_project',ready:false,project_prepared:false,print_volume:report,diagnostics:[]});
    const review=findElement(c.$('slice-result'),element=>element.id==='print-volume-review');
    assert(review,'The preparation result exposes its size review');
    assert.match(review.textContent,/현재 CAD와 기록된 출력 크기/);
    assert.match(review.textContent,/배치 추가 확인 필요/);
    assert.match(review.textContent,/현재 CAD.*120.*80.*35/);
    assert.match(review.textContent,/설정에 기록된 출력 공간.*100.*100.*200/);
    assert.match(review.textContent,/0°.*범위 내 배치 미확인/);
    assert.match(review.textContent,/90°.*범위 내 배치 미확인/);
    assert.match(review.textContent,/가로 120 mm인 현재 CAD/);
    assert.match(review.textContent,/다른 각도의 배치는 확인하지 않았습니다/);
    assert.match(review.textContent,/브림과 서포트/);
  });
  await check('Passing 90-degree size review also renders for manual settings without claiming an applied placement',()=>{
    const c=fixture(),report=printVolumeReport({status:'fits',can_prepare:true,recorded_volume_mm:[90,130,200],
      orientations:[{rotation_degrees:0,fits:false},{rotation_degrees:90,fits:true}],placement_mm:[5,5,0],rotation_degrees:90,issues:[]});
    c.renderSliceResult({ready:true,print_volume:report,diagnostics:[]});
    const review=findElement(c.$('slice-result'),element=>element.id==='print-volume-review');
    assert(review,'Manual full-config preparation exposes the same size review');
    assert.match(review.textContent,/기록된 출력 공간과 크기 비교 완료/);
    assert.match(review.textContent,/90°.*크기 비교 통과/);
    assert.match(review.textContent,/회전이나 배치를 적용하지 않았습니다/);
    assert.match(review.textContent,/실물 출력/);
    assert.doesNotMatch(review.textContent,/출력 성공|출력 가능 확정|배치 적용 완료/);
  });
  await check('Height overflow and unknown recorded dimensions stay distinguishable from zero or a successful fit',()=>{
    const c=fixture();
    c.renderSliceResult({ready:false,print_volume:printVolumeReport({status:'height_exceeded',recorded_volume_mm:[null,null,30],orientations:[],
      issues:[{code:'height_exceeded',message:'현재 CAD 높이 35 mm가 기록된 출력 높이 30 mm를 초과합니다.'}]})});
    const review=findElement(c.$('slice-result'),element=>element.id==='print-volume-review');
    assert(review,'A height rejection keeps the numeric comparison visible');
    assert.match(review.textContent,/기록된 출력 높이 초과/);
    assert.match(review.textContent,/설정에 기록된 출력 공간.*미확인.*미확인.*30/);
    assert.match(review.textContent,/높이 35 mm.*높이 30 mm/);
    assert.doesNotMatch(review.textContent,/0°.*크기 비교 통과|90°.*크기 비교 통과/);
  });
  await check('Current and recorded size reviews preserve height differences at the comparison tolerance',()=>{
    for(const recorded of [false,true])for(const [height,display] of [[11.999,'11.999'],[11.999998999,'11.999998999']]) {
      const c=fixture();c.numberFormat=new Intl.NumberFormat('ko-KR',{maximumFractionDigits:2});
      c.renderSliceResult({ready:false,print_volume:printVolumeReport({status:'height_exceeded',model_dimensions_mm:[120,80,12],
        recorded_volume_mm:[200,200,height],orientations:[],issues:[{code:'height_exceeded',message:'기록된 출력 높이를 초과합니다.'}]})},null,recorded);
      const review=findElement(c.$('slice-result'),element=>element.id==='print-volume-review');
      const modelRow=findElement(review,element=>element.children?.[0]?.textContent===(recorded?'기록된 CAD':'현재 CAD'));
      const volumeRow=findElement(review,element=>element.children?.[0]?.textContent==='설정에 기록된 출력 공간');
      assert.equal(modelRow.children[3].textContent,'12');
      assert.equal(volumeRow.children[3].textContent,display,'The compared height must not round up to the model height');
      assert.match(review.textContent,/기록된 출력 높이 초과/);
      assert.equal(c.numberFormat.format(height),'12','Other display formatting keeps its existing precision');
    }
  });
  await check('The size-review action focuses dimension editing without replacing current CAD, selected settings or notes',()=>{
    const c=fixture();c.renderJob(job());studioApplied(c);
    c.$('parameter-width').value='0120.0';c.$('outcome-notes').value=' keep this note\n';c.$('slicer-json').value='{ unfinished';
    const before=plain({job:c.state.job,source:c.state.studioApplied,width:c.$('parameter-width').value,notes:c.$('outcome-notes').value,json:c.$('slicer-json').value});
    let focused=false,scrolled=false;
    c.$('parameter-heading').focus=()=>{focused=true;};
    c.$('parameter-heading').scrollIntoView=()=>{scrolled=true;};
    c.renderSliceResult({ready:false,print_volume:printVolumeReport()});
    const action=findElement(c.$('slice-result'),element=>element.textContent==='현재 치수 수정하기');
    assert(action,'A current size review provides a direct path to the existing dimension editor');
    action.listeners.click();
    assert.equal(focused,true);assert.equal(scrolled,true);
    assert.deepEqual(plain({job:c.state.job,source:c.state.studioApplied,width:c.$('parameter-width').value,notes:c.$('outcome-notes').value,json:c.$('slicer-json').value}),before);
  });
  await check('History labels its size review as recorded and never presents the current-edit action',()=>{
    const c=fixture(),archived={...job(),latest_slice:{phase:'complete',plan:{kind:'studio_project',ready:false,project_prepared:false,
      project_source:studioInspection(),print_volume:printVolumeReport(),diagnostics:[]},execution:null}};
    c.renderJob(archived);
    const review=findElement(c.$('slice-result'),element=>element.id==='print-volume-review');
    assert(review,'History retains its recorded size comparison');
    assert.match(review.textContent,/이 작업에 기록된 출력 크기 비교/);
    assert.match(review.textContent,/현재 입력을 다시 비교한 결과가 아닙니다/);
    assert.equal(findElement(review,element=>element.textContent==='현재 치수 수정하기'),undefined);
    assert.equal(c.state.studioApplied,null);assert.equal(c.$('execute-studio-project').disabled,true);
  });
  await check('Changing CAD, manual settings or selected Studio source clears a current size review and prepared downloads',()=>{
    for(const change of ['cad','manual','source']) {
      const c=fixture();c.state.job={...job(),artifacts:{prepared_three_mf:'/api/jobs/job-a/files/prepared_three_mf'}};studioApplied(c);
      c.renderSliceResult({kind:'studio_project',ready:true,project_prepared:true,print_volume:printVolumeReport({status:'fits',can_prepare:true,issues:[]}),diagnostics:[]});
      assert(findElement(c.$('slice-result'),element=>element.id==='print-volume-review'),`${change} starts with a visible review`);
      if(change==='cad')c.invalidateCurrentJob('CAD changed');
      else if(change==='manual')c.manualSlicerChanged();
      else {c.state.studioCandidate=studioInspection('b'.repeat(32));c.state.studioCandidateEpoch=c.state.connectionEpoch;c.state.studioCandidateStorage=null;c.applyStudioCandidate();}
      assert.equal(findElement(c.$('slice-result'),element=>element.id==='print-volume-review'),undefined,`${change} clears stale size evidence`);
      assert.equal(c.state.job?.artifacts.prepared_three_mf,undefined);assert.equal(c.state.studioSlicePrepared,false);
    }
  });
  await check('Studio summary exposes recorded height while keeping raw area points separate from derived dimensions',()=>{
    const c=fixture(),inspection=studioInspection();inspection.summary.printable_height='180';inspection.summary.printable_area=['5x8','115x8','115x208','5x208'];
    c.renderStudioSource(c.$('studio-project-candidate'),inspection,'Candidate');
    assert.match(c.$('studio-project-candidate').textContent,/기록된 출력 높이.*180/);
    assert.match(c.$('studio-project-candidate').textContent,/5x8/);
    assert.doesNotMatch(c.$('studio-project-candidate').textContent,/110 × 200/);
  });
  await check('Contextual proposal leaves exact draft and source untouched until explicit apply, then sends selection provenance',async()=>{
    const c=editFixture();assert.equal(typeof c.planModelEdit,'function');c.$('parameter-width').value='0150.0';const source=c.state.projectSource;let body;c.api=async(path,payload)=>{body=plain(payload);return editReply();};await c.planModelEdit();
    assert.equal(c.$('parameter-width').value,'0150.0');assert.equal(c.$('parameter-height').value,'30');assert.equal(c.state.modelEditCandidate.review.parameters.height,35);assert.match(c.$('model-edit-changes').textContent,/30.*35/);
    c.applyModelEdit();assert.equal(c.$('parameter-height').value,'35');assert.equal(c.$('parameter-width').value,'0150.0');assert.equal(c.state.projectSource,source);assert.equal(c.state.job,null);
    assert.equal(body.base_parameters.height,30);assert.equal(Object.keys(body.base_parameters).length,12);assert.equal(body.parent_job_id,undefined);
    c.api=async(path,payload)=>{body=plain(payload);throw new Error('CAD unavailable');};await c.generateModel();assert.deepEqual(body.model_edit,editReply().review.selection);assert.deepEqual(body.project_selection,{id:'idea',recipe_sha256:'a'.repeat(64)});
    c.manualModelChanged();assert.equal(c.state.modelEditApplied,null);assert.equal(c.$('parameter-width').value,'0150.0');
  });
  await check('Contextual cancel failure and stale scope preserve exact draft, job notes and source',async()=>{
    const mutations=[c=>c.cancelModelEdit(),c=>{c.$('parameter-width').value='0150.0';},c=>{c.$('parameter-width').validity={badInput:true};},c=>{c.state.projectSource={...project(),recipe_sha256:'b'.repeat(64)};},c=>{c.state.connectionEpoch++;},c=>{c.state.storage={path:'/new'};},c=>{c.$('model-edit-text').value='different';},c=>{c.$('model-edit-mode').value='llm';},c=>{c.state.job={...job(),id:'different'};}];
    for(const mutate of mutations) {
      const c=editFixture();assert.equal(typeof c.planModelEdit,'function');c.$('outcome-notes').value='exact pending note';let finish;c.api=()=>new Promise(resolve=>{finish=resolve;});const pending=c.planModelEdit();mutate(c);finish(editReply());await pending;
      assert.equal(c.state.modelEditCandidate,null);assert.equal(c.state.modelEditPending,false);assert.equal(c.$('parameter-height').value,'30');assert.equal(c.$('outcome-notes').value,'exact pending note');
    }
    const c=editFixture();c.api=async()=>{throw new Error('provider failed');};await c.planModelEdit();assert.equal(c.state.modelEditPending,false);assert.equal(c.$('parameter-height').value,'30');assert.match(c.$('model-edit-feedback').textContent,/provider failed/);
    c.api=async()=>editReply();await c.planModelEdit();c.cancelModelEdit();c.applyModelEdit();assert.equal(c.$('parameter-height').value,'30');
  });
  await check('Pending contextual requests and unapplied reviews participate in pending-work protection',async()=>{
    const c=editFixture();c.state.projectSource=null;assert.equal(c.hasPendingWork(),false);let finish;c.api=()=>new Promise(resolve=>{finish=resolve;});const pending=c.planModelEdit();assert.equal(c.hasPendingWork(),true);finish(editReply());await pending;assert.equal(c.hasPendingWork(),true);c.cancelModelEdit();assert.equal(c.hasPendingWork(),false);
  });
  await check('Changing and restoring edit text still rejects the prior response and releases only its pending owner',async()=>{
    const c=editFixture();let finish;c.api=()=>new Promise(resolve=>{finish=resolve;});const pending=c.planModelEdit();c.$('model-edit-text').value='different';c.modelEditInputChanged();c.$('model-edit-text').value='높이를 5mm 늘려줘';c.modelEditInputChanged();finish(editReply());await pending;assert.equal(c.state.modelEditCandidate,null);assert.equal(c.state.modelEditPending,false);assert.equal(c.$('parameter-height').value,'30');
  });
  await check('Older contextual completions cannot replace a newer candidate or release its busy owner',async()=>{
    const c=editFixture();assert.equal(typeof c.planModelEdit,'function');const replies=[];c.api=()=>new Promise((resolve,reject)=>replies.push({resolve,reject}));const old=c.planModelEdit();c.cancelModelEdit();const fresh=c.planModelEdit();replies[0].reject(new Error('old failure'));await old;assert.equal(c.state.modelEditPending,true);replies[1].resolve(editReply());await fresh;assert.equal(c.state.modelEditPending,false);assert(c.state.modelEditCandidate);assert.doesNotMatch(c.$('model-edit-feedback').textContent,/old failure/);
  });
  await check('Contextual reviews accept explicitly unchanged operations alongside an actual change',async()=>{
    const c=editFixture();const reply=editReply();reply.review.selection.operations.unshift({field:'width',op:'set',value:150});c.api=async()=>reply;await c.planModelEdit();assert(c.state.modelEditCandidate);assert.equal(c.state.modelEditCandidate.review.changes.length,1);c.applyModelEdit();assert.equal(c.$('parameter-width').value,'150');assert.equal(c.$('parameter-height').value,'35');assert.equal(c.state.modelEditApplied.operations.length,2);
  });
  await check('Complete contextual response validation rejects missing fields, unrelated changes, malformed operations and wrong context',async()=>{
    const corruptions=[r=>{delete r.review.parameters.bottom;},r=>{delete r.review.selection.base_parameters.slots;},r=>{r.review.parameters.depth=91;},r=>{r.review.changes=[];},r=>{r.review.changes[0].before=29;},r=>{r.review.parameters.height='35';},r=>{r.engine='llm';},r=>{r.review.review_sha256='invalid';},r=>{r.review.selection.request_text='wrong';},r=>{r.review.selection.parent={job_id:'a'.repeat(32),parameters_sha256:'1'.repeat(64),model_sha256:'4'.repeat(64),manifest_sha256:'5'.repeat(64)};},r=>{r.review.selection.operations.push({...r.review.selection.operations[0]});},r=>{r.review.selection.operations[0].field='slots';},r=>{r.review.parameters.extra=1;},r=>{r.questions=['unexpected'];},r=>{r.review.changes.push({field:'width',before:150,after:150});},r=>{r.review.selection.schema_version=true;},r=>{r.review.parameters.slots=6;}];
    for(const corrupt of corruptions){const c=editFixture();assert.equal(typeof c.planModelEdit,'function');const reply=editReply();corrupt(reply);c.api=async()=>reply;await c.planModelEdit();assert.equal(c.state.modelEditCandidate,null);assert.equal(c.$('parameter-height').value,'30');assert.equal(c.state.modelEditPending,false);assert.match(c.$('model-edit-feedback').textContent,/응답|제안/);}
  });
  await check('Applying contextual edits retains notes under verified parent and subsequent manual/history changes detach selection',async()=>{
    const c=editFixture();assert.equal(typeof c.planModelEdit,'function');const original={...job(),id:'a'.repeat(32),result:{...job().result,template:'tray',parameters:editBase()}};c.renderJob(original);c.$('outcome-notes').value='parent observations';
    const parent={job_id:original.id,parameters_sha256:'1'.repeat(64),model_sha256:'4'.repeat(64),manifest_sha256:'5'.repeat(64)};let sent;c.api=async(path,payload)=>{sent=payload;return editReply(parent);};await c.planModelEdit();assert.equal(sent.parent_job_id,original.id);assert.equal(c.state.job,original);c.applyModelEdit();assert.equal(c.state.job,null);assert.equal(c.state.retainedOutcomeDrafts[0].job_id,original.id);assert.equal(c.state.retainedOutcomeDrafts[0].notes,'parent observations');
    const record={...editReply(parent).review,provenance:'user_confirmed_parameters'};c.renderJob({...original,id:'b'.repeat(32),model_edit:record});assert.match(c.$('generated-model-edit').textContent,/높이를 5mm/);assert.match(c.$('generated-model-edit').textContent,/30.*35/);assert.match(c.$('generated-model-edit').textContent,/aaaaaaaa/);
    c.changeView=()=>{};c.performModelReplacement({kind:'history',job:original});assert.equal(c.state.modelEditApplied,null);assert.equal(c.$('generated-model-edit').hidden,true);
  });
  await check('Invalidating an old model retains exact outcome draft and original storage identity',()=>{
    const c=fixture();c.state.storage={path:'/original'};c.renderJob(job());c.$('outcome-result').value='failure';c.$('outcome-notes').value='  exact old note\n';
    c.invalidateCurrentJob('changed');assert.deepEqual(plain(c.state.retainedOutcomeDrafts.map(x=>[x.job_id,x.storage_path,x.result,x.notes])),[['job-a','/original','failure','  exact old note\n']]);assert.equal(c.state.job,null);
  });
  await check('Same-dimension regeneration retains old notes only after success and never attaches them to new job',async()=>{
    const c=fixture();c.state.storage={path:'/original'};c.renderJob(job());c.$('outcome-notes').value='old observation';c.api=async()=>({...job(),id:'new-job'});await c.generateModel();
    assert.equal(c.state.job.id,'new-job');assert.equal(c.$('outcome-notes').value,'');assert.equal(c.state.retainedOutcomeDrafts[0]?.job_id,'job-a');assert.equal(c.state.retainedOutcomeDrafts[0]?.notes,'old observation');
  });
  await check('Failed regeneration and invalid job responses preserve current notes without creating retained replacements',async()=>{
    for(const malformed of [false,true]){const c=fixture();c.renderJob(job());c.$('outcome-notes').value='  unchanged note\n';c.api=async()=>{if(malformed)return {id:'new-job',result:null};throw new Error('generation failed');};await c.generateModel();assert.equal(c.state.job.id,'job-a');assert.equal(c.$('outcome-notes').value,'  unchanged note\n');assert.equal(c.state.retainedOutcomeDrafts.length,0);assert.equal(c.state.workflowBusy,false);}
  });
  await check('Changed edit parents preserve selected draft and report an edit-specific recovery path',async()=>{
    const c=editFixture();c.api=async()=>editReply();await c.planModelEdit();c.applyModelEdit();const selected=plain(c.state.modelEditApplied);c.api=async()=>{const error=new Error('이전 모델 변경');error.status=409;error.code='model_edit_parent_changed';throw error;};await c.generateModel();assert.deepEqual(plain(c.state.modelEditApplied),selected);assert.equal(c.$('parameter-height').value,'35');assert.match(c.$('model-feedback').textContent,/수정 제안/);assert.doesNotMatch(c.$('model-feedback').textContent,/출처 연결을 해제/);
  });
  await check('A prefilled new-model plan protects a pristine unapplied contextual candidate until explicit replacement',async()=>{
    const c=editFixture();c.state.projectSource=null;c.$('request-text').value='new tray';c.api=async()=>editReply();await c.planModelEdit();const candidate=c.state.modelEditCandidate;assert(candidate);
    c.api=async()=>({status:'ready',parameters:{template:'tray',width:88},message:'ready'});await c.preparePlan();assert.equal(c.state.workflowBusy,false);assert.equal(c.state.modelReplacement?.kind,'plan');assert.equal(c.state.modelEditCandidate,candidate);assert.equal(c.state.parameters.width,150);assert.equal(c.$('parameter-height').value,'30');
    c.cancelModelReplacement();assert.equal(c.state.modelEditCandidate,candidate);assert.equal(c.$('request-text').value,'new tray');assert.equal(c.$('model-edit-text').value,'높이를 5mm 늘려줘');assert.equal(c.$('parameter-width').value,'150');
    await c.preparePlan();c.confirmModelReplacement();assert.equal(c.state.parameters.width,88);assert.equal(c.state.modelEditCandidate,null);
  });
  await check('A prefilled new-model plan protects a pristine pending contextual request through cancel and ignores it after confirmed replacement',async()=>{
    const c=editFixture();c.state.projectSource=null;c.$('request-text').value='new tray';let finish;c.api=path=>path==='/api/model-edits/plan'?new Promise(resolve=>{finish=resolve;}):Promise.resolve({status:'ready',parameters:{template:'tray',width:88},message:'ready'});
    const pending=c.planModelEdit(),request=c.state.modelEditRequest;assert.equal(c.state.modelEditPending,true);await c.preparePlan();assert.equal(c.state.workflowBusy,false);assert.equal(c.state.modelReplacement?.kind,'plan');assert.equal(c.state.modelEditPending,true);assert.equal(c.state.modelEditRequest,request);assert.equal(c.state.parameters.width,150);
    c.cancelModelReplacement();assert.equal(c.state.modelEditPending,true);assert.equal(c.state.modelEditRequest,request);assert.equal(c.$('request-text').value,'new tray');assert.equal(c.$('model-edit-text').value,'높이를 5mm 늘려줘');assert.equal(c.$('parameter-width').value,'150');
    await c.preparePlan();c.confirmModelReplacement();assert.equal(c.state.parameters.width,88);assert.equal(c.state.modelEditPending,false);finish(editReply());await pending;assert.equal(c.state.modelEditCandidate,null);assert.equal(c.state.parameters.width,88);
  });
  await check('A first new-model request on pristine defaults applies without replacement while exact customized strings stay protected',async()=>{
    const clean=fixture();clean.$('request-text').value='new tray';clean.api=async()=>({status:'ready',parameters:{template:'tray',width:88},message:'ready'});await clean.preparePlan();assert.equal(clean.state.parameters.width,88);assert.equal(clean.state.modelReplacement,null);
    const dirty=fixture();dirty.$('parameter-width').value='120.0';dirty.$('request-text').value='new tray';dirty.api=clean.api;await dirty.preparePlan();assert.equal(dirty.state.parameters.width,120);assert.equal(dirty.state.modelReplacement?.kind,'plan');dirty.cancelModelReplacement();assert.equal(dirty.$('parameter-width').value,'120.0');
  });
  await check('Dirty new-model plans await explicit replacement after busy releases and cancellation keeps exact work',async()=>{
    const c=fixture();c.renderJob(job());c.state.projectSource=project();c.$('parameter-width').value='0120.0';c.$('request-text').value='new tray';c.$('outcome-notes').value='pending';c.api=async()=>({status:'ready',parameters:{template:'tray',width:88},message:'ready'});await c.preparePlan();
    assert.equal(c.state.workflowBusy,false);assert.equal(c.state.job.id,'job-a');assert.equal(c.$('parameter-width').value,'0120.0');assert.equal(c.state.modelReplacement?.kind,'plan');c.cancelModelReplacement();assert.equal(c.$('outcome-notes').value,'pending');assert.equal(c.state.projectSource.id,'idea');
  });
  await check('Corrupt profile restoration is atomic before epochs, guided edits and controls change',()=>{
    for (const corrupt of [s=>{s.target_index=4;},s=>{delete s.setup.printer_model;},s=>{s.documents='bad';},s=>{s.schema_version=2;}]) {
      const c=profileFixture();c.$('profile-json').value='{ unfinished';c.state.guidedEdits={nozzle_temperature:' 2.'};
      const saved=plain(c.captureProfileSnapshot());corrupt(saved);
      const before=plain({state:c.state,text:c.$('profile-json').value,title:c.$('workspace-title').value});
      assert.throws(()=>c.restoreWorkspace(workspaceRecord(saved)),/작업|저장|형식/);
      assert.deepEqual(plain({state:c.state,text:c.$('profile-json').value,title:c.$('workspace-title').value}),before);
    }
  });
  await check('Named original and edited library opens stage coherent candidates without replacing current input',async()=>{
    for(const edited of [false,true])for(const draft of [null,{...Object.fromEntries(studioDescriptor().fields.map(f=>[f.key,f.value])),filament_flow_ratio:' 1. '}]){
      const c=fixture();studioApplied(c);c.api=async()=>studioDescriptor();await c.openStudioSettings();c.editStudioSetting('nozzle_temperature','unfinished');
      const envelope=studioNamed(edited,draft);c.$('studio-library-kind').value='workspaces';c.$('studio-library-list').value=envelope.workspace.id;c.api=async()=>envelope;
      assert.equal(typeof c.openStudioLibrary,'function');await c.openStudioLibrary();
      assert.equal(c.state.studioSettingsDraft.nozzle_temperature,'unfinished');assert.equal(c.state.studioWorkspaceId,undefined);
      c.applyStudioCandidate();assert.equal(c.state.studioSettingsDraft.nozzle_temperature,'unfinished');
      c.applyStudioCandidate(true);assert.equal(c.state.studioWorkspaceId,envelope.workspace.id);
      assert.equal(c.state.studioSettingsApplied?.revision.revision_id,edited?'e'.repeat(32):undefined);
      assert.equal(c.state.studioSettingsDraft.filament_flow_ratio,draft?.filament_flow_ratio||'0.98');
      assert.equal(c.state.studioSettingsDraft.nozzle_temperature,draft?.nozzle_temperature||(edited?'216':'215'));
      assert.equal(c.studioWorkspaceDirty(),false);assert.equal(c.state.studioSettingsReview,null);assert.equal(c.state.studioSlicePrepared,false);
    }
  });
  await check('Saved invalid Studio draft is persistence clean but cannot prepare stale effective settings',async()=>{
    const c=fixture();studioApplied(c);c.api=async()=>studioDescriptor();await c.openStudioSettings();c.editStudioSetting('filament_flow_ratio',' 1. ');c.$('studio-workspace-title').value='Unfinished';
    assert.equal(typeof c.saveStudioWorkspace,'function');let captured;c.api=async(path,body)=>{captured=plain(body);return {...studioNamed(false,body.snapshot.draft_values).workspace,title:body.title};};
    await c.saveStudioWorkspace();assert.equal(captured.snapshot.draft_values.filament_flow_ratio,' 1. ');
    assert.equal(c.studioWorkspaceDirty(),false);assert.equal(c.studioHasUnsavedChanges(),false);assert.equal(c.studioSettingsDirty(),true);
    c.state.job=job();c.renderStudioProject();assert.equal(c.$('prepare-studio-project').disabled,true);
    await c.runStudioSlice(false);assert.equal(captured.snapshot.draft_values.filament_flow_ratio,' 1. ');
  });
  await check('Studio save conflict preserves draft and save-copy creates a new record',async()=>{
    const c=fixture();studioApplied(c);c.api=async()=>studioDescriptor();await c.openStudioSettings();c.editStudioSetting('filament_flow_ratio','-');c.$('studio-workspace-title').value='Work';
    c.state.studioWorkspaceId='b'.repeat(32);c.state.studioWorkspaceRevision=3;let payload,method;
    c.api=async()=>{const e=new Error('conflict');e.status=409;e.code='workspace_conflict';throw e;};
    assert.equal(typeof c.saveStudioWorkspace,'function');await c.saveStudioWorkspace();assert.equal(c.state.studioWorkspaceRevision,3);assert.equal(c.state.studioSettingsDraft.filament_flow_ratio,'-');
    assert.match(c.$('studio-library-feedback').textContent,/복사/);
    c.api=async(path,body,verb)=>{payload=body;method=verb;return {...studioNamed(false,body.snapshot.draft_values).workspace,title:body.title};};await c.saveStudioWorkspace(true);
    assert.equal(method,'POST');assert.equal(payload.expected_revision,undefined);assert.equal(c.state.studioSettingsDraft.filament_flow_ratio,'-');
  });
  await check('Late library opens, cancellations, selection changes and root changes preserve current input',async()=>{
    for(const change of [c=>c.cancelStudioCandidate(),c=>c.editStudioSetting('nozzle_temperature','newer'),c=>{c.state.connectionEpoch++;},c=>{c.state.storage={path:'/new'};},c=>{c.$('studio-library-list').value='c'.repeat(32);}]){
      const c=fixture();studioApplied(c);c.api=async()=>studioDescriptor();await c.openStudioSettings();c.editStudioSetting('nozzle_temperature','before');c.$('studio-library-kind').value='workspaces';c.$('studio-library-list').value='b'.repeat(32);
      let finish;c.api=()=>new Promise(done=>{finish=done;});assert.equal(typeof c.openStudioLibrary,'function');const pending=c.openStudioLibrary();change(c);finish(studioNamed());await pending;
      assert.equal(c.state.studioCandidate,null);assert.equal(c.state.studioWorkspaceId,undefined);assert.match(c.state.studioSettingsDraft.nozzle_temperature,/before|newer/);
    }
  });
  for(const change of ['selection','kind'])await check(`Completed stale library open releases its pending controls after ${change} changes`,async()=>{
    for(const failure of [false,true]){
      const c=fixture();studioApplied(c);c.api=async()=>studioDescriptor();await c.openStudioSettings();c.editStudioSetting('filament_flow_ratio','current draft');c.$('studio-workspace-title').value='Current title';
      c.$('studio-library-kind').value='workspaces';c.$('studio-library-list').value='b'.repeat(32);
      let settle;c.api=path=>path.startsWith('/api/studio-library?')?Promise.resolve({items:[],next_cursor:null}):new Promise((resolve,reject)=>{settle=failure?reject:resolve;});
      const pending=c.openStudioLibrary();assert.equal(c.state.studioPending,true);
      if(change==='kind'){c.$('studio-library-kind').value='sources';c.studioLibrarySelectionChanged(true);}else c.studioLibrarySelectionChanged();
      c.$('studio-library-list').value='c'.repeat(32);
      settle(failure?new Error('Old failed open'):studioNamed());await pending;
      assert.equal(c.state.studioCandidate,null);assert.equal(c.state.studioPending,false);assert.equal(c.state.studioPendingName,'');
      assert.equal(c.$('studio-library-open').disabled,false);assert.equal(c.$('studio-workspace-save').disabled,false);assert.equal(c.$('studio-settings-open').disabled,false);
      assert.equal(c.state.studioSettingsDraft.filament_flow_ratio,'current draft');assert.equal(c.$('studio-workspace-title').value,'Current title');
    }
  });
  await check('Completed older library open cannot clear a newer open request pending state',async()=>{
    for(const change of ['selection','kind'])for(const failure of [false,true]){
      const c=fixture();studioApplied(c);c.$('studio-library-kind').value='workspaces';c.$('studio-library-list').value='b'.repeat(32);
      const pendingResponses=[];c.api=path=>path.startsWith('/api/studio-library?')?Promise.resolve({items:[],next_cursor:null}):new Promise((resolve,reject)=>pendingResponses.push({resolve,reject}));
      const first=c.openStudioLibrary();
      if(change==='kind'){c.$('studio-library-kind').value='sources';c.studioLibrarySelectionChanged(true);}else c.studioLibrarySelectionChanged();
      c.$('studio-library-list').value='c'.repeat(32);const second=c.openStudioLibrary();const request=c.state.studioRequest;
      if(failure)pendingResponses[0].reject(new Error('Old failed open'));else pendingResponses[0].resolve(studioNamed());await first;
      assert.equal(c.state.studioRequest,request);assert.equal(c.state.studioPending,true);assert.equal(c.state.studioPendingName,'보관한 설정');assert.equal(c.state.studioCandidate,null);assert.equal(c.$('studio-library-open').disabled,true);
      const result=change==='kind'?studioInspection('c'.repeat(32)):studioNamed();if(change==='selection')result.workspace.id='c'.repeat(32);
      pendingResponses[1].resolve(result);await second;assert.equal(c.state.studioPending,false);assert.equal(c.state.studioCandidate.source_id,result.source?.source_id||result.source_id);
    }
  });
  await check('Late Studio save acknowledges only submitted text and ignores changed root or selection',async()=>{
    for(const change of ['typing','root','selection']){
      const c=fixture();studioApplied(c);c.api=async()=>studioDescriptor();await c.openStudioSettings();c.editStudioSetting('filament_flow_ratio','first');c.$('studio-workspace-title').value='Work';
      let finish,body;c.api=(path,payload)=>new Promise(done=>{finish=done;body=plain(payload);});assert.equal(typeof c.saveStudioWorkspace,'function');const pending=c.saveStudioWorkspace();
      if(change==='typing')c.editStudioSetting('filament_flow_ratio','newer');else if(change==='root')c.state.storage={path:'/new'};else c.cancelStudioCandidate();
      finish(studioNamed(false,body.snapshot.draft_values).workspace);await pending;
      if(change==='typing'){assert.equal(c.state.studioSettingsDraft.filament_flow_ratio,'newer');assert.equal(c.studioWorkspaceDirty(),true);}
      else assert.equal(c.state.studioWorkspaceId,undefined);
    }
  });
  await check('Named candidate installs source revision descriptor and draft before any render',async()=>{
    const c=fixture();studioApplied(c);c.api=async()=>studioDescriptor();await c.openStudioSettings();c.editStudioSetting('nozzle_temperature','old draft');c.$('studio-library-kind').value='workspaces';c.$('studio-library-list').value='b'.repeat(32);c.api=async()=>studioNamed(true,null);await c.openStudioLibrary();
    const render=c.renderStudioProject;c.renderStudioProject=()=>{assert.equal(c.state.studioWorkspaceId,'b'.repeat(32));assert.equal(c.state.studioSettingsApplied.revision.revision_id,'e'.repeat(32));assert.equal(c.state.studioSettingsDescriptor.source_id,'a'.repeat(32));assert.equal(c.state.studioSettingsDraft.nozzle_temperature,'216');render();};
    c.applyStudioCandidate(true);
  });
  await check('Legacy history candidate never inherits a previously staged named workspace attachment',async()=>{
    const c=fixture();c.$('studio-library-kind').value='workspaces';c.$('studio-library-list').value='b'.repeat(32);c.api=async()=>studioNamed(false,null);await c.openStudioLibrary();assert(c.state.studioWorkspaceCandidate);
    c.state.studioRecorded=studioInspection('c'.repeat(32));c.api=async()=>c.state.studioRecorded;await c.revalidateStudioProject(true);
    assert.equal(c.state.studioWorkspaceCandidate,null);c.applyStudioCandidate();assert.equal(c.state.studioApplied.source_id,'c'.repeat(32));assert.equal(c.state.studioWorkspaceId,null);
  });
  await check('Saved Studio persistence stays clean across reconnect while source preparation requires revalidation',async()=>{
    const c=fixture();studioApplied(c);c.api=async()=>studioDescriptor();await c.openStudioSettings();c.editStudioSetting('filament_flow_ratio','-');c.$('studio-workspace-title').value='Work';
    c.api=async(path,body)=>({...studioNamed(false,body.snapshot.draft_values).workspace,title:body.title});await c.saveStudioWorkspace();
    c.state.connectionEpoch++;assert.equal(c.studioWorkspaceDirty(),false);assert.equal(c.studioHasUnsavedChanges(),false);assert.equal(c.studioSourceCurrent(),false);assert.equal(c.studioSettingsDirty(),true);
  });
  await check('Studio original can save before opening an editor or creating CAD',async()=>{
    const c=fixture();studioApplied(c);c.$('studio-workspace-title').value='Original before CAD';let submitted;
    c.api=async(path,body)=>body?(submitted=plain(body),{...studioNamed(false,null).workspace,title:body.title}):studioDescriptor();
    await c.saveStudioWorkspace();assert.equal(submitted.snapshot.draft_values,null);assert.equal(submitted.snapshot.settings_revision_id,null);assert.equal(c.state.studioWorkspaceId,'b'.repeat(32));assert.equal(c.studioWorkspaceDirty(),false);assert.equal(c.state.job,null);
  });
  await check('Studio catalog plural kinds paginate metadata and ignore late selection or root responses',async()=>{
    const c=fixture();c.$('studio-library-kind').value='sources';const paths=[];
    const item=id=>({id,kind:'source',title:'<source>',summary:'Recorded',metadata_status:'recorded',has_draft:false,updated_at:null});
    c.api=async path=>{paths.push(path);return {items:[item(paths.length===1?'a'.repeat(32):'b'.repeat(32))],next_cursor:paths.length===1?'a'.repeat(32):null};};
    await c.loadStudioLibrary();await c.loadStudioLibrary(true);assert.equal(c.state.studioLibraryItems.length,2);assert.match(paths[0],/kind=sources/);assert.match(paths[1],/before=aaaaaaaa/);assert.match(c.$('studio-library-list').textContent,/<source>/);
    for(const change of [()=>{c.$('studio-library-list').value='b'.repeat(32);},()=>{c.state.storage={path:'/new'};}]){
      let finish;c.api=()=>new Promise(done=>{finish=done;});const pending=c.loadStudioLibrary();change();finish({items:[],next_cursor:null});await pending;assert.equal(c.state.studioLibraryItems.length,2);
    }
  });
  await check('Malformed named and failed integrity opens retain source draft saved identity and candidate',async()=>{
    for(const corrupt of [r=>{r.workspace.snapshot.effective_settings_sha256='0'.repeat(64);},r=>{delete r.workspace.snapshot.draft_values;},r=>{r.editor.fields.pop();},r=>{r.settings_revision=null;},r=>{r.workspace.revision=Number.MAX_SAFE_INTEGER;}]){
      const c=fixture();studioApplied(c);c.api=async()=>studioDescriptor();await c.openStudioSettings();c.editStudioSetting('nozzle_temperature','live draft');c.$('studio-library-kind').value='workspaces';c.$('studio-library-list').value='b'.repeat(32);
      const result=studioNamed(true,null);corrupt(result);c.api=async()=>result;await c.openStudioLibrary();assert.equal(c.state.studioCandidate,null);assert.equal(c.state.studioSettingsDraft.nozzle_temperature,'live draft');assert.equal(c.state.studioSettingsApplied,null);assert.match(c.$('studio-library-feedback').textContent,/유지/);
    }
    const c=fixture();studioApplied(c);c.$('studio-library-kind').value='workspaces';c.$('studio-library-list').value='b'.repeat(32);let paths=[];c.api=async path=>{paths.push(path);const e=new Error('missing saved revision');e.status=409;e.code='studio_workspace_integrity';throw e;};await c.openStudioLibrary();assert.equal(paths.length,1);assert.equal(c.state.studioApplied.source_id,'a'.repeat(32));
  });
  await check('Studio workspace exact draft bounds use Unicode code points without trimming',async()=>{
    const c=fixture();studioApplied(c);c.api=async()=>studioDescriptor();await c.openStudioSettings();
    c.editStudioSetting('filament_flow_ratio','😀'.repeat(512));assert.equal(c.studioWorkspaceSnapshot().draft_values.filament_flow_ratio,'😀'.repeat(512));
    c.editStudioSetting('filament_flow_ratio','😀'.repeat(513));assert.throws(()=>c.studioWorkspaceSnapshot(),/512/);assert.equal(c.state.studioSettingsDraft.filament_flow_ratio,'😀'.repeat(513));
  });
  await check('Canceling Studio deletion has no request and successful deletion retains exact inputs',async()=>{
    const c=fixture();studioApplied(c);c.state.studioWorkspaceId='b'.repeat(32);c.state.studioWorkspaceRevision=2;c.api=async()=>studioDescriptor();await c.openStudioSettings();c.editStudioSetting('filament_flow_ratio',' 1. ');
    let requests=0;c.api=async(path,body,verb)=>{requests++;assert.equal(verb,'DELETE');assert.equal(body.expected_revision,2);return null;};c.window.confirm=()=>false;await c.deleteStudioWorkspace();assert.equal(requests,0);assert.equal(c.state.studioWorkspaceId,'b'.repeat(32));
    c.window.confirm=()=>true;await c.deleteStudioWorkspace();assert.equal(requests,1);assert.equal(c.state.studioWorkspaceId,null);assert.equal(c.state.studioSettingsDraft.filament_flow_ratio,' 1. ');assert.equal(c.state.studioApplied.source_id,'a'.repeat(32));
  });
  await check('HTTP 204 delete acknowledgement does not require JSON',async()=>{
    const c=fixture();c.fetch=async()=>({ok:true,status:204,json:async()=>{throw new Error('empty');}});assert.equal(await c.api('/api/studio-workspaces/'+'b'.repeat(32),{expected_revision:2},'DELETE'),null);
  });
  await check('Studio six-field editor retains exact invalid strings and never partially applies',async()=>{
    const c=fixture();studioApplied(c);c.state.job=job();const descriptor=studioDescriptor();c.api=async()=>descriptor;
    await c.openStudioSettings();assert.equal(c.state.studioSettingsDraft.nozzle_temperature,'215');
    c.editStudioSetting('nozzle_temperature',' 216 ');c.editStudioSetting('filament_flow_ratio','1.');
    c.api=async()=>{throw new Error('Invalid decimal');};await c.reviewStudioSettings();
    assert.equal(c.state.studioSettingsDraft.filament_flow_ratio,'1.');assert.equal(c.state.studioSettingsDraft.nozzle_temperature,' 216 ');
    assert.equal(c.state.studioSettingsReview,null);assert.equal(c.state.studioSettingsApplied,null);assert.equal(c.$('prepare-studio-project').disabled,true);assert.equal(c.hasPendingWork(),true);
    c.cancelStudioSettings();assert.equal(c.state.studioSettingsOpen,false);assert.equal(c.state.studioSettingsApplied,null);
  });
  await check('Studio review requires explicit apply and preparation binds its immutable revision',async()=>{
    const c=fixture();studioApplied(c);c.state.job=job();c.api=async()=>studioDescriptor();await c.openStudioSettings();c.editStudioSetting('nozzle_temperature','216');
    const review=studioReview();c.api=async()=>review;await c.reviewStudioSettings();assert.equal(c.state.studioSettingsApplied,null);
    let created;c.api=async(path,body)=>{created={path,body};return studioEnvelope();};await c.applyStudioSettings();
    assert.equal(created.body.review_sha256,review.review_sha256);assert.equal(c.state.studioSettingsApplied.revision.revision_id,'e'.repeat(32));
    let sent;c.api=async(path,body)=>{if(body){sent=body;return {plan:{kind:'studio_project',project_prepared:true,ready:false,project_source:studioInspection(),settings_revision:studioEnvelope().revision,settings_review:review}};}return job();};
    await c.runStudioSlice(false);assert.deepEqual(plain(sent),{job_id:'job-a',studio_settings_revision_id:'e'.repeat(32),execute:false});
    c.resetStudioSettings();assert.equal(c.state.studioSettingsApplied,null);assert.equal(c.$('studio-project-prepared-download').hidden,true);
  });
  await check('Late Studio descriptor review create and revalidation are inert after context changes',async()=>{
    for(const operation of ['descriptor','review','create','revalidate'])for(const change of [c=>c.cancelStudioSettings(),c=>c.editStudioSetting('nozzle_temperature','217'),c=>{c.state.connectionEpoch++;},c=>{c.state.storage={path:'/new'};},c=>{c.state.job={...job(),id:'different'};},c=>{c.state.studioSettingsApplied=studioEnvelope('f'.repeat(32));},c=>studioApplied(c,studioInspection('b'.repeat(32)))])for(const fail of [false,true]){
      const c=fixture();studioApplied(c);c.state.job=job();c.api=async()=>studioDescriptor();await c.openStudioSettings();c.editStudioSetting('nozzle_temperature','216');
      c.state.studioSettingsReview=studioReview();c.state.studioSettingsReviewContext=c.studioContext();
      if(operation==='revalidate') {c.state.studioSettingsApplied=studioEnvelope();c.state.connectionEpoch++;}
      let settle;c.api=()=>new Promise((resolve,reject)=>{settle=fail?reject:resolve;});
      const pending=operation==='descriptor'?c.openStudioSettings():operation==='review'?c.reviewStudioSettings():operation==='create'?c.applyStudioSettings():c.revalidateStudioProject();
      assert(settle,operation+' starts request');change(c);const expected=c.studioSettingsIdentity(c.state.studioSettingsApplied);c.$('studio-settings-feedback').textContent='Current feedback';c.$('studio-project-feedback').textContent='Current source';
      settle(fail?new Error('Old error'):operation==='descriptor'?studioDescriptor():operation==='review'?studioReview():studioEnvelope());await pending;
      assert.equal(c.studioSettingsIdentity(c.state.studioSettingsApplied),expected);assert.equal(c.$('studio-settings-feedback').textContent,'Current feedback');assert.equal(c.$('studio-project-feedback').textContent,'Current source');
    }
  });
  await check('Studio source replacement requires explicit draft discard and cancel keeps applied revision',async()=>{
    const c=fixture();studioApplied(c);c.state.studioSettingsApplied=studioEnvelope();c.api=async()=>studioDescriptor();await c.openStudioSettings();c.editStudioSetting('filament_flow_ratio',' 1. ');
    c.state.studioCandidate=studioInspection('b'.repeat(32));c.state.studioCandidateEpoch=0;c.state.studioCandidateStorage=null;c.applyStudioCandidate();
    assert.equal(c.state.studioApplied.source_id,'a'.repeat(32));assert.equal(c.$('studio-settings-replace-choice').hidden,false);
    c.cancelStudioCandidate();assert.equal(c.state.studioSettingsDraft.filament_flow_ratio,' 1. ');assert.equal(c.state.studioSettingsApplied.revision.revision_id,'e'.repeat(32));
    c.state.studioCandidate=studioInspection('b'.repeat(32));c.state.studioCandidateEpoch=0;c.state.studioCandidateStorage=null;c.applyStudioCandidate(true);
    assert.equal(c.state.studioApplied.source_id,'b'.repeat(32));assert.equal(c.state.studioSettingsDraft,null);assert.equal(c.state.studioSettingsApplied,null);
  });
  await check('Edited history revalidation stages full revision and never silently adopts original',async()=>{
    const c=fixture();const envelope=studioEnvelope();c.renderJob({...job(),latest_slice:{phase:'complete',plan:{kind:'studio_project',project_source:studioInspection(),settings_revision:envelope.revision,settings_review:envelope.review}}});
    let path;c.api=async url=>{path=url;return envelope;};await c.revalidateStudioProject(true);
    assert.equal(path,'/api/studio-settings-revisions/'+'e'.repeat(32));assert.equal(c.state.studioSettingsApplied,null);assert.equal(c.state.studioSettingsCandidate.revision.revision_id,'e'.repeat(32));
    c.applyStudioCandidate();assert.equal(c.state.studioSettingsApplied.revision.revision_id,'e'.repeat(32));assert.equal(c.state.studioSlicePrepared,false);
  });
  await check('All six Studio text controls expose original values and preserve the complete submitted draft',async()=>{
    const c=fixture();studioApplied(c);const descriptor=studioDescriptor();c.api=async()=>descriptor;await c.openStudioSettings();
    const inputs=c.$('studio-settings-fields').children.map(label=>label.children.find(child=>child.dataset.studioSetting));assert.equal(inputs.length,6);
    const values=[' 216 ','221','1.010000','13.00','56','57'];
    inputs.forEach((input,index)=>{assert.equal(input.type,'text');assert.equal(input.maxLength,undefined);assert.equal(input.value,descriptor.fields[index].value);input.value=values[index];input.listeners.input();});
    let sent;c.api=async(path,body)=>{sent=body;return studioReview();};await c.reviewStudioSettings();
    assert.deepEqual(plain(sent.values),Object.fromEntries(descriptor.fields.map((field,index)=>[field.key,values[index]])));
    assert.equal(c.state.studioSettingsApplied,null);assert.match(c.$('studio-settings-fields').textContent,/원본/);
  });
  await check('Rejected overlong and partial Studio text remains exact without truncation',async()=>{
    const c=fixture();studioApplied(c);c.api=async()=>studioDescriptor();await c.openStudioSettings();
    for(const invalid of [' ', '1.', '1e2', '+1', '9'.repeat(33), 'NaN']) {c.editStudioSetting('filament_flow_ratio',invalid);c.api=async()=>{throw new Error('Unsupported input');};await c.reviewStudioSettings();assert.equal(c.state.studioSettingsDraft.filament_flow_ratio,invalid);assert.equal(c.state.studioSettingsReview,null);assert.equal(c.state.studioSettingsApplied,null);}
  });
  await check('Numerically unchanged Studio review returns explicitly to original without creating a record',async()=>{
    const c=fixture();studioApplied(c);c.state.studioSettingsApplied=studioEnvelope();c.api=async()=>studioDescriptor();await c.openStudioSettings();c.editStudioSetting('nozzle_temperature',' 215 ');
    c.api=async()=>({...studioReview(),values:{},changes:[],changed_count:0,effective_settings_sha256:'d'.repeat(64)});await c.reviewStudioSettings();
    assert.equal(c.state.studioSettingsApplied.revision.revision_id,'e'.repeat(32));let creates=0;c.api=async()=>{creates++;throw new Error('No create allowed');};await c.applyStudioSettings();
    assert.equal(creates,0);assert.equal(c.state.studioSettingsApplied,null);assert.equal(c.state.studioSettingsOpen,false);
  });
  await check('Any Studio text edit detaches prepared and native results; cancel preserves applied settings',async()=>{
    const c=fixture();studioApplied(c);c.state.job={...job(),artifacts:{prepared_three_mf:'/api/jobs/job-a/files/prepared_three_mf',sliced_three_mf:'/api/jobs/job-a/files/sliced_three_mf'},latest_slice:{phase:'complete',plan:{kind:'studio_project',project_prepared:true,project_source:studioInspection(),settings_revision:studioEnvelope().revision}}};
    c.state.studioSettingsApplied=studioEnvelope();c.state.studioSlicePrepared=true;c.state.studioPreparedSignature=c.studioContext();c.api=async()=>studioDescriptor();await c.openStudioSettings();c.editStudioSetting('filament_flow_ratio','1e');
    assert.equal(c.state.studioSlicePrepared,false);assert.equal(c.$('studio-project-prepared-download').hidden,true);assert.doesNotMatch(c.$('download-links').textContent,/설정 포함|슬라이스 3MF/);
    c.cancelStudioSettings();assert.equal(c.state.studioSettingsApplied.revision.revision_id,'e'.repeat(32));assert.equal(c.$('prepare-studio-project').disabled,false);assert.equal(c.$('execute-studio-project').disabled,true);
  });
  await check('Studio pending unapplied and reviewed drafts protect page exit and replacement confirmation',async()=>{
    const c=offersFixture();studioApplied(c);c.state.studioSettingsApplied=studioEnvelope();c.state.studioSavedIdentity=JSON.stringify([c.studioSourceIdentity(c.state.studioApplied),c.studioSettingsIdentity(c.state.studioSettingsApplied)]);assert.equal(c.studioHasUnsavedChanges(),false);
    c.api=async()=>studioDescriptor();await c.openStudioSettings();c.editStudioSetting('filament_flow_ratio','1.');assert.equal(c.exitIsProtected(),true);
    const signature=c.replacementSignature();c.editStudioSetting('filament_flow_ratio','1.0');assert.notEqual(c.replacementSignature(),signature);
    c.cancelStudioSettings();assert.equal(c.studioHasUnsavedChanges(),false);c.state.studioSettingsPending=true;assert.equal(c.exitIsProtected(),true);
  });
  await check('Reconnection retains Studio exact draft and revision without replay; revalidation cannot fall back',async()=>{
    const c=fixture();studioApplied(c);c.state.job=job();c.state.studioSettingsApplied=studioEnvelope();c.api=async()=>studioDescriptor();await c.openStudioSettings();c.editStudioSetting('filament_flow_ratio',' 1. ');
    const requests=[];c.api=async(path,body)=>{requests.push({path,body});if(path==='/api/bootstrap')return {session_token:'new-token',storage:null,templates:c.state.templates,environment:{available:false},provider:{}};return {};};
    await c.bootstrap();assert(requests.every(request=>request.body===undefined));assert.equal(c.state.studioSettingsDraft.filament_flow_ratio,' 1. ');assert.equal(c.state.studioSettingsApplied.revision.revision_id,'e'.repeat(32));assert.equal(c.$('prepare-studio-project').disabled,true);
    c.api=async()=>{throw new Error('Stored revision is missing');};await c.revalidateStudioProject();assert.equal(c.state.studioSettingsApplied.revision.revision_id,'e'.repeat(32));assert.equal(c.state.studioSettingsDraft.filament_flow_ratio,' 1. ');assert.equal(c.$('prepare-studio-project').disabled,true);
    c.api=async()=>studioEnvelope();await c.revalidateStudioProject();assert.equal(c.$('prepare-studio-project').disabled,true);c.cancelStudioSettings();assert.equal(c.$('prepare-studio-project').disabled,false);assert.equal(c.$('execute-studio-project').disabled,true);
  });
  await check('Malformed edited history and contradictory reviews never fall back to bare original',async()=>{
    const incomplete={...studioEnvelope().revision};delete incomplete.review_sha256;
    for(const revision of [incomplete,{},false,0,'','broken',null])for(const withReview of [false,true]) {
      if(revision===null&&!withReview)continue;
      const c=fixture();const review=withReview?studioReview():null;
      c.renderJob({...job(),latest_slice:{phase:'complete',plan:{kind:'studio_project',project_source:studioInspection(),settings_revision:revision,settings_review:review}}});
      const requests=[];c.api=async path=>{requests.push(path);return studioInspection();};await c.revalidateStudioProject(true);
      assert.deepEqual(requests,[]);assert.equal(c.state.studioCandidate,null);assert.equal(c.state.studioApplied,null);assert.equal(c.$('prepare-studio-project').disabled,true);assert.match(c.$('studio-project-feedback').textContent,/설정.*기록|기록.*설정/);
      assert.deepEqual(plain(c.state.studioSettingsRecorded),revision);
    }
    for(const invalid of [false,0,'',{},'broken']){const invalidContext=fixture();studioApplied(invalidContext);invalidContext.state.studioSettingsApplied=invalid;assert.equal(invalidContext.studioSourceCurrent(),false);}
    const c=fixture();studioApplied(c);c.state.studioSettingsApplied={revision:incomplete,review:studioReview()};const requests=[];c.api=async path=>{requests.push(path);return studioInspection();};await c.revalidateStudioProject();assert.deepEqual(requests,[]);assert.equal(c.studioSourceCurrent(),false);
    c.state.studioCandidate=studioInspection();c.state.studioCandidateEpoch=0;c.state.studioCandidateStorage=null;c.state.studioSettingsCandidate={revision:incomplete,review:studioReview()};c.applyStudioCandidate();assert.equal(c.state.studioSettingsApplied.revision.review_sha256,undefined);assert.equal(c.$('prepare-studio-project').disabled,true);
  });
  await check('Studio import stages a candidate without replacing manual JSON or unfinished material text',async()=>{
    const c=profileFixture();c.$('slicer-json').value=' { "manual": "unchanged" }\n';c.$('profile-json').value='{ unfinished  ';
    let request;c.api=async(path,body)=>{request={path,body};return studioInspection();};
    await c.importStudioProject(studioInput());
    assert.equal(request.path,'/api/studio-projects/import');assert.deepEqual(plain(request.body),{filename:'Studio 원본.3mf',content_base64:'UEsD'});
    assert.equal(c.state.studioApplied,null);assert.equal(c.state.studioCandidate.source_id,'a'.repeat(32));
    assert.equal(c.$('slicer-json').value,' { "manual": "unchanged" }\n');assert.equal(c.$('profile-json').value,'{ unfinished  ');
    assert.equal(c.$('studio-project-candidate').hidden,false);assert.match(c.$('studio-project-candidate').textContent,/Fixture Printer/);
    assert.equal(c.hasPendingWork(),true);c.cancelStudioCandidate();assert.equal(c.state.studioCandidate,null);assert.equal(c.$('slicer-json').value,' { "manual": "unchanged" }\n');
  });
  await check('Explicit Studio apply changes only the selected setup and detaches previous preparation downloads',async()=>{
    const c=profileFixture();c.state.job=job();c.state.job.artifacts.prepared_three_mf='/api/jobs/job-a/files/prepared_three_mf';
    c.$('slicer-json').value='  {"keep":"manual"}\n';c.$('profile-json').value='{ unfinished  ';c.state.slicePrepared=true;
    c.api=async()=>studioInspection();await c.importStudioProject(studioInput());c.applyStudioCandidate();
    assert.equal(c.state.studioApplied.source_id,'a'.repeat(32));assert.equal(c.state.job.id,'job-a');assert.equal(c.state.slicePrepared,false);assert.equal(c.state.studioSlicePrepared,false);
    assert.equal(c.state.job.artifacts.prepared_three_mf,undefined);assert.equal(c.state.job.artifacts.sliced_three_mf,undefined);
    assert.equal(c.$('slicer-json').value,'  {"keep":"manual"}\n');assert.equal(c.$('profile-json').value,'{ unfinished  ');
  });
  await check('Unsupported Studio candidates cannot replace a supported applied source',async()=>{
    const c=fixture();studioApplied(c);const original=c.state.studioApplied;
    c.api=async()=>studioInspection('b'.repeat(32),{supported:false,issues:[{code:'unsupported_version',message:'지원 버전 확인 필요'}]});
    await c.importStudioProject(studioInput('new.3mf'));c.applyStudioCandidate();
    assert.equal(c.state.studioApplied,original);assert.equal(c.$('studio-project-apply').disabled,true);assert.match(c.$('studio-project-candidate').textContent,/지원 버전/);
    c.cancelStudioCandidate();assert.equal(c.state.studioApplied,original);assert.equal(c.state.studioCandidate,null);
  });
  await check('A newer Studio selection suppresses both old import successes and old errors',async()=>{
    for(const staleError of [false,true]){
      const c=fixture();let settleOld,entered;let calls=0;const began=new Promise(resolve=>{entered=resolve;});
      c.api=async()=>++calls===1?new Promise((resolve,reject)=>{settleOld=staleError?reject:resolve;entered();}):studioInspection('b'.repeat(32),{source:{filename:'current.3mf',bytes:3,sha256:'e'.repeat(64)}});
      const old=c.importStudioProject(studioInput('old.3mf'));await began;
      await c.importStudioProject(studioInput('current.3mf'));settleOld(staleError?new Error('Obsolete import failure'):studioInspection());await old;
      assert.equal(c.state.studioCandidate.source.filename,'current.3mf');assert.doesNotMatch(c.$('studio-project-feedback').textContent,/Obsolete/);assert.equal(c.state.studioPending,false);
    }
  });
  await check('Cancellation model replacement and reconnect suppress late Studio import responses',async()=>{
    const changes=[c=>c.cancelStudioCandidate(),c=>{c.state.job={...job(),id:'job-new'};},c=>{c.state.connectionEpoch++;}];
    for(const change of changes)for(const fail of [false,true]){
      const c=fixture();let reply,entered;const began=new Promise(resolve=>{entered=resolve;});c.api=()=>new Promise((resolve,reject)=>{reply=fail?reject:resolve;entered();});
      const pending=c.importStudioProject(studioInput());await began;change(c);
      reply(fail?new Error('Late import failure'):studioInspection());await pending;
      assert.equal(c.state.studioCandidate,null);assert.doesNotMatch(c.$('studio-project-feedback').textContent,/Late import failure/);
    }
  });
  await check('Studio size limits reject before reading and malformed imports retain the applied source',async()=>{
    const c=fixture();studioApplied(c);let reads=0,calls=0;
    c.api=async()=>{calls++;throw new Error('Invalid project');};
    await c.importStudioProject({files:[{name:'large.3mf',size:16*1024*1024+1,arrayBuffer:async()=>{reads++;return new ArrayBuffer(0);}}],value:'large.3mf'});
    assert.equal(reads,0);assert.equal(calls,0);assert.equal(c.state.studioApplied.source_id,'a'.repeat(32));
    await c.importStudioProject(studioInput());assert.equal(calls,1);assert.equal(c.state.studioApplied.source_id,'a'.repeat(32));assert.match(c.$('studio-project-feedback').textContent,/Invalid project/);
  });
  await check('Supported Studio project composition works without an installed native executable',async()=>{
    const c=fixture();c.state.environment={available:false};c.state.job=job();studioApplied(c);let request;
    c.api=async(path,body)=>{if(path==='/api/slice'){request=plain(body);return {plan:{kind:'studio_project',project_prepared:true,ready:false,project_source:studioInspection(),project_sha256:'f'.repeat(64),diagnostics:['Studio 없음']},execution:null};}return {...job(),artifacts:{prepared_three_mf:'/api/jobs/job-a/files/prepared_three_mf'}};};
    c.renderStudioProject();assert.equal(c.$('prepare-studio-project').disabled,false);assert.equal(c.$('execute-studio-project').disabled,true);
    await c.runStudioSlice(false);assert.deepEqual(request,{job_id:'job-a',studio_project_id:'a'.repeat(32),execute:false});
    assert.match(c.$('download-links').textContent,/설정 포함 3MF/);assert.doesNotMatch(c.$('download-links').textContent,/슬라이스 3MF/);
    assert.equal(c.state.studioSlicePrepared,false);assert.match(c.$('slice-feedback').textContent,/설정.*3MF/);
  });
  await check('Project and manual preparation never enable each other execution controls',async()=>{
    const c=fixture();c.state.job=job();studioApplied(c);c.$('slicer-json').value='{}';
    c.api=async(path,body)=>path==='/api/slice'?{plan:{kind:body.studio_project_id?'studio_project':undefined,project_prepared:Boolean(body.studio_project_id),ready:true,project_source:studioInspection(),diagnostics:[]}}:job();
    await c.runStudioSlice(false);assert.equal(c.$('execute-studio-project').disabled,false);assert.equal(c.$('execute-slice').disabled,true);
    await c.runSlice(false);assert.equal(c.$('execute-slice').disabled,false);assert.equal(c.$('execute-studio-project').disabled,true);
  });
  await check('Late project preparation cannot render into a different source model or connection',async()=>{
    for(const change of [c=>{c.state.job={...job(),id:'new-job'};},c=>{studioApplied(c,studioInspection('b'.repeat(32)));},c=>{c.state.connectionEpoch++;},c=>{c.state.studioSettingsApplied=studioEnvelope();}])for(const fail of [false,true]){
      const c=fixture();c.state.job=job();studioApplied(c);let settle;c.api=()=>new Promise((resolve,reject)=>{settle=fail?reject:resolve;});
      const pending=c.runStudioSlice(false);change(c);c.$('slice-feedback').textContent='Current feedback';
      settle(fail?new Error('Old preparation failed'):{plan:{kind:'studio_project',ready:true,project_prepared:true,diagnostics:['Old plan']}});await pending;
      assert.equal(c.state.studioSlicePrepared,false);assert.equal(c.$('slice-feedback').textContent,'Current feedback');
    }
  });
  await check('Reconnection requires explicit identity-checked Studio source revalidation',async()=>{
    const c=fixture();c.state.storage={path:'/old'};c.state.job=job();studioApplied(c);c.state.connectionEpoch++;
    c.renderStudioProject();assert.equal(c.$('prepare-studio-project').disabled,true);assert.equal(c.$('studio-project-revalidate').disabled,false);
    let requested;c.api=async path=>{requested=path;return studioInspection();};await c.revalidateStudioProject();
    assert.equal(requested,'/api/studio-projects/'+'a'.repeat(32));assert.equal(c.$('prepare-studio-project').disabled,false);
    c.state.connectionEpoch++;c.api=async()=>studioInspection('a'.repeat(32),{source:{filename:'foreign.3mf',bytes:3,sha256:'e'.repeat(64)}});
    await c.revalidateStudioProject();assert.equal(c.$('prepare-studio-project').disabled,true);assert.equal(c.state.studioApplied.source.filename,'Studio 원본.3mf');assert.match(c.$('studio-project-feedback').textContent,/一致|일치|달라/);
  });
  await check('History displays a recorded Studio source without adopting it or enabling execution',async()=>{
    const c=fixture();const recorded={...job(),latest_slice:{phase:'complete',plan:{kind:'studio_project',ready:true,project_prepared:true,project_source:studioInspection(),diagnostics:[]},execution:null}};
    c.renderJob(recorded);assert.equal(c.state.studioApplied,null);assert.equal(c.state.studioRecorded.source_id,'a'.repeat(32));assert.equal(c.$('execute-studio-project').disabled,true);assert.equal(c.$('studio-project-recorded').hidden,false);
    c.api=async()=>studioInspection();await c.revalidateStudioProject(true);assert.equal(c.state.studioApplied,null);assert.equal(c.state.studioCandidate.source_id,'a'.repeat(32));
    c.applyStudioCandidate();assert.equal(c.$('execute-studio-project').disabled,true);
  });
  await check('Studio source identity rejects foreign archive links and changed-storage handles',()=>{
    const c=fixture();c.state.storage={path:'/original'};studioApplied(c);c.state.storage={path:'/restored'};c.renderStudioProject();
    assert.equal(c.studioSourceCurrent(),false);assert.equal(c.$('prepare-studio-project').disabled,true);
    c.renderStudioSource(c.$('studio-project-applied'),studioInspection('a'.repeat(32),{archive_url:'https://evil.example/archive'}),'Recorded');
    assert.equal(findElement(c.$('studio-project-applied'),element=>element.href==='https://evil.example/archive'),undefined);
  });
  await check('Interrupted and running project records cannot expose a stale prepared download',()=>{
    const c=fixture();studioApplied(c);
    for(const phase of ['complete','running','interrupted']) {
      c.state.job={...job(),artifacts:{prepared_three_mf:'/api/jobs/job-a/files/prepared_three_mf'},latest_slice:{phase,plan:{kind:'studio_project',project_prepared:true,project_source:studioInspection()}}};
      c.renderStudioProject();c.renderDownloads(c.state.job);
      assert.equal(c.$('studio-project-prepared-download').hidden,phase!=='complete');
      if(phase!=='complete')assert.doesNotMatch(c.$('download-links').textContent,/설정 포함 3MF/);
    }
  });
  await check('Late manual preparation cannot replace a changed project source model draft or connection',async()=>{
    const changes=[c=>{c.state.job={...job(),id:'new-job'};},c=>{studioApplied(c,studioInspection('b'.repeat(32)));},c=>{c.state.connectionEpoch++;},c=>{c.state.studioSettingsApplied=studioEnvelope();},c=>{c.$('slicer-json').value=' { "newer": true }\n';}];
    for(const change of changes)for(const fail of [false,true]) {
      const c=fixture();c.state.job=job();studioApplied(c);c.$('slicer-json').value=' { "submitted": true }\n';let settle;
      c.api=path=>path==='/api/slice'?new Promise((resolve,reject)=>{settle=fail?reject:resolve;}):Promise.resolve(job());
      const pending=c.runSlice(false);change(c);c.$('slice-feedback').textContent='Current feedback';
      settle(fail?new Error('Obsolete manual preparation'):{plan:{ready:true,diagnostics:['Obsolete plan']}});await pending;
      assert.equal(c.state.slicePrepared,false);assert.equal(c.$('slice-feedback').textContent,'Current feedback');assert.equal(c.state.slicerSavedText,'');
    }
  });
  await check('Replacing CAD clears its recorded source while retaining the selected Studio input',()=>{
    const c=fixture();studioApplied(c);c.state.job=job();c.state.studioRecorded=studioInspection('b'.repeat(32));c.state.studioSavedIdentity=c.studioSourceIdentity(c.state.studioRecorded);
    c.invalidateCurrentJob('New CAD required');
    assert.equal(c.state.studioRecorded,null);assert.equal(c.state.studioSavedIdentity,null);assert.equal(c.state.studioApplied.source_id,'a'.repeat(32));assert.equal(c.$('studio-project-recorded').hidden,true);assert.equal(c.$('studio-project-history-source').hidden,true);
  });
  await check('Empty default purchase rows do not protect exit, but nonempty and invalid drafts do',()=>{
    const c=offersFixture();assert.equal(c.exitIsProtected(),false);
    c.editOffer('offer-1-name','  ');assert.equal(c.exitIsProtected(),true);
    c.editOffer('offer-1-name','');assert.equal(c.exitIsProtected(),false);
    c.editOffer('offer-2-shipping','',{badInput:true,valid:false});assert.equal(c.exitIsProtected(),true);
    c.$('offer-2-shipping').validity={badInput:false,valid:true};assert.equal(c.exitIsProtected(),false);
    c.$('offer-currency').value='USD';c.$('offer-currency').listeners.change();assert.equal(c.exitIsProtected(),true);
    c.$('offer-currency').value='KRW';c.$('offer-currency').listeners.change();assert.equal(c.exitIsProtected(),false);
  });
  await check('A late successful comparison rejects a defensive programmatic currency edit',async()=>{
    const c=offersFixture();c.fillOffer();let reply,calls=0;
    c.api=async()=>{calls++;return new Promise(resolve=>{reply=resolve;});};
    const pending=c.submitOffers();assert.equal(c.$('offer-1-price').disabled,true);assert.equal(c.$('offer-currency').disabled,true);assert.equal(c.$('compare-offers').disabled,true);
    c.$('offer-currency').value='USD';c.$('offer-currency').listeners.change();reply(offerReply('Obsolete result'));await pending;
    assert.equal(c.$('offers-result').hidden,true);assert.doesNotMatch(c.$('offer-comparison').textContent,/Obsolete/);assert.equal(c.$('offer-currency').value,'USD');assert.equal(calls,1);assert.equal(c.$('compare-offers').disabled,false);
  });
  await check('Exact purchase text, added rows, shipping and invalid-number changes invalidate pending results',async()=>{
    const edits=[c=>c.editOffer('offer-1-price','01000'),c=>c.editOffer('offer-1-grams','1000.0'),c=>c.editOffer('offer-1-name','Current product '),c=>c.editOffer('offer-1-shipping','0'),c=>c.editOffer('offer-2-name','Another product'),c=>c.editOffer('offer-1-price','',{badInput:true,valid:false}),c=>{c.editOffer('offer-1-price','2000');c.editOffer('offer-1-price','1000');}];
    for(const edit of edits){const c=offersFixture();c.fillOffer();let reply;c.api=()=>new Promise(resolve=>{reply=resolve;});const pending=c.submitOffers();edit(c);reply(offerReply('Obsolete result'));await pending;assert.equal(c.$('offers-result').hidden,true);assert.doesNotMatch(c.$('offer-comparison').textContent,/Obsolete/);}
  });
  await check('Purchase signatures also reject changed values when no input event was dispatched',async()=>{
    const c=offersFixture();c.fillOffer();let reply;c.api=()=>new Promise(resolve=>{reply=resolve;});const pending=c.submitOffers();c.$('offer-1-price').value='2000';reply(offerReply('Obsolete result'));await pending;
    assert.equal(c.$('offers-result').hidden,true);assert.equal(c.$('offer-1-price').value,'2000');
  });
  await check('A late purchase error after edits cannot replace the current feedback',async()=>{
    const c=offersFixture();c.fillOffer();let reject;c.api=()=>new Promise((resolve,fail)=>{reject=fail;});const pending=c.submitOffers();c.editOffer('offer-1-shipping','0');c.showNotice('offers-feedback','Keep current input feedback','info');reject(new Error('Obsolete comparison failure'));await pending;
    assert.match(c.$('offers-feedback').textContent,/Keep current input/);assert.doesNotMatch(c.$('offers-feedback').textContent,/Obsolete/);assert.equal(c.$('offer-1-shipping').value,'0');assert.equal(c.$('offers-result').hidden,true);
  });
  await check('Superseded purchase network errors do not disconnect the current edited workspace',async()=>{
    const c=offersFixture();c.fillOffer();let reject;c.fetch=()=>new Promise((resolve,fail)=>{reject=fail;});const pending=c.submitOffers();c.$('offer-currency').value='USD';c.$('offer-currency').listeners.change();reject(new Error('Synthetic transport failure'));await pending;
    assert.equal(c.state.token,'test-token');assert.equal(c.state.connectionState,'connected');assert.equal(c.$('offers-result').hidden,true);
  });
  await check('An active purchase comparison protects exit even when every input is cleared',async()=>{
    const c=offersFixture();c.fillOffer();let reply;c.api=()=>new Promise(resolve=>{reply=resolve;});const pending=c.submitOffers();for(const key of ['name','price','grams','shipping'])c.editOffer(`offer-1-${key}`,'');
    assert.equal(c.exitIsProtected(),true);reply(offerReply());await pending;assert.equal(c.exitIsProtected(),false);assert.equal(c.$('offers-result').hidden,true);
  });
  await check('Explicit purchase retry uses current currency and shipping without replay or saved-state claims',async()=>{
    const c=offersFixture();c.fillOffer();let reply;const requests=[];c.api=(path,payload)=>{requests.push(plain(payload));return new Promise(resolve=>{reply=resolve;});};const old=c.submitOffers();c.$('offer-currency').value='USD';c.$('offer-currency').listeners.change();c.editOffer('offer-1-shipping','0');reply(offerReply('Old'));await old;assert.equal(requests.length,1);
    c.api=async(path,payload)=>{requests.push(plain(payload));return offerReply('Current result','USD');};await c.submitOffers();assert.equal(requests.length,2);assert.equal(requests[0].offers[0].shipping,null);assert.equal(requests[1].offers[0].shipping,0);assert.equal(requests[1].offers[0].currency,'USD');assert.equal(c.$('offers-result').hidden,false);assert.match(c.$('offer-comparison').textContent,/Current result/);assert.equal(c.exitIsProtected(),true);
  });
  await check('Invalid partial purchase numbers are preserved and never sent as unknown shipping',async()=>{
    const c=offersFixture();c.fillOffer();c.$('offer-1-shipping').validity={badInput:true,valid:false};let calls=0;c.api=async()=>{calls++;return offerReply();};await c.submitOffers();assert.equal(calls,0);assert.equal(c.$('offer-1-shipping').validity.badInput,true);assert.equal(c.$('offers-feedback').hidden,false);assert.equal(c.$('offers-result').hidden,true);
  });
  await check('A current purchase error stays actionable and releases its busy state',async()=>{
    const c=offersFixture();c.fillOffer();c.api=async()=>{throw new Error('Current comparison failure');};await c.submitOffers();assert.match(c.$('offers-feedback').textContent,/Current comparison failure/);assert.equal(c.$('compare-offers').disabled,false);assert.equal(c.state.offersPending,false);assert.equal(c.$('offer-1-price').disabled,false);
  });
  await check('Expired sessions expose reconnect, clear credentials and never replay the failed mutation',async()=>{
    const c=fixture();let calls=0;c.$('bootstrap-error').hidden=true;
    c.fetch=async()=>{calls++;return {ok:false,status:403,json:async()=>({detail:'다시 연결해 주세요.',code:'session_expired'})};};
    await assert.rejects(c.api('/api/models',{template:'tray'}),error=>error.status===403);
    assert.equal(calls,1);assert.equal(c.state.token,null);assert.equal(c.$('bootstrap-error').hidden,false);assert.match(c.$('connection-status').textContent,/연결/);
  });
  await check('Page exit protects model-only unfinished input and a pending model operation',()=>{
    const c=profileFixture();c.$('parameter-width').value='';c.$('parameter-width').validity={badInput:true,valid:false};c.state.workflowBusy=true;
    let handler,prevented=false;c.window.addEventListener=(name,callback)=>{if(name==='beforeunload')handler=callback;};
    const start=source.indexOf('  window.addEventListener("beforeunload"'),end=source.indexOf('  window.addEventListener("pagehide"',start);
    vm.runInContext(source.slice(start,end),c);handler({preventDefault(){prevented=true;}});assert.equal(prevented,true);
  });
  await check('History asks before replacing an unfinished model and cancel keeps its exact state',async()=>{
    const c=fixture(),saved=job();saved.result.parameters.width=88;c.state.parameters.width=120;c.$('parameter-width').value='';c.$('parameter-width').validity={badInput:true,valid:false};c.$('model-replace-confirm').hidden=true;c.changeView=()=>{};
    c.api=async path=>path.startsWith('/api/jobs?')||path==='/api/jobs'?{jobs:[saved],next_cursor:null}:saved;
    await c.loadHistory();await c.$('history-list').children[0].children.find(child=>child.listeners.click).listeners.click();
    assert.equal(c.state.parameters.width,120);assert.equal(c.state.job,null);assert.equal(c.$('model-replace-confirm').hidden,false);
    c.cancelModelReplacement();assert.equal(c.$('parameter-width').value,'');assert.equal(c.$('parameter-width').validity.badInput,true);assert.equal(c.state.parameters.width,120);
  });
  await check('Older history failure cannot erase a newer successful list',async()=>{
    const c=fixture(),pending=[];c.api=()=>new Promise((resolve,reject)=>pending.push({resolve,reject}));
    const old=c.loadHistory(),fresh=c.loadHistory();pending[1].resolve({jobs:[job()],next_cursor:null});await fresh;const latest=c.$('history-list').textContent;
    pending[0].reject(new Error('older failure'));await old;assert.equal(c.$('history-list').textContent,latest);assert.doesNotMatch(c.$('history-feedback').textContent,/older failure/);
  });
  await check('History uses a bounded cursor page and retains loaded records if more loading fails',async()=>{
    const c=fixture();const requested=[];c.api=async path=>{requested.push(path);return {jobs:[job()],next_cursor:'next cursor'};};
    await c.loadHistory();assert.equal(requested[0],'/api/jobs?limit=20');assert.equal(c.$('history-more').hidden,false);
    const previous=c.$('history-list').textContent;c.api=async path=>{requested.push(path);throw new Error('page failed');};await c.loadHistory(true);
    assert.equal(requested[1],'/api/jobs?limit=20&before=next%20cursor');assert.equal(c.$('history-list').textContent,previous);assert.equal(c.$('history-more').hidden,false);
  });
  await check('A successful CAD response from before reconnect cannot replace the current result',async()=>{
    const c=fixture(),kept={...job(),id:'kept-job'},stale={...job(),id:'old-server-job'};c.renderJob(kept);const downloads=c.$('download-links').textContent;let release;const calls=[];
    c.fetch=async path=>{calls.push(path);if(path==='/api/models')return new Promise(resolve=>{release=resolve;});return {ok:true,status:200,json:async()=>({session_token:'new-token',templates:c.state.templates,environment:{available:false},storage:{path:'/new-root',source:'argument',recovery:{}}})};};
    const pending=c.generateModel();await c.bootstrap();release({ok:true,status:200,json:async()=>stale});await pending;
    assert.equal(c.state.job,kept);assert.equal(c.$('download-links').textContent,downloads);assert.equal(c.state.token,'new-token');assert.equal(c.state.storage.path,'/new-root');assert.equal(calls.filter(path=>path==='/api/models').length,1);assert.match(c.$('model-feedback').textContent,/이전|연결/);assert.match(c.$('model-feedback').textContent,/기록/);assert.doesNotMatch(c.$('model-feedback').textContent,/실제 CAD 모델과 파일을 생성/);
  });
  await check('A successful text plan from the old connection cannot replace current dimensions',async()=>{
    const c=fixture();c.$('request-text').value='keep this request';let release;c.fetch=async path=>path==='/api/plan'?new Promise(resolve=>{release=resolve;}):{ok:true,status:200,json:async()=>({session_token:'new-token',templates:c.state.templates,environment:{}})};
    const pending=c.preparePlan();await c.bootstrap();release({ok:true,status:200,json:async()=>({status:'ready',parameters:{template:'tray',width:88},message:'old plan'})});await pending;
    assert.equal(c.state.parameters.width,120);assert.equal(c.$('parameter-width').value,'120');assert.equal(c.$('request-text').value,'keep this request');assert.doesNotMatch(c.$('plan-feedback').textContent,/old plan/);assert.match(c.$('plan-feedback').textContent,/연결/);
  });
  await check('A successful workspace save from the old connection cannot adopt its record identity',async()=>{
    const c=profileFixture();c.$('workspace-title').value='Keep title';c.$('profile-json').value='{ unfinished';const snapshot=c.captureProfileSnapshot(),before=c.state.workspaceSavedSignature;let release;c.loadWorkspaces=async()=>{};
    c.fetch=async path=>path==='/api/profile-workspaces'?new Promise(resolve=>{release=resolve;}):{ok:true,status:200,json:async()=>({session_token:'new-token',templates:c.state.templates,environment:{},storage:{path:'/new-root',source:'argument',recovery:{}}})};
    const pending=c.saveWorkspace();await c.bootstrap();release({ok:true,status:200,json:async()=>workspaceRecord(snapshot)});await pending;
    assert.equal(c.state.workspaceId,null);assert.equal(c.state.workspaceRevision,null);assert.equal(c.state.workspaceSavedSignature,before);assert.equal(c.$('profile-json').value,'{ unfinished');assert.equal(c.$('workspace-title').value,'Keep title');assert.match(c.$('workspace-feedback').textContent,/기록/);
  });
  await check('Old slice success cannot become current or fetch its job from the new connection',async()=>{
    const c=fixture();c.renderJob(job());c.$('slicer-json').value='{"machine":{},"process":{},"filaments":[]}';let release;const calls=[];
    c.fetch=async path=>{calls.push(path);if(path==='/api/slice')return new Promise(resolve=>{release=resolve;});return {ok:true,status:200,json:async()=>({session_token:'new-token',templates:c.state.templates,environment:{available:false}})};};
    const pending=c.runSlice(false);await c.bootstrap();release({ok:true,status:200,json:async()=>({plan:{ready:true,diagnostics:[]},execution:null})});await pending;
    assert.equal(c.state.slicePrepared,false);assert.equal(calls.some(path=>path.startsWith('/api/jobs/')),false);assert.match(c.$('slice-feedback').textContent,/연결/);assert.match(c.$('slice-feedback').textContent,/기록/);
  });
  await check('Connection changes while JSON is arriving reject successful reads before consumers receive data',async()=>{
    const c=fixture();let finishJson,ready;const reading=new Promise(resolve=>{ready=resolve;});c.fetch=async()=>({ok:true,status:200,json:()=>new Promise(resolve=>{finishJson=resolve;ready();})});const pending=c.api('/api/jobs/job-a');await reading;c.state.connectionEpoch+=1;c.state.token='new-token';finishJson(job());
    await assert.rejects(pending,error=>error.code==='connection_changed');assert.equal(c.state.token,'new-token');assert.equal(c.state.connectionState,'connected');
  });
  await check('A known storage location change detaches old job and workspace identities while preserving edits',async()=>{
    const c=profileFixture(),source=project();c.state.storage={path:'/old-root',source:'argument'};c.renderJob(job());c.state.projectSource=source;c.$('parameter-width').value='';c.$('parameter-width').validity={badInput:true,valid:false};c.$('request-text').value='keep request';c.$('profile-json').value='{ unfinished';c.$('workspace-title').value='keep title';c.state.workspaceId='old-workspace';c.state.workspaceRevision=7;c.state.workspaceSavedSignature=c.workspaceSignature();c.state.guidedEdits={nozzle_temperature:{value:'-'}};c.$('slicer-json').value='{ keep raw config';c.state.historyItems=[job()];c.state.historyLoaded=true;c.state.historyCursor='old-cursor';c.renderHistory();
    c.api=async path=>path==='/api/bootstrap'?{session_token:'new-token',templates:c.state.templates,environment:{},storage:{path:'/new-root',source:'argument',recovery:{indexed:0,interrupted:0,unreadable:0}}}:{workspaces:[]};await c.bootstrap();
    assert.equal(c.state.job,null);assert.equal(c.$('model-result').hidden,true);assert.equal(c.$('download-links').children.length,0);assert.equal(c.state.workspaceId,null);assert.equal(c.state.workspaceRevision,null);assert.equal(c.state.workspaceSavedSignature,null);assert.equal(c.state.historyItems.length,0);assert.equal(c.state.historyCursor,null);assert.equal(c.$('history-list').children.length,0);assert.equal(c.$('parameter-width').value,'');assert.equal(c.$('parameter-width').validity.badInput,true);assert.equal(c.$('request-text').value,'keep request');assert.equal(c.state.projectSource,source);assert.equal(c.$('profile-json').value,'{ unfinished');assert.equal(c.$('workspace-title').value,'keep title');assert.equal(c.state.guidedEdits.nozzle_temperature.value,'-');assert.equal(c.$('slicer-json').value,'{ keep raw config');assert.equal(c.workspaceDirty(),true);assert.match(c.$('storage-change-notice').textContent,/저장 위치가 바뀌/);assert.match(c.$('storage-change-notice').textContent,/old-root/);assert.match(c.$('storage-change-notice').textContent,/원래/);
  });
  await check('Reconnect to the same known storage preserves current result and saved workspace identity',async()=>{
    const c=profileFixture(),saved=job();c.state.storage={path:'/same-root',source:'argument'};c.renderJob(saved);c.state.workspaceId='same-workspace';c.state.workspaceRevision=4;c.$('workspace-title').value='Saved title';c.state.workspaceSavedSignature=c.workspaceSignature();const signature=c.state.workspaceSavedSignature,downloads=c.$('download-links').textContent;
    c.api=async path=>path==='/api/bootstrap'?{session_token:'new-token',templates:c.state.templates,environment:{},storage:{path:'/same-root',source:'argument',recovery:{}}}:{workspaces:[]};await c.bootstrap();
    assert.equal(c.state.job,saved);assert.equal(c.state.workspaceId,'same-workspace');assert.equal(c.state.workspaceRevision,4);assert.equal(c.state.workspaceSavedSignature,signature);assert.equal(c.$('download-links').textContent,downloads);
  });
  await check('Storage switches retain readable unsaved outcome notes with their original job and protect exit',async()=>{
    const c=profileFixture(),original={...job(),id:'old-job'};c.state.storage={path:'/old-root',source:'argument'};c.renderJob(original);c.$('outcome-result').value='failure';c.$('outcome-notes').value='Unsubmitted result notes';
    c.api=async path=>path==='/api/bootstrap'?{session_token:'new-token',templates:c.state.templates,environment:{},storage:{path:'/new-root',source:'argument',recovery:{}}}:{workspaces:[]};await c.bootstrap();
    assert.match(c.$('retained-outcome-notes').textContent,/Unsubmitted result notes/);assert.match(c.$('retained-outcome-notes').textContent,/old-job/);assert.match(c.$('retained-outcome-notes').textContent,/old-root/);assert.equal(c.$('retained-outcome-notes').hidden,false);assert.equal(c.hasPendingWork(),true);
    c.renderJob({...job(),id:'new-job'});assert.equal(c.$('outcome-notes').value,'');assert.match(c.$('retained-outcome-notes').textContent,/Unsubmitted result notes/);assert.equal(c.state.retainedOutcomeDrafts[0].result,'failure');assert.equal(c.hasPendingWork(),true);
    const dismiss=findElement(c.$('retained-outcome-notes'),element=>Boolean(element.listeners.click));dismiss.listeners.click();assert.equal(c.state.retainedOutcomeDrafts.length,0);assert.equal(c.$('retained-outcome-notes').hidden,true);assert.equal(c.hasPendingWork(),false);
  });
  await check('Multiple storage switches retain each unsaved outcome under its own original job and path',async()=>{
    const c=profileFixture();c.state.storage={path:'/root-a',source:'argument'};let target='/root-b';c.api=async path=>path==='/api/bootstrap'?{session_token:'new-token',templates:c.state.templates,environment:{},storage:{path:target,source:'argument',recovery:{}}}:{workspaces:[]};
    c.renderJob({...job(),id:'job-a'});c.$('outcome-notes').value='note A';await c.bootstrap();c.renderJob({...job(),id:'job-b'});c.$('outcome-notes').value='note B';target='/root-c';await c.bootstrap();
    assert.deepEqual(plain(c.state.retainedOutcomeDrafts.map(item=>[item.job_id,item.storage_path,item.notes])),[['job-a','/root-a','note A'],['job-b','/root-b','note B']]);assert.match(c.$('retained-outcome-notes').textContent,/note A/);assert.match(c.$('retained-outcome-notes').textContent,/note B/);assert.equal(c.state.job,null);
  });
  await check('Unrelated HTTP failures do not expire a working session',async()=>{
    const c=fixture();c.$('bootstrap-error').hidden=true;c.fetch=async()=>({ok:false,status:403,json:async()=>({detail:'다른 조건의 거절',code:'other_rejection'})});
    await assert.rejects(c.api('/api/models',{}),error=>error.status===403&&error.code==='other_rejection');assert.equal(c.state.token,'test-token');assert.equal(c.$('bootstrap-error').hidden,true);
  });
  await check('A stale history network failure cannot change current connection state',async()=>{
    const c=fixture(),pending=[];c.fetch=()=>new Promise((resolve,reject)=>pending.push({resolve,reject}));
    const old=c.loadHistory(),fresh=c.loadHistory();pending[1].resolve({ok:true,json:async()=>({jobs:[job()],next_cursor:'more'})});await fresh;
    pending[0].reject(new Error('old network failure'));await old;assert.equal(c.state.token,'test-token');assert.equal(c.state.connectionState,'connected');assert.match(c.$('history-list').textContent,/Tray/);assert.equal(c.state.historyCursor,'more');
  });
  await check('A network failure from before reconnect cannot invalidate the new session',async()=>{
    const c=fixture();let reject;c.fetch=()=>new Promise((_resolve,fail)=>{reject=fail;});const pending=c.api('/api/models',{});c.state.connectionEpoch+=1;c.state.token='new-session';
    reject(new Error('old disconnect'));await assert.rejects(pending,/처리 여부/);assert.equal(c.state.token,'new-session');assert.equal(c.state.connectionState,'connected');
  });
  await check('Reconnect preserves pending model and filament input, source and downloads while showing storage',async()=>{
    const c=profileFixture(),saved=job();c.renderJob(saved);const source=project();c.state.projectSource=source;c.$('parameter-width').value='';c.$('parameter-width').validity={badInput:true,valid:false};c.$('request-text').value='new request';c.$('profile-json').value='{ unfinished';c.$('setup-printer-model').value='keep printer';c.$('workspace-title').value='keep work';c.state.guidedEdits={nozzle_temperature:{value:'-'}};
    const downloads=c.$('download-links').textContent,paths=[];c.api=async path=>{paths.push(path);return path==='/api/bootstrap'?{session_token:'new-token',templates:c.state.templates,environment:{},storage:{path:'/Users/test/한글 폴더',source:'user_default',legacy:false,recovery:{indexed:12,interrupted:2,unreadable:1}}}:{workspaces:[]};};await c.bootstrap();
    assert.equal(c.state.token,'new-token');assert.equal(c.state.connectionState,'connected');assert.equal(c.$('parameter-width').value,'');assert.equal(c.$('parameter-width').validity.badInput,true);assert.equal(c.$('request-text').value,'new request');assert.equal(c.$('profile-json').value,'{ unfinished');assert.equal(c.$('setup-printer-model').value,'keep printer');assert.equal(c.$('workspace-title').value,'keep work');assert.equal(c.state.projectSource,source);assert.equal(c.state.job,saved);assert.equal(c.$('download-links').textContent,downloads);assert.equal(c.state.guidedEdits.nozzle_temperature.value,'-');assert.equal(c.$('storage-path').textContent,'/Users/test/한글 폴더');assert.match(c.$('storage-recovery').textContent,/중단 처리 2개/);assert.deepEqual(paths,['/api/bootstrap','/api/profile-workspaces','/api/studio-library?kind=workspaces&limit=25']);
  });
  await check('Reconnect invalidates a pending history open without replacing current work',async()=>{
    const c=fixture();let reply;c.changeView=()=>{};c.api=path=>path==='/api/jobs/job-a'?new Promise(resolve=>{reply=resolve;}):Promise.resolve({session_token:'new-token',templates:c.state.templates,environment:{}});
    const open=c.openHistoryJob(job(),new Element());await c.bootstrap();reply(job());await open;assert.equal(c.state.job,null);assert.equal(c.state.modelReplacement,null);assert.equal(c.state.token,'new-token');
  });
  await check('Saved generated work is clean until its input, outcome, or slicer draft changes',()=>{
    const c=profileFixture();c.renderJob(job());assert.equal(c.hasPendingWork(),false);
    c.$('parameter-width').value='120.0';assert.equal(c.hasPendingWork(),true);c.$('parameter-width').value='120';assert.equal(c.hasPendingWork(),false);
    c.$('outcome-notes').value='unsaved observation';assert.equal(c.hasPendingWork(),true);c.$('outcome-notes').value='';
    c.state.slicerStaged=true;assert.equal(c.hasPendingWork(),true);c.state.slicerStaged=false;c.state.workspaceBusy=true;assert.equal(c.hasPendingWork(),true);
  });
  await check('Template and reset replacement cancellation preserves exact numeric input and generated result',()=>{
    for(const action of [{kind:'template',template:'cable_comb'},{kind:'reset',template:'tray'}]) {
      const c=fixture(),saved=job();c.renderJob(saved);c.$('parameter-width').value='0120';c.state.projectSource=project();const downloads=c.$('download-links').textContent;
      c.requestModelReplacement(action);assert.equal(c.state.template,'tray');assert.equal(c.$('model-replace-confirm').hidden,false);c.cancelModelReplacement();assert.equal(c.$('parameter-width').value,'0120');assert.equal(c.state.projectSource.id,'idea');assert.equal(c.state.job,saved);assert.equal(c.$('download-links').textContent,downloads);
    }
  });
  await check('Editing after replacement confirmation requires renewed confirmation before applying',()=>{
    const c=fixture();c.$('parameter-width').value='121';c.requestModelReplacement({kind:'template',template:'cable_comb'});c.$('parameter-width').value='122';c.confirmModelReplacement();assert.equal(c.state.template,'tray');assert.equal(c.$('parameter-width').value,'122');assert.match(c.$('model-replace-detail').textContent,/한 번 더/);
    c.confirmModelReplacement();assert.equal(c.state.template,'cable_comb');assert.equal(c.state.parameters.width,80);assert.equal(c.$('model-replace-confirm').hidden,true);
  });
  await check('Only the latest explicitly chosen replacement target can be applied',()=>{
    const c=fixture();c.$('parameter-width').value='121';c.requestModelReplacement({kind:'template',template:'cable_comb'});c.requestModelReplacement({kind:'reset',template:'tray'});c.confirmModelReplacement();assert.equal(c.state.template,'tray');assert.equal(c.state.parameters.width,120);
  });
  await check('History response arriving after a draft edit cannot apply or ask for an obsolete replacement',async()=>{
    const c=fixture();let reply;c.api=()=>new Promise(resolve=>{reply=resolve;});const pending=c.openHistoryJob(job(),new Element());c.$('parameter-width').value='121';reply(job());await pending;
    assert.equal(c.state.job,null);assert.equal(c.state.modelReplacement,null);assert.equal(c.$('parameter-width').value,'121');assert.match(c.$('history-feedback').textContent,/편집을 유지/);
  });
  await check('History refresh keeps prior records and cursor after a current failure, then recovers',async()=>{
    const c=fixture();c.api=async()=>({jobs:[job()],next_cursor:'cursor-a'});await c.loadHistory();const shown=c.$('history-list').textContent;c.api=async()=>{throw new Error('temporary failure');};await c.loadHistory();assert.equal(c.$('history-list').textContent,shown);assert.equal(c.state.historyCursor,'cursor-a');assert.match(c.$('history-feedback').textContent,/유지/);
    c.api=async()=>({jobs:[{...job(),id:'job-b',title:'Recovered'}],next_cursor:null});await c.loadHistory();assert.match(c.$('history-list').textContent,/Recovered/);assert.doesNotMatch(c.$('history-list').textContent,/Tray/);assert.equal(c.$('history-more').hidden,true);
  });
  await check('History cursor appends unique records and visibly distinguishes interrupted and unreadable items',async()=>{
    const c=fixture();let count=0;c.api=async()=>++count===1?{jobs:[job()],next_cursor:'more'}:{jobs:[job(),{id:'stopped',title:'Stopped',status:'interrupted'},{id:'broken',title:'Broken',status:'unreadable',diagnostic:'원본 파일은 보존했습니다.'}],next_cursor:null};await c.loadHistory();await c.loadHistory(true);
    assert.equal(c.state.historyItems.length,3);assert.equal(c.$('history-list').children.length,3);assert.match(c.$('history-list').textContent,/생성 중단/);assert.match(c.$('history-list').textContent,/기록 읽기 확인 필요/);assert.match(c.$('history-list').textContent,/원본 파일은 보존/);assert.equal(c.$('history-more').hidden,true);
  });
  await check('Interrupted requests prepare editable dimensions only after confirmation and create no model',async()=>{
    const c=fixture(),saved={id:'stopped',title:'중단된 모델 생성',status:'interrupted',result:null,request:{template:'tray',width:88},design_source:project(),events:[{type:'generation_interrupted',message:'완료 전에 중단되었습니다.'}]};c.changeView=()=>{};c.renderJob(job());c.$('parameter-width').value='123';c.api=async()=>saved;
    await c.openHistoryJob(saved,new Element());assert.match(c.$('history-feedback').textContent,/중단/);const retry=c.$('history-feedback').children.find(child=>child.listeners.click);assert(retry);retry.listeners.click();assert.equal(c.state.parameters.width,120);c.confirmModelReplacement();assert.equal(c.state.parameters.width,88);assert.equal(c.state.projectSource.id,'idea');assert.equal(c.state.job,null);assert.equal(c.$('model-result').hidden,true);assert.equal(c.$('download-links').children.length,0);assert.match(c.$('model-feedback').textContent,/새 모델을 생성/);
  });
  await check('Legacy interrupted records without saved inputs do not invent a retry or download',async()=>{
    const c=fixture(),record={id:'legacy',status:'interrupted',result:null,events:[]};c.api=async()=>record;await c.openHistoryJob(record,new Element());assert.equal(c.$('history-feedback').children.some(child=>child.listeners.click),false);assert.equal(c.state.job,null);assert.equal(c.$('download-links').children.length,0);
  });
  await check('Unreadable history errors keep the current draft and prior visible list',async()=>{
    const c=fixture();c.state.historyItems=[{id:'bad',status:'unreadable',title:'Bad'}];c.state.historyLoaded=true;c.renderHistory();const shown=c.$('history-list').textContent;c.$('parameter-width').value='0120';c.api=async()=>{const error=new Error('원본 파일은 보존했습니다.');error.status=409;error.code='job_record_unreadable';throw error;};await c.openHistoryJob(c.state.historyItems[0],new Element());assert.equal(c.$('parameter-width').value,'0120');assert.equal(c.$('history-list').textContent,shown);assert.equal(c.state.job,null);assert.match(c.$('history-feedback').textContent,/원본 파일은 보존/);
  });
  await check('Running and interrupted slice phases never render old slice success or sliced downloads',()=>{
    for(const phase of ['running','interrupted']) {const c=fixture(),saved=job();saved.latest_slice={phase,plan:{ready:true},execution:{status:'sliced',checks:[]}};c.renderJob(saved);assert.match(c.$('slice-feedback').textContent,phase==='running'?/실행 중/:/중단/);assert.doesNotMatch(c.$('download-links').textContent,/슬라이스 3MF/);assert.match(c.$('download-links').textContent,/STL/);assert.equal(c.state.slicePrepared,false);}
  });
  await check('A busy CAD response retains source without falsely reporting a changed recipe',async()=>{
    const c=fixture();c.state.projectSource=project();c.api=async()=>{const error=new Error('다른 모델 작업을 처리 중입니다.');error.status=409;error.code='resource_busy';throw error;};await c.generateModel();assert.match(c.$('model-feedback').textContent,/처리 중/);assert.doesNotMatch(c.$('model-feedback').textContent,/출처 연결/);assert.equal(c.state.projectSource.id,'idea');
  });
  await check('Browsing and filtering preserve exact unfinished draft and generated source',()=>{
    const c=fixture(),saved=job(); c.state.job=saved;c.state.projectSource={id:'saved',recipe_sha256:'b'.repeat(64)};
    c.$('parameter-width').value='';c.$('parameter-width').validity={badInput:true,valid:false};c.$('request-text').value='keep text';
    c.setDiscoveryCatalog({purposes:[{id:'all',title:'전체'}],projects:[project()]});c.browseProject('idea');c.discoveryFiltersChanged();
    assert.equal(c.state.job,saved);assert.equal(c.$('parameter-width').value,'');assert.equal(c.state.projectSource.id,'saved');assert.equal(c.$('request-text').value,'keep text');
  });
  await check('Numerically equivalent edited strings still require replacement confirmation and survive cancel',()=>{
    const c=fixture();c.setDiscoveryCatalog({purposes:[],projects:[project()]});c.$('parameter-width').value='120.0';c.browseProject('idea');c.requestProjectApplication();
    assert.equal(c.state.projectReplacement?.id,'idea');assert.equal(c.state.parameters.width,120);assert.equal(c.$('parameter-width').value,'120.0');
    c.cancelProjectApplication();assert.equal(c.$('parameter-width').value,'120.0');assert.equal(c.state.projectSource,null);
  });
  await check('A refreshed catalog makes preserved old recipe cards stale until a fresh recommendation',async()=>{
    const c=fixture(),oldProject=project(),newProject={...project(),recipe_sha256:'b'.repeat(64)};c.setDiscoveryCatalog({purposes:[],projects:[oldProject]});c.browseProject('idea');
    const savedSource=project(),savedJob=job();c.state.projectSource=savedSource;c.state.job=savedJob;c.$('parameter-width').value='120.0';c.$('request-text').value='keep request';
    c.setDiscoveryCatalog({purposes:[],projects:[newProject]},true);assert.equal(c.state.discoveryStale,true);assert.equal(c.$('discovery-apply').disabled,true);assert.match(c.$('discovery-summary').textContent,/이전 조건/);
    c.requestProjectApplication();assert.equal(c.state.projectReplacement,null);assert.equal(c.state.discoveryMatches[0].project.recipe_sha256,oldProject.recipe_sha256);assert.equal(c.state.projectSource,savedSource);assert.equal(c.state.job,savedJob);assert.equal(c.$('parameter-width').value,'120.0');assert.equal(c.$('request-text').value,'keep request');
    c.api=async()=>({matches:[{project:newProject}],excluded_count:0});await c.recommendProjects();c.browseProject('idea');assert.equal(c.state.discoveryStale,false);assert.equal(c.$('discovery-apply').disabled,false);assert.equal(c.state.discoveryMatches[0].project.recipe_sha256,newProject.recipe_sha256);
  });
  await check('Explicit application asks before replacing invalid live input and cancel preserves it',()=>{
    const c=fixture();c.setDiscoveryCatalog({purposes:[],projects:[project()]});c.$('parameter-width').value='';c.$('parameter-width').validity={badInput:true,valid:false};
    c.browseProject('idea');c.requestProjectApplication();assert.equal(c.state.projectReplacement.id,'idea');assert.equal(c.$('parameter-width').value,'');
    c.cancelProjectApplication();assert.equal(c.state.projectReplacement,null);assert.equal(c.$('parameter-width').value,'');
    c.requestProjectApplication();c.confirmProjectApplication();assert.equal(c.state.parameters.width,90);assert.equal(c.state.projectSource.id,'idea');
  });
  await check('Detach preserves input text and invalidates a generated result',()=>{
    const c=fixture();c.state.projectSource=project();c.state.job=job();c.$('parameter-width').value='001.20';c.$('request-text').value='keep';
    c.detachProjectSource();assert.equal(c.$('parameter-width').value,'001.20');assert.equal(c.$('request-text').value,'keep');assert.equal(c.state.projectSource,null);assert.equal(c.state.job,null);
  });
  await check('Partial placement numbers are rejected instead of becoming missing axes',()=>{
    const c=fixture();c.$('space-width').value='';c.$('space-width').validity={badInput:true,valid:false};assert.throws(()=>c.discoveryQuery(),/가로/);
  });
  await check('Late recommendations cannot replace results after filter edits or catalog reload',async()=>{
    for(const mutate of [c=>{c.$('space-width').value='10';c.discoveryFiltersChanged();},c=>c.setDiscoveryCatalog({purposes:[],projects:[project('new')]}),c=>{c.$('space-height').value='9';}]) {
      const c=fixture();c.setDiscoveryCatalog({purposes:[],projects:[project()]});let done;c.api=()=>new Promise(resolve=>{done=resolve;});const pending=c.recommendProjects();mutate(c);done({matches:[],excluded_count:1});await pending;assert.equal(c.state.discoveryMatches.length,1);
    }
  });
  await check('Workflow guards block discovery application, confirmation, and detach handlers',()=>{
    const c=fixture();c.setDiscoveryCatalog({purposes:[],projects:[project()]});c.browseProject('idea');c.state.projectReplacement=project();c.state.projectSource=project();c.state.workflowBusy=true;
    c.requestProjectApplication();c.confirmProjectApplication();c.detachProjectSource();assert.equal(c.state.parameters.width,120);assert.equal(c.state.projectSource.id,'idea');
  });
  await check('Generic/reset drafts clear source and successful text plans clear it',async()=>{
    const c=fixture();c.state.projectSource=project();c.applyDraft('tray');assert.equal(c.state.projectSource,null);
    c.state.projectSource=project();c.$('request-text').value='request';c.api=async()=>({status:'ready',parameters:{template:'tray',width:100}});await c.preparePlan();c.confirmModelReplacement();assert.equal(c.state.projectSource,null);assert.equal(c.state.parameters.width,100);
  });
  await check('History and generated source use the saved snapshot rather than today’s catalog',async()=>{
    const c=fixture(),value=job();value.design_source={kind:'project_catalog',project_id:'idea',recipe_sha256:'b'.repeat(64),recipe:{...project(),title:'Saved old title'}};
    c.setDiscoveryCatalog({purposes:[],projects:[project()]});c.changeView=()=>{};c.api=async path=>path.startsWith('/api/jobs?')?{jobs:[value],next_cursor:null}:value;await c.loadHistory();
    await c.$('history-list').children[0].children.find(child=>child.listeners.click).listeners.click();
    assert.match(c.$('generated-source').textContent,/Saved old title/);assert.equal(c.state.projectSource.recipe_sha256,'b'.repeat(64));assert.match(c.$('draft-source').textContent,/Saved old title/);
  });
  await check('Generation sends only source identity and stale conflict preserves draft for detach',async()=>{
    const c=fixture();c.state.projectSource=project();c.$('parameter-width').value='97';c.document.querySelectorAll=selector=>selector==='[data-parameter]'?[Object.assign(new Element(),{dataset:{parameter:'width'},valueAsNumber:97})]:[];
    let body;c.api=async(path,payload)=>{body=plain(payload);const error=new Error('Recipe changed');error.status=409;throw error;};await c.generateModel();
    assert.deepEqual(body.project_selection,{id:'idea',recipe_sha256:'a'.repeat(64)});assert.equal(body.width,97);assert.equal(c.$('parameter-width').value,'97');assert.match(c.$('model-feedback').textContent,/출처 연결/);assert.equal(c.state.projectSource.id,'idea');
  });
  await check('Changed filters and failed requests visibly invalidate old placement comparisons',async()=>{
    const c=fixture();c.setDiscoveryCatalog({purposes:[],projects:[project()]});c.state.discoveryMatches=[{project:project(),space_fit:{status:'fits'}}];c.browseProject('idea');
    c.$('space-width').value='2';c.discoveryFiltersChanged();assert.equal(c.state.discoveryStale,true);assert.equal(c.$('discovery-apply').disabled,true);assert.doesNotMatch(c.$('discovery-cards').textContent,/입력한 축의 공간 크기와 비교됨/);
    c.api=async()=>{throw new Error('offline');};await c.recommendProjects();assert.equal(c.state.discoveryStale,true);assert.equal(c.$('discovery-apply').disabled,true);
  });
  await check('Reconnecting preserves browsed results and exact active source even when catalog changes',()=>{
    const c=fixture();c.setDiscoveryCatalog({purposes:[],projects:[project()]});c.browseProject('idea');c.state.projectSource=project();c.state.job=job();c.$('parameter-width').value='';c.$('parameter-width').validity={badInput:true};
    c.setDiscoveryCatalog({purposes:[],projects:[project('new')]},true);assert.equal(c.state.discoveryBrowsed,'idea');assert.equal(c.state.discoveryMatches[0].project.id,'idea');assert.equal(c.state.projectSource.id,'idea');assert.equal(c.$('parameter-width').value,'');assert.equal(c.state.job.id,'job-a');
  });
  await check('Newer recommendation wins and late failures cannot replace its result',async()=>{
    const c=fixture();c.setDiscoveryCatalog({purposes:[],projects:[project()]});const replies=[];c.api=()=>new Promise((resolve,reject)=>replies.push({resolve,reject}));
    const older=c.recommendProjects();c.$('space-width').value='100';c.discoveryFiltersChanged();const newer=c.recommendProjects();replies[1].resolve({matches:[{project:project('new')}],excluded_count:0});await newer;replies[0].reject(new Error('old failure'));await older;
    assert.equal(c.state.discoveryMatches[0].project.id,'new');assert.doesNotMatch(c.$('discovery-feedback').textContent,/old failure/);assert.equal(c.state.discoveryPending,false);
  });
  await check('A free-text plan cannot replace parameter strings edited while its response was pending',async()=>{
    const c=fixture();c.$('request-text').value='first';c.state.projectSource=project();let done;c.api=()=>new Promise(resolve=>{done=resolve;});const pending=c.preparePlan();c.$('request-text').value='newer';done({status:'ready',parameters:{template:'tray',width:70}});await pending;assert.equal(c.state.parameters.width,120);assert.equal(c.state.projectSource.id,'idea');
  });
  await check('Placement rotation never rewrites starting geometry and source metadata stays text',()=>{
    const c=fixture(),p=project();p.source.creator='<img onerror=alert(1)>';c.setDiscoveryCatalog({purposes:[],projects:[p]});c.state.discoveryMatches=[{project:p,space_fit:{status:'fits_rotated'}}];c.$('parameter-width').value='120';c.browseProject('idea');c.requestProjectApplication();assert.equal(c.state.parameters.width,90);assert.match(c.$('draft-source').textContent,/<img onerror/);assert.equal(c.state.projectSource.parameters.depth,60);
    const metadata=c.$('draft-source').children.find(element=>element.className==='source-metadata');assert(metadata);assert.match(metadata.textContent,/geometry.py/);assert.doesNotMatch(c.$('draft-source').children.filter(element=>element!==metadata).map(element=>element.textContent).join(' '),/geometry.py|repository_original/);
  });
  await check('A failed refresh makes old fit labels stale even when filter values stayed unchanged',async()=>{
    const c=fixture();c.setDiscoveryCatalog({purposes:[],projects:[project()]});c.state.discoveryMatches=[{project:project(),space_fit:{status:'fits'}}];c.browseProject('idea');c.api=async()=>{throw new Error('offline');};await c.recommendProjects();
    assert.equal(c.state.discoveryStale,true);assert.equal(c.$('discovery-apply').disabled,true);assert.doesNotMatch(c.$('discovery-cards').textContent,/입력한 축의 공간 크기와 비교됨/);assert.match(c.$('discovery-summary').textContent,/이전 조건/);
  });
  await check('Actual bootstrap retry preserves a newer partial draft and applied source',async()=>{
    const c=fixture();c.setDiscoveryCatalog({purposes:[],projects:[project()]});c.browseProject('idea');c.state.projectSource=project();c.state.job=job();let done;c.api=()=>new Promise(resolve=>{done=resolve;});const pending=c.bootstrap();
    c.$('parameter-width').value='';c.$('parameter-width').validity={badInput:true};c.$('request-text').value='new draft';c.$('space-width').value='21';c.discoveryFiltersChanged();
    c.api=async()=>({items:[],next_cursor:null});done({session_token:'new',templates:c.state.templates,discovery:{purposes:[],projects:[project('new')]},environment:{}});await pending;
    assert.equal(c.$('parameter-width').value,'');assert.equal(c.$('request-text').value,'new draft');assert.equal(c.$('space-width').value,'21');assert.equal(c.state.projectSource.id,'idea');assert.equal(c.state.job.id,'job-a');assert.equal(c.state.discoveryMatches[0].project.id,'idea');
  });
  await check('A generated response cannot relabel a changed live draft as the generated result',async()=>{
    const c=fixture(),input=Object.assign(c.$('parameter-width'),{dataset:{parameter:'width'},value:'120',valueAsNumber:120});c.document.querySelectorAll=selector=>selector==='[data-parameter]'?[input]:[];let done;c.api=()=>new Promise(resolve=>{done=resolve;});
    const pending=c.generateModel();input.value='121';done(job());await pending;assert.equal(c.state.job,null);assert.match(c.$('model-feedback').textContent,/작업 기록/);
  });
  await check('An old empty result is labelled as previous conditions after a filter edit',()=>{
    const c=fixture();c.setDiscoveryCatalog({purposes:[],projects:[project()]});c.state.discoveryMatches=[];c.discoveryFiltersChanged();assert.match(c.$('discovery-summary').textContent,/이전 조건/);assert.match(c.$('discovery-cards').textContent,/이전 조건/);
  });
  await check('Changing a template removes the previous job and preview target',()=>{
    const c=fixture();c.state.job=job();c.applyDraft('cable_comb');
    assert.equal(c.state.job,null);assert.equal(c.$('model-result').hidden,true);assert.equal(c.viewer.mesh,null);
  });
  await check('A saved plan with execution:null renders as a plan',()=>{
    const c=fixture(),value=job();value.latest_slice={plan:{ready:true,diagnostics:[]},execution:null};
    c.renderJob(value);assert.match(c.$('slice-feedback').textContent,/실행 계획/);assert.doesNotMatch(c.$('slice-feedback').textContent,/실행 결과 확인 필요/);
  });
  await check('A preparation response refreshes stale slice download aliases',async()=>{
    const c=fixture();c.state.job=job();c.$('slicer-json').value='{"machine":{},"process":{},"filaments":[]}';
    c.api=async(path)=>path==='/api/slice'?{plan:{ready:false,diagnostics:[]},execution:null}:{...job(),artifacts:{stl:'/api/jobs/job-a/files/stl'}};
    await c.runSlice(false);assert.equal(c.state.job.artifacts.sliced_three_mf,undefined);
  });
  await check('Pending slicing locks model generation until completion',async()=>{
    const c=fixture();c.state.job=job();c.$('slicer-json').value='{"machine":{},"process":{},"filaments":[]}';
    let resolve;c.api=path=>path==='/api/slice'?new Promise(done=>{resolve=done;}):Promise.resolve({...job(),artifacts:{}});
    const pending=c.runSlice(false);let failure;
    try {assert.equal(c.$('generate-button').disabled,true);}catch(error){failure=error;}
    resolve({plan:{ready:false,diagnostics:[]},execution:null});await pending;
    if(failure)throw failure;assert.equal(c.$('generate-button').disabled,false);
  });
  await check('Staged native files invalidate old slice downloads and block execution until assembled',async()=>{
    const c=fixture();c.state.job=job();c.state.slicePrepared=true;c.$('slicer-json').value='{"old":"manual"}';
    const machine={name:'Fixture machine',type:'machine',from:'User',nozzle_diameter:['0.4']};
    await c.readSlicerFiles('machine',{files:[{name:'machine.json',size:100,text:async()=>JSON.stringify(machine)}],value:'machine.json'});
    assert.equal(c.state.slicerStaged,true);assert.equal(c.state.slicePrepared,false);
    assert.equal(c.state.job.artifacts.sliced_three_mf,undefined);assert.equal(c.$('prepare-slice').disabled,true);assert.equal(c.$('execute-slice').disabled,true);
    assert.equal(c.$('slicer-json').value,'{"old":"manual"}');
    let requests=0;c.api=async()=>{requests++;};await c.runSlice(true);assert.equal(requests,0);
    c.cancelSlicerAssembly();assert.equal(c.$('slicer-json').value,'{"old":"manual"}');assert.equal(c.$('prepare-slice').disabled,false);
    assert.equal(c.$('execute-slice').disabled,true);
  });
  await check('Native helper preserves file values, filament order and explicit plate choice',async()=>{
    const c=fixture();c.state.job=job();
    const machine={name:'Machine',type:'machine',from:'system',nozzle_diameter:['0.4'],custom:['001','2']};
    const process={name:'Process',type:'process',from:'User',layer_height:'0.2'};
    const filaments=[{name:'A',type:'filament',from:'user',nozzle_temperature:['215']},{name:'B',type:'filament',from:'User',nozzle_temperature:['220']}];
    for(const [kind,profiles] of [['machine',[machine]],['process',[process]],['filaments',filaments]]) {
      await c.readSlicerFiles(kind,{files:profiles.map((profile,index)=>({name:`${kind}-${index}.json`,size:100,text:async()=>JSON.stringify(profile)})),value:'file'});
    }
    assert.throws(()=>c.assembleSlicerBundle(),/플레이트/);
    c.$('slicer-plate').value='Textured PEI Plate';c.changeSlicerPlate();c.assembleSlicerBundle();
    assert.deepEqual(JSON.parse(c.$('slicer-json').value),{source:'user_export',plate_type:'Textured PEI Plate',machine,process,filaments});
    assert.equal(c.state.slicerStaged,false);assert.equal(c.state.slicePrepared,false);assert.equal(c.$('prepare-slice').disabled,false);
    assert.equal(c.$('execute-slice').disabled,true);
  });
  await check('Malformed replacement and excessive filament selections preserve the accepted stage',async()=>{
    const c=fixture();const original={name:'Kept machine',type:'machine',from:'User'};
    c.state.slicerFiles.machine={filename:'kept.json',profile:original};c.$('slicer-json').value='{"kept":"bundle"}';
    await c.readSlicerFiles('machine',{files:[{name:'bad.json',size:4,text:async()=>'{bad'}],value:'bad.json'});
    assert.equal(c.state.slicerFiles.machine.profile,original);assert.equal(c.$('slicer-json').value,'{"kept":"bundle"}');
    assert.match(c.$('slicer-helper-feedback').textContent,/bad.json/);
    let reads=0;await c.readSlicerFiles('filaments',{files:Array.from({length:17},()=>({name:'f.json',size:10,text:async()=>{reads++;return '{}';}})),value:'file'});
    assert.equal(reads,0);assert.equal(c.state.slicerFiles.filaments.length,0);assert.match(c.$('slicer-helper-feedback').textContent,/16/);
  });
  await check('A late native file read cannot overwrite a new job or manual configuration',async()=>{
    for(const change of ['job','manual']) {
      const c=fixture();c.state.job=job();let finish;
      const pending=c.readSlicerFiles('machine',{files:[{name:'old.json',size:100,text:()=>new Promise(done=>{finish=done;})}],value:'old.json'});
      if(change==='job')c.renderJob({...job(),id:'new-job',artifacts:{}});
      else {c.$('slicer-json').value='{"new":"manual"}';c.manualSlicerChanged();}
      finish('{"name":"Old machine","type":"machine","from":"User"}');await pending;
      assert.equal(c.state.slicerFiles.machine,null);assert.deepEqual(plain(c.state.slicerPending),{});
      if(change==='manual')assert.equal(c.$('slicer-json').value,'{"new":"manual"}');
    }
  });
  await check('Independent native file reads can finish in either order without losing a selection',async()=>{
    const c=fixture();let machineDone,processDone;
    const machine=c.readSlicerFiles('machine',{files:[{name:'m.json',size:100,text:()=>new Promise(done=>{machineDone=done;})}],value:'m.json'});
    const process=c.readSlicerFiles('process',{files:[{name:'p.json',size:100,text:()=>new Promise(done=>{processDone=done;})}],value:'p.json'});
    processDone('{"name":"P","type":"process","from":"User"}');await process;
    machineDone('{"name":"M","type":"machine","from":"User"}');await machine;
    assert.equal(c.state.slicerFiles.machine.profile.name,'M');assert.equal(c.state.slicerFiles.process.profile.name,'P');
    assert.deepEqual(plain(c.state.slicerPending),{});
  });
  await check('A newer selection replaces an older pending file of the same native kind',async()=>{
    const c=fixture();let oldDone,newDone;
    const older=c.readSlicerFiles('machine',{files:[{name:'old.json',size:100,text:()=>new Promise(done=>{oldDone=done;})}],value:'old.json'});
    const newer=c.readSlicerFiles('machine',{files:[{name:'new.json',size:100,text:()=>new Promise(done=>{newDone=done;})}],value:'new.json'});
    newDone('{"name":"New","type":"machine","from":"User"}');await newer;
    oldDone('{"name":"Old","type":"machine","from":"User"}');await older;
    assert.equal(c.state.slicerFiles.machine.filename,'new.json');assert.equal(c.state.slicerFiles.machine.profile.name,'New');
    assert.deepEqual(plain(c.state.slicerPending),{});
  });
  await check('Native helper rejects oversized aggregate requests without dropping accepted files',async()=>{
    const c=fixture();const machine={name:'Large machine',type:'machine',from:'user',description:'x'.repeat(7*1024*1024)};
    c.state.slicerFiles.machine={filename:'machine.json',profile:machine};c.$('slicer-json').value='{"kept":"manual"}';
    const process=JSON.stringify({name:'Large process',type:'process',from:'user',description:'x'.repeat(2*1024*1024)});
    await c.readSlicerFiles('process',{files:[{name:'process.json',size:process.length,text:async()=>process}],value:'process.json'});
    assert.equal(c.state.slicerFiles.machine.profile,machine);assert.equal(c.state.slicerFiles.process,null);
    assert.equal(c.$('slicer-json').value,'{"kept":"manual"}');assert.match(c.$('slicer-helper-feedback').textContent,/8 MiB/);
    let reads=0;await c.readSlicerFiles('machine',{files:[{name:'too-large.json',size:8*1024*1024+1,text:async()=>{reads++;return '{}';}}],value:'large.json'});
    assert.equal(reads,0);assert.equal(c.state.slicerFiles.machine.profile,machine);
  });
  await check('Whole-bundle file read cannot replace a newer manual edit',async()=>{
    const c=fixture();c.state.job=job();let finish;
    const pending=c.readSlicerBundle({files:[{name:'old.json',size:100,text:()=>new Promise(done=>{finish=done;})}],value:'old.json'});
    c.$('slicer-json').value='{"new":"manual"}';c.manualSlicerChanged();
    finish('{"old":"bundle"}');await pending;
    assert.equal(c.$('slicer-json').value,'{"new":"manual"}');assert.deepEqual(plain(c.state.slicerPending),{});
  });
  await check('A real CLI probe result distinguishes file detection from supported command-line capabilities',async()=>{
    const c=fixture();c.state.job=job();c.state.slicePrepared=true;let finish;
    c.api=(path,body)=>{assert.equal(path,'/api/slicer/probe');assert.deepEqual(plain(body),{});return new Promise(done=>{finish=done;});};
    const pending=c.probeSlicer();assert.equal(c.$('generate-button').disabled,true);assert.equal(c.$('slicer-machine-file').disabled,true);assert.equal(c.state.slicePrepared,false);
    finish({available:true,path:'/test/bambu-studio',version:'2.9.1.70',capabilities:['--slice'],diagnostics:['Missing expected option'],cli_supported:false});
    await pending;assert.equal(c.$('prepare-slice').disabled,true);assert.equal(c.$('execute-slice').disabled,true);
    assert.match(c.$('slicer-probe-feedback').textContent,/2.9.1.70/);assert.match(c.$('slicer-probe-feedback').textContent,/Missing expected option/);
    assert.equal(c.state.environment.cli_supported,false);assert.equal(c.$('generate-button').disabled,false);
  });
  await check('Execution summaries show only returned native version and output digest evidence',()=>{
    const c=fixture();c.renderSliceResult({}, {status:'sliced',bambu_version:'2.9.1.70',output_sha256:'a'.repeat(64),estimated_time_seconds:null,filament_grams:null,checks:[]});
    assert.match(c.$('slice-result').textContent,/2.9.1.70/);assert.match(c.$('slice-result').textContent,new RegExp('a'.repeat(64)));
  });
  await check('A failed new probe does not leave an earlier CLI success badge looking current',async()=>{
    const c=fixture();c.state.environment={available:true,path:'/test/bambu-studio',cli_supported:true,version:'old',capabilities:['--slice'],diagnostics:[]};
    c.renderSlicerEnvironment();assert.match(c.$('slicer-status').textContent,/CLI 기능 확인됨/);
    c.api=async()=>{throw new Error('Connection failed');};await c.probeSlicer();
    assert.equal(c.state.environment.cli_supported,undefined);assert.equal(c.$('slicer-status').textContent,'실행 파일 감지됨');
    assert.match(c.$('slicer-probe-feedback').textContent,/Connection failed/);
  });
  await check('Failed history opens the recorded cause without dereferencing a model',async()=>{
    const c=fixture();const failedJob={id:'failed-job',title:'모델 생성 실패',status:'failed',created_at:'2026-11-12T00:00:00Z',result:null,events:[{type:'generation_failed',message:'벽과 바닥 안쪽에 양수 크기의 공간이 필요합니다.'}]};
    c.api=async path=>path.startsWith('/api/jobs?')?{jobs:[failedJob],next_cursor:null}:failedJob;
    await c.loadHistory();
    const card=c.$('history-list').children[0];
    const button=card.children.find(child=>child.listeners.click);
    assert(button);
    await button.listeners.click();
    assert.match(c.$('history-feedback').textContent,/양수 크기의 공간/);
    assert.doesNotMatch(c.$('history-feedback').textContent,/Cannot read/);
    assert.equal(c.state.job,null);
  });
  await check('Profile edits revoke a previous report and hide both review and inheritance results',()=>{
    const c=profileFixture();const revoked=[];
    c.URL={revokeObjectURL:url=>revoked.push(url)};
    c.state.profileDownloadUrl='blob:previous';c.state.profileReport={status:'resolved'};
    c.$('profile-download').setAttribute('href','blob:previous');
    c.invalidateProfile();
    assert.deepEqual(revoked,['blob:previous']);assert.equal(c.state.profileReport,null);
    for(const id of ['profile-result','profile-resolution','profile-download'])assert.equal(c.$(id).hidden,true);
    assert.equal(c.$('profile-download').attributes.href,undefined);
  });
  await check('A late profile review cannot restore a result after inputs change',async()=>{
    const c=profileFixture();c.$('profile-json').value='{}';
    let resolve,rendered=0;c.api=()=>new Promise(done=>{resolve=done;});
    c.renderProfile=()=>rendered++;c.renderProfileResolution=()=>rendered++;
    const pending=c.reviewProfile();c.invalidateProfile();resolve({decision:'needs_input'});
    await pending;assert.equal(rendered,0);assert.equal(c.state.profileReport,null);
  });
  await check('A late file read cannot overwrite a newer profile draft',async()=>{
    const c=profileFixture();let resolve;
    const input={files:[{name:'old.json',size:15,text:()=>new Promise(done=>{resolve=done;})}],value:'old.json'};
    const pending=c.importProfileFiles(input);
    c.$('profile-json').value='{"name":"New draft"}';c.invalidateProfile();
    resolve('{"name":"Old preset"}');await pending;
    assert.equal(c.$('profile-json').value,'{"name":"New draft"}');assert.equal(c.state.profileDocuments.length,0);
  });
  await check('A failed file import preserves the accepted document and its current review',async()=>{
    const c=profileFixture();const original={filename:'kept.json',profile:{name:'Kept'},draftText:'{"name":"Edited"}'};
    c.state.profileDocuments=[original];c.$('profile-json').value=original.draftText;
    const report={status:'resolved'};c.state.profileReport=report;c.state.profileDownloadUrl='blob:accepted';
    c.$('profile-download').setAttribute('href','blob:accepted');
    await c.importProfileFiles({files:[{name:'bad.json',size:4,text:async()=>'{bad'}],value:'bad.json'});
    assert.equal(c.state.profileDocuments.length,1);assert.equal(c.state.profileDocuments[0],original);
    assert.equal(c.$('profile-json').value,original.draftText);assert.equal(c.state.profileReport,report);
    assert.equal(c.$('profile-resolution').hidden,false);assert.equal(c.$('profile-download').attributes.href,'blob:accepted');
    assert.equal(c.$('profile-feedback').hidden,false);assert.match(c.$('profile-feedback').textContent,/bad.json/);
  });
  await check('Appending a missing parent preserves an existing unfinished draft and target',async()=>{
    const c=profileFixture();const kept={filename:'child.json',profile:{name:'Child',inherits:'Parent'},draftText:'  {"name":\nunfinished'};
    c.state.profileDocuments=[kept];c.$('profile-json').value=kept.draftText;c.$('setup-nozzle').value='0.40';
    const text='{"name":"Parent","nozzle_temperature":["205"]}';
    await c.importProfileFiles({files:[{name:'parent.json',size:text.length,text:async()=>text}],value:'parent.json'});
    assert.equal(c.state.profileDocuments.length,2);assert.equal(c.state.profileDocuments[0],kept);
    assert.equal(c.state.profileTarget,0);assert.equal(c.$('profile-json').value,kept.draftText);
    assert.equal(c.$('setup-nozzle').value,'0.40');assert.equal(c.state.profileReport,null);
  });
  await check('The first import adopts a valid pasted draft and refuses to replace an unfinished paste',async()=>{
    for(const valid of [true,false]) {
      const c=profileFixture();const pasted=valid?'  {"name":"Pasted"}\n':'  {"name":\n';
      c.$('profile-json').value=pasted;const text='{"name":"Imported"}';
      await c.importProfileFiles({files:[{name:'new.json',size:text.length,text:async()=>text}],value:'new.json'});
      assert.equal(c.$('profile-json').value,pasted);
      assert.equal(c.state.profileDocuments.length,valid?2:0);
      if(valid) {assert.equal(c.state.profileDocuments[0].filename,'pasted-filament.json');assert.equal(c.state.profileDocuments[0].draftText,pasted);}
      else assert.match(c.$('profile-feedback').textContent,/입력|초안/);
    }
  });
  await check('Reimporting an exact original keeps its edited draft, origin and existing review',async()=>{
    const c=profileFixture();const origin={type:'bambu_preset_archive',archive_name:'first.bbsflmt',archive_sha256:'a'.repeat(64),member_path:'filament/kept.json',member_sha256:'b'.repeat(64)};
    const original={name:'Kept',nozzle_temperature:['205']};const kept={filename:'filament/kept.json',profile:original,draftText:'{"name":"Kept","nozzle_temperature":["215"]}',origin};
    c.state.profileDocuments=[kept];c.$('profile-json').value=kept.draftText;const report={status:'resolved'};c.state.profileReport=report;
    const text=JSON.stringify(original);
    await c.importProfileFiles({files:[{name:'again.json',size:text.length,text:async()=>text}],value:'again.json'});
    assert.equal(c.state.profileDocuments.length,1);assert.equal(c.state.profileDocuments[0],kept);
    assert.equal(c.$('profile-json').value,kept.draftText);assert.deepEqual(c.state.profileDocuments[0].origin,origin);
    assert.equal(c.state.profileReport,report);assert.match(c.$('profile-feedback').textContent,/중복|이미/);
  });
  await check('Conflicting original or edited preset names reject the entire addition',async()=>{
    for(const name of ['Original','Renamed']) {
      const c=profileFixture();const kept={filename:'kept.json',profile:{name:'Original',value:'1'},draftText:'{"name":"Renamed","value":"2"}'};
      c.state.profileDocuments=[kept];c.$('profile-json').value=kept.draftText;
      const documents=[{name:'New independent'},{name,value:'conflict'}];
      await c.importProfileFiles({files:documents.map((profile,index)=>({name:`${index}.json`,size:100,text:async()=>JSON.stringify(profile)})),value:'files'});
      assert.equal(c.state.profileDocuments.length,1);assert.equal(c.state.profileDocuments[0],kept);
      assert.equal(c.$('profile-json').value,kept.draftText);assert.match(c.$('profile-feedback').textContent,/이름|중복/);
    }
  });
  await check('Archive import preserves original member text and origin without inventing profile metadata',async()=>{
    const c=profileFixture();const result=archiveResult();let submitted;
    c.$('setup-nozzle').value='0.40';c.api=async(path,body)=>{submitted={path,body:plain(body)};return result;};
    await c.importProfileArchive(archiveInput());
    assert.equal(submitted.path,'/api/profiles/import-archive');assert.equal(submitted.body.filename,'synthetic.bbsflmt');
    assert.equal(submitted.body.content_base64,Buffer.from([80,75,3]).toString('base64'));
    assert.equal(c.state.profileDocuments.length,1);assert.equal(c.$('profile-json').value,result.documents[0].draft_text);
    assert.deepEqual(plain(c.state.profileDocuments[0].profile),result.documents[0].profile);
    assert.deepEqual(plain(c.state.profileDocuments[0].origin),result.documents[0].origin);
    assert.equal(c.state.profileDocuments[0].profile.type,undefined);assert.equal(c.state.profileDocuments[0].profile.source,undefined);
    assert.equal(c.$('setup-nozzle').value,'0.40');assert.equal(c.$('profile-origin').hidden,false);
    assert.match(c.$('profile-origin-fields').textContent,/synthetic.bbsflmt/);
    assert.match(c.$('profile-feedback').textContent,/printer\/Printer.json/);
  });
  await check('Archive parse errors and conflicting members roll back without dropping the accepted review',async()=>{
    for(const rejected of [true,false]) {
      const c=profileFixture();const kept={filename:'kept.json',profile:{name:'Kept'},draftText:'{"name":"Kept"}'};
      c.state.profileDocuments=[kept];c.$('profile-json').value=kept.draftText;const report={status:'resolved'};c.state.profileReport=report;
      c.$('profile-download').setAttribute('href','blob:accepted');
      const result=archiveResult();result.documents.push({filename:'other.json',profile:{name:'Kept',conflict:true},draft_text:'{"name":"Kept","conflict":true}',origin:archiveOrigin()});
      c.api=async()=>{if(rejected)throw new Error('Invalid archive member');return result;};
      await c.importProfileArchive(archiveInput());
      assert.equal(c.state.profileDocuments.length,1);assert.equal(c.state.profileDocuments[0],kept);
      assert.equal(c.state.profileReport,report);assert.equal(c.$('profile-json').value,kept.draftText);
      assert.equal(c.$('profile-download').attributes.href,'blob:accepted');
      assert.match(c.$('profile-feedback').textContent,/유지했습니다/);
    }
  });
  await check('Late archive responses cannot replace edits, a new workspace, clear, or a newer JSON import',async()=>{
    for(const action of ['edit','workspace','clear','newer_import']) {
      const c=profileFixture();let finish;
      c.api=()=>new Promise(done=>{finish=done;});
      const importing=c.importProfileArchive(archiveInput());await new Promise(done=>setImmediate(done));
      if(action==='edit') {c.$('profile-json').value='{"name":"Newer draft"}';c.invalidateProfile();c.markWorkspaceChanged();}
      if(action==='workspace') {const snapshot=plain(c.captureProfileSnapshot());snapshot.profile_text='{"name":"Other workspace"}';c.restoreWorkspace(workspaceRecord(snapshot));}
      if(action==='clear') c.clearProfileLibrary();
      if(action==='newer_import') await c.importProfileFiles({files:[{name:'newer.json',size:18,text:async()=>'{"name":"Newer"}'}],value:'newer.json'});
      const text=c.$('profile-json').value,documents=plain(c.state.profileDocuments),workspace=c.state.workspaceId;
      finish(archiveResult());await importing;
      assert.equal(c.$('profile-json').value,text);assert.deepEqual(plain(c.state.profileDocuments),documents);assert.equal(c.state.workspaceId,workspace);
    }
  });
  await check('An obsolete archive byte read never reaches the parser and an oversized archive is not read',async()=>{
    const c=profileFixture();let finish,calls=0;c.api=async()=>{calls++;return archiveResult();};
    const input=archiveInput();input.files[0].arrayBuffer=()=>new Promise(done=>{finish=done;});
    const importing=c.importProfileArchive(input);c.newWorkspace();finish(new Uint8Array([80,75]).buffer);await importing;
    assert.equal(calls,0);assert.equal(c.state.profileDocuments.length,0);
    const oversized=archiveInput();oversized.files[0].size=4*1024*1024+1;oversized.files[0].arrayBuffer=async()=>{throw new Error('must not read');};
    await c.importProfileArchive(oversized);assert.equal(calls,0);assert.match(c.$('profile-feedback').textContent,/4 MiB/);
  });
  await check('Import budgets account for exact unfinished text and deduplicate before the document limit',async()=>{
    const c=profileFixture();const kept={filename:'unfinished.json',profile:{name:'Unfinished'},draftText:' '.repeat(2*1024*1024)+'{'};
    c.state.profileDocuments=[kept];c.$('profile-json').value=kept.draftText;
    await c.importProfileFiles({files:[{name:'new.json',size:14,text:async()=>'{"name":"New"}'}],value:'new.json'});
    assert.equal(c.state.profileDocuments.length,1);assert.equal(c.$('profile-json').value,kept.draftText);assert.match(c.$('profile-feedback').textContent,/편집 문자열/);
    const full=profileFixture();full.state.profileDocuments=Array.from({length:64},(_,index)=>({filename:`${index}.json`,profile:{name:`Preset ${index}`},draftText:JSON.stringify({name:`Preset ${index}`})}));
    full.$('profile-json').value=full.state.profileDocuments[0].draftText;
    await full.importProfileFiles({files:[{name:'again.json',size:20,text:async()=>'{"name":"Preset 0"}'}],value:'again.json'});
    assert.equal(full.state.profileDocuments.length,64);assert.match(full.$('profile-feedback').textContent,/건너뛰/);
    await full.importProfileFiles({files:[{name:'new.json',size:14,text:async()=>'{"name":"New"}'}],value:'new.json'});
    assert.equal(full.state.profileDocuments.length,64);assert.match(full.$('profile-feedback').textContent,/최대 64개/);
  });
  await check('Archive provenance survives snapshot reopening and current/original review requests',async()=>{
    const c=profileFixture();c.api=async()=>archiveResult();await c.importProfileArchive(archiveInput());
    const snapshot=plain(c.captureProfileSnapshot());c.restoreWorkspace(workspaceRecord(snapshot));
    assert.deepEqual(plain(c.state.profileDocuments[0].origin),archiveOrigin());
    assert.equal(c.$('profile-origin').hidden,false);assert.equal(c.state.profileReport,null);
    const original=plain(c.state.profileDocuments[0].profile);const edited={...original,nozzle_temperature:['220']};c.$('profile-json').value=JSON.stringify(edited);
    let submitted;c.api=async(path,body)=>{submitted=plain(body);return {status:'needs_input',review:null};};c.renderProfileResolution=()=>{};
    await c.reviewProfile();assert.deepEqual(submitted.documents[0].origin,archiveOrigin());assert.deepEqual(submitted.baseline.documents[0].origin,archiveOrigin());
    assert.deepEqual(submitted.documents[0].profile,edited);assert.deepEqual(submitted.baseline.documents[0].profile,original);
  });
  await check('Profile import refuses numbers that JSON parsing cannot preserve',async()=>{
    for(const number of ['1e999','9007199254740993']) {
      const c=profileFixture();c.$('profile-json').value='{"name":"Kept draft"}';
      await c.importProfileFiles({files:[{name:'number.json',size:100,text:async()=>'{"name":"Numeric preset","vendor_value":'+number+'}'}],value:'number.json'});
      assert.equal(c.state.profileDocuments.length,0);
      assert.equal(c.$('profile-json').value,'{"name":"Kept draft"}');
      assert.match(c.$('profile-feedback').textContent,/숫자/);
    }
  });
  await check('Adding files bounds preserved originals independently of smaller edited drafts',async()=>{
    const c=profileFixture();const original={name:'A',description:'x'.repeat(1200*1024)};
    const kept={filename:'A.json',profile:original,draftText:'{"name":"A"}'};
    c.state.profileDocuments=[kept];c.$('profile-json').value=kept.draftText;
    const text=JSON.stringify({name:'B',description:'y'.repeat(1200*1024)});
    await c.importProfileFiles({files:[{name:'B.json',size:text.length,text:async()=>text}],value:'B.json'});
    assert.equal(c.state.profileDocuments.length,1);assert.equal(c.state.profileDocuments[0],kept);
    assert.equal(c.$('profile-json').value,kept.draftText);assert.match(c.$('profile-feedback').textContent,/원본 JSON 합계/);
  });
  await check('Adopting an oversized pasted original leaves the standalone draft untouched',()=>{
    const c=profileFixture();const text=JSON.stringify({name:'Large',description:'x'.repeat(2*1024*1024)});
    c.$('profile-json').value=text;c.adoptProfileText();
    assert.equal(c.state.profileDocuments.length,0);assert.equal(c.$('profile-json').value,text);
    assert.match(c.$('profile-feedback').textContent,/원본 JSON 합계/);
  });
  await check('Guided numbers preserve scalar, singleton and numeric-string shapes',()=>{
    const c=profileFixture();
    for(const [original,expected] of [[210,220],['210','220'],[[210],[220]],[['210'],['220']],[undefined,['220']]]) {
      assert.deepEqual(plain(c.numericSetting(original,'220',true)),expected);
    }
    for(const original of [[205,215],['205','205'],[],false,{value:210}]) assert.throws(()=>c.numericSetting(original,'220',true));
    for(const value of ['', ' ', 'Infinity', '1e999', '9007199254740993', '0', '-1']) assert.throws(()=>c.numericSetting(['210'],value,true));
    assert.deepEqual(plain(c.numericSetting(['55'],'0',false)),['0']);
  });
  await check('Guided inherited overrides preserve parents, originals and envelope metadata',()=>{
    const c=profileFixture();
    const parent={name:'Base',filament_flow_ratio:['0.98']};
    const original={settings:{name:'Child',inherits:'Base'},source:{authority:'user'},validation:{status:'unverified'}};
    c.state.profileDocuments=[{filename:'child.json',profile:original,draftText:JSON.stringify(original)},{filename:'base.json',profile:parent,draftText:JSON.stringify(parent)}];
    c.$('profile-json').value=c.state.profileDocuments[0].draftText;
    c.state.profileReport={status:'resolved',resolved_profile:{settings:{name:'Child',filament_flow_ratio:['0.98']}},field_sources:{filament_flow_ratio:{filename:'base.json'}}};
    c.renderGuidedEditor();
    c.state.guidedEdits={filament_flow_ratio:'0.99'};
    c.applyGuidedEdits();
    const edited=JSON.parse(c.$('profile-json').value);
    assert.deepEqual(edited.settings,{name:'Child',inherits:'Base',filament_flow_ratio:['0.99']});
    assert.deepEqual(edited.source,original.source);assert.deepEqual(edited.validation,original.validation);
    assert.equal(original.settings.filament_flow_ratio,undefined);assert.deepEqual(parent.filament_flow_ratio,['0.98']);
    assert.equal(c.state.profileDocuments[1].draftText,JSON.stringify(parent));
    assert.equal(c.state.profileReport,null);assert.equal(c.workspaceDirty(),true);
    c.removeGuidedOverride('filament_flow_ratio');
    assert.equal(JSON.parse(c.$('profile-json').value).settings.filament_flow_ratio,undefined);
    assert.equal(JSON.parse(c.$('profile-json').value).settings.inherits,'Base');
  });
  await check('Guided edits reject an empty field atomically and multi-value controls remain disabled',()=>{
    const c=profileFixture();const original={name:'Preset',nozzle_temperature:['210'],filament_flow_ratio:0.98,filament_max_volumetric_speed:['12','15']};
    c.state.profileDocuments=[{filename:'p.json',profile:original,draftText:JSON.stringify(original)}];
    c.$('profile-json').value=JSON.stringify(original);c.renderGuidedEditor();
    const row=c.$('profile-guided-fields').children.find(item=>item.dataset.field==='filament_max_volumetric_speed');
    assert.equal(row.children[0].children[0].disabled,true);
    c.state.guidedEdits={nozzle_temperature:'220',filament_flow_ratio:''};
    assert.throws(()=>c.applyGuidedEdits(),/빈 값/);
    assert.equal(c.$('profile-json').value,JSON.stringify(original));
    assert.deepEqual(c.state.guidedEdits,{nozzle_temperature:'220',filament_flow_ratio:''});
  });
  await check('Snapshots preserve exact malformed drafts, setup strings, selection and originals',()=>{
    const c=profileFixture();const original={name:'Original'};
    c.state.profileDocuments=[{filename:'base.json',profile:{name:'Base'},draftText:'{"name":"Base"}'},{filename:'p.json',profile:original,draftText:'old'}];
    c.state.profileTarget=1;c.$('profile-json').value='  { "name":\nunfinished';
    c.$('setup-nozzle').value='0.40';c.$('setup-identity').value='exact';
    const snapshot=plain(c.captureProfileSnapshot());
    assert.equal(snapshot.documents[1].draft_text,'  { "name":\nunfinished');assert.equal(snapshot.profile_text,'');
    assert.equal(snapshot.target_index,1);assert.equal(snapshot.setup.nozzle_diameter,'0.40');
    assert.deepEqual(snapshot.documents[1].profile,original);
    c.state.profileReport={status:'resolved'};c.$('profile-download').setAttribute('href','blob:old');
    c.restoreWorkspace(workspaceRecord(snapshot));
    assert.equal(c.$('profile-json').value,snapshot.documents[1].draft_text);assert.equal(c.state.profileTarget,1);
    assert.equal(c.$('setup-nozzle').value,'0.40');assert.equal(c.state.profileReport,null);
    assert.equal(c.$('profile-download').attributes.href,undefined);assert.equal(c.workspaceDirty(),false);
  });
  await check('Saving malformed JSON stores text without requiring a profile review',async()=>{
    const c=profileFixture();c.$('profile-json').value='{ unfinished';c.$('workspace-title').value='My work';
    let submitted;
    c.api=async(path,body,method)=>{
      if(method==='POST'){submitted=plain(body);return workspaceRecord(body.snapshot,{title:body.title});}
      return {workspaces:[workspaceRecord(submitted.snapshot,{title:submitted.title})]};
    };
    await c.saveWorkspace();assert.equal(submitted.snapshot.profile_text,'{ unfinished');
    assert.equal(c.$('profile-json').value,'{ unfinished');assert.equal(c.workspaceDirty(),false);
    assert.equal(c.state.workspaceRevision,1);
  });
  await check('A save reply keeps newer edits dirty and updates the next expected revision',async()=>{
    const c=profileFixture();c.$('profile-json').value='{"name":"Captured"}';c.$('workspace-title').value='Work';
    let finish,submitted;
    c.api=(path,body,method)=>method==='POST'?new Promise(done=>{submitted=plain(body);finish=done;}):Promise.resolve({workspaces:[]});
    const pending=c.saveWorkspace();
    c.$('profile-json').value='{"name":"Newer"}';c.markWorkspaceChanged();
    finish(workspaceRecord(submitted.snapshot,{title:submitted.title,revision:2}));await pending;
    assert.equal(c.$('profile-json').value,'{"name":"Newer"}');assert.equal(c.workspaceDirty(),true);
    assert.equal(c.state.workspaceRevision,2);assert.match(c.$('workspace-feedback').textContent,/한 번 더 저장/);
    let update;
    c.api=async(path,body,method)=>{if(method==='PUT'){update=plain(body);return workspaceRecord(body.snapshot,{title:body.title,revision:3});}return {workspaces:[]};};
    await c.saveWorkspace();assert.equal(update.expected_revision,2);assert.equal(c.workspaceDirty(),false);
  });
  await check('Edits during the saved-list refresh keep the final save notice truthful',async()=>{
    const c=profileFixture();c.$('profile-json').value='{}';c.$('workspace-title').value='Work';
    let finishList;
    c.api=(path,body,method)=>method==='POST'?Promise.resolve(workspaceRecord(body.snapshot,{title:body.title})):new Promise(done=>{finishList=done;});
    const pending=c.saveWorkspace();await new Promise(done=>setImmediate(done));
    c.$('workspace-title').value='Changed during refresh';c.markWorkspaceChanged();
    finishList({workspaces:[]});await pending;
    assert.equal(c.workspaceDirty(),true);assert.match(c.$('workspace-feedback').textContent,/한 번 더 저장/);
  });
  await check('A late load does not overwrite new edits or bind the loaded workspace',async()=>{
    const c=profileFixture();const snapshot=plain(c.captureProfileSnapshot());snapshot.profile_text='{"name":"Saved"}';
    c.$('workspace-list').value='a'.repeat(32);let finish;c.api=()=>new Promise(done=>{finish=done;});
    const pending=c.openWorkspace();c.$('profile-json').value='{"name":"Newer"}';c.markWorkspaceChanged();c.invalidateProfile();
    finish(workspaceRecord(snapshot));await pending;
    assert.equal(c.$('profile-json').value,'{"name":"Newer"}');assert.equal(c.state.workspaceId,null);
    assert.match(c.$('workspace-feedback').textContent,/현재 작업을 유지/);
  });
  await check('A later file selection takes precedence over an earlier pending workspace open',async()=>{
    const c=profileFixture();const snapshot=plain(c.captureProfileSnapshot());
    snapshot.documents=[{filename:'saved.json',profile:{name:'Saved'},draft_text:'{"name":"Saved"}'}];
    c.$('workspace-list').value='a'.repeat(32);let finishOpen,finishFile;
    c.api=()=>new Promise(done=>{finishOpen=done;});
    const opening=c.openWorkspace();
    const importing=c.importProfileFiles({files:[{name:'new.json',size:14,text:()=>new Promise(done=>{finishFile=done;})}],value:'new.json'});
    finishOpen(workspaceRecord(snapshot));await opening;
    finishFile('{"name":"New"}');await importing;
    assert.equal(c.state.workspaceId,null);assert.equal(c.state.profileDocuments.length,1);
    assert.equal(c.state.profileDocuments[0].filename,'new.json');assert.equal(c.$('profile-json').value,'{"name":"New"}');
  });
  await check('A save from an old workspace cannot bind its response to another workspace',async()=>{
    const c=profileFixture();c.$('workspace-title').value='Old';c.$('profile-json').value='{}';
    let finish,submitted;c.api=(path,body)=>new Promise(done=>{submitted=plain(body);finish=done;});
    const pending=c.saveWorkspace();const snapshot=plain(c.captureProfileSnapshot());snapshot.profile_text='{"name":"Other"}';
    c.restoreWorkspace(workspaceRecord(snapshot,{id:'b'.repeat(32),title:'Other',revision:7}));
    finish(workspaceRecord(submitted.snapshot,{title:'Old'}));await pending;
    assert.equal(c.state.workspaceId,'b'.repeat(32));assert.equal(c.state.workspaceRevision,7);
    assert.equal(c.$('profile-json').value,'{"name":"Other"}');assert.equal(c.workspaceDirty(),false);
  });
  await check('Save conflicts retain dirty input and the previously loaded revision',async()=>{
    const c=profileFixture();const snapshot=plain(c.captureProfileSnapshot());
    c.restoreWorkspace(workspaceRecord(snapshot,{revision:4}));c.$('profile-json').value='{ unfinished';c.markWorkspaceChanged();
    c.api=async()=>{const error=new Error('conflict');error.status=409;throw error;};
    await c.saveWorkspace();assert.equal(c.state.workspaceRevision,4);assert.equal(c.$('profile-json').value,'{ unfinished');
    assert.equal(c.workspaceDirty(),true);assert.match(c.$('workspace-feedback').textContent,/다른 이름으로 저장/);
  });
  await check('Canceling an unsaved open keeps the current draft without a request',async()=>{
    const c=profileFixture();c.$('profile-json').value='{}';c.$('workspace-list').value='a'.repeat(32);c.window.confirm=()=>false;
    let requests=0;c.api=async()=>{requests++;};await c.openWorkspace();
    assert.equal(requests,0);assert.equal(c.$('profile-json').value,'{}');
  });
  await check('Removing one document and restoring another keep imported originals intact',()=>{
    const c=profileFixture();const original={name:'Original',nozzle_temperature:['210']};
    c.state.profileDocuments=[{filename:'bad.json',profile:{name:'Bad'},draftText:'{bad'},{filename:'p.json',profile:original,draftText:'{"name":"Edited"}'}];
    c.$('profile-json').value='{bad';c.removeProfileDocument();
    assert.equal(c.state.profileDocuments.length,1);assert.equal(c.$('profile-json').value,'{"name":"Edited"}');
    c.restoreProfileOriginal();assert.deepEqual(JSON.parse(c.$('profile-json').value),original);
    assert.deepEqual(original,{name:'Original',nozzle_temperature:['210']});assert.equal(c.workspaceDirty(),true);
  });
  await check('Library review sends original baseline identity even after a target rename',async()=>{
    const c=profileFixture();const original={name:'Original',nozzle_temperature:['210']};
    c.state.profileDocuments=[{filename:'p.json',profile:original,draftText:'{"name":"Renamed","nozzle_temperature":["220"]}'}];
    c.$('profile-json').value=c.state.profileDocuments[0].draftText;let submitted;
    c.api=async(path,body)=>{submitted=plain(body);return {status:'needs_input',review:null};};
    c.renderProfileResolution=()=>{};await c.reviewProfile();
    assert.equal(submitted.target_name,'Renamed');assert.equal(submitted.baseline.target_name,'Original');
    assert.deepEqual(submitted.baseline.documents[0].profile,original);
  });
  await check('Reopened key order changes do not label an unchanged imported document as edited',async()=>{
    const c=profileFixture();const original={settings:{name:'Preset',a:1,b:['2']},scope:{}};
    c.state.profileDocuments=[{filename:'p.json',profile:original,draftText:'{"scope":{},"settings":{"b":["2"],"a":1,"name":"Preset"}}'}];
    c.$('profile-json').value=c.state.profileDocuments[0].draftText;
    c.api=async()=>({status:'needs_input',review:null});let report;c.renderProfileResolution=value=>{report=value;};
    await c.reviewProfile();assert.deepEqual(plain(report.edited_filenames),[]);
    assert.equal(c.sameJson({value:['1',2]},{value:['1',2]}),true);
    assert.equal(c.sameJson({value:['1',2]},{value:[1,'2']}),false);
  });
  await check('Evidence rendering and cancellation keep raw JSON exact and never copy setup or parent claims',()=>{
    const c=profileFixture(),raw={name:'Child',inherits:'Parent',nozzle_temperature:['215']};
    const text=selectedProfile(c,raw);
    c.$('setup-printer-model').value='Current user hardware';
    c.state.profileReport={status:'resolved',resolved_profile:{settings:raw,scope:{printer_model:'Parent hardware'},source:{publisher:'Parent publisher'}},field_sources:{}};
    c.$('profile-evidence').open=true;c.renderGuidedEditor();
    assert.equal(guidedInput(c,'scope.printer_model').value,'');
    assert.equal(guidedInput(c,'source.publisher').value,'');
    assert.equal(guidedInput(c,'source.retrieved_at').value,'');
    assert.equal(c.$('profile-evidence').open,true);
    editGuided(c,'source.publisher','Temporary claim');
    assert.equal(c.$('profile-json').value,text);assert.equal(c.workspaceDirty(),true);
    c.renderGuidedEditor();c.markWorkspaceChanged();c.applyGuidedEdits();
    assert.equal(c.$('profile-json').value,text);assert.deepEqual(plain(c.state.guidedEdits),{});
    assert.deepEqual(c.state.profileDocuments[0].profile,raw);
    assert.equal(c.$('setup-printer-model').value,'Current user hardware');
    assert.equal(c.$('profile-evidence').open,true);
  });
  await check('Applying mixed settings and evidence wraps only the selected raw draft while preserving origin and setup',()=>{
    const c=profileFixture(),raw={name:'Child',inherits:'Parent',nozzle_temperature:['215'],source:{legacy:'raw setting'}};
    const origin=archiveOrigin(),text=selectedProfile(c,raw,origin),parent={settings:{name:'Parent'},scope:{printer_model:'Parent hardware'}};
    c.state.profileDocuments.push({filename:'parent.json',profile:parent,draftText:JSON.stringify(parent)});
    for(const [name,id] of Object.entries(c.profileSetupFields()))c.$(id).value=`user:${name}`;
    const setup=plain(c.captureProfileSnapshot().setup);
    editGuided(c,'nozzle_temperature','220');
    editGuided(c,'scope.printer_model','Profile hardware');
    editGuided(c,'scope.nozzle_diameter','0.6');
    editGuided(c,'source.publisher','  Supplied publisher  ');
    assert.equal(c.$('profile-json').value,text);assert.equal(c.$('profile-json').disabled,true);
    for(const id of ['profile-target','profile-file','profile-archive','setup-printer-model'])assert.equal(c.$(id).disabled,true);
    c.applyGuidedEdits();
    assert.deepEqual(JSON.parse(c.$('profile-json').value),{
      settings:{name:'Child',inherits:'Parent',nozzle_temperature:['220'],source:{legacy:'raw setting'}},
      scope:{printer_model:'Profile hardware',nozzle_diameter:0.6},source:{publisher:'  Supplied publisher  '},
    });
    assert.deepEqual(c.state.profileDocuments[0].profile,raw);assert.deepEqual(c.state.profileDocuments[0].origin,origin);
    assert.equal(c.state.profileDocuments[1].draftText,JSON.stringify(parent));assert.deepEqual(c.state.profileDocuments[1].profile,parent);
    assert.deepEqual(plain(c.captureProfileSnapshot().setup),setup);assert.equal(c.$('profile-json').disabled,false);
  });
  await check('Evidence changes preserve unknown metadata and exact strings while empty text removes only its key',()=>{
    const c=profileFixture(),profile={id:'identity',settings:{name:'Preset',inherits:'Base'},scope:{printer_model:'  Literal model  ',nozzle_diameter:['0.40'],custom:{keep:['a']}},source:{authority:'custom claim',publisher:'Old publisher',url:'  https://example.test/source  ',extra:[1,2]},validation:{status:'unverified'},extra:{keep:true}};
    selectedProfile(c,profile);
    assert.equal(guidedInput(c,'source.authority').value,'custom claim');assert.equal(guidedInput(c,'scope.printer_model').value,'  Literal model  ');
    editGuided(c,'source.publisher','');editGuided(c,'scope.nozzle_diameter','0.60');editGuided(c,'source.retrieved_at','  2026-11-13  ');
    c.applyGuidedEdits();
    const expected=plain(profile);delete expected.source.publisher;expected.scope.nozzle_diameter=['0.60'];expected.source.retrieved_at='  2026-11-13  ';
    assert.deepEqual(JSON.parse(c.$('profile-json').value),expected);assert.deepEqual(c.state.profileDocuments[0].profile,profile);
    editGuided(c,'source.publisher','  ');c.applyGuidedEdits();
    assert.equal(JSON.parse(c.$('profile-json').value).source.publisher,'  ');
  });
  await check('Invalid scope nozzle leaves every pending settings and evidence edit unapplied',()=>{
    const c=profileFixture(),profile={name:'Preset',nozzle_temperature:['215']},text=selectedProfile(c,profile);
    editGuided(c,'nozzle_temperature','220');editGuided(c,'source.publisher','Publisher');editGuided(c,'scope.nozzle_diameter','0');
    assert.throws(()=>c.applyGuidedEdits(),/양수/);
    assert.equal(c.$('profile-json').value,text);assert.equal(c.state.profileDocuments[0].draftText,text);
    assert.deepEqual(plain(c.state.guidedEdits),{nozzle_temperature:'220','source.publisher':'Publisher','scope.nozzle_diameter':'0'});
    assert.deepEqual(c.state.profileDocuments[0].profile,profile);
  });
  await check('Scope nozzle edits preserve existing scalar and singleton representations',()=>{
    for(const [before,after] of [[0.4,0.6],['0.40','0.60'],[[0.4],[0.6]],[['0.40'],['0.60']]]) {
      const c=profileFixture();selectedProfile(c,{settings:{name:'Preset'},scope:{nozzle_diameter:before}});
      editGuided(c,'scope.nozzle_diameter','0.60');c.applyGuidedEdits();
      assert.deepEqual(JSON.parse(c.$('profile-json').value).scope.nozzle_diameter,after);
    }
  });
  await check('A browser-invalid partial nozzle input is not mistaken for removing evidence',()=>{
    for(const scope of [{nozzle_diameter:'0.40'},{}]) {
      const c=profileFixture(),profile={settings:{name:'Preset'},scope},text=selectedProfile(c,profile);
      const input=guidedInput(c,'scope.nozzle_diameter');
      // Number inputs expose an unfinished '-' as empty value with badInput.
      input.validity={badInput:true};editGuided(c,'scope.nozzle_diameter','');
      assert.equal(c.workspaceDirty(),true);
      assert.throws(()=>c.applyGuidedEdits(),/숫자/);
      assert.equal(c.$('profile-json').value,text);assert.equal(c.state.profileDocuments[0].draftText,text);
      input.validity={badInput:false};editGuided(c,'scope.nozzle_diameter','0.6');c.applyGuidedEdits();
      assert.deepEqual(JSON.parse(c.$('profile-json').value).scope.nozzle_diameter,Object.hasOwn(scope,'nozzle_diameter')?'0.6':0.6);
    }
  });
  await check('Unsupported evidence values stay visible and unchanged while another field is edited',()=>{
    const c=profileFixture(),profile={settings:{name:'Preset'},scope:{printer_model:['A','B'],nozzle_diameter:[0.4,0.6],material_id:null},source:{authority:{legacy:true},publisher:'Old'}};
    selectedProfile(c,profile);
    for(const key of ['scope.printer_model','scope.nozzle_diameter','scope.material_id','source.authority'])assert.equal(guidedInput(c,key).disabled,true);
    assert.match(c.$('profile-evidence-scope').textContent,/\["A","B"\]/);
    assert.match(c.$('profile-evidence-source').textContent,/legacy/);
    editGuided(c,'source.publisher','Updated');c.applyGuidedEdits();
    const edited=JSON.parse(c.$('profile-json').value);assert.deepEqual(edited.scope,profile.scope);assert.deepEqual(edited.source.authority,{legacy:true});
    assert.equal(edited.source.publisher,'Updated');assert.deepEqual(c.state.profileDocuments[0].profile,profile);
  });
  await check('Malformed evidence groups remain read-only without blocking a separate supported group edit',()=>{
    for(const [group,legacy,key] of [['scope',['legacy scope'],'source.publisher'],['source',false,'scope.printer_model']]) {
      const c=profileFixture(),profile={settings:{name:'Preset'},[group]:legacy};selectedProfile(c,profile);
      assert.match(c.$(`profile-evidence-${group}`).textContent,/JSON/);
      editGuided(c,key,'Explicit value');c.applyGuidedEdits();
      assert.deepEqual(JSON.parse(c.$('profile-json').value)[group],legacy);assert.deepEqual(c.state.profileDocuments[0].profile,profile);
    }
  });
  await check('Numeric-only changes and reverted evidence leave raw shape intact',()=>{
    const c=profileFixture(),raw={name:'Preset',nozzle_temperature:['215']};selectedProfile(c,raw);
    editGuided(c,'source.publisher','Temporary');editGuided(c,'source.publisher','');
    editGuided(c,'nozzle_temperature','220');c.applyGuidedEdits();
    assert.deepEqual(JSON.parse(c.$('profile-json').value),{name:'Preset',nozzle_temperature:['220']});
  });
  await check('Saving pending evidence preserves originals and restores inputs without a current review',async()=>{
    const c=profileFixture(),raw={name:'Preset'},origin=archiveOrigin();selectedProfile(c,raw,origin);c.$('workspace-title').value='Evidence work';
    editGuided(c,'scope.printer_model','Profile hardware');editGuided(c,'source.publisher','Publisher');
    let submitted;c.api=async(path,body,method)=>{if(method==='POST'){submitted=plain(body);return workspaceRecord(body.snapshot,{title:body.title});}return {workspaces:[]};};
    await c.saveWorkspace();
    assert.deepEqual(submitted.snapshot.documents[0].profile,raw);assert.deepEqual(submitted.snapshot.documents[0].origin,origin);
    assert.deepEqual(JSON.parse(submitted.snapshot.documents[0].draft_text),{settings:{name:'Preset'},scope:{printer_model:'Profile hardware'},source:{publisher:'Publisher'}});
    c.state.profileReport={status:'resolved'};c.$('profile-download').setAttribute('href','blob:old');
    c.restoreWorkspace(workspaceRecord(submitted.snapshot));
    assert.equal(guidedInput(c,'scope.printer_model').value,'Profile hardware');assert.equal(guidedInput(c,'source.publisher').value,'Publisher');
    assert.equal(c.state.profileReport,null);assert.equal(c.$('profile-download').attributes.href,undefined);assert.equal(c.workspaceDirty(),false);
  });
  await check('New evidence input invalidates a pending review, archive import, and workspace open',async()=>{
    for(const action of ['review','archive','open']) {
      const c=profileFixture(),raw={name:'Preset'},text=selectedProfile(c,raw);let finish,rendered=0;
      const saved=workspaceRecord(plain(c.captureProfileSnapshot()));
      c.api=()=>new Promise(done=>{finish=done;});c.renderProfileResolution=()=>{rendered++;};
      c.$('workspace-list').value=saved.id;
      const pending=action==='review'?c.reviewProfile():action==='archive'?c.importProfileArchive(archiveInput()):c.openWorkspace();
      await new Promise(done=>setImmediate(done));
      editGuided(c,'source.publisher','Newer publisher');
      finish(action==='review'?{status:'resolved',review:null}:action==='archive'?archiveResult():saved);await pending;
      assert.equal(c.$('profile-json').value,text);assert.equal(c.state.profileDocuments.length,1);
      assert.equal(c.state.guidedEdits['source.publisher'],'Newer publisher');assert.equal(rendered,0);
      assert.equal(c.state.workspaceId,null);assert.equal(c.state.profileReport,null);
    }
  });
  await check('Evidence typed while a save is pending is not reported as saved',async()=>{
    const c=profileFixture();selectedProfile(c,{name:'Preset'});c.$('workspace-title').value='Work';
    editGuided(c,'source.publisher','Captured publisher');let submitted,finish;
    c.api=(path,body,method)=>method==='POST'?new Promise(done=>{submitted=plain(body);finish=done;}):Promise.resolve({workspaces:[]});
    const pending=c.saveWorkspace();editGuided(c,'source.publisher','Newer publisher');
    finish(workspaceRecord(submitted.snapshot,{title:'Work'}));await pending;
    assert.equal(JSON.parse(submitted.snapshot.documents[0].draft_text).source.publisher,'Captured publisher');
    assert.equal(c.state.guidedEdits['source.publisher'],'Newer publisher');assert.equal(c.workspaceDirty(),true);
    assert.match(c.$('workspace-feedback').textContent,/한 번 더 저장/);
  });
  await check('Evidence changes are rendered separately from effective setting changes with presence and raw values',()=>{
    const c=profileFixture();c.$('profile-evidence-review').hidden=true;
    c.renderProfileResolution({status:'needs_input',issues:[],chain:[],warnings:[],field_sources:{},edit_review:{status:'unchanged',changed_fields:[],evidence_status:'compared',evidence_changes:[
      {path:'scope.printer_model',before_present:false,after_present:true,after:'Profile hardware'},
      {path:'source.publisher',before_present:true,after_present:false,before:'<img src=x onerror=alert(1)>'},
      {path:'validation.custom',before_present:true,after_present:true,before:null,after:{claim:'value'}},
    ]}});
    assert.equal(c.$('profile-evidence-review').hidden,false);assert.equal(c.$('profile-edit-review').hidden,true);
    const area=c.$('profile-evidence-changes');assert.match(area.textContent,/Profile hardware/);assert.match(area.textContent,/<img src=x/);
    assert.match(area.textContent,/null/);assert.match(area.textContent,/claim/);
    assert(findElement(area,element=>element.dataset.evidencePath==='scope.printer_model'));
    c.renderProfileResolution({status:'needs_input',edit_review:{status:'unchanged',changed_fields:[],evidence_status:'compared',evidence_changes:[]}});
    assert.equal(c.$('profile-evidence-review').hidden,true);assert.equal(c.$('profile-evidence-changes').textContent,'');
  });
  await check('Printer status pins the first reporting certificate and sends it on the next read only',async()=>{
    const c=printerFixture(),bodies=[];
    c.api=async(path,body)=>{bodies.push(plain(body));return printerReport();};
    await c.checkPrinterStatus();
    assert.deepEqual(bodies[0],{host:'192.168.0.20',serial:'01S00TEST000001',access_code:'SECRET-CODE'});
    assert.equal(c.state.printerPins['192.168.0.20|01S00TEST000001'],'a'.repeat(64));
    const text=c.$('printer-result').textContent;
    assert.match(text,/출력 중/);assert.match(text,/42%/);assert.match(text,/51 \/ 120/);assert.match(text,/0700_8000_0002_0001/);assert.match(text,/GFA00/);
    assert.doesNotMatch(text,/SECRET-CODE/);assert.equal(c.$('printer-result').hidden,false);assert.equal(c.$('printer-unpin').hidden,false);
    await c.checkPrinterStatus();
    assert.equal(bodies[1].pinned_certificate_sha256,'a'.repeat(64));
    c.printerInputChanged();assert.equal(c.state.printerStatus,null);assert.equal(c.$('printer-result').attributes['aria-hidden'],'true');
    assert.match(c.$('printer-feedback').textContent,/이전 대상의 확인 결과/);assert.equal(c.$('printer-status-badge').textContent,'입력이 바뀌어 다시 확인 필요');
  });
  await check('A changed certificate or non-reporting read never renders print values or replaces the pin',async()=>{
    const c=printerFixture();c.state.printerPins['192.168.0.20|01S00TEST000001']='b'.repeat(64);
    c.api=async()=>printerReport({connection:{state:'certificate_changed',detail:'이전에 확인한 인증서와 다릅니다.'},print:null,identity:null,
      certificate:{sha256:'c'.repeat(64),issuer_verified:false,pinned:true,matches_pin:false}});
    await c.checkPrinterStatus();
    assert.equal(c.state.printerPins['192.168.0.20|01S00TEST000001'],'b'.repeat(64));
    assert.doesNotMatch(c.$('printer-result').textContent,/진행률/);
    assert.match(c.$('printer-feedback').textContent,/인증서와 다릅니다/);
    assert.match(c.$('printer-result').textContent,/고정한 인증서와 다름/);assert.doesNotMatch(c.$('printer-result').textContent,/처음 확인한 인증서/);
    c.clearPrinterPin();assert.equal(c.state.printerPins['192.168.0.20|01S00TEST000001'],undefined);
  });
  await check('Editing printer inputs during a read discards the late result',async()=>{
    const c=printerFixture();let finish;
    c.api=()=>new Promise(done=>{finish=done;});
    const pending=c.checkPrinterStatus();
    c.$('printer-host').value='192.168.0.21';c.printerInputChanged();
    finish(printerReport());await pending;
    assert.equal(c.state.printerStatus,null);assert.deepEqual(plain(c.state.printerPins),{});
  });
  await check('Printer discovery explains unavailable listeners and lets a device fill the target',async()=>{
    const c=printerFixture();
    c.renderPrinterDevices({state:'listen_unavailable',devices:[]});
    assert.match(c.$('printer-discover-feedback').textContent,/직접 입력/);
    c.renderPrinterDevices({state:'listened',seconds:4,devices:[{host:'10.0.0.9',serial:'01P00ABCDEF0001',model_code:'C12',model_name:'P1S',name:'Shop',location_matches_sender:false}]});
    const area=c.$('printer-devices');assert.match(area.textContent,/P1S \(C12\)/);assert.match(area.textContent,/주소가 다릅니다/);
    findElement(area,element=>element.listeners?.click).listeners.click();
    assert.equal(c.$('printer-host').value,'10.0.0.9');assert.equal(c.$('printer-serial').value,'01P00ABCDEF0001');
  });
  await check('Printability review renders statuses, advice and a fix action only for actionable fields',()=>{
    const c=fixture();let focused=null;c.$('parameter-wall').focus=()=>{focused='wall';};c.$('parameter-wall').scrollIntoView=()=>{};
    c.renderPrintability({status:'review',basis:{note:'기준 0.4 mm 노즐'},items:[
      {id:'min_thickness',label:'가장 얇은 부분',status:'warn',value:'0.80 mm (바깥 벽)',detail:'1.9줄',advice:'늘리세요',field:'wall'},
      {id:'stability',label:'세운 비율',status:'pass',value:'0.4',detail:'안정',advice:null,field:null},
      {id:'bed_contact',label:'바닥 접촉면',status:'fail',value:'0 cm²',detail:'<img src=x onerror=alert(1)>',advice:'눕히세요',field:null}]});
    const area=c.$('printability-items');assert.equal(c.$('printability-review').hidden,false);
    assert.equal(c.$('printability-status').textContent,'확인할 점이 있어요');assert.match(area.textContent,/<img src=x/);
    const fixes=[];findElement(area,element=>{if(element.listeners?.click)fixes.push(element);return false;});
    assert.equal(fixes.length,1);fixes[0].listeners.click();assert.equal(focused,'wall');
    c.renderPrintability(undefined);assert.equal(c.$('printability-review').hidden,true);
  });
  await check('Nozzle recheck renders the new basis, ignores late results for another job and reverts on failure',async()=>{
    const c=fixture();c.state.job={id:'job-a',result:{mesh:{vertices:[[0,0,0]],faces:[[0,0,0]]}}};c.$('printability-nozzle').value='0.4';
    const review=(n,status)=>({status,basis:{nozzle_mm:n,note:`${n} mm`},items:[{id:'min_thickness',label:'가장 얇은 부분',status:status==='ok'?'pass':'warn',value:'1.2 mm',detail:'d',advice:null,field:null}]});
    c.renderPrintability(review(0.4,'ok'));
    let bodies=[];c.api=async(path,body)=>{bodies.push([path,plain(body)]);return review(0.8,'review');};
    await c.recheckPrintability(0.8);
    assert.deepEqual(bodies[0],['/api/jobs/job-a/printability',{nozzle_mm:0.8}]);
    assert.equal(c.$('printability-nozzle').value,'0.8');assert.equal(c.$('printability-status').textContent,'확인할 점이 있어요');
    let finish;c.api=()=>new Promise(done=>{finish=done;});
    const pending=c.recheckPrintability(0.2);c.state.job={id:'job-b',result:{}};finish(review(0.2,'ok'));await pending;
    assert.equal(c.$('printability-basis').textContent,'0.8 mm');
    c.state.job={id:'job-a',result:{mesh:{}}};c.api=async()=>{throw new Error('서버 오류');};
    await c.recheckPrintability(0.6);
    assert.equal(c.$('printability-nozzle').value,'0.8');assert.match(c.$('printability-feedback').textContent,/서버 오류/);
    assert.equal(c.state.printabilityPending,false);
  });
  await check('Printer-reported nozzle offers a recheck only when it differs, and old jobs get an explicit check',()=>{
    const c=fixture();c.state.job={id:'job-a',result:{mesh:{vertices:[[0,0,0]]}}};
    c.renderPrintability({status:'ok',basis:{nozzle_mm:0.4,note:''},items:[]});
    assert.equal(c.$('printability-use-printer').hidden,true);
    c.state.printerStatus={connection:{state:'reporting'},print:{nozzle:{diameter_mm:0.6}}};c.updatePrintabilityControls();
    assert.equal(c.$('printability-use-printer').hidden,false);assert.match(c.$('printability-use-printer').textContent,/0.6 mm/);
    c.state.printerStatus={connection:{state:'access_rejected'},print:null};c.updatePrintabilityControls();
    assert.equal(c.$('printability-use-printer').hidden,true);
    c.renderPrintability(undefined);
    assert.equal(c.$('printability-review').hidden,false);assert.equal(c.$('printability-run').hidden,false);
    assert.equal(c.$('printability-status').textContent,'아직 점검 안 함');
    c.state.job={id:'job-b',result:{}};c.renderPrintability(undefined);assert.equal(c.$('printability-review').hidden,true);
  });
  await check('Journey shows progress, a single next action, attention that yields once the user moves on, and resets with the job',()=>{
    const c=fixture();
    c.state.job=null;c.renderJourney();
    assert.equal(c.$('journey-next-button').dataset.target,'parameter-heading');
    assert.equal(c.$('journey-steps').children[0].attributes['aria-current'],'step');
    const job={id:'job-a',result:{dimensions_mm:{x:120,y:80,z:35},printability:{status:'review',items:[]}},user_outcome:null,latest_slice:null};
    c.state.job=job;c.state.printabilityReview=null;c.renderJourney();
    assert.equal(c.$('journey-next-button').dataset.target,'printability-review');
    assert.match(c.$('journey-steps').textContent,/120 × 80 × 35 mm/);assert.match(c.$('journey-steps').textContent,/확인할 점 있음/);
    c.state.downloadedJobId='job-a';c.renderJourney();
    assert.equal(c.$('journey-next-button').dataset.target,'outcome-card');assert.equal(c.$('journey-next-button').dataset.focus,'outcome-result');
    assert.equal(c.$('journey-steps').children[3].attributes['aria-current'],'step');
    c.state.downloadedJobId='other-job';c.renderJourney();
    assert.equal(c.$('journey-next-button').dataset.target,'printability-review');
    c.state.job={...job,user_outcome:{result:'failure'}};c.state.slicePrepared=true;c.state.downloadedJobId=null;c.renderJourney();
    // A reviewed plan alone is not a prepared file.
    assert.equal(c.$('journey-next-button').dataset.target,'printability-review');
    c.state.job={...job,user_outcome:{result:'failure'},latest_slice:{phase:'finished',plan:{ready:false},execution:{status:'failed'}}};c.renderJourney();
    assert.equal(c.$('journey-next-button').dataset.target,'printability-review');
    c.state.job={...job,user_outcome:{result:'failure'},latest_slice:{phase:'finished',plan:{ready:true},execution:{status:'sliced'}}};c.renderJourney();
    assert.match(c.$('journey-steps').textContent,/슬라이스 파일 있음/);
    assert.match(c.$('journey-steps').textContent,/실패로 기록/);assert.equal(c.$('journey-next-button').dataset.target,'parameter-heading');
    c.state.slicePrepared=false;c.state.job=null;c.renderJourney();
    assert.equal(c.$('journey-next-button').dataset.target,'parameter-heading');assert.doesNotMatch(c.$('journey-steps').textContent,/실패로 기록/);
  });
  await check('History tells same-title records apart, filters loaded results honestly and escapes notes',()=>{
    const c=fixture();c.state.historyLoaded=true;c.state.historyCursor='next';
    Object.assign(c.fields,{wall:{label:'벽 두께',min:0.8,max:20,step:0.1},bottom:{label:'바닥 두께',min:0.8,max:20,step:0.1},dividers:{label:'칸막이 수',min:0,max:12,step:1,unit:'개'}});
    const base={title:'칸막이 수납함 · 120 × 80 × 35 mm',template:'tray',status:'geometry_validated',created_at:'2026-11-16T00:00:00Z'};
    c.state.historyItems=[
      {...base,id:'a',summary:{parameters:{wall:0.8,bottom:2,dividers:0},printability:'review'},user_outcome:null},
      {...base,id:'b',summary:{parameters:{wall:2,bottom:2,dividers:2},printability:'ok',slice:'sliced'},user_outcome:{result:'success',notes:'<b>딱</b> 맞음'}},
      {...base,id:'c',user_outcome:{result:'failure',notes:''}}];
    c.renderHistory();
    const text=c.$('history-list').textContent;
    assert.match(text,/벽 두께 0.8 mm/);assert.match(text,/칸막이 수 2개/);assert.match(text,/슬라이스 완료/);assert.match(text,/메모: <b>딱<\/b> 맞음/);assert.match(text,/점검 확인할 점/);
    c.setHistoryFilter('success');
    assert.match(c.$('history-list').textContent,/불러온 3개 중 1개/);assert.match(c.$('history-list').textContent,/이전 기록을 더 불러오면/);
    assert.equal(c.$('history-list').children.filter(x=>x.dataset?.jobId).map(x=>x.dataset.jobId).join(),'b');
    c.setHistoryFilter('unrecorded');assert.equal(c.$('history-list').children.filter(x=>x.dataset?.jobId).map(x=>x.dataset.jobId).join(),'a');
    c.state.historyItems=[];c.setHistoryFilter('failure');assert.match(c.$('history-list').textContent,/아직 만들어 둔 모델이 없어요/);
  });
  await check('A printer finish report hints at the outcome without selecting it',()=>{
    const c=fixture();c.$('outcome-result').value='not_tested';
    c.state.job={id:'job-a',result:{dimensions_mm:{x:1,y:1,z:1}},user_outcome:null};
    c.state.printerStatus={connection:{state:'reporting'},observed_at:'2026-11-16T00:00:00Z',target:{serial:'01S00X'},print:{state:'FINISH',state_label:'프린터가 완료를 보고함',job_name:'tray'}};
    c.renderJourney();
    assert.equal(c.$('outcome-printer-hint').hidden,false);assert.match(c.$('outcome-printer-hint').textContent,/상태: 출력 완료 보고/);assert.match(c.$('outcome-printer-hint').textContent,/자동으로 선택하지 않습니다/);
    assert.equal(c.$('outcome-result').value,'not_tested');
    c.state.printerStatus.print.state='RUNNING';c.renderJourney();assert.equal(c.$('outcome-printer-hint').hidden,true);
    c.state.printerStatus.print.state='FAILED';c.state.job=null;c.renderJourney();assert.equal(c.$('outcome-printer-hint').hidden,true);
  });
  await check('Offer comparison adds the current model material-cost upper bound and labels shipping-excluded values',()=>{
    const c=fixture();
    c.state.job={id:'j',title:'칸막이 수납함 · 120 × 80 × 35 mm',result:{printability:{items:[{id:'material',grams:50,value:'약 50 g'}]}}};
    c.renderOffersModelHint();assert.equal(c.$('offers-model-hint').hidden,false);assert.match(c.$('offers-model-hint').textContent,/약 50 g/);
    c.renderOffers({groups:{KRW:[{name:'A',grams:1000,price:20000,delivered_total:20000,price_per_kg:20000,product_price_per_kg:20000},{name:'B',grams:1000,price:30000,delivered_total:null,price_per_kg:null,product_price_per_kg:30000}]}});
    const text=c.$('offer-comparison').textContent;
    assert.match(text,/현재 모델 재료비 상한 · 50 g/);assert.match(text,/₩1,000/);assert.match(text,/₩1,500/);assert.match(text,/배송비 제외 금액/);
    assert.equal(c.$('offer-model-note').hidden,false);
    c.state.job=null;c.renderOffers({groups:{KRW:[{name:'A',grams:1000,price:20000,delivered_total:20000,price_per_kg:20000,product_price_per_kg:20000}]}});
    assert.doesNotMatch(c.$('offer-comparison').textContent,/재료비 상한/);assert.equal(c.$('offer-model-note').hidden,true);
    c.renderOffersModelHint();assert.equal(c.$('offers-model-hint').hidden,true);
  });
  await check('Printer-reported values fill only empty setup fields and each AMS slot is an explicit choice',()=>{
    const c=fixture();const events=[];c.Event=class{constructor(type){this.type=type;}};
    for(const id of ['setup-printer-model','setup-nozzle','setup-material']){c.$(id).value='';c.$(id).dispatchEvent=e=>events.push([id,e.type]);}
    c.state.printerStatus={connection:{state:'access_rejected'}};c.renderSetupPrinterFill();assert.equal(c.$('setup-printer-fill').hidden,true);
    c.state.printerStatus={connection:{state:'reporting'},observed_at:'2026-11-16T00:00:00Z',target:{serial:'01S00X'},identity:{product_name:'Bambu Lab P1S'},
      print:{nozzle:{diameter_mm:0.4},material_slots:[{unit:0,slot:0,product:'PLA Basic',filament_id:'GFA00'},{unit:0,slot:1,empty:true},{unit:'external',slot:254,material:'PETG',filament_id:'GFG99'}]}};
    c.$('setup-printer-model').value='내가 쓴 모델';
    c.renderSetupPrinterFill();
    assert.equal(c.$('setup-printer-fill').hidden,false);
    const buttons=c.$('setup-printer-fill-actions').children;
    assert.equal(buttons.length,3);assert.match(buttons[1].textContent,/AMS 1·슬롯 1: PLA Basic \(GFA00\)/);assert.match(buttons[2].textContent,/외부 스풀/);
    buttons[0].listeners.click();
    assert.equal(c.$('setup-printer-model').value,'내가 쓴 모델');assert.equal(c.$('setup-nozzle').value,'0.4');
    assert.match(c.$('setup-printer-fill-status').textContent,/노즐 지름/);assert.doesNotMatch(c.$('setup-printer-fill-status').textContent,/프린터 모델·/);
    buttons[1].listeners.click();assert.equal(c.$('setup-material').value,'GFA00');
    buttons[2].listeners.click();assert.equal(c.$('setup-material').value,'GFA00');assert.match(c.$('setup-printer-fill-status').textContent,/바꾸지 않았습니다/);
    assert.deepEqual(events.map(e=>e[0]),['setup-nozzle','setup-material']);
  });
  await check('Copied settings round-trip, invalid pastes explain the problem, and steppers clamp to the field range',async()=>{
    const c=fixture();c.Event=class{constructor(type){this.type=type;}};
    Object.assign(c.fields,{depth:{label:'세로',min:10,max:500,step:0.1},dividers:{label:'칸막이 수',min:0,max:12,step:1,unit:'개'}});
    c.state.templates=[{id:'tray',title:'칸막이 수납함',defaults:{width:120,depth:80,dividers:0},editable_fields:['width','depth','dividers'],description:'Tray'}];
    c.state.template='tray';
    for(const [k,v] of [['width','120'],['depth','80'],['dividers','2']]){const e=c.$('parameter-'+k);e.value=v;e.validity={valid:true};}
    const snapshot=c.currentParameterSnapshot();
    assert.deepEqual(plain(snapshot.parameters),{width:120,depth:80,dividers:2});assert.equal(snapshot.format,'3d-printer-agent/parameters');
    const parsed=c.parseParameterText(JSON.stringify(snapshot));
    assert.equal(parsed.template.id,'tray');assert.deepEqual(plain(parsed.parameters),{width:120,depth:80,dividers:2});
    for(const [text,pattern] of [['nope',/JSON/],['[]',/찾지 못했습니다/],['{"format":"other","template":"tray","parameters":{"width":100}}',/이 앱에서 복사한/],
      ['{"template":"cube","parameters":{"width":100}}',/지원하지 않습니다/],['{"template":"tray","parameters":{"width":5}}',/10~500/],
      ['{"template":"tray","parameters":{"dividers":1.5}}',/정수/],['{"template":"tray","parameters":{"slots":3}}',/쓰지 않는 치수/],['{"template":"tray","parameters":{}}',/치수가 없습니다/]]){
      assert.throws(()=>c.parseParameterText(text),pattern);
    }
    const width=c.$('parameter-width');let events=0;width.dispatchEvent=()=>{events+=1;};
    width.value='499.5';width.valueAsNumber=499.5;c.stepParameter('width',1);assert.equal(width.value,'500');
    width.valueAsNumber=10;c.stepParameter('width',-1);assert.equal(width.value,'10');assert.equal(events,2);
    c.$('parameter-wall').value='2';c.$('parameter-wall').valueAsNumber=0.8;c.$('parameter-wall').dispatchEvent=()=>{};
    Object.assign(c.fields,{wall:{label:'벽 두께',min:0.8,max:20,step:0.1}});c.stepParameter('wall',1);assert.equal(c.$('parameter-wall').value,'0.9');
    c.$('parameter-width').value='';assert.throws(()=>c.currentParameterSnapshot(),/올바르게 입력/);
  });
  await check('A stalled saved-list load after a successful reconnect never keeps the reconnect control busy',async()=>{
    const c=fixture();studioApplied(c);
    c.api=async(path)=>path==='/api/bootstrap'?{session_token:'new-token',storage:null,templates:c.state.templates,environment:{available:false},provider:{}}:{};
    c.loadWorkspaces=()=>new Promise(()=>{});  // never resolves, like a request cut off by a server restart
    const pending=c.bootstrap();
    for(let i=0;i<10;i++) await new Promise(done=>setImmediate(done));
    assert.equal(c.state.connectionState,'connected');assert.equal(c.state.bootstrapPending,false);
    assert.equal(c.$('reconnect-button').disabled,false);assert.equal(c.$('reconnect-button').textContent,'다시 연결');
    void pending;
  });
  await check('Text parameters stay strings in reads, copies and pastes',()=>{
    const c=fixture();
    Object.assign(c.fields,{text:{label:'글자',kind:'text',maxLength:20,unit:''},text_size:{label:'글자 크기',min:6,max:40,step:0.5}});
    c.state.templates=[{id:'name_tag',title:'이름 키링',defaults:{text:'MINSU',text_size:12},editable_fields:['text','text_size'],description:'Tag'}];
    c.state.template='name_tag';
    const text=c.$('parameter-text');text.value='  민수 ';text.dataset.parameter='text';text.validity={valid:true};
    const size=c.$('parameter-text_size');size.value='14';size.valueAsNumber=14;size.dataset.parameter='text_size';size.validity={valid:true};
    assert.equal(c.readParameter(text),'민수');assert.equal(c.readParameter(size),14);
    assert.equal(c.parameterInputComplete(text),true);text.value='   ';assert.equal(c.parameterInputComplete(text),false);text.value='민수';
    const snapshot=c.currentParameterSnapshot();assert.deepEqual(plain(snapshot.parameters),{text:'민수',text_size:14});
    assert.deepEqual(plain(c.parseParameterText(JSON.stringify(snapshot)).parameters),{text:'민수',text_size:14});
    assert.throws(()=>c.parseParameterText('{"template":"name_tag","parameters":{"text":42}}'),/1~20자/);
    assert.throws(()=>c.parseParameterText('{"template":"name_tag","parameters":{"text":"'+'x'.repeat(21)+'"}}'),/1~20자/);
  });
  await check('Template cards never show undefined sizes for a text-sized template',()=>{
    const c=fixture();
    assert.equal(c.templateSizeText({width:120,depth:80,height:35}),'120 × 80 × 35 mm · 기본 크기');
    assert.equal(c.templateSizeText({text:'MINSU',text_size:12,wall:3}),'기본 글자 “MINSU” · 글자 크기 12 mm');
    assert.equal(c.templateSizeText({wall:2}),'크기는 입력값에 맞춰 정해집니다');
    for(const value of [c.templateSizeText({text:'A',text_size:6}),c.templateSizeText({})]) assert.doesNotMatch(value,/undefined/);
  });
  await check('Colour choices stay optional strings in reads, copies, pastes, edits and the preview legend',()=>{
    const c=fixture();
    Object.assign(c.fields,{text:{label:'글자',kind:'text',maxLength:20,unit:''},color:{label:'모델 색',kind:'color',unit:''},accent_color:{label:'글자 색',kind:'color',unit:''}});
    c.state.templates=[{id:'name_tag',title:'이름 키링',defaults:{text:'MINSU',color:'',accent_color:''},editable_fields:['text','color','accent_color'],description:'Tag'}];
    c.state.template='name_tag';c.state.parameters={text:'MINSU',color:'',accent_color:''};
    const field=c.colorField(c.state.templates[0],'accent_color','글자 색');
    const swatches=field.children.find(child=>child.className==='color-swatches');
    assert.equal(swatches.children.length,12);
    assert.equal(swatches.children[0].attributes['aria-checked'],'true');
    const hidden=field.children.find(child=>child.type==='hidden');
    assert.equal(hidden.dataset.parameter,'accent_color');assert.equal(hidden.value,'');
    const text=c.$('parameter-text');text.value='지우';text.dataset.parameter='text';text.validity={valid:true};
    const body=c.$('parameter-color');body.value='';body.dataset.parameter='color';
    const accent=c.$('parameter-accent_color');accent.value='';accent.dataset.parameter='accent_color';
    let dispatched=0;accent.dispatchEvent=()=>{dispatched+=1;};
    c.chooseColor('accent_color','red');
    assert.equal(accent.value,'red');assert.equal(dispatched,1);
    c.chooseColor('accent_color','teal');assert.equal(accent.value,'red');assert.equal(dispatched,1);
    assert.equal(c.parameterInputComplete(body),true);assert.equal(c.readParameter(body),'');assert.equal(c.readParameter(accent),'red');
    assert.deepEqual(plain(c.currentParameterSnapshot().parameters),{text:'지우',accent_color:'red'});
    assert.deepEqual(plain(c.parseParameterText('{"template":"name_tag","parameters":{"text":"A","color":"white","accent_color":""}}').parameters),{text:'A',color:'white',accent_color:''});
    assert.throws(()=>c.parseParameterText('{"template":"name_tag","parameters":{"color":"#ff0000"}}'),/중 하나/);
    const edit=c.currentEditParameters();
    assert.equal(edit.accent_color,'red');assert.equal(Object.hasOwn(edit,'color'),false);
    assert.throws(()=>c.validateEditParameters({...edit,accent_color:'navy'}),/색 응답/);
    assert.throws(()=>c.validateEditParameters({template:'tray',width:120,depth:80,height:35,wall:2,bottom:2,dividers:0,slots:5,cable_diameter:6,inset_diameter:52,inset_depth:2,fit_clearance:0.3,accent_color:'red'}),/색 응답/);
    c.renderColorLegend([{label:'받침',name:'흰색',hex:'#F4F4F1',filament:1,volume_mm3:1000},{label:'글자',name:'빨강',hex:'#D2302C',filament:2,volume_mm3:500}]);
    assert.equal(c.$('preview-colors').hidden,false);
    assert.match(c.$('preview-colors').textContent,/글자: 빨강 · 필라멘트 2/);
    c.renderColorLegend(null);assert.equal(c.$('preview-colors').hidden,true);
  });
  await check('Printer sending needs a sliced job, a live single-use review and the bed confirmation',async()=>{
    const c=fixture();
    c.state.token='t';c.state.printerPins={'192.168.0.20|01S00SYNTH000001':'a'.repeat(64)};
    c.currentPrinterTarget=()=>({host:'192.168.0.20',serial:'01S00SYNTH000001',access_code:'abcd1234'});
    c.resetPrintSend({id:'j1',artifacts:{},latest_slice:null});
    assert.equal(c.$('print-send-card').hidden,true);
    const job={id:'j1',artifacts:{sliced_three_mf:'/api/jobs/j1/files/sliced_three_mf'},latest_slice:{phase:'done',execution:{status:'sliced'}}};
    c.state.job=job;c.resetPrintSend(job);
    assert.equal(c.$('print-send-card').hidden,false);
    assert.equal(c.$('print-send-review').disabled,false);
    assert.equal(c.$('print-send-start').disabled,true);
    assert.equal(c.printSendTarget().pinned_certificate_sha256,'a'.repeat(64));
    const sent=[];
    c.withBusy=async(_button,_label,work)=>work();
    c.api=async(path,body)=>{sent.push([path,body]);
      if(path==='/api/printers/print/review') return {ready:true,review_token:'tok-1234567890abcdef',expires_in_seconds:180,job_title:'Tag',filename:'pa-1.gcode.3mf',file_bytes:2048,
        summary:{filaments:[{id:1,type:'PLA',color:'#FFFFFF',used_g:2}],nozzle_diameters:'0.4',prediction_seconds:600,weight_g:2},printer:{state_label:'대기 중',nozzle:{diameter_mm:0.4}},
        mapping:{use_ams:false,ams_mapping:[-1],slots:[{filament:1,location:'외부 스풀'}]},material_slots:[{unit:0,slot:0,material:'PLA'}],problems:[],warnings:[],printer_model:{sliced_code:'C12',sliced_name:'P1S',reported_product:'Bambu Lab P1S'}};
      return {status:'started',detail:'ok',stages:{printer_ready:true,uploaded:true,command_sent:true,printer_reported_start:true}};};
    await c.reviewPrintSend();
    assert.equal(sent[0][1].job_id,'j1');assert.equal(sent[0][1].access_code,'abcd1234');assert.equal(sent[0][1].slots,null);
    c.renderPrintSendSummary({...c.state.printSend.review,problems:['이 파일은 P1S용으로 슬라이스했지만 프린터는 A1입니다.']});
    assert.match(c.$('print-send-summary').textContent,/슬라이스 P1S · 프린터 보고 Bambu Lab P1S/);
    assert.match(c.$('print-send-summary').textContent,/보낼 수 없는 이유.*P1S용/s);
    assert.equal(c.$('print-send-confirm').disabled,false);
    assert.equal(c.$('print-send-start').disabled,true);
    c.$('print-send-confirm').checked=true;c.updatePrintSendControls();
    assert.equal(c.$('print-send-start').disabled,false);
    await c.startPrintSend();
    assert.deepEqual(plain(sent[1]),['/api/printers/print/start',{review_token:'tok-1234567890abcdef',access_code:'abcd1234',bed_clear_confirmed:true}]);
    assert.equal(c.$('print-send-badge').textContent,'프린터가 출력 시작을 보고함');
    assert.match(c.$('print-send-result').textContent,/프린터의 출력 시작 보고/);
    assert.equal(c.$('print-send-start').disabled,true);
    await c.startPrintSend();
    assert.equal(sent.length,2);
    c.state.printSend.review={review_token:'tok-2',};c.state.printSend.expiresAt=Date.now()-1;c.state.printSend.jobId='j1';
    c.$('print-send-confirm').checked=true;c.updatePrintSendControls();
    assert.equal(c.$('print-send-start').disabled,true);
    c.resetPrintSend(null);assert.equal(c.$('print-send-card').hidden,true);
  });
  await check('The store guide filters by material, kind and name and only links http(s) addresses',()=>{
    const c=fixture();
    const guide={checked_on:'2026-11-17',materials:['PLA','PETG'],kinds:{own_brand:'자체 브랜드'},scope:'s',excluded:[{name:'퓨어필라'}],
      stores:[{id:'a',name:'Bambu Lab 한국 공식 스토어',bambu:true,kinds:['official_brand_store'],materials:['PLA','PETG'],sells:'Bambu Lab 정품',urls:[{label:'스토어',url:'https://kr.store.bambulab.com/'}],evidence:'e'},
              {id:'b',name:'태강쓰리디',bambu:false,kinds:['own_brand'],materials:['PLA'],sells:'국산 PLA+',urls:[{label:'x',url:'javascript:alert(1)'}],evidence:'e'}],
      unconfirmed:[{id:'u',name:'플라실',reason:'확인 못함',urls:[]}]};
    c.setStoreGuide(guide);
    assert.equal(c.$('store-guide').hidden,false);
    assert.match(c.$('store-guide-checked').textContent,/2026-11-17/);
    assert.match(c.$('store-guide-scope').textContent,/퓨어필라/);
    assert.equal(c.$('store-guide-list').children.length,2);
    c.state.storeFilter={material:'PETG',kind:'all',query:''};c.renderStoreGuide();
    assert.equal(c.$('store-guide-list').children.length,1);
    c.state.storeFilter={material:'all',kind:'bambu',query:''};c.renderStoreGuide();
    assert.equal(c.$('store-guide-list').children[0].dataset.store,'a');
    c.state.storeFilter={material:'all',kind:'own_brand',query:''};c.renderStoreGuide();
    assert.equal(c.$('store-guide-list').children[0].dataset.store,'b');
    c.state.storeFilter={material:'all',kind:'all',query:'뱀부'};c.renderStoreGuide();
    assert.equal(c.$('store-guide-list').children.length,1);
    c.state.storeFilter={material:'all',kind:'all',query:'없는 이름'};c.renderStoreGuide();
    assert.match(c.$('store-guide-count').textContent,/없습니다/);
    assert.equal(c.storeLink({label:'x',url:'javascript:alert(1)'}),null);
    const link=c.storeLink({label:'스토어',url:'https://kr.store.bambulab.com/'});
    assert.equal(link.rel,'noopener noreferrer');assert.equal(link.target,'_blank');
    assert.match(c.$('store-guide-unconfirmed-summary').textContent,/1곳/);
    c.setStoreGuide(null);assert.equal(c.$('store-guide').hidden,true);
  });
  await check('Remembered printers keep host, serial and pin but never the access code, and progress follows the started job',async()=>{
    const c=fixture();
    const store={};c.window.localStorage={getItem:(k)=>store[k]??null,setItem:(k,v)=>{store[k]=String(v);}};
    c.PRINTER_STORE_KEY='ppa.printers.v1';c.PRINT_FOLLOW_SECONDS=30;c.PRINT_FOLLOW_LIMIT_MS=1e9;
    c.state.printerPins={};c.updatePrinterControls=()=>{};c.printerInputChanged=()=>{};
    c.$('printer-remember').checked=true;
    c.rememberPrinter({host:'192.168.0.20',serial:'01S00SYNTH000001',access_code:'abcd1234'},{connection:{state:'reporting'},certificate:{sha256:'a'.repeat(64)},identity:{product_name:'P1S'}});
    assert.doesNotMatch(store['ppa.printers.v1'],/abcd1234/);
    const saved=c.loadSavedPrinters();
    assert.deepEqual(plain(saved.map(item=>[item.host,item.serial,item.pin,item.label])),[['192.168.0.20','01S00SYNTH000001','a'.repeat(64),'P1S']]);
    assert.equal(c.state.printerPins['192.168.0.20|01S00SYNTH000001'],'a'.repeat(64));
    c.$('printer-remember').checked=false;
    c.rememberPrinter({host:'192.168.0.30',serial:'01S00SYNTH000002'},{connection:{state:'reporting'},certificate:{sha256:'b'.repeat(64)}});
    assert.equal(c.loadSavedPrinters().length,1);
    store['ppa.printers.v1']='[{"host":"x","serial":"bad serial","pin":"zz"},"junk"]';
    assert.equal(c.loadSavedPrinters().length,0);
    store['ppa.printers.v1']='not json';assert.deepEqual(plain(c.loadSavedPrinters()),[]);
    c.window.localStorage={getItem:()=>{throw new Error('blocked');},setItem:()=>{throw new Error('blocked');}};
    assert.deepEqual(plain(c.loadSavedPrinters()),[]);assert.equal(c.storeSavedPrinters([{host:'h',serial:'S'}]),false);
    // Following progress: polls the same printer and stops on the printer's own finish report.
    const timers=[];c.setTimeout=(fn,ms)=>{timers.push([fn,ms]);return timers.length;};c.clearTimeout=()=>{};
    c.currentPrinterTarget=()=>({host:'192.168.0.20',serial:'01S00SYNTH000001',access_code:'abcd1234'});
    const area=c.$('print-send-result');const appended=[];area.append=(...nodes)=>appended.push(...nodes);
    const ids={};const original=c.node;c.node=(tag,cls,text)=>{const el=original(tag,cls,text);return el;};
    for(const id of ['print-follow','print-follow-bar','print-follow-text','print-follow-status','print-follow-stop']) c.$(id).parentElement={setAttribute(){}};
    c.$('print-follow-bar').style={};
    c.startPrintFollow({status:'started',subtask:'printer-agent 1',printer:{state:'PREPARE',state_label:'출력 준비 중',progress_percent:0}});
    assert.equal(c.state.printFollow.active,true);assert.equal(timers.at(-1)[1],30000);
    let calls=0;c.api=async(path,body)=>{calls+=1;assert.equal(path,'/api/printers/status');assert.equal(body.pinned_certificate_sha256,'a'.repeat(64));
      return calls===1?{connection:{state:'reporting'},observed_at:'2026-11-17T00:00:00Z',print:{state:'RUNNING',state_label:'출력 중',progress_percent:40,remaining_minutes:5,layer:8,total_layers:20,job_name:'printer-agent 1'}}
                     :{connection:{state:'reporting'},observed_at:'2026-11-17T00:01:00Z',print:{state:'FINISH',state_label:'프린터가 완료를 보고함',progress_percent:100,job_name:'printer-agent 1'}};};
    await c.pollPrintFollow();
    assert.match(c.$('print-follow-text').textContent,/40%.*남은 시간 약 5분.*레이어 8\/20/);
    assert.equal(c.state.printFollow.active,true);
    await c.pollPrintFollow();
    assert.equal(c.state.printFollow.active,false);
    assert.match(c.$('print-send-feedback').textContent,/완료를 보고/);
    const before=calls;await c.pollPrintFollow();assert.equal(calls,before);
    c.startPrintFollow({status:'started',subtask:'x'});c.currentPrinterTarget=()=>({host:'192.168.0.99',serial:'01S00SYNTH000001',access_code:'abcd1234'});
    await c.pollPrintFollow();assert.equal(c.state.printFollow.active,false);assert.match(c.$('print-follow-status').textContent,/바뀌었/);
  });
  await check('Print controls follow the reported state, need a pin and confirm a stop',async()=>{
    const c=fixture();
    c.PRINT_FOLLOW_SECONDS=30;c.PRINT_FOLLOW_LIMIT_MS=1e9;
    c.state.printerPins={};c.state.job={id:'j1'};
    for(const id of ['print-control-pause','print-control-resume','print-control-stop','print-stop-confirm','print-stop-yes','print-control-feedback','print-follow-text','print-follow-status','print-follow-stop']) c.$(id);
    c.$('print-follow-bar').style={};c.$('print-follow-bar').parentElement={setAttribute(){}};
    c.updatePrintControls('RUNNING');
    assert.deepEqual([c.$('print-control-pause').hidden,c.$('print-control-resume').hidden,c.$('print-control-stop').hidden],[false,true,false]);
    c.updatePrintControls('PAUSE');
    assert.deepEqual([c.$('print-control-pause').hidden,c.$('print-control-resume').hidden,c.$('print-control-stop').hidden],[true,false,false]);
    c.updatePrintControls('IDLE');
    assert.deepEqual([c.$('print-control-pause').hidden,c.$('print-control-resume').hidden,c.$('print-control-stop').hidden],[true,true,true]);
    c.state.printFollow={active:true,timer:null,lastState:'RUNNING',host:'192.168.0.20',serial:'01S00SYNTH000001'};
    c.currentPrinterTarget=()=>({host:'192.168.0.20',serial:'01S00SYNTH000001',access_code:'abcd1234'});
    const sent=[];c.api=async(path,body)=>{sent.push([path,body]);return {status:'applied',detail:'ok',printer:{state:body.action==='pause'?'PAUSE':'FAILED',state_label:'x'}};};
    await c.sendPrintControl('pause');
    assert.equal(sent.length,0);assert.match(c.$('print-control-feedback').textContent,/인증서/);
    c.state.printerPins['192.168.0.20|01S00SYNTH000001']='a'.repeat(64);
    await c.sendPrintControl('pause');
    assert.deepEqual(plain(sent[0]),['/api/printers/print/control',{host:'192.168.0.20',serial:'01S00SYNTH000001',access_code:'abcd1234',pinned_certificate_sha256:'a'.repeat(64),action:'pause',stop_confirmed:false,job_id:'j1'}]);
    assert.equal(c.state.printFollow.lastState,'PAUSE');
    c.askPrintStop();assert.equal(c.$('print-stop-confirm').hidden,false,'confirm shown');
    await c.sendPrintControl('stop');
    assert.equal(sent[1][1].stop_confirmed,true,'stop confirmed');
    assert.equal(c.state.printFollow.active,false,'follow stopped');
    assert.equal(c.$('print-stop-confirm').hidden,true,'confirm hidden');
  });
  await check('Failure reasons show only for a failure, count as unsaved work and open a reviewed model edit',()=>{
    const c=fixture();
    const boxes=[{value:'too_tight',checked:false,dataset:{outcomeReason:'too_tight'}},{value:'stringing',checked:false,dataset:{outcomeReason:'stringing'}}];
    c.document.querySelectorAll=(selector)=>selector==='[data-outcome-reason]'?boxes:[];
    c.state.job={id:'j1',user_outcome:{result:'failure',notes:'',reasons:['too_tight']}};
    c.$('outcome-result').value='failure';c.$('outcome-notes').value='';
    c.syncOutcomeReasons(['too_tight']);
    assert.equal(c.$('outcome-reasons').hidden,false);
    assert.deepEqual(plain(c.selectedOutcomeReasons()),['too_tight']);
    assert.equal(c.outcomeHasUnsavedChanges(),false);
    boxes[1].checked=true;assert.equal(c.outcomeHasUnsavedChanges(),true);
    c.$('outcome-result').value='success';c.syncOutcomeReasons([]);assert.equal(c.$('outcome-reasons').hidden,true);
    c.renderRecovery({items:[{reason:'too_tight',label:'너무 꽉',actions:['여유를 늘리세요'],model_edit:{text:'여유 0.2mm 늘려줘',changes:[{field:'fit_clearance',before:0.3,after:0.5}]}},
                             {reason:'stringing',label:'거미줄',actions:['온도'],model_edit:null}],scope:'s'});
    assert.equal(c.$('outcome-recovery').hidden,false);
    let proposed=0;c.$('model-edit-panel').scrollIntoView=()=>{};c.$('model-edit-propose').click=()=>{proposed+=1;};c.$('model-edit-text').dispatchEvent=()=>{};
    c.proposeRecoveryEdit('여유 0.2mm 늘려줘');
    assert.equal(c.$('model-edit-text').value,'여유 0.2mm 늘려줘');assert.equal(proposed,1);
    c.renderRecovery({items:[]});assert.equal(c.$('outcome-recovery').hidden,true);
  });
  await check('A printer failure report kept on the job is sent with follow reads, shown as a hint and opens recovery with the HMS search link',async()=>{
    const c=fixture();
    c.PRINT_FOLLOW_SECONDS=300;c.PRINT_FOLLOW_LIMIT_MS=1e9;
    for(const id of ['print-control-pause','print-control-resume','print-control-stop','print-stop-confirm','print-follow-text','print-follow-status','print-follow-stop','print-follow-refresh','outcome-printer-hint','outcome-recovery']) c.$(id);
    c.$('print-follow-bar').style={};c.$('print-follow-bar').parentElement={setAttribute(){}};
    c.state.printerPins={};c.currentPrinterTarget=()=>({host:'192.168.0.20',serial:'01S00SYNTH000001',access_code:'abcd1234'});
    c.setTimeout=()=>1;c.clearTimeout=()=>{};
    c.state.job={id:'j1',title:'T',user_outcome:{result:'not_tested',notes:'draft kept'}};
    c.state.printFollow={active:true,timer:null,startedAt:Date.now(),host:'192.168.0.20',serial:'01S00SYNTH000001',jobName:'printer-agent j1',jobId:'j1'};
    const report={state:'FAILED',serial:'01S00SYNTH000001',observed_at:'2026-11-19T00:00:00Z',codes:[{kind:'print_error',code:'0300-400C'}]};
    const calls=[];c.api=async(path,b)=>{calls.push([path,b]);if(path==='/api/printers/status')return {connection:{state:'reporting'},observed_at:'2026-11-19T00:00:00Z',print:{state:'FAILED',state_label:'실패',job_name:'printer-agent j1'},job_link:{recorded:true,report}};
      return {items:[{reason:'printer_reported',label:'프린터가 보고한 실패',actions:['코드 0300-400C'],model_edit:null,codes:['0300-400C'],lookup_url:'https://wiki.bambulab.com/en/hms/home'}],scope:'s'};};
    await c.pollPrintFollow();await new Promise(r=>setImmediate(r));
    assert.equal(calls[0][1].job_id,'j1');
    assert.equal(c.state.job.printer_report.state,'FAILED');assert.equal(c.state.job.user_outcome.notes,'draft kept');
    assert.equal(c.$('outcome-printer-hint').hidden,false);assert.match(c.$('outcome-printer-hint').textContent,/0300-400C/);assert.match(c.$('outcome-printer-hint').textContent,/실물 확인이 아닙니다/);
    assert.equal(calls[1][0],'/api/jobs/j1/recovery');assert.equal(c.$('outcome-recovery').hidden,false);
    const link=c.$('outcome-recovery').children[1].children.find(child=>child.tagName==='A'||child.href);
    assert.equal(link.href,'https://wiki.bambulab.com/en/hms/home');assert.equal(link.rel,'noopener noreferrer');
    c.state.job={id:'j2',title:'U',user_outcome:null};c.linkPrinterReport('j1',report);assert.equal(c.state.job.printer_report,undefined);
  });
  await check('Inventory shows totals, low stock and offers a one-time deduction for a sliced job',()=>{
    const c=fixture();c.numberFormat=new Intl.NumberFormat('ko-KR',{maximumFractionDigits:2});
    const spool=(id,extra)=>({id,revision:1,brand:'B',material:'PLA',color_name:'검정',color_hex:'#232323',net_weight_g:1000,empty_spool_g:250,remaining_g:800,status:'opened',location:'서랍',history:[],...extra});
    c.state.inventory={spools:[spool('a'),spool('b',{remaining_g:90,material:'PETG'}),spool('c',{remaining_g:0,status:'empty'})],
      totals:{spools:2,remaining_g:890,remaining_value_krw:20000,by_material:{PLA:800,PETG:90},low_stock_ids:['b']},low_stock_g:150,unreadable:1,scope:'s'};
    c.renderInventory();
    assert.match(c.$('inventory-totals').textContent,/사용 중인 스풀 2개/);assert.match(c.$('inventory-totals').textContent,/150 g 미만 1개/);
    assert.match(c.$('inventory-scope').textContent,/읽을 수 없는 기록 1개/);
    const cards=c.$('inventory-list').children;assert.equal(cards.length,3);
    assert.match(cards[1].className,/is-low/);assert.match(cards[2].className,/is-empty/);
    c.state.job={id:'j1',latest_slice:{execution:{status:'needs_review',filament_grams:12}}};c.renderOutcomeSpool();assert.equal(c.$('outcome-spool').hidden,true);
    c.state.job={id:'j1',latest_slice:{execution:{status:'sliced',filament_grams:12.5}}};c.renderOutcomeSpool();
    assert.equal(c.$('outcome-spool').hidden,false);assert.equal(c.$('outcome-spool-select').children.length,2);
    assert.equal(c.$('outcome-spool-grams').value,'12.5');assert.equal(c.$('outcome-spool-use').disabled,false);
    c.state.inventory.spools[0].history=[{kind:'used',job_id:'j1'}];c.renderOutcomeSpool();
    assert.match(c.$('outcome-spool-help').textContent,/이미 B PLA · 검정에서 뺐습니다/);assert.equal(c.$('outcome-spool-use').disabled,true);
  });
  await check('Glossary filters by words and category, lists the first-run steps and remembers a closed welcome',()=>{
    const c=fixture();const stored={};
    c.window.localStorage={getItem:key=>stored[key]??null,setItem:(key,value)=>{stored[key]=value;}};
    c.pageNames={models:'모델 만들기',profiles:'재료 설정'};
    const glossary={categories:{material:'재료',slice:'슬라이스'},scope:'쉬운 설명',
      terms:[{id:'pla',term:'PLA',aka:'Polylactic acid',category:'material',short:'흔한 재료',detail:'열에 약함',related:['support'],view:'profiles'},
             {id:'support',term:'서포트',aka:'Support',category:'slice',short:'받침',detail:'떼어냄',related:[],view:null}],
      onboarding:[{id:'make',title:'만들기',text:'고르기',view:'models'},{id:'record',title:'기록',text:'남기기',view:'unknown'}]};
    c.setGlossary(glossary);
    assert.equal(c.$('glossary-list').children.length,2);assert.match(c.$('glossary-count').textContent,/2개 · 전체 2개/);
    assert.equal(c.$('onboarding-steps').children.length,2);assert.equal(c.$('onboarding-steps').children[1].children.length,1,'an unknown view gets no open button');
    assert.match(c.$('glossary-list').children[0].textContent,/관련: 서포트/);assert.match(c.$('glossary-list').children[0].textContent,/재료 설정 열기/);
    c.state.glossaryFilter.query='support';c.renderGlossary();assert.equal(c.$('glossary-list').children.length,1);
    c.state.glossaryFilter={category:'material',query:''};c.renderGlossary();assert.equal(c.$('glossary-list').children[0].id,'term-pla');
    c.state.glossaryFilter.query='없는말';c.renderGlossary();assert.equal(c.$('glossary-list').children.length,0);assert.match(c.$('glossary-count').textContent,/찾는 말이 없습니다/);
    assert.equal(c.$('welcome').hidden,false);c.dismissWelcome();assert.equal(c.$('welcome').hidden,true);
    c.renderWelcome();assert.equal(c.$('welcome').hidden,true,'closing the welcome is remembered');
    c.window.localStorage={getItem(){throw new Error('blocked');},setItem(){throw new Error('blocked');}};
    c.renderWelcome();assert.equal(c.$('welcome').hidden,false,'without storage the welcome simply shows');c.dismissWelcome();assert.equal(c.$('welcome').hidden,true);
    c.setGlossary(null);assert.equal(c.$('welcome').hidden,true,'no glossary, no welcome');
    c.$('term-popover').hidden=true;c.openTerm('missing',null);assert.equal(c.$('term-popover').hidden,true,'unknown terms do not open');
  });
  await check('Printer slots link to spools, warn on another material and guide the send and the deduction',async()=>{
    const c=fixture();c.numberFormat=new Intl.NumberFormat('ko-KR',{maximumFractionDigits:2});
    const spool=(id,extra)=>({id,revision:1,brand:'B',material:'PLA',color_name:id,remaining_g:800,net_weight_g:1000,status:'opened',history:[],deductions:[],slot:null,...extra});
    c.state.inventory={spools:[spool('a',{slot:{serial:'01S00TEST000001',position:'ams-0-1'},status:'loaded'}),spool('b',{material:'PETG-HF',remaining_g:2}),spool('c',{status:'empty',remaining_g:0})],totals:{spools:2,remaining_g:802,by_material:{},low_stock_ids:[]}};
    c.state.printerSlotView={serial:'01S00TEST000001',slots:[{unit:0,slot:0,material:'PETG'},{unit:0,slot:1,material:'PETG'},{unit:'external',slot:null,material:'PLA'},{unit:'x'}]};
    c.renderPrinterSlotLinks();
    const rows=c.$('printer-slot-links').children.slice(1);
    assert.equal(rows.map(row=>row.dataset.position).join(),'ams-0-0,ams-0-1,external','unknown positions are skipped');
    const select=rows[1].children[1];assert.equal(select.value,'a');assert.equal(select.children.length,3,'empty spools are not offered');
    assert.match(rows[1].textContent,/재고 기록은 PLA, 프린터 보고는 PETG/);assert.doesNotMatch(rows[0].textContent,/프린터 보고는/);
    assert.equal(c.positionLabel('ams-1-3'),'AMS 2 · 4번 칸');assert.equal(c.sendChoicePosition(5),'ams-1-1');assert.equal(c.sendChoicePosition('external'),'external');
    assert.equal(c.materialBase('PETG-HF'),'PETG');
    const calls=[];c.api=async(path,body)=>{calls.push([path,body]);return {};};c.loadInventory=async()=>{};
    await c.linkSpoolToSlot('ams-0-0','b');assert.equal(JSON.stringify(calls[0]),JSON.stringify(['/api/spools/b/slot',{expected_revision:1,serial:'01S00TEST000001',position:'ams-0-0'}]));
    await c.linkSpoolToSlot('ams-0-1','');assert.equal(JSON.stringify(calls[1]),JSON.stringify(['/api/spools/a/slot',{expected_revision:1,serial:null,position:null}]));
    await c.linkSpoolToSlot('ams-0-1','a');assert.equal(calls.length,2,'choosing the linked spool again sends nothing');
    // Send review: the chosen slot names its spool and warns when the record holds less than the estimate.
    const slotSelect=new Element();slotSelect.dataset.printSlot='0';slotSelect.value='1';
    const hint=new Element();hint.dataset.printSpool='0';
    c.document.querySelectorAll=selector=>selector==='[data-print-slot]'?[slotSelect]:selector==='[data-print-spool]'?[hint]:[];
    c.currentPrinterTarget=()=>({host:'h',serial:'01s00test000001',access_code:''});
    c.state.printSend={jobId:'j1',review:{summary:{filaments:[{id:1,used_g:900}]}}};
    c.renderPrintSendSpools();assert.match(hint.textContent,/기록상 800 g 남아 예상 사용량 900 g보다 적습니다/);
    c.state.printSend.review.summary.filaments[0].used_g=12;c.renderPrintSendSpools();assert.match(hint.textContent,/a · 기록상 800 g 남음/);
    slotSelect.value='2';c.renderPrintSendSpools();assert.match(hint.textContent,/연결한 재고 스풀이 없습니다/);
    slotSelect.value='1';assert.equal(c.sentSpoolForJob('j1').id,'a');assert.equal(c.sentSpoolForJob('other'),null);
    c.state.job={id:'j1',latest_slice:{execution:{status:'sliced',filament_grams:12}}};c.$('outcome-spool-select').value='b';c.renderOutcomeSpool();
    assert.equal(c.$('outcome-spool-select').value,'a','the spool in the slot the print was sent to is chosen');assert.match(c.$('outcome-spool-help').textContent,/보낸 칸에 연결된 B PLA · a/);
  });
  await check('Both slicing workflows refresh the deduction panel, and a new slice clears it',async()=>{
    const c=fixture();c.numberFormat=new Intl.NumberFormat('ko-KR',{maximumFractionDigits:2});
    const spool={id:'a',revision:1,brand:'B',material:'PLA',color_name:'검정',color_hex:'#232323',net_weight_g:1000,empty_spool_g:250,remaining_g:800,status:'opened',location:'서랍',history:[],deductions:[]};
    c.state.inventory={spools:[spool],totals:{spools:1,remaining_g:800,by_material:{PLA:800},low_stock_ids:[]},unreadable:0,scope:'s'};
    c.state.job={...job(),latest_slice:null};c.$('slicer-json').value='{"machine":{},"process":{},"filaments":[]}';
    c.api=async(path)=>path==='/api/slice'?{plan:{ready:true,diagnostics:[]},execution:{status:'sliced'}}
      :{...job(),latest_slice:{phase:'complete',execution:{status:'sliced',filament_grams:12.5}}};
    c.$('outcome-spool').hidden=true;
    await c.runSlice(true);
    assert.equal(c.$('outcome-spool').hidden,false,'the full-settings workflow offers the deduction');
    assert.equal(c.$('outcome-spool-select').children.length,1);assert.equal(c.$('outcome-spool-grams').value,'12.5');
    spool.deductions=[{job_id:'job-a',at:'2026-11-21T00:00:00Z',grams:12.5}];c.renderOutcomeSpool();
    assert.match(c.$('outcome-spool-help').textContent,/이미/);assert.equal(c.$('outcome-spool-use').disabled,true);
    c.resetSlicePreparation('다시 슬라이싱합니다.');assert.equal(c.$('outcome-spool').hidden,true,'a replaced slice takes its offer with it');
  });
  await check('Slice comparison shows estimates against the current settings and applies only the listed keys',()=>{
    const c=fixture();c.numberFormat=new Intl.NumberFormat('ko-KR',{maximumFractionDigits:2});
    c.state.job={id:'j1'};
    const record={scope:'s',variants:[{id:'original',label:'지금 설정',overrides:{},status:'sliced',minutes:100,grams:50,layers:500,support:false},
      {id:'fast',label:'빠르게',overrides:{layer_height:'0.28',sparse_infill_density:'10%'},status:'sliced',minutes:70,grams:45,layers:357,support:false},
      {id:'fine',label:'곱게',overrides:{layer_height:'0.12'},status:'not_ready',diagnostics:['출력 영역 밖']}]};
    c.renderSliceComparison(record);
    const area=c.$('slice-compare');assert.equal(area.hidden,false);
    const rows=area.children[0].children;
    assert.match(rows[2].textContent,/70분 \(-30%\)/);assert.match(rows[2].textContent,/45 g \(-10%\)/);assert.match(rows[2].textContent,/레이어 0\.28 · 채움 10%/);
    assert.match(rows[3].textContent,/슬라이스하지 못함 · 출력 영역 밖/);
    c.$('slicer-json').value=JSON.stringify({source:'user_export',machine:{name:'m'},process:{layer_height:'0.2',sparse_infill_density:['15%'],wall_loops:'2'},filaments:[{}]});
    let input=0;c.$('slicer-json').dispatchEvent=()=>{input+=1;};
    c.applySliceVariant(record.variants[1]);
    const applied=JSON.parse(c.$('slicer-json').value);
    assert.deepEqual(plain(applied.process),{layer_height:'0.28',sparse_infill_density:['10%'],wall_loops:'2'});
    assert.deepEqual(plain(applied.machine),{name:'m'});assert.equal(input,1);
    c.renderSliceComparison(null);assert.equal(area.hidden,true);
  });
  await check('An imported placement is rotated like the server and set on the bed, and its summary reads in cm²',()=>{
    const c=fixture();c.numberFormat=new Intl.NumberFormat('ko-KR',{maximumFractionDigits:2});
    const flip=[[1,0,0],[0,-1,0],[0,0,-1]];
    const placed=c.placedPreview({vertices:[[0,0,0],[10,0,0],[0,20,0],[0,0,5]],faces:[[0,1,2]]},flip);
    assert.deepEqual(plain(placed.vertices.map(p=>p.map(v=>Math.round(v*1000)/1000+0))),[[-5,10,5],[5,10,5],[-5,-10,5],[-5,10,0]]);
    assert.deepEqual(plain(placed.faces),[[0,1,2]]);
    assert.equal(c.importOrientationText({overhang_mm2:250,contact_mm2:2400,size_mm:{x:60,y:40,z:35}}),'돌출부 2.5 cm² · 바닥 접촉 24.0 cm² · 60 × 40 × 35 mm');
    c.state.token='t';c.$('import-file').files=[];c.updateImportControls();assert.equal(c.$('import-submit').disabled,true);
    c.$('import-file').files=[{name:'a.stl'}];c.updateImportControls();assert.equal(c.$('import-submit').disabled,false);
    c.state.importPending=true;c.updateImportControls();assert.equal(c.$('import-submit').disabled,true);
  });
  await check('Starting-project sizes use the stated outer size for name tags and keycaps',()=>{
    const c=fixture();c.numberFormat=new Intl.NumberFormat('ko-KR',{maximumFractionDigits:2});
    assert.equal(c.projectSizeText({parameters:{width:90,depth:60,height:18}}),'90 × 60 × 18 mm');
    assert.equal(c.projectSizeText({parameters:{width:120,depth:80,height:8},size_mm:{width:41.8125,depth:18,height:8,basis:'exact'}}),'41.81 × 18 × 8 mm');
    assert.equal(c.projectSizeText({parameters:{width:120,depth:80,height:35},size_mm:{width:62,depth:16,height:4,basis:'upper_bound'}}),'최대 62 × 16 × 4 mm · 글꼴에 따라 가로가 달라짐');
  });
  await check('An edited model shows its earlier attempts oldest first with recorded outcomes, printer codes and changes',async()=>{
    const c=fixture();
    c.$('outcome-attempts');
    c.state.failureReasons={too_tight:'너무 꽉'};
    const calls=[];
    c.api=async(path)=>{calls.push(path);return {attempts:[
      {job_id:'c',created_at:'2026-11-19T02:00:00Z',user_outcome:null,printer_report:null,sliced:false,sent_to_printer:false,changes_from_parent:{changes:[{field:'wall',before:2,after:2.4}]}},
      {job_id:'b',created_at:'2026-11-19T01:00:00Z',user_outcome:null,printer_report:{state:'FAILED',codes:['0300-400C']},sliced:true,sent_to_printer:true,changes_from_parent:{changes:[{field:'fit_clearance',before:0.2,after:0.4}]}},
      {job_id:'a',created_at:'2026-11-19T00:00:00Z',user_outcome:{result:'failure',reasons:['too_tight']},printer_report:null,sliced:true,sent_to_printer:true,changes_from_parent:null}],stopped:'missing'};};
    c.state.job={id:'n',title:'N'};await c.loadAttempts(c.state.job);
    assert.equal(calls.length,0);assert.equal(c.$('outcome-attempts').hidden,true);
    c.state.job={id:'c',title:'C',model_edit:{selection:{parent:{job_id:'b'}}}};
    await c.loadAttempts(c.state.job);
    assert.deepEqual(calls,['/api/jobs/c/attempts']);
    const area=c.$('outcome-attempts');assert.equal(area.hidden,false,area.textContent);
    assert.equal(area.children.length,4,area.textContent);const items=area.children[1].children;
    assert.deepEqual(items.map(item=>item.dataset.attempt),['a','b','c']);
    assert.match(items[0].children[1].textContent,/직접 기록: 실패 \(너무 꽉\)/);
    assert.match(items[1].children[1].textContent,/프린터 보고: 실패 · 0300-400C/);
    assert.match(items[1].children[2].textContent,/0.2 → 0.4/);
    assert.match(items[2].children[1].textContent,/결과 기록 없음/);
    assert.equal(items[2].getAttribute?items[2].getAttribute('aria-current'):items[2].attributes?.['aria-current'],'true');
    assert.match(area.children[2].textContent,/이 PC에 없습니다/);
    c.renderAttempts({attempts:[{job_id:'x',created_at:'2026-11-19T00:00:00Z'}]},'x');assert.equal(area.hidden,true);
    const sliced=[{job_id:'b',slice_settings:{filament_type:['PLA'],layer_height:'0.16'},slice_changes:{compared_with:'a',changes:[{key:'layer_height',before:'0.2',after:'0.16'},{key:'nozzle_temperature',before:['220'],after:['215']}]}},
      {job_id:'a',slice_settings:{filament_type:['PLA'],nozzle_diameter:['0.4'],layer_height:'0.2',nozzle_temperature:['220']},slice_changes:null}].reverse();
    assert.equal(c.attemptSliceText(sliced[0],sliced),'슬라이스 설정: 재료 PLA · 노즐 0.4 · 레이어 높이 0.2 · 노즐 온도 220');
    assert.equal(c.attemptSliceText(sliced[1],sliced),'슬라이스 설정 변경(1번째 시도 대비): 레이어 높이 0.2 → 0.16, 노즐 온도 220 → 215');
    assert.equal(c.attemptSliceText({slice_settings:{layer_height:'0.2'},slice_changes:{compared_with:'a',changes:[]}},sliced),'슬라이스 설정: 1번째 시도와 같음');
    assert.equal(c.attemptSliceText({slice_settings:null},sliced),'');
  });
  await check('Review fixes: stop stays available during a pause, idle ends following, drafts keep reasons, recovery uses rules',async()=>{
    const c=fixture();
    c.PRINT_FOLLOW_SECONDS=300;c.PRINT_FOLLOW_LIMIT_MS=1e9;
    for(const id of ['print-control-pause','print-control-resume','print-control-stop','print-stop-confirm','print-follow-text','print-follow-status','print-follow-stop','print-follow-refresh']) c.$(id);
    c.$('print-follow-bar').style={};c.$('print-follow-bar').parentElement={setAttribute(){}};
    c.state.printControlPending='pause';c.updatePrintControls('RUNNING');
    assert.equal(c.$('print-control-pause').disabled,true);assert.equal(c.$('print-control-stop').disabled,false);
    c.state.printControlPending='stop';c.updatePrintControls('RUNNING');assert.equal(c.$('print-control-stop').disabled,true);
    c.state.printControlPending=false;
    c.state.printerPins={};c.currentPrinterTarget=()=>({host:'192.168.0.20',serial:'01S00SYNTH000001',access_code:'abcd1234'});
    c.setTimeout=()=>1;c.clearTimeout=()=>{};
    c.state.printFollow={active:true,timer:null,startedAt:Date.now(),host:'192.168.0.20',serial:'01S00SYNTH000001',jobName:'printer-agent 1'};
    let body=null;c.api=async(path,b)=>{body=b;return {connection:{state:'reporting'},observed_at:'2026-11-17T00:00:00Z',print:{state:'IDLE',state_label:'대기 중',job_name:''}};};
    await c.pollPrintFollow();
    assert.equal(body.include_version,false);
    assert.equal(c.state.printFollow.active,false);
    assert.match(c.$('print-send-feedback').textContent,/작업 이름을 보고하지/);
    const boxes=[{value:'warping',checked:true,dataset:{outcomeReason:'warping'}}];
    c.document.querySelectorAll=(s)=>s==='[data-outcome-reason]'?boxes:[];
    c.state.job={id:'j1',title:'T',user_outcome:null};c.$('outcome-result').value='failure';c.$('outcome-notes').value='';
    c.state.failureReasons={warping:'모서리가 들뜨거나 휨'};
    c.retainOutcomeDraft('/data');
    assert.deepEqual(plain(c.state.retainedOutcomeDrafts.at(-1).reasons),['warping']);
    c.$('model-edit-mode').value='llm';c.$('model-edit-panel').scrollIntoView=()=>{};c.$('model-edit-propose').click=()=>{};c.$('model-edit-text').dispatchEvent=()=>{};
    c.proposeRecoveryEdit('여유 0.2mm 늘려줘');
    assert.equal(c.$('model-edit-mode').value,'templates');
  });
  await check('The update check reports the result and links only https release pages',async()=>{
    const c=fixture();
    c.withBusy=async(_b,_l,work)=>work();
    c.document.createTextNode=(text)=>({textContent:text});
    c.api=async(path,body)=>{assert.equal(path,'/api/updates/check');assert.deepEqual(plain(body),{});
      return {status:'update_available',detail:'새 버전 0.23.0이 있습니다.',current_version:'0.22.0',latest_version:'0.23.0',published_at:'2026-11-17T06:35:19Z',
        release_url:'https://github.com/uulab-official/3d-printer-agent/releases/tag/v0.23.0',update_guide:'javascript:alert(1)'};};
    await c.checkForUpdate();
    const kids=c.$('update-result').children;
    assert.match(kids[0].textContent,/현재 0\.22\.0 · 최신 0\.23\.0/);
    const links=kids.filter(child=>child.href);
    assert.equal(links.length,1);assert.match(links[0].href,/^https:\/\/github\.com\//);assert.equal(links[0].rel,'noopener noreferrer');
    c.api=async()=>{throw new Error('연결 실패');};
    await c.checkForUpdate();
    assert.equal(c.$('update-result').textContent,'연결 실패');
  });
  await check('Radio groups are one Tab stop and arrow keys move and select the choice',()=>{
    const c=fixture();
    const group=new (c.$('x').constructor)();group.attributes.role='radiogroup';
    const radios=['all','PLA','PETG'].map((value,index)=>{const r=new (c.$('x').constructor)();r.attributes.role='radio';r.dataset.value=value;r.setAttribute('aria-checked',String(index===1));r.closest=(s)=>s.includes('radiogroup')?group:r;r.clicked=0;r.click=()=>{r.clicked+=1;for(const o of radios)o.setAttribute('aria-checked',String(o===r));};r.focused=0;r.focus=()=>{r.focused+=1;};return r;});
    group.append(...radios);
    c.syncRadioGroup(group);
    assert.deepEqual(radios.map(r=>r.tabIndex),[-1,0,-1]);
    let prevented=0;
    c.radioGroupKey({key:'ArrowRight',target:radios[1],preventDefault(){prevented+=1;}});
    assert.equal(radios[2].clicked,1);assert.equal(radios[2].focused,1);assert.deepEqual(radios.map(r=>r.tabIndex),[-1,-1,0]);
    c.radioGroupKey({key:'ArrowRight',target:radios[2],preventDefault(){prevented+=1;}});
    assert.equal(radios[0].clicked,1);  // wraps around
    c.radioGroupKey({key:'End',target:radios[0],preventDefault(){prevented+=1;}});
    assert.equal(radios[2].clicked,2);
    c.radioGroupKey({key:'a',target:radios[2],preventDefault(){prevented+=1;}});
    assert.equal(prevented,3);
  });
  await check('A keycap legend may be blank and the key size is a later field',()=>{
    const c=fixture();
    const key={template:'keycap',width:120,depth:80,height:8,wall:1.3,bottom:2,dividers:0,slots:5,cable_diameter:6,inset_diameter:52,inset_depth:2,fit_clearance:0.15,text:'',text_size:5,text_depth:0.8,key_units:1.5};
    assert.deepEqual(plain(c.validateEditParameters(key)),['key_units','text','text_size','text_depth','height','wall','bottom','fit_clearance']);
    assert.equal(c.parameterKeys('keycap').slice(-4).join(),'text,text_size,text_depth,key_units');
    assert.throws(()=>c.validateEditParameters({...key,text:'Escape!'}),/글자 응답/);
    assert.throws(()=>c.validateEditParameters({...key,width:30}),/치수 응답/);
    assert.throws(()=>c.validateEditParameters({template:'name_tag',width:120,depth:80,height:35,wall:3,bottom:2,dividers:0,slots:5,cable_diameter:6,inset_diameter:52,inset_depth:2,fit_clearance:0.3,text:' ',text_size:12,text_depth:2,hole_diameter:4}),/글자 응답/);
  });
  console.log('State regression checks:',passed,'passed,',failed,'failed');process.exitCode=failed?1:0;
})();
