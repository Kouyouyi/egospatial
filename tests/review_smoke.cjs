const fs=require("node:fs"),vm=require("node:vm"),assert=require("node:assert/strict"),path=require("node:path");
const root=process.argv[2] || (()=>{throw new Error("Pass review directory")})(),html=fs.readFileSync(root+"/review.html","utf8"),I=JSON.parse(fs.readFileSync(root+"/index.json","utf8"));
const elements={};for(const m of html.matchAll(/\bid="([^"]+)"/g))elements[m[1]]={textContent:"",innerHTML:"",value:"",handlers:{},addEventListener(k,f){this.handlers[k]=f},querySelectorAll(){return []},pause(){},play(){return Promise.resolve()},showModal(){this.open=true},close(){this.open=false}};
elements["initial-index"].textContent=JSON.stringify(I);let context;
const document={getElementById(id){assert(elements[id],id);return elements[id]},createElement(){return {remove(){}}},head:{appendChild(s){const target=path.join(root,s.src.split("?")[0]);assert(fs.existsSync(target),target);new vm.Script(fs.readFileSync(target,"utf8")).runInContext(context);if(s.onload)s.onload();}}};
const sandbox={document,window:{},console,setInterval(){},Date,Map,JSON,encodeURIComponent};context=vm.createContext(sandbox);
const script=html.slice(html.lastIndexOf("<script>")+8,html.lastIndexOf("</script>"));new vm.Script(script).runInContext(context);
assert.equal(I.total,I.samples.length);assert.equal(new Set(I.samples.map(x=>x.id)).size,I.total);assert.equal(I.label_vocabulary.length,31);
for(const item of I.samples.filter(x=>x.status==="completed")){
 sandbox.select(item.id);const c=JSON.parse(fs.readFileSync(root+"/"+item.detail_json,"utf8")),body=elements["detail-body"].innerHTML;
 assert.equal((body.match(/class="attachment /g)||[]).length,c.image_files.length);
 assert(body.includes("当前帧 · f"+c.current_frame));assert(body.includes("结束帧 · f"+c.after_frame));assert(body.includes("正确标签"));
 assert(body.includes(c.reference.action_labels[0].replace(/\+/g," + ")));assert(body.includes(c.output.answer.replace(/[&<>"']/g,ch=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[ch]))));
 assert.equal(c.request.image_source_frames.at(-1),c.current_frame);assert(!c.request.image_source_frames.includes(c.after_frame));
 assert(c.spatial_memory.every(m=>m.source_frame<c.request.image_source_frames[c.spatial_memory.length]));if(c.video.file)assert(fs.existsSync(root+"/"+c.video.file));for(const file of c.image_files)assert(fs.existsSync(root+"/"+file));
}
elements["result-filter"].value="wrong";sandbox.changeFilters();assert.equal(sandbox.filtered().length,I.samples.filter(x=>x.status==="completed"&&!x.correct).length);
elements["kind-filter"].value="navigation";sandbox.changeFilters();assert(sandbox.filtered().every(x=>x.kind==="navigation"&&!x.correct));
elements["result-filter"].value="";elements["kind-filter"].value="";sandbox.changeFilters();
const pending=I.samples.find(x=>x.status!=="completed");if(pending){sandbox.select(pending.id);assert(elements["detail-body"].innerHTML.includes("没有真实输入输出"));}
console.log("PASS latest-only unique index; "+I.completed+" completed cases loaded from local scripts; all actual images/outputs/reference labels/videos; filters and pending-state semantics.");
