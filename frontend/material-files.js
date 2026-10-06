/* Keep upload bytes independent of the browser's native file-input lifetime. */
(function(root){
  async function snapshotFile(source){
    const name=source?.name||'未命名材料';
    let bytes;
    try{bytes=await source.arrayBuffer();}catch(error){throw new Error('无法读取“'+name+'”，请重新选择这份材料。');}
    if(!bytes.byteLength||bytes.byteLength!==source.size)throw new Error('“'+name+'”的文件内容为空或不完整，请重新选择这份材料；已有结果仍保留。');
    return new File([bytes],name,{type:source.type,lastModified:source.lastModified||Date.now()});
  }
  async function captureFiles(files){return Promise.all(Array.from(files,snapshotFile));}
  async function prepareItems(items){
    const copies=await captureFiles(items.map(i=>i.file));
    copies.forEach((file,index)=>{items[index].file=file;});
  }
  const api={snapshotFile,captureFiles,prepareItems};root.PvMaterialFiles=api;
  if(typeof module==='object'&&module.exports)module.exports=api;
})(globalThis);
