'use strict';
/* Presentation only: saved titles, notes, dates and quantities stay untouched. */
window.calendarPresentation=(()=>{
 function time(value,language='zh'){
  if(language!=='zh'||!/^\d{2}:\d{2}$/.test(value||''))return value||'';
  const [hour,minute]=value.split(':').map(Number);if(hour>23||minute>59)return value;
  const period=hour<6?'凌晨':hour<12?'上午':hour===12?'中午':hour<18?'下午':'晚上';
  return period+' '+(hour%12||12)+':'+String(minute).padStart(2,'0');
 }
 function task(row,language='zh'){
  let title=row.title,note=row.note||'',timeLabel=time(row.time,language);
  if(language==='zh'){
   title=({'巡豬':'巡視豬隻','查看污水':'檢查污水','驗水':'水質檢驗'})[title]||title;
   let match;
   if((match=/^(南投|新北|嘉義)出豬(\d+)頭$/.exec(title)))title='出豬：'+match[1]+' '+match[2]+' 頭';
   else if((match=/^([\d、，, ]+)棟打疫苗$/.exec(title)))title='施打疫苗（'+match[1]+'棟）';
   else if((match=/^([\d、，, ]+)棟秤重$/.exec(title)))title='豬隻秤重（'+match[1]+'棟）';
   if(!timeLabel&&['上午','下午','中午','晚上','凌晨'].includes(note)){timeLabel=note;note='';}
  }
  return {title,note,timeLabel};
 }
 function sharedDaily(days,accept=()=>true){
  const remaining=days.map(day=>day.tasks.slice()),daily=[],signature=row=>JSON.stringify([row.title,row.time||'',row.note||'']);
  if(days.length!==7)return {daily,remaining};
  for(const row of days[0].tasks){
   if(row.mode!=='weekly'||daily.length>=6)continue;
   const key=signature(row),indices=remaining.map(tasks=>tasks.findIndex(t=>t.mode==='weekly'&&signature(t)===key));
   if(indices.every(i=>i>=0)&&accept([...daily,row])){daily.push(row);indices.forEach((index,i)=>remaining[i].splice(index,1));}
  }
  return {daily,remaining};
 }
 function groups(rows,language='zh'){
  const result=[];for(const row of rows){const key=task(row,language).timeLabel;let group=result.find(g=>g.time===key);if(!group){group={time:key,tasks:[]};result.push(group);}group.tasks.push(row);}return result;
 }
 return {time,task,sharedDaily,groups};
})();
