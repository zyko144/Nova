(()=>{
 if(window.__novaProtectionInstalled)return;window.__novaProtectionInstalled=true;
 const send=message=>{try{if(window.chrome?.webview)chrome.webview.postMessage(message);else window.__novaBridge?.message(JSON.stringify(message));}catch{}};
 let dirty=false,lastGesture=0;
 document.addEventListener('input',e=>{if(e.isTrusted&&e.target.matches('input:not([type=search]),textarea,[contenteditable=true]')&&!dirty){dirty=true;send({type:'nova-dirty',value:true});}},true);
 document.addEventListener('submit',()=>{dirty=false;send({type:'nova-dirty',value:false});},true);
 document.addEventListener('pointerdown',()=>lastGesture=Date.now(),true);
 window.__novaEmergency=()=>{document.querySelectorAll('video,audio').forEach(e=>{e.pause();if(e.srcObject?.getTracks)e.srcObject.getTracks().forEach(t=>t.stop());});window.stop();};
 const media=navigator.mediaDevices;
 if(media?.getUserMedia){const original=media.getUserMedia.bind(media);media.getUserMedia=async c=>{
   const stream=await original(c);window.__novaStreams=window.__novaStreams||[];window.__novaStreams.push(stream);
   const report=()=>send({type:'nova-capture-state',audio:window.__novaStreams.some(s=>s.getAudioTracks().some(t=>t.readyState==='live')),video:window.__novaStreams.some(s=>s.getVideoTracks().some(t=>t.readyState==='live'))});
   stream.getTracks().forEach(t=>t.addEventListener('ended',report));report();return stream;
 };}
 window.__novaStopCapture=()=>{(window.__novaStreams||[]).forEach(s=>s.getTracks().forEach(t=>t.stop()));send({type:'nova-capture-state',audio:false,video:false});};
 window.__novaEmergency=()=>{window.__novaStopCapture();document.querySelectorAll('video,audio').forEach(e=>{e.pause();e.removeAttribute('autoplay');});window.stop();};
})();
