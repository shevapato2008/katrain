import { Box, Card, CardContent, Typography, CardActionArea } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import MenuBookIcon from '@mui/icons-material/MenuBook';
import PsychologyIcon from '@mui/icons-material/Psychology';

const TsumegoHubPage = () => {
    const navigate = useNavigate();

    const options = [
        {
            title: '练习册',
            desc: '按级别分类的死活题练习',
            icon: <MenuBookIcon sx={{ fontSize: 60, color: 'primary.main' }} />,
            path: '/galaxy/tsumego/workbook',
        },
        {
            title: 'AI解题',
            desc: '手动摆放棋子，AI分析最佳着法',
            icon: <PsychologyIcon sx={{ fontSize: 60, color: 'secondary.main' }} />,
            path: '/galaxy/tsumego/ai-solver',
        },
    ];

    return (
        <Box sx={{ p: 4, maxWidth: 1200, mx: 'auto' }}>
            <Typography variant="h4" sx={{ mb: 1, fontWeight: 'bold' }}>死活题</Typography>
            <Typography variant="subtitle1" color="text.secondary" sx={{ mb: 6 }}>
                选择练习模式
            </Typography>

            <Box sx={{
                display: 'grid',
                gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' },
                gap: 4
            }}>
                {options.map((opt) => (
                    <Card
                        key={opt.title}
                        sx={{
                            height: '100%',
                            borderRadius: 4,
                            position: 'relative',
                            transition: 'transform 0.2s',
                            '&:hover': {
                                transform: 'translateY(-4px)',
                                boxShadow: 8
                            }
                        }}
                    >
                        <CardActionArea
                            sx={{ height: '100%', p: 2 }}
                            onClick={() => navigate(opt.path)}
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
                            </CardContent>
                        </CardActionArea>
                    </Card>
                ))}
            </Box>
        </Box>
    );
};

export default TsumegoHubPage;
