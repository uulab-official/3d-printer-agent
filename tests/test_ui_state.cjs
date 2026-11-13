// Controller state checks using DOM doubles; this is not a browser/layout test.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync('print_agent/static/app.js', 'utf8');
const names = ['node','friendly','showNotice','hideNotice','setBadge','withBusy','withWorkflow','updateWorkflowControls','invalidateCurrentJob','applyDraft','metric','localDownload','renderDownloads','renderJob','updateSliceControls','renderSliceResult','resetSlicePreparation','parseObject','runSlice','dateTime','loadHistory'];
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
    $, console, URL, Intl, Number, Math, JSON, Object, Array, String, Error, Blob, TextEncoder,
    state:{token:'test-token',templates:[{id:'tray',defaults:{width:120},editable_fields:['width'],description:'Tray'},{id:'cable_comb',defaults:{width:80},editable_fields:['width'],description:'Cable'}],template:'tray',parameters:{width:120},environment:{available:true},job:null,slicePrepared:false,workflowBusy:false},
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
  for(const name of ['profileName','sameJson','invalidateProfile','renderProfileLibrary','importProfileFiles','selectProfileTarget','clearProfileLibrary','reviewProfile','profileSetupFields','captureProfileSnapshot','workspaceSignature','workspaceDirty','markWorkspaceChanged','updateWorkspaceStatus','loadWorkspaces','saveWorkspace','restoreWorkspace','openWorkspace','newWorkspace','deleteWorkspace','guidedFieldDefinitions','numericSetting','profileSettings','renderGuidedEditor','applyGuidedEdits','removeGuidedOverride','adoptProfileText','removeProfileDocument','restoreProfileOriginal']) {
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
  await check('A failed file import preserves the previous editable document and invalidates success',async()=>{
    const c=profileFixture();const original={filename:'kept.json',profile:{name:'Kept'},draftText:'{"name":"Edited"}'};
    c.state.profileDocuments=[original];c.$('profile-json').value=original.draftText;
    await c.importProfileFiles({files:[{name:'bad.json',size:4,text:async()=>'{bad'}],value:'bad.json'});
    assert.equal(c.state.profileDocuments.length,1);assert.equal(c.state.profileDocuments[0],original);
    assert.equal(c.$('profile-json').value,original.draftText);assert.equal(c.$('profile-resolution').hidden,true);
    assert.equal(c.$('profile-feedback').hidden,false);assert.match(c.$('profile-feedback').textContent,/bad.json/);
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
