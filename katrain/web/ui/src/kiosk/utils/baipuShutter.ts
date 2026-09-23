import { readAudioPref } from '../../utils/audioPrefs';

/**
 * 摆谱的快门声:WebAudio 现合成的一声短「嗒」(没有音频资源)。在**这一帧写完之后**才响 ——
 * 它是「可以摆下一颗了」的信号。能响就响,被浏览器拦了就算了。
 *
 * **它归「落子音效」那把开关**,不归语音:语音那把关的是七句引导语,这一声和落子声是同一类。
 * 以前它不读任何开关 ⇒ 设置里写着「关」,摆谱照样每拍一帧响一声。
 *
 * 单独成一个文件:页面文件只许导出组件(fast refresh),而这一声要能单测 ——
 * WebAudio 没有 `Audio` 那样的缓存对象可以桩。
 */
export function playShutter() {
  if (!readAudioPref('sfx')) return;
  try {
    const Ctx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    const ctx = new Ctx();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.frequency.value = 880;
    gain.gain.setValueAtTime(0.0001, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.2, ctx.currentTime + 0.005);
    gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.09);
    osc.connect(gain).connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 0.1);
    osc.onended = () => ctx.close();
  } catch {
    // no audio available — silent
  }
}
