// Preview chrome only: the Kiosk product always lays out at exactly 1024 × 600.
const productCanvas=document.querySelector('#product-canvas');
function fitProductCanvas(){
  if(document.body.dataset.surface==='galaxy'){productCanvas.style.transform='';document.querySelector('#viewport-caption').textContent='';return;}
  const scale=Math.min(1,innerWidth/1024,innerHeight/600);
  productCanvas.style.transform=`scale(${scale})`;
  document.querySelector('#viewport-caption').textContent=`Kiosk · 1024 × 600 实机画布 · ${Math.round(scale*100)}% 显示`;
}
addEventListener('resize',fitProductCanvas);fitProductCanvas();
