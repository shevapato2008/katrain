import { useEffect, useRef, type ReactNode } from 'react';

export default function VisionDialog({ title, children, onClose }: { title: string; children: ReactNode; onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    dialog.showModal();
    return () => { dialog.close(); };
  }, []);
  return <dialog ref={ref} className="vision-review" aria-label={title} onCancel={onClose}>
    <div className="vision-review-head"><h2>{title}</h2><button className="vision-button" type="button" onClick={onClose}>关闭</button></div>
    {children}
  </dialog>;
}
