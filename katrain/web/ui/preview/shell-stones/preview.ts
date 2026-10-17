import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { createBoardTexture, createStone, STONE_DIMENSIONS } from './stoneModel';
import './preview.css';

const stage = document.querySelector<HTMLDivElement>('#model-stage')!;
const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFShadowMap;
renderer.domElement.setAttribute('aria-label', '可旋转检查的黑白双面凸碁石模型');
renderer.domElement.setAttribute('role', 'img');
stage.replaceChildren(renderer.domElement);

const scene = new THREE.Scene();
scene.background = new THREE.Color('#bda077');
const pmrem = new THREE.PMREMGenerator(renderer);
// Two broad studio cards avoid the many sharp reflections of a furnished room.
const studio = new THREE.Scene();
studio.background = new THREE.Color(.08, .08, .08);
for (const [position, size, intensity] of [
  [[-3, 5, 4], [4.5, 5.5], 3],
  [[5, 2, -4], [3, 4], .7],
] as const) {
  const card = new THREE.Mesh(new THREE.PlaneGeometry(size[0], size[1]), new THREE.MeshBasicMaterial({ color: new THREE.Color().setScalar(intensity), side: THREE.DoubleSide }));
  card.position.set(position[0], position[1], position[2]); card.lookAt(0, 0, 0); studio.add(card);
}
const environment = pmrem.fromScene(studio, .1);
studio.traverse(object => { if (object instanceof THREE.Mesh) { object.geometry.dispose(); object.material.dispose(); } });
pmrem.dispose();
scene.environment = environment.texture;
scene.environmentIntensity = .48;

function addLights(target: THREE.Scene, shadow = false) {
  target.add(new THREE.HemisphereLight(0xeaf0ff, 0xa08b70, .3));
  const key = new THREE.DirectionalLight(0xfff9ee, 1.6);
  key.position.set(-3.8, 6.5, 4);
  key.castShadow = shadow;
  if (shadow) {
    key.shadow.mapSize.set(2048, 2048);
    key.shadow.camera.left = key.shadow.camera.bottom = -5;
    key.shadow.camera.right = key.shadow.camera.top = 5;
    key.shadow.camera.near = .1; key.shadow.camera.far = 20;
    key.shadow.normalBias = .012; key.shadow.bias = -.0002;
    key.shadow.radius = 9; key.shadow.intensity = .4;
  }
  target.add(key);
  const fill = new THREE.DirectionalLight(0xe9f0ff, .2);
  fill.position.set(4, 3, -4); target.add(fill);
}
addLights(scene, true);

const boardTexture = createBoardTexture();
const boardMaterial = new THREE.MeshStandardMaterial({ map: boardTexture, roughness: .88, metalness: 0 });
const board = new THREE.Mesh(new THREE.BoxGeometry(8, .16, 6), [
  new THREE.MeshStandardMaterial({ color: '#b18c5e', roughness: .9 }),
  new THREE.MeshStandardMaterial({ color: '#b18c5e', roughness: .9 }),
  boardMaterial, new THREE.MeshStandardMaterial({ color: '#b18c5e', roughness: .9 }),
  new THREE.MeshStandardMaterial({ color: '#b18c5e', roughness: .9 }),
  new THREE.MeshStandardMaterial({ color: '#b18c5e', roughness: .9 }),
]);
board.position.y = -.081;
board.receiveShadow = true; scene.add(board);

const black = createStone('B'), white = createStone('W');
black.position.x = -1.37; white.position.x = 1.37;
scene.add(black, white);

// A restrained diffuse contact patch grounds the rounded lower pole.
const contactCanvas = Object.assign(document.createElement('canvas'), { width: 96, height: 96 });
const contactContext = contactCanvas.getContext('2d')!;
const contactGradient = contactContext.createRadialGradient(48, 48, 0, 48, 48, 48);
contactGradient.addColorStop(0, 'rgba(22,17,12,.24)');
contactGradient.addColorStop(.45, 'rgba(22,17,12,.12)');
contactGradient.addColorStop(1, 'rgba(22,17,12,0)');
contactContext.fillStyle = contactGradient; contactContext.fillRect(0, 0, 96, 96);
const contactMap = new THREE.CanvasTexture(contactCanvas);
for (const stone of [black, white]) {
  const contact = new THREE.Mesh(new THREE.PlaneGeometry(2.5, 2.5), new THREE.MeshBasicMaterial({
    map: contactMap, transparent: true, opacity: .8, depthWrite: false,
  }));
  contact.rotation.x = -Math.PI / 2; contact.position.set(stone.position.x, .002, 0); scene.add(contact);
}

const camera = new THREE.OrthographicCamera(-5, 5, 1.75, -1.75, .01, 100);
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true; controls.dampingFactor = .12;
controls.enablePan = false;
controls.minZoom = .65; controls.maxZoom = 2.2;
controls.maxPolarAngle = Math.PI / 2 - .015;
controls.target.set(0, .32, 0);
const viewPositions = { top: [0, 9, .001], oblique: [3.4, 5.6, 7.5], side: [0, .72, 9] } as const;
type View = keyof typeof viewPositions;

function resize() {
  const width = stage.clientWidth, height = stage.clientHeight;
  const aspect = width / Math.max(height, 1);
  camera.left = -1.75 * aspect; camera.right = 1.75 * aspect;
  camera.top = 1.75; camera.bottom = -1.75;
  camera.updateProjectionMatrix(); renderer.setSize(width, height, false);
}
new ResizeObserver(resize).observe(stage);
function setView(view: View) {
  const [x, y, z] = viewPositions[view];
  camera.position.set(x, y, z); camera.zoom = 1;
  camera.up.set(0, 1, 0);
  camera.updateProjectionMatrix(); controls.target.set(0, .32, 0); controls.update();
  document.querySelectorAll<HTMLButtonElement>('[data-view]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.view === view)));
  renderer.render(scene, camera);
}
document.querySelectorAll<HTMLButtonElement>('[data-view]').forEach(button => button.addEventListener('click', () => setView(button.dataset.view as View)));
resize(); setView('top');

// Render before animation starts, using the SAME WebGL context as its GPU-only PMREM.
// A second renderer cannot sample the first renderer's environment render target.
const previewPixelRatio = renderer.getPixelRatio();
renderer.setPixelRatio(1); renderer.setSize(256, 256, false);
const spriteScene = new THREE.Scene();
spriteScene.environment = environment.texture; spriteScene.environmentIntensity = scene.environmentIntensity;
addLights(spriteScene);
const sprites: Record<string, string> = {};
function makeSprite(color: 'B' | 'W', seed = 17, plain = false) {
  const key = `${color}-${seed}${plain ? '-plain' : ''}`;
  if (sprites[key]) return sprites[key];
  const stone = createStone(color, seed, plain);
  spriteScene.add(stone);
  const radius = STONE_DIMENSIONS[color].diameter / STONE_DIMENSIONS.W.diameter;
  const topCamera = new THREE.OrthographicCamera(-radius, radius, radius, -radius, .01, 30);
  topCamera.position.set(0, 9, 0); topCamera.up.set(0, 0, -1); topCamera.lookAt(0, 0, 0);
  renderer.render(spriteScene, topCamera);
  const data = renderer.domElement.toDataURL('image/png');
  spriteScene.remove(stone); stone.geometry.dispose(); stone.material.dispose();
  sprites[key] = data; return data;
}
const blackSprite = makeSprite('B'), whiteSprite = makeSprite('W');
document.querySelector<HTMLImageElement>('#plain-white')!.src = makeSprite('W', 17, true);
document.querySelector<HTMLImageElement>('#shell-white')!.src = whiteSprite;

const labels = ['12', 'A', 'triangle', 'square', 'cross', 'ring'];
const sizeGrid = document.querySelector<HTMLDivElement>('#size-grid')!;
for (const size of [24, 32, 48]) {
  const card = document.createElement('article'); card.className = 'size-card';
  card.innerHTML = `<div class="size-heading"><strong>${size} px</strong><span>数字 / 字母 / 标记 / 末手</span></div><div class="sample-board" aria-label="${size} 像素黑白棋子及标记"></div>`;
  const sample = card.querySelector<HTMLDivElement>('.sample-board')!;
  const cell = Math.max(size + 8, 40);
  sample.style.setProperty('--grid', `${cell}px`);
  sample.style.setProperty('--diameter', `${size}px`);
  sample.style.setProperty('--label-size', `${Math.round(size * .42)}px`);
  sample.style.setProperty('--start-y', `${(133 - cell) / 2}px`);
  function layOut() {
    const start = (sample.clientWidth - cell * 5) / 2;
    sample.style.setProperty('--start-x', `${start}px`);
    sample.querySelectorAll<HTMLElement>('.stone-cell').forEach((item, i) => item.style.left = `${start + (i % 6) * cell}px`);
  }
  // The second row tests every symbol on the inverse stone color.
  for (let row = 0; row < 2; row++) for (let col = 0; col < 6; col++) {
    const color = (col + row) % 2 ? 'W' : 'B';
    const item = document.createElement('div');
    item.className = `stone-cell ${color === 'W' ? 'white' : 'black'}`;
    item.style.top = `${(133 - cell) / 2 + row * cell}px`;
    const img = document.createElement('img'); img.alt = color === 'W' ? '蛤贝白石' : '那智黑石';
    img.src = makeSprite(color, color === 'W' ? 17 + col * 7 : 17);
    item.append(img);
    const label = document.createElement('span');
    label.className = `stone-label ${labels[col]}`;
    if (col < 2) label.textContent = labels[col];
    label.setAttribute('aria-label', labels[col]); item.append(label);
    sample.append(item);
  }
  sizeGrid.append(card); new ResizeObserver(layOut).observe(sample); layOut();
}
renderer.setPixelRatio(previewPixelRatio);
resize(); renderer.render(scene, camera);

document.querySelectorAll<HTMLButtonElement>('[data-board]').forEach(button => button.addEventListener('click', () => {
  const background = button.dataset.board!;
  document.body.classList.toggle('board-dark', background === 'dark');
  document.body.classList.toggle('board-light', background === 'light');
  boardMaterial.map = background === 'wood' ? boardTexture : null;
  boardMaterial.color.set(background === 'dark' ? '#465058' : background === 'light' ? '#e3dfd4' : '#ffffff');
  boardMaterial.needsUpdate = true;
  scene.background = new THREE.Color(background === 'dark' ? '#313b44' : background === 'light' ? '#d1cec5' : '#bda077');
  document.querySelectorAll<HTMLButtonElement>('[data-board]').forEach(item => item.setAttribute('aria-pressed', String(item === button)));
}));

const dropImage = document.querySelector<HTMLImageElement>('#drop-board img')!;
dropImage.src = blackSprite;
function replayDrop() {
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  dropImage.getAnimations().forEach(animation => animation.cancel());
  dropImage.animate([
    { transform: 'translateY(-5px) scale(1.025)', filter: 'drop-shadow(2px 5px 3px #0003)' },
    { transform: 'translateY(0) scale(1)', filter: 'drop-shadow(1px 2px 1px #0005)' },
  ], { duration: 360, easing: 'cubic-bezier(.2,.7,.25,1)' });
}
document.querySelector('#replay-drop')!.addEventListener('click', replayDrop);
setInterval(replayDrop, 2800);

renderer.setAnimationLoop(() => { controls.update(); renderer.render(scene, camera); });
Object.assign(window, {
  __stonePreviewReady: true,
  __stonePreview: { setView, sprites, dimensions: STONE_DIMENSIONS, renderer: 'Three.js WebGL · original closed lathe geometry' },
});
