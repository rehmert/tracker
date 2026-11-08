document.addEventListener('DOMContentLoaded',()=>{
 const $=id=>document.getElementById(id), status=$('food-scan-status'),barcode=$('food-barcode');
 const fields=['energy','proteins','carbohydrates','fat','fiber','sugars','saturated-fat','sodium','potassium','calcium','iron','magnesium','vitamin-c','vitamin-d','vitamin-b12','cholesterol'];
 function populate(data){
  for(const k of fields){
   const input=$('food-nutrient-'+k);
   if(input)input.value='';
  }
  if(data.name)$('food-name').value=data.name;if(data.serving_description)$('food-serving').value=data.serving_description;
  for(const [k,v] of Object.entries(data.nutrients||{})){let e=$('food-nutrient-'+k);if(e&&v!==null&&Number.isFinite(Number(v)))e.value=v;}
  if(data.source)$('food-source').value=data.source;
  $('food-entry-form')?.dispatchEvent(new Event('food:nutrition-loaded'));
 }
 async function lookup(){let b=barcode.value.trim();if(!/^\d{8,14}$/.test(b)){status.textContent='Enter an 8–14 digit barcode.';return;}
  status.textContent='Looking up barcode…';try{const r=await fetch('/food/barcode/'+encodeURIComponent(b));const data=await r.json();if(!r.ok)throw Error(data.detail||'Lookup failed');
    populate(data);status.textContent='Found '+data.name+' ('+data.basis+'). Verify the label before saving.';}
  catch(e){status.textContent=e.message+' You can enter values manually or photograph the nutrition label.';}}
 $('food-lookup').addEventListener('click',lookup);
 const video=$('food-camera');let stream=null,active=false,detector=null;
 function stop(){active=false;if(stream)stream.getTracks().forEach(t=>t.stop());stream=null;video.hidden=true;$('food-stop-scan').hidden=true;}
 $('food-stop-scan').addEventListener('click',stop);
 async function recognize(file){if(!('BarcodeDetector' in window)){status.textContent='Barcode recognition not supported by this browser; enter the numbers manually.';return;}
  try{const bitmap=await createImageBitmap(file),reader=new BarcodeDetector({formats:['ean_13','ean_8','upc_a','upc_e']});const found=await reader.detect(bitmap);bitmap.close();
    if(found.length){barcode.value=found[0].rawValue;await lookup()}else status.textContent='No barcode detected; retake with even lighting or type the code.';}
  catch(e){status.textContent='Photo barcode detection failed. Try manual lookup.';}}
 $('food-barcode-photo').addEventListener('change',e=>{if(e.target.files[0])recognize(e.target.files[0])});
 $('food-start-scan').addEventListener('click',async()=>{
  if(!navigator.mediaDevices?.getUserMedia||!('BarcodeDetector' in window)){status.textContent='Live scanning is not available in this browser or without HTTPS. Use barcode photo or manual entry.';return;}
  try{detector=new BarcodeDetector({formats:['ean_13','ean_8','upc_a','upc_e']});
  stream=await navigator.mediaDevices.getUserMedia({video:{facingMode:{ideal:'environment'}}});video.srcObject=stream;video.hidden=false;$('food-stop-scan').hidden=false;await video.play();active=true;
  status.textContent='Point rear camera at barcode.';while(active){if(video.readyState>=2){const matches=await detector.detect(video);if(matches.length){barcode.value=matches[0].rawValue;stop();await lookup();break;}}
    await new Promise(r=>setTimeout(r,300));}}
  catch(e){status.textContent='Camera scan unavailable. Use the photo or manual barcode field.';stop();}
 });
 $('food-label-photo').addEventListener('change',async e=>{
  const file=e.target.files[0];if(!file)return;status.textContent='Reading nutrition label…';const form=new FormData();form.append('photo',file);
  try{const r=await fetch('/food/photo',{method:'POST',body:form});const data=await r.json();if(!r.ok)throw Error(data.error||data.detail||'OCR failed');
    populate(data);$('food-source').value='Nutrition label photo (OCR reviewed)';
    status.textContent='Photo analyzed. VERIFY the serving basis, all extracted numbers and units before saving; OCR can be wrong.';
    $('food-review-warning').textContent=data.warning; }
  catch(err){status.textContent=err.message+' Please enter the nutrition label manually.';}
 });
});