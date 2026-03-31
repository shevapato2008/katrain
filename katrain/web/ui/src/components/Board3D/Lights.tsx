import { memo } from 'react';

/**
 * Scene lighting: warm ambient + hemisphere + directional key/fill/rim + spot.
 * Ported from go-board-3d.html setupLights().
 */
const Lights = () => {
  return (
    <>
      <ambientLight color={0xffecd2} intensity={0.5} />
      <hemisphereLight args={[0xfff8f0, 0x8b7355, 0.3]} />
      <directionalLight
        color={0xfff4e0}
        intensity={1.0}
        position={[10, 18, 12]}
        castShadow
        shadow-mapSize-width={2048}
        shadow-mapSize-height={2048}
        shadow-camera-near={1}
        shadow-camera-far={50}
        shadow-camera-left={-16}
        shadow-camera-right={16}
        shadow-camera-top={16}
        shadow-camera-bottom={-16}
        shadow-bias={-0.0005}
        shadow-normalBias={0.02}
      />
      <directionalLight color={0xd4e0ff} intensity={0.35} position={[-8, 10, -4]} />
      <directionalLight color={0xffc87c} intensity={0.25} position={[-2, 5, -14]} />
      <spotLight
        color={0xfff8f0}
        intensity={0.4}
        position={[0, 20, 0]}
        angle={Math.PI / 6}
        penumbra={0.5}
        decay={1}
        distance={35}
      />
      <pointLight color={0xffe8c8} intensity={0.2} distance={20} position={[0, 3, 14]} />
    </>
  );
};

export default memo(Lights);
