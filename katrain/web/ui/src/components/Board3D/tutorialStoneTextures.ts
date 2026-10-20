import { SRGBColorSpace, TextureLoader, type Texture } from 'three';
import { TUTORIAL_STONE_SPRITE_URLS } from '../tutorials/tutorialStoneSprites';

export interface RecordingStoneSprites { B: Texture; W: readonly Texture[] }

// One texture per exported asset, shared by every stone and recording frame.
let textures: Promise<RecordingStoneSprites> | null = null;
export function loadRecordingStoneSprites(): Promise<RecordingStoneSprites> {
  if (!textures) {
    const loader = new TextureLoader();
    const load = async (url: string) => {
      const texture = await loader.loadAsync(url);
      texture.colorSpace = SRGBColorSpace;
      return texture;
    };
    textures = Promise.all([
      load(TUTORIAL_STONE_SPRITE_URLS.B),
      Promise.all(TUTORIAL_STONE_SPRITE_URLS.W.map(load)),
    ]).then(([B, W]) => ({ B, W }));
  }
  return textures;
}
