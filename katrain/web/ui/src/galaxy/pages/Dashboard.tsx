import { Box, Card, Typography, CardActionArea } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import SportsEsportsIcon from '@mui/icons-material/SportsEsports';
import ScienceIcon from '@mui/icons-material/Science';
import AssessmentIcon from '@mui/icons-material/Assessment';
import LiveTvIcon from '@mui/icons-material/LiveTv';
import ExtensionIcon from '@mui/icons-material/Extension';
import { useSettings } from '../../context/SettingsContext';
import { i18n } from '../../i18n';

const ModuleCard = ({ title, desc, icon, path, disabled }: any) => {
    const navigate = useNavigate();
    return (
        <Card sx={{ height: '100%', bgcolor: 'background.paper', opacity: disabled ? 0.5 : 1 }}>
            <CardActionArea 
                disabled={disabled} 
                onClick={() => navigate(path)} 
                sx={{ height: '100%', p: 3, display: 'flex', flexDirection: 'column', alignItems: 'flex-start', justifyContent: 'flex-start' }}
            >
                <Box sx={{ p: 1.5, borderRadius: 2, bgcolor: disabled ? 'action.disabledBackground' : 'primary.dark', color: disabled ? 'text.disabled' : 'primary.contrastText', mb: 2 }}>
                    {icon}
                </Box>
                <Typography variant="h5" gutterBottom fontWeight="bold">
                    {title}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                    {desc}
                </Typography>
            </CardActionArea>
        </Card>
    );
}

const Dashboard = () => {
    useSettings(); // Subscribe to translation changes for re-render
    const modules = [
        { 
            title: i18n.t('btn:Play', 'Play'), 
            desc: i18n.t('dashboard:play_desc', "Challenge AI opponents or play against friends. Features Rated games to establish your rank."), 
            icon: <SportsEsportsIcon fontSize="large"/>, 
            path: "/galaxy/play" 
        },
        { 
            title: i18n.t('Research', 'Research'), 
            desc: i18n.t('dashboard:research_desc', "Analyze games with AI, explore variations, and manage your SGF library."), 
            icon: <ScienceIcon fontSize="large"/>, 
            path: "/galaxy/research" 
        },
        { 
            title: i18n.t('analysis:report', 'Report'), 
            desc: i18n.t('dashboard:report_desc', "Detailed game reports and style analysis. (Coming Soon)"), 
            icon: <AssessmentIcon fontSize="large"/>, 
            path: "/galaxy/report",
            disabled: true 
        },
        {
            title: i18n.t('Live', 'Live'),
            desc: i18n.t('dashboard:live_desc', "Watch top games and live tournaments with AI analysis."),
            icon: <LiveTvIcon fontSize="large"/>,
            path: "/galaxy/live"
        },
        {
            title: i18n.t('Tsumego', 'Tsumego'),
            desc: i18n.t('dashboard:tsumego_desc', "Practice life and death problems to sharpen your reading skills."),
            icon: <ExtensionIcon fontSize="large"/>,
            path: "/galaxy/tsumego"
        }
    ];

    return (
        <Box sx={{ p: 6, maxWidth: 1200, mx: 'auto', width: '100%', overflow: 'auto' }}>
            <Box sx={{ mb: 6 }}>
                <Typography variant="h3" fontWeight="800" gutterBottom sx={{ background: 'linear-gradient(45deg, #4a6b5c 30%, #5d8270 90%)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
                    {i18n.t('dashboard:welcome', 'Welcome to Galaxy Go')}
                </Typography>
                <Typography variant="h6" color="text.secondary">
                    {i18n.t('dashboard:tagline', 'Your professional Go training and analysis platform.')}
                </Typography>
            </Box>

            <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 4 }}>
                {modules.map((m) => (
                    <ModuleCard key={m.title} {...m} />
                ))}
            </Box>
        </Box>
    );
};

export default Dashboard;