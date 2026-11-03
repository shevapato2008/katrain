import * as THREE from 'three';
import { createStoneGeometry, createStoneMaterial, STONE_DIMENSIONS } from '../../src/components/tutorials/stoneModel';
import { addStoneStudioLights, configureStoneRenderer, createStoneEnvironment, STONE_ENVIRONMENT_INTENSITY } from '../../src/components/tutorials/stoneStudio';

/** Render the existing authored model with its original, photo-free shell material. */
function renderSprites(): Record<string, string> {
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true });
  renderer.setPixelRatio(1);
  renderer.setSize(256, 256);
  renderer.setClearColor(0, 0);
  configureStoneRenderer(renderer);
  const scene = new THREE.Scene();
  const environment = createStoneEnvironment(renderer);
  scene.environment = environment.texture;
  scene.environmentIntensity = STONE_ENVIRONMENT_INTENSITY;
  addStoneStudioLights(scene);
  const camera = new THREE.OrthographicCamera(-1.03, 1.03, 1.03, -1.03, .01, 30);
  camera.position.set(0, 9, 0);
  camera.up.set(0, 0, -1);
  camera.lookAt(0, 0, 0);
  const result: Record<string, string> = {};
  for (const color of ['B', 'W'] as const) {
    const geometry = createStoneGeometry(color);
    const variants = color === 'W' ? 8 : 1;
    for (let variant = 0; variant < variants; variant++) {
      const material = createStoneMaterial(color, variant, false, 256);
      const mesh = new THREE.Mesh(geometry, material);
      mesh.position.y = STONE_DIMENSIONS[color].thickness / STONE_DIMENSIONS.W.diameter;
      scene.add(mesh);
      renderer.render(scene, camera);
      result[color === 'B' ? 'black.png' : `white-${String(variant).padStart(2, '0')}.png`] = renderer.domElement.toDataURL('image/png');
      scene.remove(mesh);
      material.dispose();
    }
    geometry.dispose();
  }
  environment.dispose();
  renderer.dispose();
  return result;
}

declare global { interface Window { __productionStoneSprites?: Record<string, string>; } }
window.__productionStoneSprites = renderSprites();
