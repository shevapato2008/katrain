import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { createBoardTexture, createStoneGeometry, STONE_DIMENSIONS } from '../../src/components/tutorials/stoneModel';
import { addStoneStudioLights, configureStoneRenderer, createStoneEnvironment, STONE_ENVIRONMENT_INTENSITY } from '../../src/components/tutorials/stoneStudio';
import sourcePhoto from './source-photo.jpg';
import derivedAlbedo from './photo-shell-albedo.png';
import './preview.css';

type Mode = 'photo' | 'derived';
type View = 'top' | 'oblique' | 'side';
const stage = document.querySelector<HTMLDivElement>('#model-stage')!;
const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
configureStoneRenderer(renderer);
renderer.domElement.setAttribute('aria-label', '可旋转的实拍贝纹双凸棋子模型');
renderer.domElement.setAttribute('role', 'img');
stage.replaceChildren(renderer.domElement);
const scene = new THREE.Scene();
scene.background = new THREE.Color('#bc9f77');
const environment = createStoneEnvironment(renderer);
scene.environment = environment.texture;
scene.environmentIntensity = STONE_ENVIRONMENT_INTENSITY;
addStoneStudioLights(scene, true);
const board = new THREE.Mesh(new THREE.BoxGeometry(7, .16, 5), new THREE.MeshStandardMaterial({
  map: createBoardTexture(), roughness: .88, metalness: 0,
}));
board.position.y = -.081; board.receiveShadow = true; scene.add(board);
const camera = new THREE.OrthographicCamera(-3.3, 3.3, 1.5, -1.5, .01, 100);
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true; controls.enablePan = false;
controls.minZoom = .6; controls.maxZoom = 2; controls.maxPolarAngle = Math.PI / 2 - .01;
controls.target.set(0, .32, 0);
const loader = new THREE.TextureLoader();
const [photo, derived] = await Promise.all([loader.loadAsync(sourcePhoto), loader.loadAsync(derivedAlbedo)]);
for (const texture of [photo, derived]) {
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.anisotropy = Math.min(8, renderer.capabilities.getMaxAnisotropy());
}
// Use only the unretouched photograph's glare-free central patch: x700..1650,
// y450..1400 of the 2339×2356 source. UV sampling does not generate new pixels.
// V runs opposite the top-down camera, so this also keeps the photograph upright.
photo.offset.set(700 / 2339, 1 - 450 / 2356);
photo.repeat.set(950 / 2339, -950 / 2356);
derived.offset.set(0, 1); derived.repeat.set(1, -1);
const materials: Record<Mode, THREE.MeshPhysicalMaterial> = Object.fromEntries(
  ([['photo', photo], ['derived', derived]] as const).map(([mode, map]) => [mode, new THREE.MeshPhysicalMaterial({
    color: 0xffffff, map, metalness: 0, roughness: .3, ior: 1.53,
    clearcoat: .12, clearcoatRoughness: .38, envMapIntensity: .6,
    emissive: 0xffffff, emissiveMap: map, emissiveIntensity: .18,
  })]),
) as Record<Mode, THREE.MeshPhysicalMaterial>;
const stone = new THREE.Mesh(createStoneGeometry('W'), materials.photo);
stone.position.y = STONE_DIMENSIONS.W.thickness / STONE_DIMENSIONS.W.diameter;
stone.castShadow = true; stone.receiveShadow = true; scene.add(stone);
let mode: Mode = 'photo';
function resize() {
  const width = stage.clientWidth, height = stage.clientHeight;
  const aspect = width / Math.max(height, 1);
  camera.left = -1.5 * aspect; camera.right = 1.5 * aspect;
  camera.top = 1.5; camera.bottom = -1.5;
  camera.updateProjectionMatrix(); renderer.setSize(width, height, false);
}
new ResizeObserver(resize).observe(stage);
function setView(view: View) {
  const positions = { top: [0, 9, .001], oblique: [3.4, 5.6, 7.5], side: [0, .72, 9] } as const;
  camera.position.set(...positions[view]); camera.up.set(0, 1, 0); camera.zoom = 1;
  controls.target.set(0, .32, 0); controls.update(); camera.updateProjectionMatrix();
  document.querySelectorAll<HTMLButtonElement>('[data-view]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.view === view)));
  renderer.render(scene, camera);
}
const spriteScene = new THREE.Scene();
spriteScene.environment = environment.texture; spriteScene.environmentIntensity = scene.environmentIntensity;
addStoneStudioLights(spriteScene);
const sprites: Record<string, string> = {};
function sprite(which: Mode, angle: number) {
  const key = `${which}-${angle}`;
  if (sprites[key]) return sprites[key];
  const ratio = renderer.getPixelRatio();
  renderer.setPixelRatio(1); renderer.setSize(256, 256, false);
  const mesh = new THREE.Mesh(stone.geometry, materials[which]);
  mesh.position.y = stone.position.y; mesh.rotation.y = angle;
  spriteScene.add(mesh);
  const top = new THREE.OrthographicCamera(-1, 1, 1, -1, .01, 30);
  top.position.set(0, 9, 0); top.up.set(0, 0, -1); top.lookAt(0, 0, 0);
  renderer.render(spriteScene, top);
  sprites[key] = renderer.domElement.toDataURL('image/png');
  spriteScene.remove(mesh); renderer.setPixelRatio(ratio); resize();
  return sprites[key];
}
function showSamples() {
  const grid = document.querySelector<HTMLDivElement>('#size-grid')!;
  grid.replaceChildren();
  for (const size of [24, 32, 48]) {
    const card = document.createElement('article'); card.className = 'size-card';
    card.innerHTML = `<div class="size-heading"><strong>${size} px</strong><span>${mode === 'photo' ? '实拍照片裁取' : 'AI 衍生对照'}</span></div><div class="sample-board"></div>`;
    const sample = card.querySelector<HTMLDivElement>('.sample-board')!;
    for (const [i, degrees] of [0, 37, 83, 127, 219].entries()) {
      const item = document.createElement('div'); item.className = 'sample-item';
      const body = document.createElement('div'); body.className = 'sample-stone';
      body.style.cssText = `width:${size}px;height:${size}px;--label-size:${Math.round(size * .42)}px`;
      const img = document.createElement('img'); img.src = sprite(mode, degrees * Math.PI / 180); img.alt = `${degrees} 度贝纹白子`;
      body.append(img);
      if (i > 2) { const label = document.createElement('b'); label.textContent = i === 3 ? '12' : '△'; body.append(label); }
      const caption = document.createElement('small'); caption.textContent = `${degrees}°`;
      item.append(body, caption); sample.append(item);
    }
    grid.append(card);
  }
}
document.querySelector<HTMLImageElement>('#source-photo')!.src = sourcePhoto;
document.querySelectorAll<HTMLButtonElement>('[data-view]').forEach(b => b.addEventListener('click', () => setView(b.dataset.view as View)));
document.querySelectorAll<HTMLButtonElement>('[data-mode]').forEach(b => b.addEventListener('click', () => {
  mode = b.dataset.mode as Mode; stone.material = materials[mode]; showSamples();
  document.querySelectorAll<HTMLButtonElement>('[data-mode]').forEach(button => button.setAttribute('aria-pressed', String(button === b)));
  document.querySelector('#material-caption')!.textContent = mode === 'photo'
    ? '实拍照片裁取；没有使用程序条纹，也没有用 AI 补绘这块纹理。'
    : 'AI 辅助去高光与延展后的衍生纹理；部分细节已重建，不等同原照片。';
}));
const download = document.querySelector<HTMLButtonElement>('#download-model')!;
async function exportModel() {
  const { GLTFExporter } = await import('three/addons/exporters/GLTFExporter.js');
  const mesh = stone.clone();
  // glTF units are metres. The existing geometry is normalized to a 2-unit diameter.
  mesh.scale.setScalar(STONE_DIMENSIONS.W.diameter / 2000);
  mesh.position.set(0, STONE_DIMENSIONS.W.thickness / 2000, 0);
  mesh.name = 'clamshell-white-photo-preview';
  mesh.userData = { source: 'https://kurokigoishiten.com/en/products/clamshell-go-stones-premium-snow-grade', texture: mode === 'photo' ? 'Original photo UV crop; unretouched' : 'AI-assisted derivative', usage: 'Local preview; commercial redistribution permission unconfirmed', dimensionsMm: STONE_DIMENSIONS.W };
  return await new GLTFExporter().parseAsync(mesh, { binary: true });
}
download.addEventListener('click', async () => {
  download.disabled = true;
  try {
    const data = await exportModel();
    if (!(data instanceof ArrayBuffer)) throw new Error('GLB export did not return a binary model');
    const url = URL.createObjectURL(new Blob([data], { type: 'model/gltf-binary' }));
    const a = document.createElement('a'); a.href = url; a.download = `clamshell-${mode}-preview.glb`; a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  } catch (error) { download.textContent = '导出失败，可重试'; console.error(error); }
  finally { download.disabled = false; }
});
resize(); showSamples(); setView('top'); download.disabled = false;
renderer.setAnimationLoop(() => { controls.update(); renderer.render(scene, camera); });
Object.assign(window, {
  __photoStoneReady: true,
  __photoStonePreview: { setView, sprites, exportModel, dimensions: STONE_DIMENSIONS.W, sourceCrop: [700, 450, 1650, 1400] },
  __exportTutorialStoneSprites: () => {
    renderer.setAnimationLoop(null);
    try {
      const exported: Record<string, string> = {};
      for (let variant = 0; variant < 32; variant++) {
        exported[`white-${String(variant).padStart(2, '0')}.png`] = sprite('photo', 2 * Math.PI * variant / 32);
      }
      return exported;
    } finally {
      resize();
      renderer.setAnimationLoop(() => { controls.update(); renderer.render(scene, camera); });
    }
  },
});
