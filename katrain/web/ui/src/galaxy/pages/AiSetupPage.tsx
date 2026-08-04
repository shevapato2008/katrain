import { useState, useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { Box, Typography, Paper, FormControl, InputLabel, Select, MenuItem, Button, Slider, Alert, Stack, Switch, FormControlLabel, Divider, Checkbox, TextField, CircularProgress } from '@mui/material';
import { API, type LadderRung, type LadderMe } from '../../api';
import LadderRankCard from '../components/play/LadderRankCard';
import { sliderToHumanKyuRankFixed } from '../../utils/rankUtils';
import { useAuth } from '../../context/AuthContext';
import { useSettings } from '../../context/SettingsContext';
import { useTranslation } from '../../hooks/useTranslation';
import { useDebounce } from '../../hooks/useDebounce';

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

    const [aiConstants, setAiConstants] = useState<any>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');

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

    // 升降级对弈: the player's own ladder state. Server-authoritative, including the
    // opponent tier -- there is nothing here for the client to choose.
    const [ladderMe, setLadderMe] = useState<LadderMe | null>(null);
    const [ladderError, setLadderError] = useState<string | null>(null);

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
        const fetchConstants = async () => {
            try {
                const constants = await API.getAIConstants();
                setAiConstants(constants);
                if (isRated) {
                    setOpponent('ai:human');
                    setTimerEnabled(true);
                    setRules('japanese');
                }
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

    useEffect(() => {
        if (!isRated) return;
        if (!token) {
            setLadderMe(null);
            setLadderError('unauthenticated');
            return;
        }
        setLadderError(null);
        API.getLadderMe(token)
            .then(setLadderMe)
            .catch((err) => {
                console.error('Failed to load ladder state', err);
                setLadderMe(null);
                setLadderError(err?.message || 'unavailable');
            });
    }, [isRated, token]);

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
        setLoading(true);
        try {
            const session = await API.createSession(token || undefined);

            // 升降级对弈 is one server call, not a client-assembled sequence: the
            // opponent tier, the players and the scoring game type are all decided
            // server-side so none of them can be talked into something easier.
            if (isRated) {
                if (!token) throw new Error(t('ladder:need_login', '登录后才能参加升降级对弈。'));
                await API.startLadderGame(token, {
                    session_id: session.session_id,
                    size: boardSize,
                    komi,
                    rules,
                    color,
                    main_time: mainTime * 60,
                    byo_length: byoLength,
                    byo_periods: byoPeriods,
                });
                navigate(`/galaxy/play/game/${session.session_id}?mode=${mode}`);
                return;
            }

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
            setLoading(false);
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

    if (loading && !aiConstants) return <Box sx={{ p: 4 }}>Loading...</Box>;

    const strategyOptions = aiConstants?.options || {};

    // Time controls. In rated play the on/off switch is locked open but the three
    // values stay editable, so this block has to travel with the settings card
    // rather than the opponent card.
    const timeControls = (
        <>
            <Box sx={{ display: 'flex', alignItems: 'center' }}>
                <FormControlLabel
                    control={
                        <Switch
                            checked={timerEnabled}
                            onChange={(e) => setTimerEnabled(e.target.checked)}
                            disabled={isRated}
                            // Locked open, not switched off. MUI's disabled palette drains
                            // the track to near-invisible grey, which reads as "off" — the
                            // opposite of what is true here. Keep the on-state colour and
                            // let the adjacent caption carry the "you can't change this".
                            sx={isRated ? {
                                '& .Mui-disabled .MuiSwitch-thumb': { color: 'primary.main' },
                                '& .Mui-disabled + .MuiSwitch-track': { bgcolor: 'primary.main', opacity: 0.5 },
                            } : undefined}
                        />
                    }
                    label={t('Enable Timer', 'Enable Timer')}
                    sx={isRated ? { '& .MuiFormControlLabel-label.Mui-disabled': { color: 'text.secondary' } } : undefined}
                />
                {isRated && (
                    <Typography variant="caption" color="text.disabled" sx={{ ml: 'auto' }}>
                        {t('ladder:timer_locked', '升降级对局固定开启')}
                    </Typography>
                )}
            </Box>

            {timerEnabled && (
                <Box sx={{ mt: 1 }}>
                    {/* The unit lives in the value, so these labels must NOT carry one.
                        The older `main time` / `byoyomi length` keys bake "(分钟)" /
                        "(秒)" into the msgstr and would render it twice; they stay in
                        use by components/TimeSettingsDialog.tsx, where the label is the
                        only place the unit appears. Hence separate keys here. */}
                    <Box sx={{ mb: 2 }}>
                        <Typography variant="caption" color="text.secondary" sx={{ display: 'flex', justifyContent: 'space-between' }}>
                            <span>{t('time:main_time', '保留时间')}</span>
                            <strong>{mainTime} {t('time:minutes', '分钟')}</strong>
                        </Typography>
                        <Slider value={mainTime} min={0} max={60} step={1} onChange={(_, v) => setMainTime(v as number)} />
                    </Box>
                    <Box sx={{ mb: 2 }}>
                        <Typography variant="caption" color="text.secondary" sx={{ display: 'flex', justifyContent: 'space-between' }}>
                            <span>{t('time:byoyomi_length', '每步读秒')}</span>
                            <strong>{byoLength} {t('time:seconds', '秒')}</strong>
                        </Typography>
                        <Slider value={byoLength} min={5} max={60} step={5} onChange={(_, v) => setByoLength(v as number)} />
                    </Box>
                    <Box>
                        <Typography variant="caption" color="text.secondary" sx={{ display: 'flex', justifyContent: 'space-between' }}>
                            <span>{t('time:byoyomi_periods', '读秒次数')}</span>
                            <strong>{byoPeriods} {t('time:times', '次')}</strong>
                        </Typography>
                        <Slider value={byoPeriods} min={1} max={10} step={1} onChange={(_, v) => setByoPeriods(v as number)} />
                    </Box>
                </Box>
            )}
        </>
    );

    return (
        <Box sx={{ p: 4, maxWidth: 1000, mx: 'auto' }}>
            <Typography variant="h4" gutterBottom sx={{ fontWeight: 'bold' }}>
                {isRated ? t('play:rated_ai_setup', 'Rated Game Setup') : t('play:free_play_setup', 'Free Play Setup')}
            </Typography>
            
            {error && <Alert severity="error" sx={{ mb: 3 }}>{error}</Alert>}

            <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' }, gap: 4, alignItems: 'start' }}>
                <Paper sx={{ p: 4, borderRadius: 4 }}>
                    <Typography variant="h6" gutterBottom>
                        {isRated ? t('Game Settings', '对局设置') : t('Board & Rules', 'Board & Rules')}
                    </Typography>

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

                    {isRated && (
                        <>
                            <Divider sx={{ my: 3 }} />
                            {timeControls}
                        </>
                    )}
                </Paper>

                {isRated ? (
                    ladderMe ? (
                        <LadderRankCard me={ladderMe} />
                    ) : (
                        // Loading, signed out, and failed are three different things and
                        // none of them is a playable card. Never render a placeholder rank.
                        <Paper sx={{ p: 4, borderRadius: 4 }}>
                            <Typography variant="h6" gutterBottom>{t('ladder:your_rank', '你的段位')}</Typography>
                            {ladderError === null ? (
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mt: 3 }}>
                                    <CircularProgress size={20} />
                                    <Typography variant="body2" color="text.secondary">
                                        {t('ladder:loading', '正在读取你的段位…')}
                                    </Typography>
                                </Box>
                            ) : ladderError === 'unauthenticated' ? (
                                <Alert severity="info" sx={{ mt: 2 }}>
                                    {t('ladder:need_login', '登录后才能参加升降级对弈。')}
                                </Alert>
                            ) : (
                                <Alert
                                    severity="error"
                                    sx={{ mt: 2 }}
                                    action={
                                        <Button color="inherit" size="small" onClick={() => {
                                            setLadderError(null);
                                            if (token) {
                                                API.getLadderMe(token).then(setLadderMe).catch((e) => {
                                                    setLadderMe(null);
                                                    setLadderError(e?.message || 'unavailable');
                                                });
                                            }
                                        }}>
                                            {t('retry', '重试')}
                                        </Button>
                                    }
                                >
                                    {t('ladder:load_failed', '读取段位失败，暂时开不了局。')}
                                </Alert>
                            )}
                        </Paper>
                    )
                ) : (
                <Paper sx={{ p: 4, borderRadius: 4 }}>
                    <Typography variant="h6" gutterBottom>{t('Opponent & Time', 'Opponent & Time')}</Typography>

                    <FormControl fullWidth margin="normal">
                        <InputLabel>{t('aistrategy', 'AI Strategy')}</InputLabel>
                        <Select value={opponent} label={t('aistrategy', 'AI Strategy')} onChange={(e) => setOpponent(e.target.value)} disabled={isRated}>
                            {aiConstants?.strategies?.map((s: string) => {
                                // Extract strategy key: remove 'ai:' or 'ai:p:' prefix
                                let strategyKey = s;
                                if (strategyKey.startsWith('ai:p:')) {
                                    strategyKey = strategyKey.substring(5);
                                } else if (strategyKey.startsWith('ai:')) {
                                    strategyKey = strategyKey.substring(3);
                                }
                                // Use the same getStrategyDisplay logic for consistency
                                const displayName = getStrategyDisplay(strategyKey);
                                return (
                                    <MenuItem key={s} value={s}>
                                        {displayName}
                                    </MenuItem>
                                );
                            })}
                        </Select>
                    </FormControl>

                    {opponent === 'ai:human' ? (
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

                    <Divider sx={{ my: 3 }} />

                    {timeControls}
                </Paper>
                )}
            </Box>

            <Box sx={{ mt: 4, display: 'flex', justifyContent: 'flex-end', gap: 2 }}>
                <Button onClick={() => navigate('/galaxy/play')}>{t('cancel', 'Cancel')}</Button>
                {/* An uncertified rung has no legal opponent to seat, so the start
                    button must be dead — the card explains why. Never fall back to
                    another AI. */}
                <Button
                    variant="contained"
                    size="large"
                    onClick={handleStartGame}
                    disabled={loading || (isRated && !ladderMe?.playable)}
                >
                    {t('btn:Play', 'Start Game')}
                </Button>
            </Box>
        </Box>
    );
};

export default AiSetupPage;
