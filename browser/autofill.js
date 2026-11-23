(()=>{
 if(window!==window.top)return;
 if(window.__novaAutofillInstalled)return;window.__novaAutofillInstalled=true;
 const emit=message=>{try{if(window.chrome?.webview)chrome.webview.postMessage(message);else window.__novaBridge?.message(JSON.stringify(message));}catch{}};
 const userField=()=>document.querySelector('input[autocomplete="username"],input[type="email"],input[name="email"],input[name="identifier"],input[name="username"],input[name="login"],input[id="identifierId"],input[autocomplete="email"]');
 let previous='';
 const capture=()=>{
   const password=[...document.querySelectorAll('input[type="password"]')].find(x=>x.value);
   const username=userField()?.value||'';
   if(!username&&!password)return;
   const value=JSON.stringify({type:'nova-capture',username:username.slice(0,254),password:(password?.value||'').slice(0,4096)});
   if(value!==previous){previous=value;emit(JSON.parse(value));}
 };
 document.addEventListener('submit',capture,true);
 document.addEventListener('keydown',e=>{if(e.key==='Enter')capture();},true);
 document.addEventListener('click',e=>{const button=e.target.closest('button,input[type="submit"],[role="button"]');if(button&&(button.type==='submit'||/connexion|connecter|continuer|suivant|sign.?in|log.?in|next|continue|créer|create/i.test(button.textContent||'')))capture();},true);
 const set=(element,value)=>{if(!element||element.value)return;const setter=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value')?.set;setter?.call(element,value);element.dispatchEvent(new Event('input',{bubbles:true}));element.dispatchEvent(new Event('change',{bubbles:true}));};
 let filledPassword='',filledFor='';
 window.__novaFill=payload=>{
   if(payload.origin!==location.origin||location.protocol!=='https:')return;
   const username=userField();
   if(payload.username)set(username,payload.username);
   const password=document.querySelector('input[type="password"]');
   if(password&&filledPassword&&password.value===filledPassword&&filledFor!==username?.value){password.value='';filledPassword='';filledFor='';}
   if(payload.password&&password&&!password.value){set(password,payload.password);filledPassword=payload.password;filledFor=payload.username||username?.value||'';}
   if(username&&payload.emails?.length&&!username.getAttribute('list')){
     let list=document.getElementById('nova-emails');
     if(!list){list=document.createElement('datalist');list.id='nova-emails';document.documentElement.append(list);}
     list.replaceChildren(...payload.emails.map(value=>{const option=document.createElement('option');option.value=value;return option;}));username.setAttribute('list','nova-emails');
   }
 };
 let requestTimer;
 const request=()=>{clearTimeout(requestTimer);requestTimer=setTimeout(()=>emit({type:'nova-fill-request',username:userField()?.value||''}),80);};
 document.addEventListener('focusin',e=>{if(e.target.matches('input'))request();},true);
 document.addEventListener('change',e=>{if(e.target===userField())request();},true);
 document.addEventListener('input',e=>{if(e.target===userField())request();},true);
 const observer=new MutationObserver(records=>{if(records.some(r=>[...r.addedNodes].some(n=>n.nodeType===1&&(n.matches?.('input')||n.querySelector?.('input')))))request();});
 const watch=()=>{if(document.documentElement)observer.observe(document.documentElement,{childList:true,subtree:true});request();};
 if(document.documentElement)watch();else document.addEventListener('DOMContentLoaded',watch,{once:true});
})();
