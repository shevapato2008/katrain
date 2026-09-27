import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createAdminApi, type ArtifactImage, type ArtifactListing } from '../api/client';
import ArtifactsPage from './ArtifactsPage';

const image = (prefix: string, status: string, problems: string[] = []): ArtifactImage => ({ prefix, status, problems, object_size: 1_820_000_000, manifest: { version: prefix.split('/')[1], board: 'rk3562', file: `smartbox-${prefix.split('/')[1]}.img.xz`, sha256: 'a'.repeat(64), size: 1_820_000_000, uploaded_by: 'provision:fan', uploaded_at: '2026-09-27T01:02:00Z' } });
const listing = (images: ArtifactImage[], state: ArtifactListing['state'] = 'configured'): ArtifactListing => ({ state, bucket: 'golden-images', images, truncated: false, error: state === 'unreachable' ? 'EndpointConnectionError' : null });
beforeEach(() => {
  Object.defineProperty(HTMLDialogElement.prototype, 'showModal', { configurable: true, value: function (this: HTMLDialogElement) { this.setAttribute('open', ''); } });
  Object.defineProperty(HTMLDialogElement.prototype, 'close', { configurable: true, value: function (this: HTMLDialogElement) { this.removeAttribute('open'); } });
});

describe('golden images page', () => {
  it('cannot release a broken image and releases a sound one with a reason', async () => {
    const api = createAdminApi(); const u = userEvent.setup();
    api.artifacts = vi.fn(async () => listing([image('rk3562/1.4.3/', 'candidate', ['manifest 指向的文件不存在']), image('rk3562/1.4.2/', 'candidate')]));
    api.artifactStatus = vi.fn(async () => ({ prefix: 'rk3562/1.4.2/', status: 'released' }));
    render(<ArtifactsPage api={api} production onUnauthorized={vi.fn()} />);
    expect(await screen.findByText('manifest 指向的文件不存在')).toBeInTheDocument();
    const [broken, sound] = screen.getAllByRole('button', { name: '发布' });
    expect(broken).toBeDisabled();
    await u.click(sound);
    const dialog = within(screen.getByRole('dialog'));
    expect(dialog.getByText('生产环境')).toBeInTheDocument();
    await u.type(dialog.getByRole('textbox'), '验收通过可发');
    await u.click(dialog.getByRole('button', { name: '确认发布' }));
    await waitFor(() => expect(api.artifactStatus).toHaveBeenCalledWith('rk3562/1.4.2/', 'released', '验收通过可发'));
  });

  it('shows the signed link with the full hash to verify against', async () => {
    const api = createAdminApi(); const u = userEvent.setup();
    api.artifacts = vi.fn(async () => listing([image('rk3562/1.4.2/', 'released')]));
    api.artifactLink = vi.fn(async () => ({ url: 'https://media.example/x?X-Amz-Signature=abc', expires_at: '2026-09-27T13:00:00Z', sha256: 'a'.repeat(64) }));
    render(<ArtifactsPage api={api} production={false} onUnauthorized={vi.fn()} />);
    await u.click(await screen.findByRole('button', { name: '下载链接' }));
    expect(await screen.findByText('https://media.example/x?X-Amz-Signature=abc')).toBeInTheDocument();
    expect(screen.getByText('a'.repeat(64))).toBeInTheDocument();
  });

  it('does not claim an empty library when the bucket is unreachable', async () => {
    const api = createAdminApi();
    api.artifacts = vi.fn(async () => listing([], 'unreachable'));
    render(<ArtifactsPage api={api} production={false} onUnauthorized={vi.fn()} />);
    expect(await screen.findByText(/连不上制品库/)).toBeInTheDocument();
    expect(screen.getByText(/列表不代表没有镜像/)).toBeInTheDocument();
  });
});
