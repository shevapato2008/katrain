import { Box, Card, CardContent, Typography, CardActionArea } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import SportsEsportsIcon from '@mui/icons-material/SportsEsports';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import PersonIcon from '@mui/icons-material/Person';
import LockIcon from '@mui/icons-material/Lock';
import { i18n } from '../../../i18n';

const PlayMenu = () => {
    const navigate = useNavigate();

    const options = [
        {
            title: i18n.t('play:vs_ai_free', "Play vs AI (Free)"),
            desc: i18n.t('play:vs_ai_free_desc', "Practice with full analysis, undo, and custom settings."),
            icon: <SmartToyIcon sx={{ fontSize: 60, color: 'primary.main' }} />,
            path: '/galaxy/play/ai?mode=free',
            disabled: false
        },
        {
            title: i18n.t('play:rated_ai', "Rated Game vs AI"),
            desc: i18n.t('play:rated_ai_desc', "Play a ranked game against a human-like AI. No analysis during game."),
            icon: <SportsEsportsIcon sx={{ fontSize: 60, color: 'secondary.main' }} />,
            path: '/galaxy/play/ai?mode=rated',
            disabled: false
        },
        {
            title: i18n.t('play:hvh', "Human vs Human"),
            desc: i18n.t('play:hvh_desc', "Challenge a friend or find an opponent online."),
            icon: <PersonIcon sx={{ fontSize: 60, color: 'text.secondary' }} />,
            path: '/galaxy/play/human',
            disabled: false
        }
    ];

    return (
        <Box sx={{ p: 4, maxWidth: 1200, mx: 'auto' }}>
            <Typography variant="h4" sx={{ mb: 1, fontWeight: 'bold' }}>{i18n.t('btn:Play', 'Play')}</Typography>
            <Typography variant="subtitle1" color="text.secondary" sx={{ mb: 6 }}>
                {i18n.t('play:choose_mode', 'Choose your game mode')}
            </Typography>

            <Box sx={{ 
                display: 'grid', 
                gridTemplateColumns: { xs: '1fr', md: '1fr 1fr 1fr' }, 
                gap: 4 
            }}>
                {options.map((opt) => (
                    <Card 
                        key={opt.title}
                        sx={{ 
                            height: '100%', 
                            borderRadius: 4,
                            position: 'relative',
                            opacity: opt.disabled ? 0.6 : 1,
                            transition: 'transform 0.2s',
                            '&:hover': {
                                transform: opt.disabled ? 'none' : 'translateY(-4px)',
                                boxShadow: opt.disabled ? 1 : 8
                            }
                        }}
                    >
                        <CardActionArea 
                            sx={{ height: '100%', p: 2 }} 
                            onClick={() => !opt.disabled && navigate(opt.path)}
                            disabled={opt.disabled}
                        >
                            <CardContent sx={{ textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2 }}>
                                {opt.icon}
                                <Box>
                                    <Typography variant="h6" fontWeight="bold" gutterBottom>
                                        {opt.title}
                                    </Typography>
                                    <Typography variant="body2" color="text.secondary">
                                        {opt.desc}
                                    </Typography>
                                </Box>
                                {opt.disabled && (
                                    <Box sx={{ position: 'absolute', top: 16, right: 16, color: 'text.disabled' }}>
                                        <LockIcon />
                                    </Box>
                                )}
                            </CardContent>
                        </CardActionArea>
                    </Card>
                ))}
            </Box>
        </Box>
    );
};

export default PlayMenu;
