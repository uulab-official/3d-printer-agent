// Controller state checks using DOM doubles; this is not a browser/layout test.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync('print_agent/static/app.js', 'utf8');
const names = ['node','friendly','showNotice','hideNotice','setBadge','withBusy','withWorkflow','updateWorkflowControls','invalidateCurrentJob','applyDraft','metric','localDownload','renderDownloads','renderJob','updateSliceControls','renderSliceResult','resetSlicePreparation','parseObject','runSlice','dateTime','loadHistory','cancelSlicerReads','renderSlicerFiles','slicerBundle','checkSlicerBundleSize','readSlicerFiles','changeSlicerPlate','assembleSlicerBundle','cancelSlicerAssembly','manualSlicerChanged','readSlicerBundle','renderSlicerEnvironment','probeSlicer'];
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
}
function fixture() {
  const ids = new Map();
  const $ = id => { if (!ids.has(id)) ids.set(id,new Element()); return ids.get(id); };
  const context = {
    $, console, URL, Intl, Number, Math, JSON, Object, Array, String, Error, Blob, TextEncoder, Uint8Array, btoa,
    state:{token:'test-token',templates:[{id:'tray',defaults:{width:120},editable_fields:['width'],description:'Tray'},{id:'cable_comb',defaults:{width:80},editable_fields:['width'],description:'Cable'}],template:'tray',parameters:{width:120},environment:{available:true},job:null,slicePrepared:false,workflowBusy:false,slicerFiles:{machine:null,process:null,filaments:[]},slicerStaged:false,slicerContext:0,slicerRequests:{},slicerPending:{}},
    fields:{width:{label:'width',min:10,max:500,step:0.1}},fieldNames:{},numberFormat:new Intl.NumberFormat('en'),
    document:{createElement:()=>new Element(),querySelectorAll:()=>[]},window:{location:{origin:'http://localhost'},setTimeout,clearTimeout,confirm:()=>true},
    viewer:{setMesh(){},clear(){this.mesh=null;},mesh:'old'},renderTemplates(){},toast(){},
  };
  vm.createContext(context);
  for (const name of names) {
    const match = new RegExp('^  (?:async )?function '+name+'\\(', 'm').exec(source);
    if (!match) throw new Error('Missing controller function: '+name);
    const tail=source.slice(match.index), end=/\n  \}(?=\n|$)/.exec(tail);
    vm.runInContext(tail.slice(0,end.index+4),context);
  }
  return context;
}
function profileFixture() {
  const context=fixture();
  Object.assign(context.state,{profileDocuments:[],profileTarget:0,profileRevision:0,profileImport:0,profileReport:null,profileDownloadUrl:null,guidedEdits:{},guidedSources:{},workspaceId:null,workspaceRevision:null,workspaceSavedSignature:null,workspaceEpoch:0,workspaceEdits:0,workspaceListRequest:0,workspaceBusy:false,workspaces:[]});
  for(const name of ['profileName','sameJson','profileDocument','invalidateProfile','renderProfileLibrary','renderProfileOrigin','beginProfileImport','currentProfileImport','appendProfileDocuments','profileImportSummary','importProfileFiles','importProfileArchive','selectProfileTarget','clearProfileLibrary','reviewProfile','profileSetupFields','captureProfileSnapshot','workspaceSignature','workspaceDirty','markWorkspaceChanged','updateWorkspaceStatus','loadWorkspaces','saveWorkspace','restoreWorkspace','openWorkspace','newWorkspace','deleteWorkspace','guidedFieldDefinitions','numericSetting','profileSettings','renderGuidedEditor','applyGuidedEdits','removeGuidedOverride','adoptProfileText','removeProfileDocument','restoreProfileOriginal']) {
    const match=new RegExp('^  (?:async )?function '+name+'\\(', 'm').exec(source);
    if(!match)throw new Error('Missing profile controller function: '+name);
    const tail=source.slice(match.index),end=/\n  \}(?=\n|$)/.exec(tail);
    vm.runInContext(tail.slice(0,end.index+4),context);
  }
  context.$('setup-identity').value='unknown';
  context.state.workspaceSavedSignature=context.workspaceSignature();
  return context;
}
const plain = value => JSON.parse(JSON.stringify(value));
const workspaceRecord = (snapshot, overrides={}) => ({id:'a'.repeat(32),title:'Saved filament',revision:1,created_at:'2026-11-13T00:00:00Z',updated_at:'2026-11-13T00:00:00Z',document_count:snapshot.documents.length,snapshot,...overrides});
const archiveOrigin = () => ({type:'bambu_preset_archive',archive_name:'synthetic.bbsflmt',archive_sha256:'a'.repeat(64),member_path:'Example/Child.json',member_sha256:'b'.repeat(64)});
const archiveResult = () => {
  const draft_text=' {\n "name": "Child", "filament_settings_id": ["Child"], "inherits": "Missing parent", "nozzle_temperature": ["215"]\n}\n';
  return {schema_version:1,archive:{filename:'synthetic.bbsflmt',sha256:'a'.repeat(64),format:'bbsflmt'},documents:[{filename:'Example/Child.json',profile:JSON.parse(draft_text),draft_text,origin:archiveOrigin()}],ignored_members:[{path:'printer/Printer.json',reason:'프린터 설정'}],warnings:['사용자가 제공한 파일입니다.']};
};
const archiveInput = () => ({files:[{name:'synthetic.bbsflmt',size:3,arrayBuffer:async()=>new Uint8Array([80,75,3]).buffer}],value:'synthetic.bbsflmt'});
const job = () => ({
  id:'job-a',title:'Tray',artifacts:{stl:'/api/jobs/job-a/files/stl',sliced_three_mf:'/api/jobs/job-a/files/sliced_three_mf'},
  result:{template:'tray',parameters:{width:120},dimensions_mm:{x:120,y:80,z:35},volume_mm3:45072,geometry_status:'validated',checks:[],warnings:[],mesh:{vertices:[],faces:[]}},
  latest_slice:null,user_outcome:null,
});
(async()=>{
  let failed=0,passed=0;
  async function check(name,test) {
    try { await test(); passed++; console.log('PASS',name); }
    catch(error) { failed++; console.log('FAIL',name,error.message); }
  }
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
    c.api=async path=>path==='/api/jobs'?{jobs:[failedJob]}:failedJob;
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
  console.log('State regression checks:',passed,'passed,',failed,'failed');process.exitCode=failed?1:0;
})();
