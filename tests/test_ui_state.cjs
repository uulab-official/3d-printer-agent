// Controller state checks using DOM doubles; this is not a browser/layout test.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync('print_agent/static/app.js', 'utf8');
const names = ['renderRetainedOutcomes','detachPreviousStorage','updateConnectionActions','renderConnection','connectionFailed','modelHasUnsavedChanges','slicerHasUnsavedChanges','outcomeHasUnsavedChanges','hasPendingWork','replacementSignature','cancelModelReplacement','requestModelReplacement','confirmModelReplacement','performModelReplacement','updateHistoryControls','openHistoryJob','renderHistory','errorMessage','api','node','friendly','showNotice','hideNotice','setBadge','withBusy','withWorkflow','updateWorkflowControls','invalidateCurrentJob','applyDraft','metric','localDownload','renderDownloads','renderJob','updateSliceControls','renderSliceResult','resetSlicePreparation','parseObject','runSlice','dateTime','loadHistory','cancelSlicerReads','renderSlicerFiles','slicerBundle','checkSlicerBundleSize','readSlicerFiles','changeSlicerPlate','assembleSlicerBundle','cancelSlicerAssembly','manualSlicerChanged','readSlicerBundle','renderSlicerEnvironment','probeSlicer','discoverySignature','discoveryQuery','discoveryFiltersChanged','setDiscoveryCatalog','renderDiscovery','renderProjectDetail','renderProjectSource','updateDiscoveryControls','browseProject','draftHasChanges','requestProjectApplication','confirmProjectApplication','cancelProjectApplication','applyProject','detachProjectSource','recommendProjects','modelDraftSignature','preparePlan','generateModel','bootstrap'];
const studioNames = ['studioSourceIdentity','studioModelSignature','studioContext','studioContextCurrent','studioSourceCurrent','studioHasUnsavedChanges','invalidateStudioRequests','renderStudioSource','renderStudioProject','importStudioProject','cancelStudioCandidate','applyStudioCandidate','revalidateStudioProject','runStudioSlice'];
names.push(...studioNames);
class Element {
  constructor() { this.children=[]; this.dataset={}; this.disabled=false; this.hidden=false; this.value=''; this._text=''; this.attributes={}; this.listeners={}; this.classList={add(){},remove(){},toggle(){}}; }
  set textContent(value) { this._text=String(value); this.children=[]; }
  get textContent() { return this._text + this.children.map(x=>x.textContent || '').join(' '); }
  append(...nodes) { this.children.push(...nodes); }
  replaceChildren(...nodes) { this._text=''; this.children=nodes; }
  setAttribute(name,value) { this.attributes[name]=value; }
  removeAttribute(name) { delete this.attributes[name]; }
  querySelector() { return new Element(); }
  addEventListener(name,callback) { this.listeners[name]=callback; }
  focus() {}
  checkValidity() { return !this.validity || this.validity.valid !== false; }
  reportValidity() { return this.checkValidity(); }
}
function fixture() {
  const ids = new Map();
  const $ = id => { if (!ids.has(id)) ids.set(id,new Element()); return ids.get(id); };
  const context = {
    $, console, URL, Intl, Number, Math, JSON, Object, Array, String, Error, Blob, TextEncoder, Uint8Array, btoa,
    state:{offersRevision:0,offersPending:false,retainedOutcomeDrafts:[],connectionState:'connected',connectionEpoch:0,bootstrapPending:false,storage:null,modelCleanSignature:null,modelReplacement:null,modelTransitionRequest:0,slicerSavedText:'',historyItems:[],historyLoaded:false,historyRequest:0,historyPending:false,historyCursor:null,token:'test-token',templates:[{id:'tray',defaults:{width:120},editable_fields:['width'],description:'Tray'},{id:'cable_comb',defaults:{width:80},editable_fields:['width'],description:'Cable'}],template:'tray',parameters:{width:120},environment:{available:true},job:null,slicePrepared:false,workflowBusy:false,slicerFiles:{machine:null,process:null,filaments:[]},slicerStaged:false,slicerContext:0,slicerRequests:{},slicerPending:{},discovery:null,discoveryPurpose:'all',discoveryMatches:[],discoveryBrowsed:null,discoveryPending:false,discoveryRequest:0,discoveryEpoch:0,discoveryRevision:0,projectSource:null,projectReplacement:null,bootstrapRequest:0},
    fields:{width:{label:'width',min:10,max:500,step:0.1}},fieldNames:{},numberFormat:new Intl.NumberFormat('en'),
    document:{createElement:()=>new Element(),querySelectorAll:()=>[]},window:{location:{origin:'http://localhost'},setTimeout,clearTimeout,confirm:()=>true},
    viewer:{setMesh(){},clear(){this.mesh=null;},mesh:'old'},workspaceDirty(){return false;},renderTemplates(){},toast(){},updateWorkspaceStatus(){},loadWorkspaces:async()=>{},
  };
  $('parameter-width').value='120';$('outcome-result').value='not_tested';$('offer-currency').value='KRW';
  vm.createContext(context);
  for (const name of names) {
    const match = new RegExp('^  (?:async )?function '+name+'\\(', 'm').exec(source);
    if (!match) throw new Error('Missing controller function: '+name);
    const tail=source.slice(match.index), end=/\n  \}(?=\n|$)/.exec(tail);
    vm.runInContext(tail.slice(0,end.index+4),context);
  }
  // Load actual offer event wiring as well as its controller functions.
  vm.runInContext(source.slice(source.indexOf('  function renderOfferRows()'),source.indexOf('  function dateTime(')),context);
  Object.assign(context.state,{studioRequest:0,studioRevision:0,studioPending:false,studioCandidate:null,studioCandidateEpoch:null,studioCandidateStorage:null,studioApplied:null,studioAppliedEpoch:null,studioAppliedStorage:null,studioRecorded:null,studioSlicePrepared:false,studioPreparedSignature:null,studioSavedIdentity:null});
  return context;
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
(async()=>{
  let failed=0,passed=0;
  async function check(name,test) {
    let deadline;
    try { await Promise.race([Promise.resolve().then(test),new Promise((_,reject)=>{deadline=setTimeout(()=>reject(new Error('Controller check timed out')),5000);})]); passed++; console.log('PASS',name); }
    catch(error) { failed++; console.log('FAIL',name,error.message); }
    finally { clearTimeout(deadline); }
  }
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
    for(const change of [c=>{c.state.job={...job(),id:'new-job'};},c=>{studioApplied(c,studioInspection('b'.repeat(32)));},c=>{c.state.connectionEpoch++;}])for(const fail of [false,true]){
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
    const changes=[c=>{c.state.job={...job(),id:'new-job'};},c=>{studioApplied(c,studioInspection('b'.repeat(32)));},c=>{c.state.connectionEpoch++;},c=>{c.$('slicer-json').value=' { "newer": true }\n';}];
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
    assert.equal(c.state.token,'new-token');assert.equal(c.state.connectionState,'connected');assert.equal(c.$('parameter-width').value,'');assert.equal(c.$('parameter-width').validity.badInput,true);assert.equal(c.$('request-text').value,'new request');assert.equal(c.$('profile-json').value,'{ unfinished');assert.equal(c.$('setup-printer-model').value,'keep printer');assert.equal(c.$('workspace-title').value,'keep work');assert.equal(c.state.projectSource,source);assert.equal(c.state.job,saved);assert.equal(c.$('download-links').textContent,downloads);assert.equal(c.state.guidedEdits.nozzle_temperature.value,'-');assert.equal(c.$('storage-path').textContent,'/Users/test/한글 폴더');assert.match(c.$('storage-recovery').textContent,/중단 처리 2개/);assert.deepEqual(paths,['/api/bootstrap','/api/profile-workspaces']);
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
    c.state.projectSource=project();c.$('request-text').value='request';c.api=async()=>({status:'ready',parameters:{template:'tray',width:100}});await c.preparePlan();assert.equal(c.state.projectSource,null);assert.equal(c.state.parameters.width,100);
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
    done({session_token:'new',templates:c.state.templates,discovery:{purposes:[],projects:[project('new')]},environment:{}});await pending;
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
  console.log('State regression checks:',passed,'passed,',failed,'failed');process.exitCode=failed?1:0;
})();
