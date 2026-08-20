import { useState, useEffect, useRef } from 'react';
import { Box, Typography, TextField, IconButton, List, ListItem, ListItemText } from '@mui/material';
import SendIcon from '@mui/icons-material/Send';
import { useAuth } from '../../../context/AuthContext';
import { useTranslation } from '../../../hooks/useTranslation';

// wire 契约 `shapes.Chat`：身份两项由**服务端**从会话身份填，客户端传什么都不作数。
// 字段叫 `from_name` **不叫 `sender`** —— 旧版把客户端自报的 `sender` 原样广播，
// 任何拿到 session_id 的登录用户都能冒名发言。
//
// 线上帧里**没有时间戳**（契约只有这三个字段），所以这里不显示时间：拿客户端的收到时刻
// 冒充发送时刻，在乱序或重连补发时就是一句假话，而看的人分辨不出来。
interface ChatMessage {
    from_id: number;
    from_name: string;
    text: string;
}

interface ChatPanelProps {
    messages: ChatMessage[];
    onSendMessage: (text: string) => void;
}

const ChatPanel = ({ messages, onSendMessage }: ChatPanelProps) => {
    const { user } = useAuth();
    const { t } = useTranslation();
    const [inputValue, setInputValue] = useState('');
    const messagesEndRef = useRef<HTMLDivElement>(null);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    const handleSend = () => {
        if (inputValue.trim()) {
            // 只发正文。发送者身份由服务端填 —— 客户端已经无法自称是谁了。
            onSendMessage(inputValue.trim());
            setInputValue('');
        }
    };

    return (
        <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', bgcolor: 'background.paper' }}>
            <Box sx={{ p: 1, bgcolor: 'rgba(0,0,0,0.1)', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                <Typography variant="subtitle2" color="text.secondary">{t('chat:title', '聊天')}</Typography>
            </Box>
            
            <List sx={{ flexGrow: 1, overflow: 'auto', px: 1 }}>
                {messages.map((msg, index) => (
                    <ListItem key={index} alignItems="flex-start" sx={{ py: 0.5 }}>
                        <ListItemText
                            primary={
                                <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                                    {/* 认自己用 from_id 不用名字：重名的两个人在名字上分不开，
                                        而 id 是服务端填的、客户端改不动。 */}
                                    <Typography variant="subtitle2" sx={{ color: msg.from_id === user?.id ? 'primary.main' : 'text.primary', fontWeight: 'bold' }}>
                                        {msg.from_name}
                                    </Typography>
                                </Box>
                            }
                            secondary={
                                <Typography variant="body2" color="text.primary" sx={{ wordBreak: 'break-word' }}>
                                    {msg.text}
                                </Typography>
                            }
                        />
                    </ListItem>
                ))}
                <div ref={messagesEndRef} />
            </List>

            <Box sx={{ p: 1, display: 'flex', gap: 1, borderTop: '1px solid rgba(255,255,255,0.05)' }}>
                <TextField
                    size="small"
                    fullWidth
                    placeholder={t('chat:placeholder', '输入消息……')}
                    value={inputValue}
                    onChange={(e) => setInputValue(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && handleSend()}
                    variant="outlined"
                    sx={{ bgcolor: 'rgba(255,255,255,0.05)' }}
                />
                <IconButton onClick={handleSend} color="primary" disabled={!inputValue.trim()}>
                    <SendIcon />
                </IconButton>
            </Box>
        </Box>
    );
};

export default ChatPanel;
