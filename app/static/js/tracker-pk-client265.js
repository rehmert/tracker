(() => {
  'use strict';

  async function request(url,options={}){
    if(!url.startsWith('/pk/'))
      throw Error('PK API path required');

    const method=options.method||'GET';
    const headers={};

    if(options.body!==undefined)
      headers['Content-Type']='application/json';

    if(method!=='GET'){
      const csrf=window.trackerCsrfToken?.();

      if(csrf)
        headers['X-Tracker-CSRF']=csrf;
    }

    const response=await fetch(url,{
      method,
      headers,
      credentials:'same-origin',
      cache:'no-store',
      signal:options.signal,
      body:options.body===undefined
        ?undefined
        :JSON.stringify(options.body)
    });

    if(!response.ok){
      const message=(
        await response.text()
      ).slice(0,180);

      throw Error(
        'HTTP '+response.status+': '+message
      );
    }

    return response.json();
  }

  window.trackerPkClient265=Object.freeze({
    request
  });
})();
