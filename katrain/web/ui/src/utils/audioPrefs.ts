/**
 * 声音开关。两把:**音效**(落子 / 提子 / 对错)和**语音**(实体盘摆子引导那几句)。
 *
 * ## 为什么以前没有开关,而这是个真问题
 *
 * `useSound` 一直导出一个 `setEnabled` —— **零个调用点**,而且它关不掉声音:
 * `enabledRef` 是 `useRef`,**每个 hook 实例各有一份**,而 `audioCache` 是模块级的。
 * 也就是说 A 组件调 `setEnabled(false)`,B 组件照样响。
 * 一个名字叫「全局静音」、实际只静自己这一份的 API,比没有更坏 ——
 * 下一个人会把它接到设置开关上,然后屏上写着「关」而喇叭还在响。
 * ⇒ 那两个出口(`setEnabled` / `isEnabled`)已删,状态搬到这里,模块级一份。
 *
 * ## 为什么是**按设备**存,不按用户
 *
 * 和做题进度**正好相反**。做题进度必须带 user id(盒子是共享设备,甲解的题不能算进乙的账);
 * 而喇叭是**这个房间的**:教室里把声音关掉,是希望它对下一个坐下来的人也是关着的。
 * 跟着账号走反而会在换人时突然响起来。⇒ 钥匙不带 user id,这是**裁定不是遗漏**。
 *
 * ## 出厂是开的
 *
 * 读不到 / 存储不可用 / 值认不出来 ⇒ 一律当**开**。静音是用户主动做的选择,
 * 「读不出来就静音」会让一台好盒子在隐私模式下变哑,而且没有任何提示。
 */

export type AudioKind = 'sfx' | 'voice';
export type StoneSoundStyle = 'random' | 'stone1' | 'stone2' | 'stone3' | 'stone4' | 'stone5' | 'off';
export type StoneSoundTone = Exclude<StoneSoundStyle, 'off'>;

export interface StoneSoundOption<T extends StoneSoundStyle = StoneSoundStyle> {
  readonly id: T;
  readonly label: string;
  readonly shortLabel: string;
}

export const STONE_SOUND_OPTIONS: ReadonlyArray<StoneSoundOption<StoneSoundStyle>> = [
  { id: 'random', label: '随机自然 (5种混音)', shortLabel: '随机自然' },
  { id: 'stone1', label: '清脆本榧 (音效一)', shortLabel: '清脆本榧' },
  { id: 'stone2', label: '温润蛤石 (音效二)', shortLabel: '温润蛤石' },
  { id: 'stone3', label: '沉稳云子 (音效三)', shortLabel: '沉稳云子' },
  { id: 'stone4', label: '脆响竹盘 (音效四)', shortLabel: '脆响竹盘' },
  { id: 'stone5', label: '醇厚木韵 (音效五)', shortLabel: '醇厚木韵' },
  { id: 'off', label: '静音关闭', shortLabel: '静音' },
];

export const STONE_SOUND_TONE_OPTIONS: ReadonlyArray<StoneSoundOption<StoneSoundTone>> =
  STONE_SOUND_OPTIONS.filter((opt): opt is StoneSoundOption<StoneSoundTone> => opt.id !== 'off');

const KEYS: Record<AudioKind, string> = {
  sfx: 'kiosk_audio_sfx',
  voice: 'kiosk_audio_voice',
};

export const STONE_SOUND_TONE_KEY = 'kiosk_stone_sound_tone';

const VALID_TONES = new Set<StoneSoundTone>(['random', 'stone1', 'stone2', 'stone3', 'stone4', 'stone5']);

type Listener = () => void;
const listeners = new Set<Listener>();

function notifyListeners(): void {
  listeners.forEach((fn) => fn());
}

/** 读一把开关。默认开;localStorage 抛异常(隐私模式)也当开。 */
export function readAudioPref(kind: AudioKind): boolean {
  try {
    // **只有明写的 `false` 算关**。`v === 'true'` 那种写法会把任何认不出来的值
    // (旧版本的键、别的分支写进去的东西、手改坏的)一律判成关 —— 那正是
    // 「读不出来就静音」:屏上写着开而喇叭不响,没有任何提示。
    return localStorage.getItem(KEYS[kind]) !== 'false';
  } catch {
    return true;
  }
}

/** 写一把开关,并通知订阅者(设置屏上那两个分段要跟着变)。 */
export function writeAudioPref(kind: AudioKind, enabled: boolean): void {
  try {
    localStorage.setItem(KEYS[kind], enabled ? 'true' : 'false');
  } catch {
    /* best-effort:存不下也要让本次会话生效,所以照样通知 */
  }
  notifyListeners();
}

export function normalizeStoneSoundTone(value?: string | null): StoneSoundTone {
  if (value && VALID_TONES.has(value as StoneSoundTone)) {
    return value as StoneSoundTone;
  }
  return 'random';
}

export function readStoneSoundTonePref(): StoneSoundTone {
  try {
    return normalizeStoneSoundTone(localStorage.getItem(STONE_SOUND_TONE_KEY));
  } catch {
    return 'random';
  }
}

export function writeStoneSoundTonePref(tone: StoneSoundTone): void {
  const normalized = normalizeStoneSoundTone(tone);
  try {
    localStorage.setItem(STONE_SOUND_TONE_KEY, normalized);
  } catch {
    /* best-effort */
  }
  notifyListeners();
}

export function readStoneSoundPref(): StoneSoundStyle {
  if (!readAudioPref('sfx')) return 'off';
  return readStoneSoundTonePref();
}

export function writeStoneSoundPref(style: StoneSoundStyle): void {
  if (style === 'off') {
    writeAudioPref('sfx', false);
  } else {
    writeStoneSoundTonePref(style);
    writeAudioPref('sfx', true);
  }
  try {
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('katrain:stone-sound-change', { detail: style }));
    }
  } catch {
    /* ignore event errors */
  }
}

export function resolveStoneSoundUrl(style: StoneSoundStyle = readStoneSoundPref()): string | null {
  if (style === 'off') return null;
  if (style === 'random') {
    const idx = Math.floor(Math.random() * 5) + 1;
    return `/assets/sounds/stone${idx}.wav`;
  }
  return `/assets/sounds/${style}.wav`;
}

export function previewStoneSound(style: StoneSoundStyle): void {
  const url = resolveStoneSoundUrl(style);
  if (!url) return;
  try {
    const audio = new Audio(url);
    audio.volume = 0.5;
    void audio.play().catch(() => {});
  } catch {
    /* ignore preview playback errors */
  }
}

/**
 * 订阅变化。给 `useSyncExternalStore` 用 —— 设置屏那两个分段读的是这里,
 * 不是自己另存一份 state:**两份状态迟早走散**,而走散的表现正好是
 * 「屏上写着关、喇叭还在响」那一种,和上面刚删掉的 bug 同形。
 */
export function subscribeAudioPref(fn: Listener): () => void {
  listeners.add(fn);
  return () => { listeners.delete(fn); };
}
