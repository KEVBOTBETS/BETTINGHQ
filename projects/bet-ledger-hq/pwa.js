(()=>{'use strict';
  const button=document.querySelector('#install-app'),dialog=document.querySelector('#install-dialog'),update=document.querySelector('#app-update'),offline=document.querySelector('#offline-notice');
  let prompt=null,registration=null,acceptedUpdate=false;
  const standalone=()=>matchMedia('(display-mode: standalone)').matches||navigator.standalone===true;
  function connection(){offline.hidden=navigator.onLine!==false;button.hidden=standalone();}
  connection();window.addEventListener('online',connection);window.addEventListener('offline',connection);
  window.addEventListener('beforeinstallprompt',event=>{event.preventDefault();prompt=event;button.hidden=false;});
  window.addEventListener('appinstalled',()=>{prompt=null;button.hidden=true;});
  button.addEventListener('click',async()=>{if(prompt){await prompt.prompt();await prompt.userChoice;prompt=null;}else dialog.showModal();});
  document.querySelector('#close-install').onclick=()=>dialog.close();
  if('serviceWorker' in navigator){navigator.serviceWorker.register('sw.js',{scope:'./',updateViaCache:'none'}).then(reg=>{
    registration=reg;const waiting=()=>{if(reg.waiting)update.hidden=false;};waiting();reg.addEventListener('updatefound',()=>{reg.installing?.addEventListener('statechange',waiting);});
  }).catch(()=>{document.querySelector('#install-note').textContent='Home-screen shortcuts remain available. Offline support could not be prepared; retry online.';});
  navigator.serviceWorker.addEventListener('controllerchange',()=>{if(acceptedUpdate)location.reload();});
  update.onclick=()=>{if(registration?.waiting){acceptedUpdate=true;registration.waiting.postMessage({type:'ACTIVATE'});}};}
})();
