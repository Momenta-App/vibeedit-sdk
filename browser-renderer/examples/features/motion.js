const gl=document.querySelector('#gl').getContext('webgl2');
if(!gl)throw new Error('WebGL2 unavailable');
const orb=document.querySelector('.orb');
orb.animate([{transform:'translateX(0)',opacity:.3},{transform:'translateX(-250px)',opacity:1}],{duration:1000,fill:'both'});
window.renderFrame=async(frame,time)=>{
 gl.clearColor(.1+.5*time,.25,.45,1);gl.clear(gl.COLOR_BUFFER_BIT);gl.finish();
 document.querySelector('#text').style.fontVariationSettings=`'wght' ${300+frame*30},'wdth' ${90+frame}`;
};
