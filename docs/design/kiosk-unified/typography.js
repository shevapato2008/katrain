/* Shared typography for this HTML design artifact only. No application settings are written. */
(() => {
  const storageKey = 'kiosk-design-typography-v1';
  const families = {wenkai:'"SmartBox Kai",serif',kaiti:'"Kiosk Preview Kaiti","SmartBox Kai",serif',lishu:'"Kiosk Preview Lishu","SmartBox Kai",serif',heiti:'"Kiosk Preview Heiti","SmartBox Kai",serif'};
  const steps = {large:0,medium:2,small:4};
  const state = {font:'wenkai',size:'large',language:'cn'};
  try {
    const saved=JSON.parse(localStorage.getItem(storageKey)||'null');
    if(saved && Object.hasOwn(families,saved.font))state.font=saved.font;
    if(saved && Object.hasOwn(steps,saved.size))state.size=saved.size;
  } catch (_) { /* A restricted browser can still use the current design session. */ }
  const preserved = '.u-shell-brand,.u-shell-en,.u-settings-launcher-brand,.u-shell-logo,.u-settings-launcher-logo,svg,canvas,img,.kiosk-plex-num,input[type="number"],[class*="u-settings-font-"]';
  function apply() {
    const roots=[document.getElementById('proposal-layer'),document.getElementById('modal-root')].filter(Boolean);
    // The launcher and its shared help dialog belong to the portal, outside Go preferences.
    if(document.querySelector('#proposal-layer .u-settings-launcher')){
      for(const root of roots){
        for(const el of [root,...root.querySelectorAll('*')]){
          for(const name of el.getAttributeNames().filter(name=>name.startsWith('data-design-')))el.removeAttribute(name);
          for(const name of Array.from(el.style).filter(name=>name.startsWith('--kiosk-design-')))el.style.removeProperty(name);
        }
      }
      return;
    }
    for(const root of roots){
      root.dataset.designSizing='off';
      root.dataset.designFont=state.font;
      root.dataset.designSize=state.size;
      root.dataset.designLanguage=state.language;
      root.style.setProperty('--kiosk-design-font',['cn','tw'].includes(state.language)?families[state.font]:'system-ui,"Hiragino Sans GB",sans-serif');
      root.style.setProperty('--kiosk-design-step',steps[state.size]+'px');
      const nodes=[root,...root.querySelectorAll('*')].filter(el=>!el.closest('svg,canvas,img,.u-shell-brand,.u-shell-en,.u-settings-launcher-brand'));
      // Measure with the size rule disabled so inherited text and newly rendered nodes never scale twice.
      const unmeasured=nodes.filter(el=>!el.hasAttribute('data-design-text'));
      const measured=unmeasured.map(el=>{const css=getComputedStyle(el);return {size:css.fontSize,family:css.fontFamily};});
      const controls=nodes.filter(el=>el.matches('button,input,select,textarea')&&!el.hasAttribute('data-design-control'));
      const controlSizes=controls.map(el=>{const css=getComputedStyle(el);return [css.width,css.height];});
      unmeasured.forEach((el,i)=>{el.style.setProperty('--kiosk-design-base-size',measured[i].size);el.setAttribute('data-design-text','');if(/monospace|Mono/i.test(measured[i].family))el.setAttribute('data-design-fixed-family','');});
      controls.forEach((el,i)=>{el.style.setProperty('--kiosk-design-control-width',controlSizes[i][0]);el.style.setProperty('--kiosk-design-control-height',controlSizes[i][1]);el.setAttribute('data-design-control','');});
      nodes.forEach(el=>{
        if(!el.closest(preserved)&&!el.closest('[data-design-fixed-family]'))el.setAttribute('data-design-family','');
      });
      root.dataset.designSizing='on';
    }
  }
  function set(values) {
    if(Object.hasOwn(families,values.font))state.font=values.font;
    if(Object.hasOwn(steps,values.size))state.size=values.size;
    if(values.language)state.language=values.language;
    try { localStorage.setItem(storageKey,JSON.stringify({font:state.font,size:state.size})); } catch (_) {}
    apply();
  }
  window.KioskDesignTypography={state,set,apply,storageKey};
})();
