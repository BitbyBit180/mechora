const evaluationLoading=document.querySelector('#evaluation-loading');
const evaluationError=document.querySelector('#evaluation-error');
const evaluationResults=document.querySelector('#evaluation-results');
const percent=value=>`${(Number(value)*100).toFixed(1)}%`;
async function loadEvaluation(){
  try{
    const response=await fetch('/api/inspections/evaluation/');
    const data=await response.json();
    if(!response.ok) throw new Error(data.detail||'Evaluation could not be loaded.');
    const matrix=data.confusion_matrix;
    document.querySelector('#eval-total').textContent=`${data.processed_samples} / ${data.total_samples}`;
    document.querySelector('#eval-recall').textContent=percent(data.defect_recall);
    document.querySelector('#eval-accuracy').textContent=percent(data.accuracy);
    document.querySelector('#eval-failed').textContent=data.failed_predictions;
    document.querySelector('#cm-tn').textContent=matrix.actual_normal.normal;
    document.querySelector('#cm-fp').textContent=matrix.actual_normal.defective;
    document.querySelector('#cm-fn').textContent=matrix.actual_defective.normal;
    document.querySelector('#cm-tp').textContent=matrix.actual_defective.defective;
    document.querySelector('#evaluation-results-body').innerHTML=(data.results||[]).map((item,index)=>{const correct=item.actual===item.predicted;return `<tr><td>${index+1}</td><td><code>${item.image_id}</code></td><td>${item.actual}</td><td>${item.predicted}</td><td>${percent(item.confidence)}</td><td><span class="evaluation-result ${correct?'evaluation-correct':'evaluation-incorrect'}">${correct?'Correct':'Incorrect'}</span></td></tr>`}).join('')||'<tr><td colspan="6" class="empty-cell">No sample results available.</td></tr>';
    document.querySelector('#eval-summary').textContent=`The classifier processed ${data.processed_samples} of ${data.total_samples} labeled samples with ${data.failed_predictions} failed predictions.`;
    document.querySelector('#eval-limitations').innerHTML=(data.limitations||[]).map(item=>`<li>${item}</li>`).join('');
    evaluationLoading.hidden=true;evaluationResults.hidden=false;
  }catch(error){evaluationLoading.hidden=true;evaluationError.textContent=error.message;evaluationError.hidden=false;}
}
loadEvaluation();
