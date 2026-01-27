import { useState, useRef, useEffect } from 'react';
import {
  Box,
  Typography,
  TextField,
  IconButton,
  List,
  ListItem,
  ListItemText,
  CircularProgress,
  Alert,
} from '@mui/material';
import SendIcon from '@mui/icons-material/Send';
import DeleteIcon from '@mui/icons-material/Delete';
import { useComments } from '../../hooks/live/useComments';
import { useAuth } from '../../context/AuthContext';
import type { Comment } from '../../types/live';
import { i18n } from '../../../i18n';

interface CommentSectionProps {
  matchId: string;
  isLive: boolean;
}

export default function CommentSection({ matchId, isLive }: CommentSectionProps) {
  const { user } = useAuth();
  const { comments, loading, error, postComment, deleteComment, canPost } = useComments(
    matchId,
    isLive
  );

  const [inputValue, setInputValue] = useState('');
  const [posting, setPosting] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new comments arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [comments.length]);

  const handleSend = async () => {
    if (!inputValue.trim() || posting) return;

    setPosting(true);
    const success = await postComment(inputValue.trim());
    if (success) {
      setInputValue('');
    }
    setPosting(false);
  };

  const handleDelete = async (commentId: number) => {
    await deleteComment(commentId);
  };

  const formatTime = (isoString: string) => {
    try {
      return new Date(isoString).toLocaleTimeString([], {
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return '';
    }
  };


  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        height: 250,
        bgcolor: 'background.paper',
        borderRadius: 1,
        overflow: 'hidden',
      }}
    >
      {/* Header */}
      <Box
        sx={{
          p: 1,
          bgcolor: 'rgba(0,0,0,0.1)',
          borderBottom: '1px solid rgba(255,255,255,0.05)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <Typography variant="subtitle2" color="text.secondary">
          {i18n.t('live:comments', 'Comments')}
        </Typography>
        <Typography variant="caption" color="text.secondary">
          {comments.length} {i18n.t('live:comments_count', 'comments')}
        </Typography>
      </Box>

      {/* Error display */}
      {error && (
        <Alert severity="error" sx={{ m: 1, py: 0 }}>
          {error}
        </Alert>
      )}

      {/* Comment list */}
      <List sx={{ flexGrow: 1, overflow: 'auto', px: 1, py: 0 }}>
        {loading && comments.length === 0 ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 2 }}>
            <CircularProgress size={24} />
          </Box>
        ) : comments.length === 0 ? (
          <Typography
            variant="body2"
            color="text.secondary"
            sx={{ textAlign: 'center', py: 2 }}
          >
            {isLive ? i18n.t('live:no_comments_live', 'No comments yet, be the first!') : i18n.t('live:no_comments', 'No comments')}
          </Typography>
        ) : (
          comments.map((comment) => (
            <CommentItem
              key={comment.id}
              comment={comment}
              isOwner={user?.id === comment.user_id}
              onDelete={handleDelete}
              formatTime={formatTime}
            />
          ))
        )}
        <div ref={messagesEndRef} />
      </List>

      {/* Input area */}
      <Box
        sx={{
          p: 1,
          display: 'flex',
          gap: 1,
          borderTop: '1px solid rgba(255,255,255,0.05)',
        }}
      >
        {canPost ? (
          <>
            <TextField
              size="small"
              fullWidth
              placeholder={i18n.t('live:comment_placeholder', 'Add a comment...')}
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleSend()}
              variant="outlined"
              disabled={posting}
              inputProps={{ maxLength: 500 }}
              sx={{ bgcolor: 'rgba(255,255,255,0.05)' }}
            />
            <IconButton
              onClick={handleSend}
              color="primary"
              disabled={!inputValue.trim() || posting}
            >
              {posting ? <CircularProgress size={20} /> : <SendIcon />}
            </IconButton>
          </>
        ) : (
          <Typography
            variant="body2"
            color="text.secondary"
            sx={{ width: '100%', textAlign: 'center', py: 0.5 }}
          >
            {!isLive
              ? i18n.t('live:comments_readonly', 'Match ended, comments are read-only')
              : i18n.t('live:login_to_comment', 'Login to comment')}
          </Typography>
        )}
      </Box>
    </Box>
  );
}

interface CommentItemProps {
  comment: Comment;
  isOwner: boolean;
  onDelete: (id: number) => void;
  formatTime: (time: string) => string;
}

function CommentItem({ comment, isOwner, onDelete, formatTime }: CommentItemProps) {
  const [deleting, setDeleting] = useState(false);

  const handleDeleteClick = async () => {
    setDeleting(true);
    await onDelete(comment.id);
    setDeleting(false);
  };

  return (
    <ListItem
      alignItems="flex-start"
      sx={{
        py: 0.5,
        px: 1,
        '&:hover': {
          bgcolor: 'rgba(255,255,255,0.02)',
        },
      }}
      secondaryAction={
        isOwner && (
          <IconButton
            edge="end"
            size="small"
            onClick={handleDeleteClick}
            disabled={deleting}
            sx={{ opacity: 0.5, '&:hover': { opacity: 1 } }}
          >
            <DeleteIcon fontSize="small" />
          </IconButton>
        )
      }
    >
      <ListItemText
        primary={
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'baseline' }}>
            <Typography
              variant="subtitle2"
              sx={{
                color: 'primary.main',
                fontWeight: 'bold',
                fontSize: '0.75rem',
              }}
            >
              {comment.username}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {formatTime(comment.created_at)}
            </Typography>
          </Box>
        }
        secondary={
          <Typography
            variant="body2"
            color="text.primary"
            sx={{ wordBreak: 'break-word', fontSize: '0.8rem' }}
          >
            {comment.content}
          </Typography>
        }
      />
    </ListItem>
  );
}
