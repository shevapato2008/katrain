import { useState, useEffect, useCallback, useRef } from 'react';
import { LiveAPI } from '../../../api/live';
import { useAuth } from '../../../context/AuthContext';
/* 这是 hook 不是组件，`i18n.t` 不配 useTranslation 订阅：错误串在事件发生那一刻定型，
   而渲染它的 CommentSection.tsx 自己已经调了 useTranslation()。 */
import { i18n } from '../../../i18n';
import type { Comment } from '../../../types/live';

interface UseCommentsOptions {
  pollInterval?: number; // ms, 0 to disable polling (default 3000)
  initialLimit?: number; // Initial number of comments to fetch
}

interface UseCommentsResult {
  comments: Comment[];
  loading: boolean;
  error: string | null;
  total: number;
  postComment: (content: string) => Promise<boolean>;
  deleteComment: (commentId: number) => Promise<boolean>;
  refresh: () => Promise<void>;
  canPost: boolean; // Whether the user can post (logged in)
}

export function useComments(
  matchId: string | undefined,
  isLive: boolean,
  options: UseCommentsOptions = {}
): UseCommentsResult {
  const { pollInterval = 3000, initialLimit = 50 } = options;
  const { token, isAuthenticated } = useAuth();

  const [comments, setComments] = useState<Comment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [total, setTotal] = useState(0);

  // Track the highest comment ID for polling
  const lastCommentIdRef = useRef<number>(0);

  // Initial fetch
  const fetchComments = useCallback(async () => {
    if (!matchId) return;

    try {
      setLoading(true);
      const data = await LiveAPI.getComments(matchId, { limit: initialLimit });
      setComments(data.comments);
      setTotal(data.total);

      // Update last ID for polling
      if (data.comments.length > 0) {
        lastCommentIdRef.current = Math.max(
          ...data.comments.map((c) => c.id)
        );
      }

      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch comments');
    } finally {
      setLoading(false);
    }
  }, [matchId, initialLimit]);

  // Poll for new comments
  const pollNewComments = useCallback(async () => {
    if (!matchId || !isLive) return;

    try {
      const data = await LiveAPI.pollComments(matchId, lastCommentIdRef.current);
      if (data.count > 0) {
        setComments((prev) => [...prev, ...data.comments]);
        setTotal((prev) => prev + data.count);
        lastCommentIdRef.current = Math.max(
          lastCommentIdRef.current,
          ...data.comments.map((c) => c.id)
        );
      }
    } catch (err) {
      // Polling failures are not critical, don't update error state
      console.warn('Comment poll failed:', err);
    }
  }, [matchId, isLive]);

  // Initial fetch on mount
  useEffect(() => {
    if (matchId) {
      fetchComments();
    }
  }, [matchId, fetchComments]);

  // Polling for live matches
  useEffect(() => {
    if (!matchId || !isLive || pollInterval <= 0) return;

    const interval = setInterval(pollNewComments, pollInterval);
    return () => clearInterval(interval);
  }, [matchId, isLive, pollInterval, pollNewComments]);

  // Post a new comment
  const postComment = useCallback(
    async (content: string): Promise<boolean> => {
      if (!matchId || !token) {
        setError('You must be logged in to post comments');
        return false;
      }

      try {
        const newComment = await LiveAPI.createComment(matchId, content, token);
        setComments((prev) => [...prev, newComment]);
        setTotal((prev) => prev + 1);
        lastCommentIdRef.current = Math.max(lastCommentIdRef.current, newComment.id);
        return true;
      } catch (err) {
        // 后端 403 的 detail.code 现在由 api/live.ts 挂在错误对象上。
        // 不分支的话用户看到的是 `Request failed 403: {"detail":{...}}` ——
        // 报错串里其实写着原因，只是没人翻译给他。
        const code = (err as { code?: string } | null)?.code;
        if (code === 'comment_requires_phone') {
          setError(i18n.t('live:comment_requires_phone',
            '发表评论需要先绑定手机号。请在左下角「设置 → 绑定手机号」完成绑定。'));
        } else {
          setError(err instanceof Error ? err.message : 'Failed to post comment');
        }
        return false;
      }
    },
    [matchId, token]
  );

  // Delete a comment
  const deleteComment = useCallback(
    async (commentId: number): Promise<boolean> => {
      if (!token) {
        setError('You must be logged in to delete comments');
        return false;
      }

      try {
        await LiveAPI.deleteComment(commentId, token);
        setComments((prev) => prev.filter((c) => c.id !== commentId));
        setTotal((prev) => Math.max(0, prev - 1));
        return true;
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to delete comment');
        return false;
      }
    },
    [token]
  );

  const refresh = useCallback(async () => {
    await fetchComments();
  }, [fetchComments]);

  return {
    comments,
    loading,
    error,
    total,
    postComment,
    deleteComment,
    refresh,
    canPost: isAuthenticated && isLive,
  };
}
