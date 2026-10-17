import * as THREE from 'three';
import recipe from '../../../../../assets/board-equipment/go/stones/clamshell-slate/v1/source/recipe.json';

const studioPreset = recipe.studio;

/** The approved shell/slate preview studio, shared with its transparent sprite export. */
export function configureStoneRenderer(renderer: THREE.WebGLRenderer) {
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = studioPreset.toneMappingExposure;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFShadowMap;
}

/** Render-target environments must stay in the creating renderer's WebGL context. */
export function createStoneEnvironment(renderer: THREE.WebGLRenderer) {
  const pmrem = new THREE.PMREMGenerator(renderer);
  const studio = new THREE.Scene();
  const [r, g, b] = studioPreset.environment.background;
  studio.background = new THREE.Color(r, g, b);
  for (const { position, size, intensity } of studioPreset.environment.cards) {
    const card = new THREE.Mesh(new THREE.PlaneGeometry(size[0], size[1]), new THREE.MeshBasicMaterial({
      color: new THREE.Color().setScalar(intensity), side: THREE.DoubleSide,
    }));
    card.position.set(position[0], position[1], position[2]);
    card.lookAt(0, 0, 0);
    studio.add(card);
  }
  const environment = pmrem.fromScene(studio, studioPreset.environment.sigma);
  studio.traverse(object => {
    if (object instanceof THREE.Mesh) { object.geometry.dispose(); object.material.dispose(); }
  });
  pmrem.dispose();
  return environment;
}

export const STONE_ENVIRONMENT_INTENSITY = studioPreset.environment.intensity;

export function addStoneStudioLights(target: THREE.Scene, shadow = false) {
  const { hemisphere, key: keyPreset, fill: fillPreset, shadow: shadowPreset } = studioPreset;
  target.add(new THREE.HemisphereLight(hemisphere.skyColor, hemisphere.groundColor, hemisphere.intensity));
  const key = new THREE.DirectionalLight(keyPreset.color, keyPreset.intensity);
  key.position.set(keyPreset.position[0], keyPreset.position[1], keyPreset.position[2]);
  key.castShadow = shadow;
  if (shadow) {
    key.shadow.mapSize.set(shadowPreset.mapSize, shadowPreset.mapSize);
    key.shadow.camera.left = key.shadow.camera.bottom = -shadowPreset.bounds;
    key.shadow.camera.right = key.shadow.camera.top = shadowPreset.bounds;
    key.shadow.camera.near = shadowPreset.near;
    key.shadow.camera.far = shadowPreset.far;
    key.shadow.normalBias = shadowPreset.normalBias;
    key.shadow.bias = shadowPreset.bias;
    key.shadow.radius = shadowPreset.radius;
    key.shadow.intensity = shadowPreset.intensity;
  }
  target.add(key);
  const fill = new THREE.DirectionalLight(fillPreset.color, fillPreset.intensity);
  fill.position.set(fillPreset.position[0], fillPreset.position[1], fillPreset.position[2]);
  target.add(fill);
}
