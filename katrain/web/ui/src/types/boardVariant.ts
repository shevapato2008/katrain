/** Read-time board adaptation; source IDs still own progress and downloads. */
export interface BoardVariant {
  status: 'original' | 'adapted' | 'unavailable';
  source_size: number;
  target_size: 19;
  policy_version: string;
  source_sha256: string;
  offset: [number, number];
  reason: string;
}
