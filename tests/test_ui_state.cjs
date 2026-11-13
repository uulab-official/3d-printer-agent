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
    document:{createElement:()=>new Element(),querySelectorAll:()=>[]},window:{location:{origin:'http://localhost'},setTimeout,clearTimeout},
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
  Object.assign(context.state,{profileDocuments:[],profileTarget:0,profileRevision:0,profileImport:0,profileReport:null,profileDownloadUrl:null});
  for(const name of ['profileName','invalidateProfile','renderProfileLibrary','importProfileFiles','selectProfileTarget','clearProfileLibrary','reviewProfile']) {
    const match=new RegExp('^  (?:async )?function '+name+'\\(', 'm').exec(source);
    if(!match)throw new Error('Missing profile controller function: '+name);
    const tail=source.slice(match.index),end=/\n  \}(?=\n|$)/.exec(tail);
    vm.runInContext(tail.slice(0,end.index+4),context);
  }
  return context;
}
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
  console.log('State regression checks:',passed,'passed,',failed,'failed');process.exitCode=failed?1:0;
})();
