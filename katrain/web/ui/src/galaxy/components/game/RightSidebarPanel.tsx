import { Box, Typography, Stack, Switch, FormControlLabel, IconButton, Button, Tooltip, type SxProps } from '@mui/material';
import { useState, useEffect, type ReactNode } from 'react';
import PlayerCard from '../../../components/PlayerCard';
import ScoreGraph from '../../../components/ScoreGraph';
import ToolGridButton from '../board/ToolGridButton';
import TimelineIcon from '@mui/icons-material/Timeline';
import TipsAndUpdatesIcon from '@mui/icons-material/TipsAndUpdates';
import MapIcon from '@mui/icons-material/Map';
import SkipPreviousIcon from '@mui/icons-material/SkipPrevious';
import FastRewindIcon from '@mui/icons-material/FastRewind';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import ArrowForwardIcon from '@mui/icons-material/ArrowForward';
import FastForwardIcon from '@mui/icons-material/FastForward';
import SkipNextIcon from '@mui/icons-material/SkipNext';
import ExitToAppIcon from '@mui/icons-material/ExitToApp';
import VisibilityIcon from '@mui/icons-material/Visibility';
import FlagIcon from '@mui/icons-material/Flag';
import UndoIcon from '@mui/icons-material/Undo';
import PanToolAltIcon from '@mui/icons-material/PanToolAlt';
import CalculateIcon from '@mui/icons-material/Calculate';
import ViewInArIcon from '@mui/icons-material/ViewInAr';
import { type GameState, API } from '../../../api';
import { useAuth } from '../../../context/AuthContext';
import { useSettings } from '../../../context/SettingsContext';
import { useTranslation } from '../../../hooks/useTranslation';
import { railToggleGroupSx, toolGridSx } from '../../../components/railStyles';

/** 右栏中段的一节：统一的内边距 + 一条分隔线。取代原来散落的 `<Divider/>`。 */
/* 横向内距由 `BoardPageShell` 的 `RAIL_GUTTER` 统一供给，这里只留纵向 ——
   以前是 `p: 2`，和外壳那份叠成 36px，而模块牌的标题在 20px（实测）。 */
const sectionSx: SxProps = { py: 2, borderBottom: '1px solid', borderColor: 'divider' };

interface RightSidebarPanelProps {
    gameState: GameState;
    analysisToggles: Record<string, boolean>;
    onToggleChange: (setting: string) => void;
    onNavigate: (nodeId: number) => void;
    onAction?: (action: string) => void;
    /**
     * 升降级对局。**只管两件事**：底部那块「升降级模式：进行中」横幅，和格子下方那句
     * 「升降级对局中道具已禁用」。
     *
     * 2026-08-22 之前它还兼管「哪些道具能按」，于是对局室为了把分析类道具关掉，
     * 无条件传了 `isRated={true}` —— 结果一局**自由**人人对弈也挂着升降级横幅、
     * 也读到那句解释。禁用逻辑已经挪到 `analysisLocked`，这个 prop 现在只说
     * 「这局算不算段位」这一件事，对局室按 `game_type` 如实传。
     */
    isRated?: boolean;
    /**
     * 本页拿不到引擎分析（人人对弈没有引擎），领地 / 建议 / 图表 / 悔棋一律置灰。
     * 与 `isRated` 正交：升降级对局对局中也锁分析，但自由的人人对弈同样锁 —— 它只是没有引擎。
     */
    analysisLocked?: boolean;
    /**
     * 这一局的分析**服务端根本不交付**（无人认领的会话 —— 未登录游客建的那种）。
     *
     * 与 `analysisLocked` 分开是因为两者禁的范围不同：`analysisLocked` 连悔棋一起禁
     * （升降级反作弊、人人对弈没引擎），而未登录游客的悔棋是通的，只有三个分析键点了没用。
     * 分不开的话就会为了关掉分析而顺手把能用的功能也关掉 —— 那正是 `isRated` 从前兼管
     * 两件事时出的问题。
     *
     * 禁用之外还要**说出原因**：一个不解释的灰键和一个坏掉的键在用户那里是同一个东西。
     */
    analysisRequiresLogin?: boolean;
    /**
     * 观战者。今天这四个键（悔棋 / 停一手 / 认输 / 数子）对观战者仍然可按，
     * 但 `onAction` 被调用方换成了空函数 —— 点了没有任何反应，是账本意义上的空按钮。
     * 传 true 就如实置灰，并把「离开对局」换成「退出观战」（观战者没有可判负的东西）。
     */
    isSpectator?: boolean;
    onTimeout?: () => void;
    onPauseTimer?: () => void;
    onPlaySound?: (sound: string) => void;
    isAnalysisPending?: boolean;  // True when waiting for KataGo analysis
    /** 观众数。不传就不渲染那一格（人机对局没有观众）。 */
    spectatorCount?: number;
    /** 终局结果条，渲染在工具格正下方。人机对局页用的是自己的结算面板，不传。 */
    resultAlert?: ReactNode;
    /** 传了才渲染「离开对局 / 退出观战」。破坏性动作不进工具格，按冻结稿走整行按钮。 */
    onLeave?: () => void;
    /**
     * true = 嵌在 `BoardPageShell` 的右栏里。此时**不自带翻手那一行** ——
     * 它归动作区（`board-rail-actions`，不跟着滚），由页面用具名导出
     * `RightSidebarActions` 放进去。false 时（人机自由对局那套旧版式）仍然自带，
     * 那条路径的渲染结果不变。
     */
    embedded?: boolean;
}

const RightSidebarPanel = ({
    gameState,
    analysisToggles,
    onToggleChange,
    onNavigate,
    onAction = () => {},
    isRated = false,
    analysisLocked,
    analysisRequiresLogin = false,
    isSpectator = false,
    onTimeout,
    onPauseTimer,
    onPlaySound,
    isAnalysisPending = false,
    spectatorCount,
    resultAlert,
    onLeave,
    embedded = false,
}: RightSidebarPanelProps) => {
    const { user, token } = useAuth();
    useSettings(); // Subscribe to translation changes for re-render
    const { t } = useTranslation();
    const [followingNames, setFollowingNames] = useState<Set<string>>(new Set());

    useEffect(() => {
        const fetchFollowing = async () => {
            if (token) {
                try {
                    const following = await API.getFollowing(token);
                    setFollowingNames(new Set(following.map(f => f.username)));
                } catch (err) {
                    console.error("Failed to fetch following list", err);
                }
            }
        };
        fetchFollowing();
    }, [token]);

    const handleToggleFollow = async (username: string) => {
        if (!token || !username) return;
        try {
            if (followingNames.has(username)) {
                await API.unfollowUser(token, username);
                setFollowingNames(prev => {
                    const next = new Set(prev);
                    next.delete(username);
                    return next;
                });
            } else {
                await API.followUser(token, username);
                setFollowingNames(prev => {
                    const next = new Set(prev);
                    next.add(username);
                    return next;
                });
            }
        } catch (err) {
            console.error("Follow toggle failed", err);
        }
    };

    const isGameOver = !!gameState.end_result;
    /* 不传 analysisLocked 时退回旧口径（升降级对局中锁分析），人机对局页因此不用改。 */
    const locked = (analysisLocked ?? isRated) && !isGameOver;
    const canShowAnalysis = !locked && !analysisRequiresLogin;
    /* 传了才显示 —— `ToolGridButton` 的 `tooltip` 是**连 disabled 一起显示**的那一支，
       正是给「为什么这个键是灰的」准备的。不传时它对灰键什么都不显示。 */
    const analysisTooltip = analysisRequiresLogin
        ? t('play:analysis_requires_login', '登录后可用')
        : undefined;

    return (
        <Box sx={{
            width: embedded ? '100%' : 500,
            height: embedded ? 'auto' : '100%',
            display: 'flex',
            flexDirection: 'column',
            bgcolor: 'background.paper',
            borderLeft: embedded ? 0 : '1px solid rgba(255,255,255,0.05)',
        }}>
            <Box sx={{ flexGrow: embedded ? 0 : 1, overflow: embedded ? 'visible' : 'auto', display: 'flex', flexDirection: 'column' }}>
                {/* Players + 对局信息 */}
                <Box sx={sectionSx}>
                    <Stack direction="row" spacing={1} data-testid="player-card-row" sx={{ minWidth: 0 }}>
                        <PlayerCard
                            player="B"
                            info={gameState.players_info.B}
                            captures={gameState.prisoner_count.B}
                            active={gameState.player_to_move === 'B'}
                            timer={gameState.timer}
                            onPauseTimer={onPauseTimer}
                            onPlaySound={onPlaySound}
                            onTimeout={gameState.player_to_move === 'B' ? onTimeout : undefined}
                            showFollowButton={gameState.players_info.B.player_type === 'human' && gameState.players_info.B.name !== user?.username}
                            isFollowed={followingNames.has(gameState.players_info.B.name)}
                            onToggleFollow={() => handleToggleFollow(gameState.players_info.B.name)}
                        />
                        <PlayerCard
                            player="W"
                            info={gameState.players_info.W}
                            captures={gameState.prisoner_count.W}
                            active={gameState.player_to_move === 'W'}
                            timer={gameState.timer}
                            onPauseTimer={onPauseTimer}
                            onPlaySound={onPlaySound}
                            onTimeout={gameState.player_to_move === 'W' ? onTimeout : undefined}
                            showFollowButton={gameState.players_info.W.player_type === 'human' && gameState.players_info.W.name !== user?.username}
                            isFollowed={followingNames.has(gameState.players_info.W.name)}
                            onToggleFollow={() => handleToggleFollow(gameState.players_info.W.name)}
                        />
                    </Stack>
                    {/* 规则 / 贴目 / 观众数。棋盘上方原来那条横栏取消后，观众数降到这里 —— 它是
                        对局的属性，不是页面的标题栏内容。 */}
                    <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mt: 1.25, gap: 1 }}>
                        <Typography variant="caption" color="text.secondary" noWrap sx={{ minWidth: 0 }}>
                            {t(gameState.ruleset, gameState.ruleset.charAt(0).toUpperCase() + gameState.ruleset.slice(1))} {t('Rules', 'Rules')} · {t('Komi', 'Komi')} {gameState.komi}
                        </Typography>
                        {spectatorCount !== undefined && (
                            <Stack direction="row" alignItems="center" spacing={0.5} sx={{ flex: 'none' }}>
                                <VisibilityIcon sx={{ fontSize: 14, color: 'text.disabled' }} />
                                <Typography variant="caption" color="text.disabled">
                                    {spectatorCount} {t('Spectators', 'Spectators')}
                                </Typography>
                            </Stack>
                        )}
                    </Stack>
                </Box>

                {/* 工具格 + 离开对局 */}
                <Box sx={sectionSx}>
                    <Box sx={toolGridSx}>
                        <ToolGridButton
                            icon={<MapIcon />}
                            label={t('Territory', 'Territory')}
                            tooltip={analysisTooltip}
                            toggle
                            active={analysisToggles.ownership}
                            onClick={() => onToggleChange('ownership')}
                            disabled={!canShowAnalysis}
                        />
                        <ToolGridButton
                            icon={<TipsAndUpdatesIcon />}
                            label={t('Advice', 'Advice')}
                            tooltip={analysisTooltip}
                            toggle
                            active={analysisToggles.hints}
                            onClick={() => onToggleChange('hints')}
                            disabled={!canShowAnalysis}
                            loading={isAnalysisPending && analysisToggles.hints}
                        />
                        <ToolGridButton
                            icon={<TimelineIcon />}
                            label={t('Graph', 'Graph')}
                            tooltip={analysisTooltip}
                            toggle
                            active={analysisToggles.score}
                            onClick={() => onToggleChange('score')}
                            disabled={!canShowAnalysis}
                        />
                        <ToolGridButton
                            icon={<UndoIcon />}
                            label={t('Undo', 'Undo')}
                            onClick={() => onAction('undo')}
                            disabled={isGameOver || locked || isSpectator}
                        />
                        <ToolGridButton
                            icon={<PanToolAltIcon />}
                            label={t('PASS', 'Pass')}
                            onClick={() => onAction('pass')}
                            disabled={isGameOver || isSpectator}
                        />
                        <ToolGridButton
                            icon={<FlagIcon />}
                            label={t('RESIGN', 'Resign')}
                            onClick={() => onAction('resign')}
                            disabled={isGameOver || isSpectator}
                            isDestructive
                        />
                        <ToolGridButton
                            icon={<CalculateIcon />}
                            label={t('COUNT', 'Count')}
                            onClick={() => onAction('count')}
                            disabled={isGameOver || isSpectator || gameState.history.length < (gameState.count_min_moves ?? 100)}
                        />
                        <ToolGridButton
                            icon={<ViewInArIcon />}
                            label={t('3D', '3D')}
                            toggle
                            active={analysisToggles.view3d}
                            onClick={() => onToggleChange('view3d')}
                        />
                    </Box>
                    {isRated && !isGameOver && (
                        <Typography variant="caption" color="error" sx={{ display: 'block', mt: 1, textAlign: 'center' }}>
                            {t('items_disabled_rated', 'Items disabled during Rated Game')}
                        </Typography>
                    )}
                    {/* 悬浮提示在触屏上是够不着的，所以那句话也要落在屏上一次。
                        与升降级那条同一个位置、同一种排版，只是不是错误色 —— 它不是故障。 */}
                    {analysisRequiresLogin && (
                        <Typography
                            data-testid="analysis-requires-login"
                            variant="caption"
                            color="text.secondary"
                            sx={{ display: 'block', mt: 1, textAlign: 'center' }}
                        >
                            {t('play:analysis_requires_login_hint', '领地 / 支招 / 图表 登录后可用')}
                        </Typography>
                    )}
                    {resultAlert && <Box sx={{ mt: 1.25 }}>{resultAlert}</Box>}
                    {onLeave && (
                        <Button
                            fullWidth
                            variant="outlined"
                            color={isSpectator ? 'inherit' : 'error'}
                            startIcon={<ExitToAppIcon />}
                            onClick={onLeave}
                            sx={{
                                mt: 1.25,
                                textTransform: 'none',
                                ...(isSpectator ? { borderColor: 'rgba(255,255,255,0.3)', color: 'text.secondary' } : {}),
                            }}
                        >
                            {isSpectator
                                ? t('game_room:exit_spectating', '退出观战')
                                : t('game_room:leave_game', '离开对局')}
                        </Button>
                    )}
                </Box>

                {/* Score Graph */}
                {analysisToggles.score && canShowAnalysis && (
                    <Box sx={{ ...sectionSx, py: 1, bgcolor: 'rgba(0,0,0,0.1)' }}>
                        <ScoreGraph
                            gameState={gameState}
                            onNavigate={onNavigate}
                            showScore={analysisToggles.score}
                            showWinrate={analysisToggles.winrate}
                        />
                    </Box>
                )}

                {/* Other Settings */}
                {/* 显示开关。冻结稿把它们做成**整行** —— 文字靠左、开关靠右、一行一个。
                    原来是 MUI 的默认排布（开关在前、文字在后、并排挤成一行），
                    320 右栏下两个开关会挨在一起，读起来像一个控件的两半。

                    2026-08-30 右栏加宽后补 `auto-fit`：整行排布在 520 档下会把标签和
                    滑块拉开近 480px，读起来不再像一个控件。`minmax(200px, 1fr)` 让它
                    **只在装得下两列时**才分两列——320/360/420 三档可用宽分别是
                    288/328/388，都小于 400，排布与加宽之前逐像素一致；520 档可用 488，
                    分成两列各 244，标签与滑块重新贴在一起。 */}
                <Box sx={{ py: 2, ...railToggleGroupSx }}>
                    {([
                        ['coords', t('Coordinates', 'Coordinates'), analysisToggles.coords, true],
                        ['numbers', t('Move Numbers', 'Move Numbers'), analysisToggles.numbers, true],
                        ['stoneDropEffect', t('Stone Effect', '落子特效'), !!analysisToggles.stoneDropEffect, !!analysisToggles.view3d],
                    ] as [string, string, boolean, boolean][]).filter(([, , , shown]) => shown).map(([key, label, checked]) => (
                        <FormControlLabel
                            key={key}
                            labelPlacement="start"
                            sx={{ ml: 0, mr: 0, width: '100%', justifyContent: 'space-between' }}
                            control={<Switch size="small" checked={checked} onChange={() => onToggleChange(key)} />}
                            label={<Typography variant="body2">{label}</Typography>}
                        />
                    ))}
                </Box>

                {/* Game Result Progress (If Rated).
                    Gated on the game still being in play: this banner says "进行中", and once
                    end_result is set that is simply false -- the settlement Alert above is what
                    reports the finished game. Leaving it up meant a resigned game still claimed
                    to be running. */}
                {isRated && !gameState.end_result && (
                    <Box sx={{ py: 2, textAlign: 'center', bgcolor: 'primary.dark' }}>
                        <Typography variant="subtitle2" sx={{ color: '#fff' }}>
                            {t('rated_mode_active', 'Rated Mode: Progressing')}
                        </Typography>
                        <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.7)' }}>
                            {t('rated_mode_desc', 'Net wins tracked for rank update')}
                        </Typography>
                    </Box>
                )}
            </Box>

            {/* 旧版式（人机自由对局）里翻手那一行仍然自带；统一版式下它归动作区。 */}
            {!embedded && <RightSidebarActions onAction={onAction} isGameOver={isGameOver} />}
        </Box>
    );
};

/**
 * 右栏动作区：前后翻手那六个键。
 *
 * 拆成具名导出，是因为统一版式的右栏分三段，**动作区不跟着滚**
 * （`BoardPageShell` 的 `board-rail-actions`）。留在面板里它就沉在滚动段的最底下，
 * 长盘时要滚到底才够得着 —— 升降级对弈页今天正是这样。
 *
 * 六个键原来**一个可及名都没有**（纯图标 `IconButton`，无 aria-label、无 Tooltip），
 * 控件账本把它们整整记成六个空按钮。名字按冻结稿补齐。
 */
export const RightSidebarActions = ({ onAction, isGameOver }: {
    onAction: (action: string) => void;
    isGameOver: boolean;
}) => {
    const { t } = useTranslation();
    const iconButtonStyle = {
        color: 'text.secondary',
        '&:hover': { color: 'text.primary', bgcolor: 'rgba(255,255,255,0.05)' },
    };
    const keys: [string, string, string, ReactNode][] = [
        ['start', 'game:nav_first', '跳到开局', <SkipPreviousIcon key="i" />],
        ['back-10', 'game:nav_back_10', '后退 10 手', <FastRewindIcon key="i" />],
        ['back', 'game:nav_back', '后退一手', <ArrowBackIcon key="i" />],
        ['forward', 'game:nav_forward', '前进一手', <ArrowForwardIcon key="i" />],
        ['forward-10', 'game:nav_forward_10', '前进 10 手', <FastForwardIcon key="i" />],
        ['end', 'game:nav_last', '跳到最后', <SkipNextIcon key="i" />],
    ];
    return (
        <Box sx={{ py: 1.25, bgcolor: '#1a1a1a', borderTop: '1px solid', borderColor: 'divider' }}>
            <Stack direction="row" justifyContent="center" spacing={0.5}>
                {keys.map(([action, key, fallback, icon]) => {
                    const name = t(key, fallback);
                    return (
                        /* Tooltip 只在键可用时挂 —— 死键上挂个复读标签没有意义，
                           和 ToolGridButton 的口径一致。可及名两种状态下都在。 */
                        <Tooltip key={action} title={isGameOver ? name : ''}>
                            <span>
                                <IconButton
                                    size="small"
                                    aria-label={name}
                                    onClick={() => onAction(action)}
                                    disabled={!isGameOver}
                                    sx={isGameOver ? iconButtonStyle : { color: 'text.disabled' }}
                                >
                                    {icon}
                                </IconButton>
                            </span>
                        </Tooltip>
                    );
                })}
            </Stack>
        </Box>
    );
};

export default RightSidebarPanel;
