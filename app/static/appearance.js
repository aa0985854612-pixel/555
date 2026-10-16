'use strict';
/* Device-local reading preferences. Changing size never reloads or writes farm data. */
(() => {
 const sizes=['small','medium','large'];
 let selected='medium';
 try { const saved=localStorage.getItem('pig-text-size');if(sizes.includes(saved))selected=saved; } catch(e) {}
 document.documentElement.dataset.textSize=selected;
 Object.assign(words,{
  app:['嘉得肉豬紀錄','Gia Đắc'],coverArtAlt:['嘉得豬場Q版休息豬群插畫','Minh họa đàn heo dễ thương đang nghỉ tại trại Gia Đắc'],textSize:['字體大小','Cỡ chữ'],fontSmall:['小','Nhỏ'],fontMedium:['中','Vừa'],fontLarge:['大','Lớn'],fontDevice:['自動記住這台裝置的選擇','Tự nhớ lựa chọn trên thiết bị này'],sourceDisclosure:['資料來源與計算說明','Nguồn dữ liệu và cách tính']
 });
 const control=document.querySelector('#font-control'),buttons=Array.from(control.querySelectorAll('[data-text-size]'));
 function labels(){
  document.querySelector('.cover-art')?.setAttribute('alt',t('coverArtAlt'));
  document.title=lang==='vi'?'Nhật ký heo thịt Gia Đắc':'嘉得肉豬紀錄';
  control.querySelector('summary').setAttribute('aria-label',t('textSize'));
  control.querySelector('[role=group]').setAttribute('aria-label',t('textSize'));
  buttons.forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.textSize===selected)));
 }
 function apply(size,persist=true){
  if(!sizes.includes(size))return;
  const anchor=document.activeElement?.closest('form')||document.querySelector('.page:not([hidden]) .card')||document.querySelector('#login-form');
  const top=anchor?.getBoundingClientRect().top;
  selected=size;document.documentElement.dataset.textSize=size;labels();
  if(persist){try{localStorage.setItem('pig-text-size',size);}catch(e){}}
  if(top!=null&&top<0)window.scrollBy(0,anchor.getBoundingClientRect().top-top);
 }
 buttons.forEach(b=>b.addEventListener('click',()=>apply(b.dataset.textSize)));
 document.addEventListener('click',e=>{if(!control.contains(e.target))control.open=false;});
 control.addEventListener('keydown',e=>{if(e.key==='Escape'){control.open=false;control.querySelector('summary').focus();}});
 window.addEventListener('storage',e=>{if(e.key==='pig-text-size')apply(sizes.includes(e.newValue)?e.newValue:'medium',false);});
 const previousTranslate=translate;
 translate=()=>{previousTranslate();labels();};
 labels();
})();
