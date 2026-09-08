import fs from 'node:fs/promises';
import { Workbook, SpreadsheetFile } from '@oai/artifact-tool';
const {tables,schemas}=JSON.parse(await fs.readFile('outputs/backend/seed.json','utf8'));
const wb=Workbook.create();
for (const [name,headers] of Object.entries(schemas)) {
  const sh=wb.worksheets.add(name);
  const values=[headers,...tables[name].map(r=>headers.map(k=>r[k]??null))];
  sh.getRangeByIndexes(0,0,values.length,headers.length).values=values;
  sh.showGridLines=false;
  const body=sh.getRangeByIndexes(0,0,Math.max(values.length,2),headers.length);
  body.format.font={name:'Arial',size:10,color:'#172B4D'};
  body.format.columnWidth=23;
  body.format.rowHeight=26;
  const header=sh.getRangeByIndexes(0,0,1,headers.length);
  header.format.fill='#EEEEEE'; header.format.font={name:'Arial',size:10,bold:true,color:'#111111'};
  sh.freezePanes.freezeRows(1);
  if(name==='Definitions') {
    sh.getRange('B1:B289').format.columnWidth=62;
    sh.getRange('C1:C289').format.columnWidth=28;
    sh.getRange('F1:G289').format.columnWidth=50;
    sh.getRange('M1:M289').format.columnWidth=100;
  }
}
wb.recalculate();
console.log((await wb.inspect({kind:'table',range:'Definitions!A1:F5',tableMaxRows:5,tableMaxCols:6})).ndjson);
for(const name of Object.keys(schemas)) {
 const img=await wb.render({sheetName:name,range:`A1:F${name==='Definitions'?8:3}`,scale:1,format:'png'});
 await fs.writeFile(`outputs/backend/${name}.png`,new Uint8Array(await img.arrayBuffer()));
}
const out=await SpreadsheetFile.exportXlsx(wb);
await out.save('outputs/backend/HSE Backend.xlsx');
