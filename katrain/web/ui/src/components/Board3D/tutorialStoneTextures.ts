import { SRGBColorSpace, TextureLoader, type Texture } from 'three';
import { TUTORIAL_STONE_SPRITE_URLS, TUTORIAL_STONE_DIAMETER_RATIO } from '../tutorials/tutorialStoneSprites';

export interface RecordingStoneSprites { B: Texture; W: readonly Texture[]; diameterRatio?: Readonly<Record<'B' | 'W', number>> }

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
    ]).then(([B, W]) => ({ B, W, diameterRatio: TUTORIAL_STONE_DIAMETER_RATIO }));
  }
  return textures;
}
