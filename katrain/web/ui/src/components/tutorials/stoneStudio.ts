import * as THREE from 'three';

/** The approved shell/slate preview studio, shared with its transparent sprite export. */
export function configureStoneRenderer(renderer: THREE.WebGLRenderer) {
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFShadowMap;
}

/** Render-target environments must stay in the creating renderer's WebGL context. */
export function createStoneEnvironment(renderer: THREE.WebGLRenderer) {
  const pmrem = new THREE.PMREMGenerator(renderer);
  const studio = new THREE.Scene();
  studio.background = new THREE.Color(.08, .08, .08);
  for (const [position, size, intensity] of [
    [[-3, 5, 4], [4.5, 5.5], 3],
    [[5, 2, -4], [3, 4], .7],
  ] as const) {
    const card = new THREE.Mesh(new THREE.PlaneGeometry(size[0], size[1]), new THREE.MeshBasicMaterial({
      color: new THREE.Color().setScalar(intensity), side: THREE.DoubleSide,
    }));
    card.position.set(position[0], position[1], position[2]);
    card.lookAt(0, 0, 0);
    studio.add(card);
  }
  const environment = pmrem.fromScene(studio, .1);
  studio.traverse(object => {
    if (object instanceof THREE.Mesh) { object.geometry.dispose(); object.material.dispose(); }
  });
  pmrem.dispose();
  return environment;
}

export const STONE_ENVIRONMENT_INTENSITY = .48;

export function addStoneStudioLights(target: THREE.Scene, shadow = false) {
  target.add(new THREE.HemisphereLight(0xeaf0ff, 0xa08b70, .3));
  const key = new THREE.DirectionalLight(0xfff9ee, 1.6);
  key.position.set(-3.8, 6.5, 4);
  key.castShadow = shadow;
  if (shadow) {
    key.shadow.mapSize.set(2048, 2048);
    key.shadow.camera.left = key.shadow.camera.bottom = -5;
    key.shadow.camera.right = key.shadow.camera.top = 5;
    key.shadow.camera.near = .1;
    key.shadow.camera.far = 20;
    key.shadow.normalBias = .012;
    key.shadow.bias = -.0002;
    key.shadow.radius = 9;
    key.shadow.intensity = .4;
  }
  target.add(key);
  const fill = new THREE.DirectionalLight(0xe9f0ff, .2);
  fill.position.set(4, 3, -4);
  target.add(fill);
}
