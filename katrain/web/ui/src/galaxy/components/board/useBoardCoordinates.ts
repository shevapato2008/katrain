import { useCallback, useState } from 'react';

export function useBoardCoordinates(edge: number) {
  const [userOverride, setUserOverride] = useState<boolean | null>(null);
  const visible = userOverride ?? edge >= 500;

  const toggle = useCallback(() => {
    setUserOverride((currentOverride) => !(currentOverride ?? edge >= 500));
  }, [edge]);

  const resetToAutomatic = useCallback(() => {
    setUserOverride(null);
  }, []);

  return { visible, userOverride, toggle, resetToAutomatic };
}
