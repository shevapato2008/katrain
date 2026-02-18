import { useState, useEffect, useRef } from 'react';
import { Box, Typography, TextField, IconButton, List, ListItem, ListItemText } from '@mui/material';
import SendIcon from '@mui/icons-material/Send';
import { useAuth } from '../../../context/AuthContext';

interface ChatMessage {
    sender: string;
    text: string;
    time: number;
}

interface ChatPanelProps {
    messages: ChatMessage[];
    onSendMessage: (text: string, sender: string) => void;
}

const ChatPanel = ({ messages, onSendMessage }: ChatPanelProps) => {
    const { user } = useAuth();
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
            onSendMessage(inputValue.trim(), user?.username || 'Guest');
            setInputValue('');
        }
    };

    return (
        <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', bgcolor: 'background.paper' }}>
            <Box sx={{ p: 1, bgcolor: 'rgba(0,0,0,0.1)', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                <Typography variant="subtitle2" color="text.secondary">Chat</Typography>
            </Box>
            
            <List sx={{ flexGrow: 1, overflow: 'auto', px: 1 }}>
                {messages.map((msg, index) => (
                    <ListItem key={index} alignItems="flex-start" sx={{ py: 0.5 }}>
                        <ListItemText
                            primary={
                                <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                                    <Typography variant="subtitle2" sx={{ color: msg.sender === user?.username ? 'primary.main' : 'text.primary', fontWeight: 'bold' }}>
                                        {msg.sender}
                                    </Typography>
                                    <Typography variant="caption" color="text.secondary">
                                        {new Date(msg.time).toLocaleTimeString()}
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
                    placeholder="Type a message..."
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
