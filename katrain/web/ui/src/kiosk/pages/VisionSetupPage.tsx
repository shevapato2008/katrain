import { useState, useCallback } from 'react';
import { Box, Button, Typography, Paper } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { Videocam, VideocamOff, ArrowBack, Check, Refresh } from '@mui/icons-material';
import { useVision } from '../context/VisionContext';
import { API } from '../../api';

const STREAM_URL = '/api/v1/vision/stream';

const VisionSetupPage = () => {
  const navigate = useNavigate();
  const { visionStatus, refreshStatus } = useVision();

  const [streamError, setStreamError] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [streamKey, setStreamKey] = useState(0);

  const handleStreamError = useCallback(() => {
    setStreamError(true);
  }, []);

  const handleRetry = useCallback(() => {
    setStreamError(false);
    setStreamKey((k) => k + 1);
  }, []);

  const handleConfirm = useCallback(async () => {
    setConfirming(true);
    try {
      await API.visionConfirmPoseLock();
      await refreshStatus();
      navigate(-1);
    } catch (err) {
      console.error('Pose lock confirmation failed', err);
    } finally {
      setConfirming(false);
    }
  }, [navigate, refreshStatus]);

  const handleBack = useCallback(() => {
    navigate(-1);
  }, [navigate]);

  const statusText = visionStatus.poseLocked ? '棋盘已识别' : '正在检测棋盘...';
  const statusColor = visionStatus.poseLocked ? 'success.main' : 'warning.main';

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        width: '100%',
        overflow: 'hidden',
        bgcolor: 'background.default',
      }}
    >
      {/* Stream viewport */}
      <Box
        sx={{
          flex: 1,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          px: 2,
          pt: 2,
          pb: 1,
          overflow: 'hidden',
        }}
      >
        <Paper
          elevation={2}
          sx={{
            width: '100%',
            maxWidth: 640,
            aspectRatio: '4 / 3',
            overflow: 'hidden',
            borderRadius: 2,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            bgcolor: 'grey.900',
            position: 'relative',
          }}
        >
          {streamError ? (
            <Box
              sx={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: 2,
              }}
            >
              <VideocamOff sx={{ fontSize: 48, color: 'error.main' }} />
              <Typography variant="body1" sx={{ color: 'error.light' }}>
                摄像头连接中断
              </Typography>
              <Button
                variant="outlined"
                color="error"
                startIcon={<Refresh />}
                onClick={handleRetry}
              >
                重试
              </Button>
            </Box>
          ) : (
            <img
              key={streamKey}
              src={STREAM_URL}
              alt="摄像头画面"
              onError={handleStreamError}
              style={{
                width: '100%',
                height: '100%',
                objectFit: 'contain',
                display: 'block',
              }}
            />
          )}
        </Paper>
      </Box>

      {/* Status + actions */}
      <Box
        sx={{
          px: 2,
          pb: 2,
          pt: 1,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: 1.5,
          flexShrink: 0,
        }}
      >
        {/* Status indicator */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Box
            sx={{
              width: 10,
              height: 10,
              borderRadius: '50%',
              bgcolor: statusColor,
            }}
          />
          <Typography variant="body1" sx={{ color: 'text.primary' }}>
            {statusText}
          </Typography>
          {visionStatus.cameraConnected ? (
            <Videocam sx={{ fontSize: 20, color: 'success.main', ml: 1 }} />
          ) : (
            <VideocamOff sx={{ fontSize: 20, color: 'error.main', ml: 1 }} />
          )}
        </Box>

        {/* Action buttons */}
        <Box sx={{ display: 'flex', gap: 2, width: '100%', maxWidth: 400 }}>
          <Button
            variant="outlined"
            size="large"
            startIcon={<ArrowBack />}
            onClick={handleBack}
            sx={{ flex: 1, minHeight: 48 }}
          >
            返回
          </Button>
          <Button
            variant="contained"
            size="large"
            startIcon={<Check />}
            onClick={handleConfirm}
            disabled={confirming || !visionStatus.poseLocked}
            sx={{ flex: 1, minHeight: 48 }}
          >
            {confirming ? '确认中...' : '确认'}
          </Button>
        </Box>
      </Box>
    </Box>
  );
};

export default VisionSetupPage;
