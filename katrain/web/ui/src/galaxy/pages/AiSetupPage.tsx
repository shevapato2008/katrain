import { useState, useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { Box, Typography, Paper, FormControl, InputLabel, Select, MenuItem, Button, Slider, Alert, Stack, Switch, FormControlLabel, Divider, Checkbox, TextField, CircularProgress } from '@mui/material';
import { API } from '../../api';
import { sliderToHumanKyuRankFixed } from '../utils/rankUtils';
import { useAuth } from '../context/AuthContext';
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
    const { user } = useAuth();
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

    const handleStartGame = async () => {
        setLoading(true);
        try {
            const session = await API.createSession();
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
            // Handle special cases
            const strategyDisplayMap: Record<string, string> = {
                'human': 'Human-like',
                'pro': 'Historical Pro',
                'default': 'KataGo',
                'handicap': 'KataHandicap',
                'scoreloss': 'Score Loss',
                'simple': 'Simple Ownership',
                'rank': 'Calibrated Rank',
                'weighted': 'Weighted',
                'pick': 'Policy Pick',
                'local': 'Local',
                'tenuki': 'Tenuki',
                'influence': 'Influence',
                'territory': 'Territory',
                'policy': 'Policy',
                'jigo': 'Jigo',
                'antimirror': 'Anti-mirror',
            };
            strategyName = strategyDisplayMap[strategyName] || (strategyName.charAt(0).toUpperCase() + strategyName.slice(1));
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
                rules: rules
            });

            // Update players with names
            await API.updatePlayer(session.session_id, userColor, "player:human", "human", userName);
            await API.updateConfig(session.session_id, `players/${userColor}/name`, userName);
            
            await API.updatePlayer(session.session_id, aiColor, "player:ai", opponent, aiLabel);
            await API.updateConfig(session.session_id, `players/${aiColor}/name`, aiLabel);

            // Update AI settings
            if (opponent === 'ai:human') {
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

    return (
        <Box sx={{ p: 4, maxWidth: 1000, mx: 'auto' }}>
            <Typography variant="h4" gutterBottom sx={{ fontWeight: 'bold' }}>
                {isRated ? 'Rated Game Setup' : 'Free Play Setup'}
            </Typography>
            
            {error && <Alert severity="error" sx={{ mb: 3 }}>{error}</Alert>}

            <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' }, gap: 4 }}>
                <Paper sx={{ p: 4, borderRadius: 4 }}>
                    <Typography variant="h6" gutterBottom>Board & Rules</Typography>
                    
                    <FormControl fullWidth margin="normal">
                        <InputLabel>Board Size</InputLabel>
                        <Select value={boardSize} label="Board Size" onChange={(e) => setBoardSize(Number(e.target.value))} disabled={isRated}>
                            <MenuItem value={19}>19x19 (Standard)</MenuItem>
                            <MenuItem value={13}>13x13</MenuItem>
                            <MenuItem value={9}>9x9</MenuItem>
                        </Select>
                    </FormControl>

                    <FormControl fullWidth margin="normal">
                        <InputLabel>Ruleset</InputLabel>
                        <Select value={rules} label="Ruleset" onChange={(e) => setRules(e.target.value)} disabled={isRated}>
                            {rulesets.map(r => <MenuItem key={r.id} value={r.id}>{r.name}</MenuItem>)}
                        </Select>
                    </FormControl>

                    <FormControl fullWidth margin="normal">
                        <InputLabel>Your Color</InputLabel>
                        <Select value={color} label="Your Color" onChange={(e) => setColor(e.target.value)}>
                            <MenuItem value="B">Black (First)</MenuItem>
                            <MenuItem value="W">White (Second)</MenuItem>
                        </Select>
                    </FormControl>

                    {!isRated && (
                        <Box sx={{ mt: 2 }}>
                            <Typography gutterBottom>Handicap (Stones): {handicap}</Typography>
                            <Slider 
                                value={handicap} min={0} max={9} step={1} 
                                onChange={(_, v) => setHandicap(v as number)} 
                                valueLabelDisplay="auto"
                            />
                            <Typography gutterBottom sx={{ mt: 2 }}>Komi: {komi}</Typography>
                            <Slider
                                value={komi} min={0.5} max={85.5} step={0.25}
                                onChange={(_, v) => setKomi(v as number)}
                                valueLabelDisplay="auto"
                            />
                        </Box>
                    )}
                </Paper>

                <Paper sx={{ p: 4, borderRadius: 4 }}>
                    <Typography variant="h6" gutterBottom>Opponent & Time</Typography>

                    <FormControl fullWidth margin="normal">
                        <InputLabel>AI Strategy</InputLabel>
                        <Select value={opponent} label="AI Strategy" onChange={(e) => setOpponent(e.target.value)} disabled={isRated}>
                            {aiConstants?.strategies?.map((s: string) => {
                                // Format display name: remove 'ai:' prefix, handle 'ai:p:' prefix
                                let displayName = t(s);
                                if (displayName.startsWith('ai:p:')) {
                                    displayName = displayName.substring(5);
                                } else if (displayName.startsWith('ai:')) {
                                    displayName = displayName.substring(3);
                                }
                                // Capitalize first letter
                                displayName = displayName.charAt(0).toUpperCase() + displayName.slice(1);
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
                                <span>Difficulty:</span>
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
                    ) : (
                        <Box sx={{ mt: 2, p: 2, bgcolor: 'background.default', borderRadius: 2 }}>
                            <Typography variant="subtitle2" gutterBottom color="primary">AI Settings</Typography>
                            {aiLoading ? <CircularProgress size={24} /> : (
                                <Box>
                                    <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2 }}>
                                        <Typography variant="caption">Est. Strength:</Typography>
                                        <Typography variant="caption" fontWeight="bold">{estimatedRank}</Typography>
                                    </Box>
                                    {Object.keys(strategySettings).length === 0 ? (
                                        <Typography variant="body2" color="text.secondary" sx={{ fontStyle: 'italic' }}>
                                            No configurable settings for this strategy
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
                    
                    <FormControlLabel
                        control={<Switch checked={timerEnabled} onChange={(e) => setTimerEnabled(e.target.checked)} disabled={isRated} />}
                        label="Enable Timer"
                        sx={{ mb: 1 }}
                    />

                    {timerEnabled && (
                        <Box sx={{ mt: 1 }}>
                            <Box sx={{ mb: 2 }}>
                                <Typography variant="caption" color="text.secondary">Main Time (Minutes): {mainTime}</Typography>
                                <Slider 
                                    value={mainTime} min={0} max={60} step={1} 
                                    onChange={(_, v) => setMainTime(v as number)}
                                />
                            </Box>
                            <Box sx={{ mb: 2 }}>
                                <Typography variant="caption" color="text.secondary">Byo-yomi (Seconds): {byoLength}</Typography>
                                <Slider 
                                    value={byoLength} min={5} max={60} step={5} 
                                    onChange={(_, v) => setByoLength(v as number)}
                                />
                            </Box>
                            <Box>
                                <Typography variant="caption" color="text.secondary">Periods: {byoPeriods}</Typography>
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
                <Button onClick={() => navigate('/galaxy/play')}>Cancel</Button>
                <Button variant="contained" size="large" onClick={handleStartGame} disabled={loading}>
                    Start Game
                </Button>
            </Box>
        </Box>
    );
};

export default AiSetupPage;
