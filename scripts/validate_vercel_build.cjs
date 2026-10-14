// Local build with the official @vercel/python builder; no Vercel API credentials.
// Install vercel@64.1.0 and @vercel/python@25.1.0 in an isolated prefix; set NODE_PATH.
const fs=require('node:fs');
const path=require('node:path');
const os=require('node:os');
const {build}=require('@vercel/python');
const {FileFsRef}=require('@vercel/build-utils');
const root=path.resolve(__dirname,'..');
const config=JSON.parse(fs.readFileSync(path.join(root,'vercel.json'),'utf8'));
(async()=>{
 const workPath=fs.mkdtempSync(path.join(os.tmpdir(),'pigledger-vercel-build-'));
 const files={};
 function add(rel){
  const file=path.join(root,rel);
  if(fs.statSync(file).isDirectory()){
   for(const name of fs.readdirSync(file))if(name!=='__pycache__')add(path.join(rel,name));
  } else if(!rel.endsWith('.pyc'))files[rel]=new FileFsRef({fsPath:file});
 }
 for(const rel of ['api','app','pyproject.toml','vercel.json'])add(rel);
 const result=await build({workPath,files,entrypoint:'api/index.py',config:{...config.functions['api/index.py'],framework:null},meta:{isDev:false}});
 const output=result.result?.output||result.output;
 const lambda=output.type==='Lambda'?output:Object.values(output).find(o=>o.type==='Lambda');
 if(!lambda?.files?.['api/index.py']||!lambda.files['app/static/index.html'])throw Error('Missing App entry or frontend');
 const names=Object.keys(lambda.files);
 if(names.some(n=>n.startsWith('.data/')||n.startsWith('release/')||n.endsWith('.xlsx')))throw Error('Private data or release package in function');
 if(lambda.runtime!=='python3.12')throw Error('Unexpected Python runtime');
 const report={type:'official Vercel Python local build; not production deployment',runtime:lambda.runtime,handler:lambda.handler,files:names.length,privateDataExcluded:true};
 fs.mkdirSync(path.join(root,'artifacts'),{recursive:true});
 fs.writeFileSync(path.join(root,'artifacts/vercel-build-results.json'),JSON.stringify(report,null,2));
 console.log(JSON.stringify(report));
})().catch(e=>{console.error(e.message);process.exitCode=1});
