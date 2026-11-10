import { memo, useEffect } from 'react';
import { useThree } from '@react-three/fiber';
import * as THREE from 'three';

function buildStudioEnvironment(gl: THREE.WebGLRenderer): THREE.Texture | null {
  try {
    const pmrem = new THREE.PMREMGenerator(gl);
    const envScene = new THREE.Scene();
    envScene.background = new THREE.Color(0.08, 0.08, 0.09);
    const cards: { pos: [number, number, number]; size: [number, number]; intensity: number }[] = [
      { pos: [-3.2, 5.2, -3.8], size: [4.6, 5.4], intensity: 2.8 },
      { pos: [4.8, 2.4, 3.8], size: [3.2, 4.0], intensity: 0.85 },
    ];
    for (const c of cards) {
      const mesh = new THREE.Mesh(
        new THREE.PlaneGeometry(c.size[0], c.size[1]),
        new THREE.MeshBasicMaterial({ color: new THREE.Color().setScalar(c.intensity), side: THREE.DoubleSide }),
      );
      mesh.position.set(...c.pos);
      mesh.lookAt(0, 0, 0);
      envScene.add(mesh);
    }
    const env = pmrem.fromScene(envScene, 0.04);
    pmrem.dispose();
    return env.texture;
  } catch {
    return null;
  }
}

/**
 * Scene lighting: studio PMREM environment + warm hemisphere + key/fill/rim directional lights.
 * Aligned 1:1 with stone-and-board-showcase-v6.html studio lighting.
 */
const Lights = () => {
  let gl: THREE.WebGLRenderer | undefined;
  let scene: THREE.Scene | undefined;
  try {
    // eslint-disable-next-line react-hooks/rules-of-hooks
    const threeState = useThree();
    gl = threeState?.gl;
    scene = threeState?.scene;
  } catch {
    // Rendered outside R3F Canvas in unit tests
  }

  useEffect(() => {
    if (!gl || !scene) return;
    const envTex = buildStudioEnvironment(gl);
    if (!envTex) return;
    const prevEnv = scene.environment;
    scene.environment = envTex;
    (scene as THREE.Scene & { environmentIntensity?: number }).environmentIntensity = 0.54;
    return () => {
      scene.environment = prevEnv;
      envTex.dispose();
    };
  }, [gl, scene]);

  return (
    <>
      <ambientLight color={0xffecd2} intensity={0.62} />
      <hemisphereLight args={[0xfff8ee, 0x9b8362, 0.42]} />
      <directionalLight
        color={0xfff9ea}
        intensity={1.65}
        position={[-10, 18, -11]}
        castShadow
        shadow-mapSize-width={2048}
        shadow-mapSize-height={2048}
        shadow-camera-near={1}
        shadow-camera-far={50}
        shadow-camera-left={-16}
        shadow-camera-right={16}
        shadow-camera-top={16}
        shadow-camera-bottom={-16}
        shadow-bias={-0.0003}
        shadow-normalBias={0.02}
      />
      <directionalLight color={0xe9efff} intensity={0.42} position={[11, 9, 11]} />
      <directionalLight color={0xffc87c} intensity={0.25} position={[-2, 5, -14]} />
      <spotLight
        color={0xfff8f0}
        intensity={0.45}
        position={[0, 20, 0]}
        angle={Math.PI / 5}
        penumbra={0.5}
        decay={1}
        distance={35}
      />
      <pointLight color={0xffe8c8} intensity={0.25} distance={20} position={[0, 3, 14]} />
    </>
  );
};

export default memo(Lights);
