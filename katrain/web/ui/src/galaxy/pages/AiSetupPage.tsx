import { useState, useEffect, useRef } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { Box, Typography, Paper, FormControl, InputLabel, Select, MenuItem, Button, Slider, Alert, Stack, Switch, FormControlLabel, Divider, Checkbox, TextField, CircularProgress } from '@mui/material';
import { API, type LadderRung } from '../../api';
import { sliderToHumanKyuRankFixed } from '../../utils/rankUtils';
import { useAuth } from '../../context/AuthContext';
import { useSettings } from '../../context/SettingsContext';
import { useTranslation } from '../../hooks/useTranslation';
import { useDebounce } from '../../hooks/useDebounce';
import AiLadderSetupOpponent from '../../features/aiLadder/AiLadderSetupOpponent';
import {
    AiLadderApiError,
    endAiLadderGame,
    retryAiLadderSettlement,
    startAiLadderGame,
} from '../../features/aiLadder/api';
import type { AiLadderCountingReason } from '../../features/aiLadder/types';
import { useAiLadderStatus } from '../../features/aiLadder/useAiLadderStatus';
import { canStartAiLadderGame } from '../../features/aiLadder/startGate';
import { saveAiLadderBefore } from '../../features/aiLadder/settlement';
import AiLadderRatedSetup from '../components/aiLadder/AiLadderRatedSetup';
import ContentPageHeader from '../components/layout/ContentPageHeader';

// Map Slider value to Rank label for UI
const valueToRank = (val: number) => {
    if (val < 20) {
        return `${20 - val}k`;
    } else {
        return `${val - 19}d`;
    }
};

const AiSetupPage = () => {
    const [searchParams] = useSearchParams();
    const navigate = useNavigate();
    const { user, token } = useAuth();
    useSettings(); // Subscribe to translation changes for re-render
    const { t } = useTranslation();
    const mode = searchParams.get('mode') || 'free';
    const isRated = mode === 'rated';
    const {
        status: aiLadderStatus,
        retry: retryAiLadderStatus,
        applyBlockingSync,
    } = useAiLadderStatus(token || undefined, isRated);

    const [aiConstants, setAiConstants] = useState<any>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [startPending, setStartPending] = useState(false);
    const [lifecyclePending, setLifecyclePending] = useState(false);
    const [lifecycleError, setLifecycleError] = useState('');
    const [syncRetryPending, setSyncRetryPending] = useState(false);
    const [lifecycleReceipt, setLifecycleReceipt] = useState<{
        gameId: string;
        scopeKey: string;
        receipt: { counted: boolean; reason: AiLadderCountingReason | null };
    }>();
    const lifecycleGeneration = useRef(0);
    const lifecycleScopeKey = `${isRated ? 'rated' : 'free'}:${token ?? ''}:${String(user?.id ?? user?.username ?? '')}`;
    const lifecycleScopeRef = useRef(lifecycleScopeKey);
    lifecycleScopeRef.current = lifecycleScopeKey;
    const blockingGameId = aiLadderStatus?.view_state === 'ready' ? aiLadderStatus.blocking_game?.game_id : undefined;
    const blockingGameState = aiLadderStatus?.view_state === 'ready' ? aiLadderStatus.blocking_game?.state : undefined;
    const blockingGameIdRef = useRef(blockingGameId);
    blockingGameIdRef.current = blockingGameId;

    useEffect(() => {
        lifecycleGeneration.current += 1;
        setLifecyclePending(false);
        setLifecycleError('');
        setLifecycleReceipt(undefined);
    }, [isRated, token, user?.id, user?.username]);

    useEffect(() => {
        lifecycleGeneration.current += 1;
        setLifecyclePending(false);
        setLifecycleError('');
        setLifecycleReceipt((receipt) => {
            if (!receipt) return undefined;
            const belongsToCurrentGame = receipt.gameId === blockingGameId;
            return belongsToCurrentGame || !blockingGameId ? receipt : undefined;
        });
    }, [blockingGameId, blockingGameState]);

    // Game Settings
    const [boardSize, setBoardSize] = useState(19);
    const [color, setColor] = useState('B');
    const [opponent, setOpponent] = useState('ai:human');
    const [rankValue, setRankValue] = useState(10); // Default ~10k (Slider 0-28)
    const [handicap, setHandicap] = useState(0);
    const [komi, setKomi] = useState(6.5);
    const [rules, setRules] = useState('japanese');

    // AI Strategy Settings (Free Play)
    const [strategySettings, setSettings] = useState<Record<string, any>>({});
    const [estimatedRank, setEstimatedRank] = useState<string>('...');
    const [aiLoading, setAiLoading] = useState(false);

    // 棋力阶梯 (strength ladder): 37 rungs fetched from GET /api/ladder-rungs.
    // Default rung 18 == native HumanSL "3K" (LADDER_RUNGS index 17).
    const [ladderRungs, setLadderRungs] = useState<LadderRung[]>([]);
    const [ladderRung, setLadderRung] = useState<number>(18);
    const isLadder = opponent === 'ai:ladder';

    // Time Settings
    const [timerEnabled, setTimerEnabled] = useState(isRated); 
    const [mainTime, setMainTime] = useState(10); 
    const [byoLength, setByoLength] = useState(30); 
    const [byoPeriods, setByoPeriods] = useState(3); 

    const rulesets = [
        { id: 'japanese', name: 'Japanese' },
        { id: 'chinese', name: 'Chinese' },
        { id: 'korean', name: 'Korean' },
        { id: 'aga', name: 'AGA' },
        { id: 'newzealand', name: 'New Zealand' },
        { id: 'tromp-taylor', name: 'Tromp-Taylor' }
    ];

    useEffect(() => {
        if (isRated) {
            setOpponent('ai:human');
            setTimerEnabled(true);
            // The conditions every rung was calibrated under, and what the server will
            // actually deal (katrain/web/api/v1/endpoints/ai_ladder.py). The controls
            // below are disabled in rated mode, so they must not sit there displaying
            // a ruleset and komi the game will not be played under.
            setBoardSize(19);
            setRules('chinese');
            setKomi(7.5);
            setHandicap(0);
            setLoading(false);
            return;
        }
        const fetchConstants = async () => {
            try {
                const constants = await API.getAIConstants();
                setAiConstants(constants);
            } catch (err) {
                console.error(err);
                setError('Failed to load AI settings');
            } finally {
                setLoading(false);
            }
        };
        fetchConstants();

        API.getLadderRungs()
            .then((data) => setLadderRungs(data.rungs))
            .catch((err) => console.error('Failed to load ladder rungs', err));
    }, [isRated]);

    // Load strategy default settings when opponent changes (Free mode)
    useEffect(() => {
        if (!isRated && opponent && aiConstants?.strategy_defaults) {
            setAiLoading(true);
            const defaults = aiConstants.strategy_defaults[opponent] || {};
            setSettings({...defaults});
            setAiLoading(false);
        }
    }, [opponent, isRated, aiConstants]);

    const debouncedSettings = useDebounce(strategySettings, 500);
    useEffect(() => {
        if (!isRated && opponent && Object.keys(debouncedSettings).length > 0) {
            API.estimateRank(opponent, debouncedSettings)
                .then(data => setEstimatedRank(data.rank))
                .catch(err => console.error("Rank estimation failed", err));
        } else if (isRated || opponent === 'ai:human') {
            setEstimatedRank(valueToRank(rankValue));
        } else {
            setEstimatedRank("...");
        }
    }, [debouncedSettings, opponent, isRated, rankValue]);

    // Handle special cases - use translations for display names
    // Moved to component level for reuse in both dropdown and game setup
    const getStrategyDisplay = (name: string): string => {
        const strategyDisplayMap: Record<string, string> = {
            'human': t('ai:human_like', 'Human-like'),
            'pro': t('ai:historical_pro', 'Historical Pro'),
            'default': 'KataGo',
            'handicap': 'KataHandicap',
            'scoreloss': t('ai:score_loss', 'Score Loss'),
            'simple': t('ai:simple_ownership', 'Simple Ownership'),
            'rank': t('ai:calibrated_rank', 'Calibrated Rank'),
            'weighted': t('ai:weighted', 'Weighted'),
            'pick': t('ai:policy_pick', 'Policy Pick'),
            'local': t('ai:local', 'Local'),
            'tenuki': t('ai:tenuki', 'Tenuki'),
            'influence': t('ai:influence', 'Influence'),
            'territory': t('ai:territory', 'Territory'),
            'policy': t('ai:policy', 'Policy'),
            'jigo': t('ai:jigo', 'Jigo'),
            'antimirror': t('ai:antimirror', 'Anti-mirror'),
            'ladder': t('ai:golaxy_parity', '棋力阶梯'),
        };
        return strategyDisplayMap[name] || (name.charAt(0).toUpperCase() + name.slice(1));
    };

    const handleStartGame = async () => {
        if (isRated) setStartPending(true);
        else setLoading(true);
        try {
            if (isRated) {
                const session = await startAiLadderGame({
                    color: color === 'B' ? 'black' : 'white',
                    time_enabled: timerEnabled,
                    main_time: mainTime,
                    byo_length: byoLength,
                    byo_periods: byoPeriods,
                }, token || undefined);
                saveAiLadderBefore(
                    session.session_id,
                    session.status,
                    String(user?.id ?? user?.username ?? 'anonymous'),
                    session.game_id,
                );
                navigate(`/galaxy/play/game/${session.session_id}?mode=rated&game_id=${encodeURIComponent(session.game_id)}`);
                return;
            }
            const session = await API.createSession(token || undefined);
            const humanKyuRank = sliderToHumanKyuRankFixed(rankValue);

            const aiColor = color === 'B' ? 'W' : 'B';
            const userColor = color === 'B' ? 'B' : 'W';

            // Format strategy name for display
            let strategyName = opponent;
            if (strategyName.startsWith('ai:p:')) {
                strategyName = strategyName.substring(5);
            } else if (strategyName.startsWith('ai:')) {
                strategyName = strategyName.substring(3);
            }
            strategyName = getStrategyDisplay(strategyName);
            const aiLabel = `AI (${strategyName})`;
            const userName = user?.username || "User";

            // Update timer config BEFORE starting new game so it's captured in the snapshot
            if (timerEnabled) {
                await API.updateConfigBulk(session.session_id, {
                    "timer/main_time": mainTime,
                    "timer/byo_length": byoLength,
                    "timer/byo_periods": byoPeriods,
                    "timer/paused": false
                });
            } else {
                await API.updateConfigBulk(session.session_id, {
                    "timer/main_time": 0,
                    "timer/byo_length": 0,
                    "timer/paused": true
                });
            }

            // Start New Game
            await API.newGame(session.session_id, {
                size: boardSize,
                handicap: handicap,
                komi: komi,
                rules: rules,
                ...(isLadder ? { ladder_rung: ladderRung } : {})
            });

            // Update players with names
            await API.updatePlayer(session.session_id, userColor, "player:human", "human", userName);
            await API.updateConfig(session.session_id, `players/${userColor}/name`, userName);
            
            await API.updatePlayer(session.session_id, aiColor, "player:ai", opponent, aiLabel);
            await API.updateConfig(session.session_id, `players/${aiColor}/name`, aiLabel);

            // Update AI settings. ai:ladder carries no configurable strategySettings (the
            // rung is injected server-side via ladder_rung above), so skip both writes.
            if (isLadder) {
                // no-op
            } else if (opponent === 'ai:human') {
                await API.updateConfig(session.session_id, `ai/${opponent}/human_kyu_rank`, humanKyuRank);
            } else if (!isRated && Object.keys(strategySettings).length > 0) {
                await API.updateConfig(session.session_id, `ai/${opponent}`, strategySettings);
            }

            // Navigate to game page immediately - AI moves will be handled by the game page via WebSocket
            navigate(`/galaxy/play/game/${session.session_id}?mode=${mode}`);
        } catch (err: any) {
            setError(err.message || 'Failed to start game');
            if (isRated) setStartPending(false);
            else setLoading(false);
        }
    };

    const handleEndGame = async (gameId: string) => {
        const requestGeneration = ++lifecycleGeneration.current;
        const requestScopeKey = lifecycleScopeKey;
        const requestIsCurrent = () => lifecycleGeneration.current === requestGeneration
            && lifecycleScopeRef.current === requestScopeKey;
        const targetIsCurrent = () => requestIsCurrent() && blockingGameIdRef.current === gameId;
        setLifecycleError('');
        setLifecyclePending(true);
        try {
            const lifecycle = await endAiLadderGame(gameId, token || undefined);
            if (!targetIsCurrent()) return;
            if (lifecycle.state === 'settled') {
                setLifecycleReceipt({ gameId, scopeKey: requestScopeKey, receipt: lifecycle.receipt });
                await retryAiLadderStatus();
            } else if (lifecycle.state === 'released' || lifecycle.state === 'pending_settlement') {
                // 没有可展示的结果时只刷新状态:挡住开局的那一局消失,页面回到正常的开局卡。
                // **不能落进 catch** —— 那样屏上会说「结束对局失败，请重试」,而此刻账号已经放开。
                await retryAiLadderStatus();
            }
        } catch (endError) {
            if (!targetIsCurrent()) return;
            if (endError instanceof AiLadderApiError && endError.status === 404) {
                // **这一条对「让掉」是承重的,不是容错。** 认输会写一行账本,那行同时是墓碑:
                // 再按一次、或者原盒子的在途结算重投,都会命中它、拿到重放回执。
                // 让掉**按定义什么都不记**,所以它没有墓碑 —— 第二次按下只能撞上「查无此局」。
                // 那不是失败,是「已经没了」,而这里是这条路唯一的收尾方式。
                // 想把 404 改成报错之前先读这句:改了,连按两次就会在一个已经放开的账号上
                // 写「结束对局失败」。钉子在 `test_pressing_end_twice_is_not_an_error_on_the_path_that_leaves_no_tombstone`
                // (后端:404 真的会发生)和 kiosk 的「连按两次」那条(前端:屏上不说失败)。
                setLifecycleError('');
                await retryAiLadderStatus();
            } else if (endError instanceof AiLadderApiError && (endError.status === 401 || endError.status === 403)) {
                setLifecycleError('登录已失效，请重新登录后再试');
            } else {
                setLifecycleError('结束对局失败，请重试');
            }
        } finally {
            if (requestIsCurrent()) setLifecyclePending(false);
        }
    };

    const handleLifecycleRetry = () => {
        setLifecycleError('');
        void retryAiLadderStatus();
    };

    /**
     * 「立即重试」按下去之后的每一条路。
     *
     * 关键是**不要为了刷新去打一次云端**:`/status` 在盒子上是转发到云端的,断网时
     * 503,而 `retryAiLadderStatus` 一失败就把整块面板换成「加载失败」—— 那正是这个
     * 按钮存在的场景。重试请求本身打的是盒子自己,断网照样成功,响应里带着这一次
     * 尝试之后的真实状态,所以失败路径只贴这份状态,不碰云端。
     *
     * 只有**送成了**才去复查:那一刻网络刚被证明是通的,而且那一局不再挡着新局,
     * 屏上要换成新的段位和一张结算回执。
     */
    const handleRetrySettlement = async (gameId: string) => {
        if (syncRetryPending) return;
        setLifecycleError('');
        setSyncRetryPending(true);
        try {
            const { sync } = await retryAiLadderSettlement(gameId, token || undefined);
            if (sync && sync.state !== 'synced') {
                // 还是没送到:退避重排、次数加一(或者被云端拒收)。就地把这份状态贴上去。
                applyBlockingSync(gameId, sync);
                return;
            }
            // 送到了。回执是云端对这一局的裁决 —— 没有它,成功就只是面板悄悄消失,
            // 用户不知道这一局到底计没计。拿不到回执也不编一个,只复查状态。
            if (sync?.receipt) {
                setLifecycleReceipt({
                    gameId,
                    scopeKey: lifecycleScopeRef.current,
                    receipt: sync.receipt,
                });
            }
            await retryAiLadderStatus();
        } catch (retryError) {
            if (retryError instanceof AiLadderApiError && (retryError.status === 401 || retryError.status === 403)) {
                setLifecycleError('登录已失效，请重新登录后再试');
            } else if (retryError instanceof AiLadderApiError && retryError.status === 404) {
                // 队列里已经没有这一局了 —— 多半是后台那一轮刚把它送成。只有这一条
                // catch 该去复查:它意味着屏上这一格已经不成立了。
                await retryAiLadderStatus();
            } else {
                setLifecycleError('重试失败，请稍后再试');
            }
        } finally {
            setSyncRetryPending(false);
        }
    };

    const handleSettingChange = (key: string, value: any) => {
        setSettings(prev => ({ ...prev, [key]: value }));
    };

    const renderOption = (key: string, value: any, spec: any) => {
        if (!aiConstants) return null;
        const isKeyProp = aiConstants.key_properties.includes(key);
        
        if (spec === 'bool') {
          return (
            <FormControlLabel
              key={key}
              control={
                <Checkbox
                  checked={!!value}
                  onChange={(e) => handleSettingChange(key, e.target.checked)}
                />
              }
              label={<Typography variant="body2" fontWeight={isKeyProp ? 'bold' : 'normal'}>{key}</Typography>}
            />
          );
        }
    
        if (Array.isArray(spec)) {
          const isTuple = Array.isArray(spec[0]);
          const values = isTuple ? spec.map((x: any) => x[0]) : spec;
          const labels = isTuple ? spec.map((x: any) => x[1]) : spec.map(String);
          const translatedLabels = labels.map((l: string) => l.replace(/\[(.*?)\]/g, (_, k) => t(k)));
    
          let currentIndex = values.indexOf(value);
          if (currentIndex === -1) currentIndex = values.findIndex((v: number) => Math.abs(v - value) < 1e-9);
          if (currentIndex === -1) currentIndex = 0;
    
          return (
            <Box key={key} sx={{ width: '100%', px: 1, mb: 1 }}>
              <Typography variant="caption" color="textSecondary">{key} {isKeyProp && '*'}</Typography>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                <Slider
                  value={currentIndex} min={0} max={values.length - 1} step={1}
                  onChange={(_, val) => handleSettingChange(key, values[val as number])}
                  size="small"
                />
                <Typography variant="body2" sx={{ minWidth: 45, textAlign: 'right' }}>{translatedLabels[currentIndex]}</Typography>
              </Box>
            </Box>
          );
        }
    
        return (
            <TextField
                key={key} label={key} value={value || ''}
                onChange={(e) => handleSettingChange(key, e.target.value)}
                fullWidth size="small" margin="dense"
            />
        );
    };

    if (isRated) {
        return (
            <Box
                sx={{
                    flex: 1,
                    minHeight: 0,
                    overflowY: 'auto',
                    px: { xs: 2, sm: 3, lg: 4 },
                    pt: { xs: 2, md: 3 },
                    pb: { xs: 'calc(80px + env(safe-area-inset-bottom))', sm: 3 },
                }}
            >
                <Box sx={{ width: '100%', maxWidth: 1500, mx: 'auto' }}>
                    <ContentPageHeader title="升降级对弈" parentLabel="对局" parentTo="/galaxy/play" />
                    {error && <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert>}
                    <Box sx={{ mt: 2.5 }}>
                        <AiLadderRatedSetup
                            status={aiLadderStatus}
                            color={color}
                            mainTime={mainTime}
                            byoLength={byoLength}
                            byoPeriods={byoPeriods}
                            startPending={startPending}
                            lifecyclePending={lifecyclePending}
                            lifecycleError={lifecycleError}
                            lifecycleReceipt={lifecycleReceipt
                                && lifecycleReceipt.scopeKey === lifecycleScopeKey
                                && (!blockingGameId || blockingGameId === lifecycleReceipt.gameId)
                                ? lifecycleReceipt.receipt
                                : undefined}
                            onColorChange={setColor}
                            onRetry={handleLifecycleRetry}
                            onStart={handleStartGame}
                            onContinue={(sessionId) => {
                                if (aiLadderStatus.view_state !== 'ready' || !aiLadderStatus.blocking_game) return;
                                const gameId = aiLadderStatus.blocking_game.game_id;
                                saveAiLadderBefore(
                                    sessionId,
                                    aiLadderStatus,
                                    String(user?.id ?? user?.username ?? 'anonymous'),
                                    gameId,
                                );
                                navigate(`/galaxy/play/game/${sessionId}?mode=rated&game_id=${encodeURIComponent(gameId)}`);
                            }}
                            onEndGame={handleEndGame}
                            onRetrySettlement={handleRetrySettlement}
                            syncRetryPending={syncRetryPending}
                        />
                    </Box>
                </Box>
            </Box>
        );
    }

    if (loading && !aiConstants) return <Box sx={{ p: 4 }}>Loading...</Box>;

    const strategyOptions = aiConstants?.options || {};

    return (
        <Box sx={{ p: 4, maxWidth: 1000, mx: 'auto' }}>
            <Typography variant="h4" gutterBottom sx={{ fontWeight: 'bold' }}>
                {isRated ? t('play:rated_ai_setup', 'Rated Game Setup') : t('play:free_play_setup', 'Free Play Setup')}
            </Typography>
            
            {error && <Alert severity="error" sx={{ mb: 3 }}>{error}</Alert>}

            <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' }, gap: 4 }}>
                <Paper sx={{ p: 4, borderRadius: 4 }}>
                    <Typography variant="h6" gutterBottom>{t('Board & Rules', 'Board & Rules')}</Typography>
                    
                    <FormControl fullWidth margin="normal">
                        <InputLabel>{t('board size', 'Board Size')}</InputLabel>
                        <Select value={boardSize} label={t('board size', 'Board Size')} onChange={(e) => setBoardSize(Number(e.target.value))} disabled={isRated}>
                            <MenuItem value={19}>19x19 ({t('Standard', 'Standard')})</MenuItem>
                            <MenuItem value={13}>13x13</MenuItem>
                            <MenuItem value={9}>9x9</MenuItem>
                        </Select>
                    </FormControl>

                    <FormControl fullWidth margin="normal">
                        <InputLabel>{t('ruleset', 'Ruleset')}</InputLabel>
                        <Select value={rules} label={t('ruleset', 'Ruleset')} onChange={(e) => setRules(e.target.value)} disabled={isRated}>
                            {rulesets.map(r => <MenuItem key={r.id} value={r.id}>{t(r.id, r.name)}</MenuItem>)}
                        </Select>
                    </FormControl>

                    <FormControl fullWidth margin="normal">
                        <InputLabel>{t('Your Color', 'Your Color')}</InputLabel>
                        <Select value={color} label={t('Your Color', 'Your Color')} onChange={(e) => setColor(e.target.value)}>
                            <MenuItem value="B">{t('Black', 'Black')} ({t('First', 'First')})</MenuItem>
                            <MenuItem value="W">{t('White', 'White')} ({t('Second', 'Second')})</MenuItem>
                        </Select>
                    </FormControl>

                    {!isRated && (
                        <Box sx={{ mt: 2 }}>
                            <Typography gutterBottom>{t('handicap', 'Handicap')} ({t('Stones', 'Stones')}): {handicap}</Typography>
                            <Slider 
                                value={handicap} min={0} max={9} step={1} 
                                onChange={(_, v) => setHandicap(v as number)} 
                                valueLabelDisplay="auto"
                            />
                            <Typography gutterBottom sx={{ mt: 2 }}>{t('komi', 'Komi')}: {komi}</Typography>
                            <Slider
                                value={komi} min={0.5} max={85.5} step={0.25}
                                onChange={(_, v) => setKomi(v as number)}
                                valueLabelDisplay="auto"
                            />
                        </Box>
                    )}
                </Paper>

                <Paper sx={{ p: 4, borderRadius: 4 }}>
                    <Typography variant="h6" gutterBottom>{t('Opponent & Time', 'Opponent & Time')}</Typography>

                    {isRated ? (
                        <AiLadderSetupOpponent
                            status={aiLadderStatus}
                            onRetry={retryAiLadderStatus}
                        />
                    ) : (
                        <>
                            <FormControl fullWidth margin="normal">
                                <InputLabel>{t('aistrategy', 'AI Strategy')}</InputLabel>
                                <Select value={opponent} label={t('aistrategy', 'AI Strategy')} onChange={(e) => setOpponent(e.target.value)} disabled={isRated}>
                                    {aiConstants?.strategies?.map((s: string) => {
                                        let strategyKey = s;
                                        if (strategyKey.startsWith('ai:p:')) {
                                            strategyKey = strategyKey.substring(5);
                                        } else if (strategyKey.startsWith('ai:')) {
                                            strategyKey = strategyKey.substring(3);
                                        }
                                        const displayName = getStrategyDisplay(strategyKey);
                                        return (
                                            <MenuItem key={s} value={s}>
                                                {displayName}
                                            </MenuItem>
                                        );
                                    })}
                                </Select>
                            </FormControl>

                            {opponent === 'ai:human' || isRated ? (
                                <Box sx={{ mt: 2, px: 1 }}>
                                    <Typography gutterBottom sx={{ display: 'flex', justifyContent: 'space-between' }}>
                                        <span>{t('Rank', 'Rank')}:</span>
                                        <strong style={{ color: '#4a6b5c' }}>{valueToRank(rankValue)}</strong>
                                    </Typography>
                                    <Slider
                                        value={rankValue} min={0} max={28} step={1}
                                        onChange={(_, v) => setRankValue(v as number)}
                                        valueLabelFormat={valueToRank}
                                        valueLabelDisplay="auto"
                                    />
                                    <Stack direction="row" justifyContent="space-between" sx={{ mt: -1 }}>
                                        <Typography variant="caption" color="text.secondary">20k</Typography>
                                        <Typography variant="caption" color="text.secondary">9d</Typography>
                                    </Stack>
                                </Box>
                            ) : isLadder ? (
                                <Box sx={{ mt: 2, p: 2, bgcolor: 'background.default', borderRadius: 2 }}>
                                    <Typography variant="subtitle2" gutterBottom color="primary">
                                        {t('ai:golaxy_parity', '棋力阶梯')}
                                    </Typography>
                                    <FormControl fullWidth margin="dense" size="small">
                                        <InputLabel>{t('ai:golaxy_parity_rung', '棋力等级')}</InputLabel>
                                        <Select
                                            value={ladderRung}
                                            label={t('ai:golaxy_parity_rung', '棋力等级')}
                                            onChange={(e) => setLadderRung(Number(e.target.value))}
                                        >
                                            {ladderRungs.map((r) => (
                                                <MenuItem key={r.rung} value={r.rung}>
                                                    {r.rank_name}
                                                </MenuItem>
                                            ))}
                                        </Select>
                                    </FormControl>
                                </Box>
                            ) : (
                                <Box sx={{ mt: 2, p: 2, bgcolor: 'background.default', borderRadius: 2 }}>
                                    <Typography variant="subtitle2" gutterBottom color="primary">{t('menu:aisettings', 'AI Settings')}</Typography>
                                    {aiLoading ? <CircularProgress size={24} /> : (
                                        <Box>
                                            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2 }}>
                                                <Typography variant="caption">{t('estimated strength', 'Est. Strength')}:</Typography>
                                                <Typography variant="caption" fontWeight="bold">{estimatedRank}</Typography>
                                            </Box>
                                            {Object.keys(strategySettings).length === 0 ? (
                                                <Typography variant="body2" color="text.secondary" sx={{ fontStyle: 'italic' }}>
                                                    {t('no ai settings', 'No configurable settings for this strategy')}
                                                </Typography>
                                            ) : (
                                                Object.keys(strategySettings).map(k =>
                                                    strategyOptions[k] && renderOption(k, strategySettings[k], strategyOptions[k])
                                                )
                                            )}
                                        </Box>
                                    )}
                                </Box>
                            )}
                        </>
                    )}

                    <Divider sx={{ my: 3 }} />
                    
                    <FormControlLabel
                        control={<Switch checked={timerEnabled} onChange={(e) => setTimerEnabled(e.target.checked)} disabled={isRated} />}
                        label={t('Enable Timer', 'Enable Timer')}
                        sx={{ mb: 1 }}
                    />

                    {timerEnabled && (
                        <Box sx={{ mt: 1 }}>
                            <Box sx={{ mb: 2 }}>
                                <Typography variant="caption" color="text.secondary">{t('main time', 'Main Time')} ({t('Minutes', 'Minutes')}): {mainTime}</Typography>
                                <Slider 
                                    value={mainTime} min={0} max={60} step={1} 
                                    onChange={(_, v) => setMainTime(v as number)}
                                />
                            </Box>
                            <Box sx={{ mb: 2 }}>
                                <Typography variant="caption" color="text.secondary">{t('byoyomi length', 'Byo-yomi')} ({t('Seconds', 'Seconds')}): {byoLength}</Typography>
                                <Slider 
                                    value={byoLength} min={5} max={60} step={5} 
                                    onChange={(_, v) => setByoLength(v as number)}
                                />
                            </Box>
                            <Box>
                                <Typography variant="caption" color="text.secondary">{t('byoyomi periods', 'Periods')}: {byoPeriods}</Typography>
                                <Slider 
                                    value={byoPeriods} min={1} max={10} step={1} 
                                    onChange={(_, v) => setByoPeriods(v as number)}
                                />
                            </Box>
                        </Box>
                    )}
                </Paper>
            </Box>

            <Box sx={{ mt: 4, display: 'flex', justifyContent: 'flex-end', gap: 2 }}>
                <Button onClick={() => navigate('/galaxy/play')}>{t('cancel', 'Cancel')}</Button>
                <Button
                    data-testid={isRated ? 'ranked-start-action' : undefined}
                    variant="contained"
                    size="large"
                    onClick={handleStartGame}
                    disabled={loading || (isRated && !canStartAiLadderGame(aiLadderStatus))}
                >
                    {t('btn:Play', 'Start Game')}
                </Button>
            </Box>
        </Box>
    );
};

export default AiSetupPage;
