// Render production presentation components with explicitly synthetic data; no auth or API fixture route.
import { createServer } from 'vite';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router-dom';
import { readFileSync, readdirSync, mkdirSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
const root=fileURLToPath(new URL('../', import.meta.url));
const output=path.join(root,'.local/previews/workspace');mkdirSync(output,{recursive:true});
const assets=path.join(root,'apps/web/dist/assets');
const css=readdirSync(assets).filter(name=>name.endsWith('.css')).map(name=>readFileSync(path.join(assets,name),'utf8')).join('\n');
const server=await createServer({root:path.join(root,'apps/web'),configFile:path.join(root,'apps/web/vite.config.ts'),server:{middlewareMode:true},appType:'custom'});
try {
 const {WorkspaceFrame,OrganizationDirectoryView,OrganizationWorkspaceView}=await server.ssrLoadModule('/src/auth/workspace-views.tsx');
 const {AuditTrail}=await server.ssrLoadModule('/src/execution/audit-trail.tsx');
 const organizations=[{id:'preview-alpha',name:'Acme Operations',slug:'acme-operations',status:'ACTIVE',role:'OWNER'},{id:'preview-beta',name:'Northstar Studio',slug:'northstar-studio',status:'ACTIVE',role:'ADMIN'},{id:'preview-gamma',name:'Fieldwork Labs',slug:'fieldwork-labs',status:'ACTIVE',role:'MEMBER'}];
 const entries=[['directory',React.createElement(OrganizationDirectoryView,{organizations}),'Organization directory',null],['overview',React.createElement(OrganizationWorkspaceView,{organization:organizations[0],workspaces:[{id:'preview-workspace',name:'Default workspace',status:'ACTIVE'}],loading:false}),'Command Center','/app/organizations/preview-alpha'],['settings',React.createElement(OrganizationWorkspaceView,{organization:organizations[0],workspaces:[{id:'preview-workspace',name:'Default workspace',status:'ACTIVE'}],loading:false,settings:true}),'Organization settings','/app/organizations/preview-alpha']];
 entries.push(['audit',React.createElement(AuditTrail,{events:[{id:'preview-completed',action:'chat.completed',resource_id:'preview-conversation',created_at:'2026-11-06T07:00:00Z'},{id:'preview-retried',action:'demo.chat_requeued',resource_id:'preview-conversation',created_at:'2026-11-06T06:59:00Z'},{id:'preview-failed',action:'chat.failed',resource_id:'preview-conversation',created_at:'2026-11-05T07:00:00Z'}]}),'Audit trail','/app/organizations/preview-alpha']);
 for (const [name,content,title,routeRoot] of entries) {
  const location=name==='directory'?'/app':name==='settings'?`${routeRoot}/settings`:name==='audit'?`${routeRoot}/audit`:routeRoot;
  const element=React.createElement(MemoryRouter,{initialEntries:[location]},React.createElement(WorkspaceFrame,{title,root:routeRoot,organizations,dark:false,toggle:()=>{},account:React.createElement('span',{style:{fontSize:'11px',color:'#647581'}},'Design preview · synthetic data')},content));
  writeFileSync(path.join(output,`${name}.html`),`<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Orqentra component preview — synthetic data</title><style>${css}</style></head><body>${renderToStaticMarkup(element)}</body></html>`);
 }
 console.log('Generated labeled workspace presentation previews in .local/previews/workspace.');
}finally{await server.close();}
