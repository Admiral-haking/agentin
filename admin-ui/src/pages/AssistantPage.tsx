import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Box,
  Button,
  Chip,
  Divider,
  FormControl,
  InputLabel,
  LinearProgress,
  List,
  ListItemButton,
  ListItemText,
  MenuItem,
  Paper,
  Select,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import AutoAwesomeRoundedIcon from '@mui/icons-material/AutoAwesomeRounded';
import { Link } from 'react-router-dom';
import { Title } from 'react-admin';
import { fetchWithAuth } from '../authProvider';

const DEFAULT_API_URL = import.meta.env.DEV
  ? 'http://localhost:8000'
  : 'https://api.teamcore.ir';
const API_URL = import.meta.env.VITE_API_URL || DEFAULT_API_URL;

type AssistantMode = 'hybrid' | 'openai' | 'deepseek';

type AssistantConversation = {
  id: number;
  title?: string | null;
  context?: string | null;
  mode?: AssistantMode | null;
  last_message_at?: string | null;
  updated_at?: string | null;
};

type AssistantMessage = {
  id?: number | string;
  role: 'user' | 'assistant';
  content: string;
  provider?: string | null;
  created_at?: string | null;
};

type AssistantActionSuggestion = {
  action_type: string;
  summary?: string;
  payload?: Record<string, unknown>;
};

const buildId = () => `${Date.now()}-${Math.random().toString(16).slice(2)}`;

const formatTime = (value?: string | null) => {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleString('fa-IR', { timeZone: 'Asia/Tehran' });
};

const extractActionSuggestion = (text: string): AssistantActionSuggestion | null => {
  const match = text.match(/```json\s*([\s\S]*?)```/i);
  if (!match) return null;
  try {
    const parsed = JSON.parse(match[1]);
    if (!parsed?.action_type) return null;
    return {
      action_type: String(parsed.action_type),
      summary: parsed.summary ? String(parsed.summary) : undefined,
      payload: parsed.payload && typeof parsed.payload === 'object' ? parsed.payload : undefined,
    };
  } catch {
    return null;
  }
};

export const AssistantPage = () => {
  const [conversations, setConversations] = useState<AssistantConversation[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<number | null>(null);
  const [messages, setMessages] = useState<AssistantMessage[]>([]);
  const [title, setTitle] = useState('');
  const [context, setContext] = useState('');
  const [mode, setMode] = useState<AssistantMode>('hybrid');
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionSuggestion, setActionSuggestion] = useState<AssistantActionSuggestion | null>(null);
  const [pendingActions, setPendingActions] = useState<number>(0);

  const bottomRef = useRef<HTMLDivElement | null>(null);

  const downloadExport = async (
    format: 'json' | 'csv',
    exportType: 'messages' | 'actions' | 'conversations' | 'training',
    scope: 'session' | 'all'
  ) => {
    setLoading(true);
    setError(null);
    try {
      const url = new URL(`${API_URL}/admin/assistant/export`);
      url.searchParams.set('format', format);
      url.searchParams.set('type', exportType);
      if (scope === 'session' && activeConversationId) {
        url.searchParams.set('conversation_id', String(activeConversationId));
      }
      const response = await fetchWithAuth(url.toString());
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data?.detail || 'Unable to export history.');
      }
      const blob = await response.blob();
      const filenameBase =
        scope === 'session' && activeConversationId
          ? `assistant_${activeConversationId}`
          : 'assistant_all';
      const extension = format === 'json' ? 'json' : 'csv';
      const filename = `${filenameBase}_${exportType}.${extension}`;
      const blobUrl = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = blobUrl;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(blobUrl);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unable to export history.';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const messageCount = useMemo(() => messages.length, [messages]);
  const modeLabels: Record<AssistantMode, string> = {
    hybrid: 'هیبرید',
    openai: 'OpenAI',
    deepseek: 'DeepSeek',
  };

  const loadConversations = async () => {
    try {
      const query = new URLSearchParams({
        skip: '0',
        limit: '50',
        sort: 'updated_at',
        order: 'desc',
      });
      const response = await fetchWithAuth(
        `${API_URL}/admin/assistant/conversations?${query}`
      );
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data?.detail || 'Unable to load conversations.');
      }
      setConversations(data.data || []);
      if (!activeConversationId && data.data?.length) {
        setActiveConversationId(data.data[0].id);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unable to load conversations.';
      setError(message);
    }
  };

  const loadPendingActions = async () => {
    try {
      const query = new URLSearchParams({
        skip: '0',
        limit: '1',
        sort: 'created_at',
        order: 'desc',
        filter: JSON.stringify({ status: 'pending' }),
      });
      const response = await fetchWithAuth(`${API_URL}/admin/assistant/actions?${query}`);
      const data = await response.json();
      if (response.ok) {
        setPendingActions(data.total || 0);
      }
    } catch {
      setPendingActions(0);
    }
  };

  const loadConversation = async (conversationId: number) => {
    setLoading(true);
    setError(null);
    try {
      const [conversationRes, messagesRes] = await Promise.all([
        fetchWithAuth(`${API_URL}/admin/assistant/conversations/${conversationId}`),
        fetchWithAuth(
          `${API_URL}/admin/assistant/conversations/${conversationId}/messages?skip=0&limit=300&sort=created_at&order=asc`
        ),
      ]);
      const conversationData = await conversationRes.json();
      const messagesData = await messagesRes.json();
      if (!conversationRes.ok) {
        throw new Error(conversationData?.detail || 'Unable to load conversation.');
      }
      if (!messagesRes.ok) {
        throw new Error(messagesData?.detail || 'Unable to load messages.');
      }
      setTitle(conversationData?.title || '');
      setContext(conversationData?.context || '');
      if (conversationData?.mode) {
        setMode(conversationData.mode);
      }
      setMessages(messagesData.data || []);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unable to load conversation.';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const startNewSession = () => {
    setActiveConversationId(null);
    setMessages([]);
    setTitle('');
    setContext('');
    setMode('hybrid');
    setActionSuggestion(null);
  };

  const saveConversation = async () => {
    if (!activeConversationId) return;
    setLoading(true);
    setError(null);
    try {
      const response = await fetchWithAuth(
        `${API_URL}/admin/assistant/conversations/${activeConversationId}`,
        {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            title: title.trim() || null,
            context: context.trim() || null,
            mode,
          }),
        }
      );
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data?.detail || 'Unable to save conversation.');
      }
      await loadConversations();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unable to save conversation.';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const sendMessage = async () => {
    const trimmed = input.trim();
    if (!trimmed || loading) return;

    const tempUserMessage: AssistantMessage = {
      id: buildId(),
      role: 'user',
      content: trimmed,
    };
    setMessages(prev => [...prev, tempUserMessage]);
    setInput('');
    setLoading(true);
    setError(null);

    try {
      const response = await fetchWithAuth(`${API_URL}/admin/assistant/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          conversation_id: activeConversationId || undefined,
          title: title.trim() || undefined,
          context: context.trim() || undefined,
          mode,
          messages: [{ role: 'user', content: trimmed }],
        }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data?.detail || data?.error || 'Unable to reach the assistant.');
      }

      const assistantMessage: AssistantMessage = {
        id: buildId(),
        role: 'assistant',
        content: data.reply || 'No response returned.',
        provider: data.provider,
      };
      setMessages(prev => [...prev, assistantMessage]);
      if (!activeConversationId && data.conversation_id) {
        setActiveConversationId(data.conversation_id);
      }
      await loadConversations();
      await loadPendingActions();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unable to reach the assistant.';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const queueAction = async () => {
    if (!actionSuggestion) return;
    setLoading(true);
    setError(null);
    try {
      const response = await fetchWithAuth(`${API_URL}/admin/assistant/actions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          conversation_id: activeConversationId || undefined,
          action_type: actionSuggestion.action_type,
          summary: actionSuggestion.summary || 'Assistant proposed change',
          payload: actionSuggestion.payload || {},
        }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data?.detail || 'Unable to queue action.');
      }
      setActionSuggestion(null);
      await loadPendingActions();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unable to queue action.';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadConversations();
    loadPendingActions();
  }, []);

  useEffect(() => {
    if (activeConversationId) {
      loadConversation(activeConversationId);
    }
  }, [activeConversationId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages, loading]);

  useEffect(() => {
    const lastAssistant = [...messages].reverse().find(msg => msg.role === 'assistant');
    if (lastAssistant?.content) {
      setActionSuggestion(extractActionSuggestion(lastAssistant.content));
    } else {
      setActionSuggestion(null);
    }
  }, [messages]);

  const handleKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) {
      event.preventDefault();
      sendMessage();
    }
  };

  const quickPrompts = [
    'خلاصه پیام‌های امروز را بده و موارد فوری را مشخص کن.',
    'برای اختلال یا کندی API یک برنامه پاسخ آماده کن.',
    'چک‌لیست استقرار امشب را بساز.',
    'اقدام‌های بعدی برای بهتر شدن پاسخ‌ها را پیشنهاد بده.',
  ];

  return (
    <Box sx={{ px: { xs: 2, md: 3 }, py: 2 }}>
      <Title title="دستیار هوشمند" />
      <Stack spacing={2} sx={{ mb: 3 }}>
        <Typography variant="h4">دستیار هوشمند</Typography>
        <Typography variant="body1" color="text.secondary">
          برای برنامه‌ریزی، تصمیم‌گیری و عیب‌یابی از دستیار استفاده کنید.
        </Typography>
      </Stack>

      <Box
        sx={{
          display: 'grid',
          gap: 2,
          gridTemplateColumns: { xs: '1fr', lg: '2fr 1fr' },
          alignItems: 'start',
        }}
      >
        <Paper sx={{ p: { xs: 2, md: 3 }, minHeight: 520 }}>
          <Stack spacing={2} sx={{ height: '100%' }}>
            <Stack direction="row" spacing={1} alignItems="center" justifyContent="space-between">
              <Stack direction="row" spacing={1} alignItems="center">
                <AutoAwesomeRoundedIcon color="primary" />
                <Typography variant="h6">گفتگو</Typography>
              </Stack>
              <Stack direction="row" spacing={1} alignItems="center">
                <Chip label={`${messageCount} پیام`} size="small" />
                <Chip label={modeLabels[mode]} size="small" color="primary" />
              </Stack>
            </Stack>
            <Divider />
            <Box
              sx={{
                flex: 1,
                overflowY: 'auto',
                pr: 1,
                display: 'flex',
                flexDirection: 'column',
                gap: 1.5,
                maxHeight: { xs: 360, md: 420 },
              }}
            >
              {messages.length === 0 && (
                <Paper
                  variant="outlined"
                  sx={{ p: 2, bgcolor: 'rgba(15,139,141,0.08)', borderStyle: 'dashed' }}
                >
                  <Typography variant="body2" color="text.secondary">
                    اول زمینه و هدف را بنویس، بعد سؤال یا اقدام موردنظر را ارسال کن.
                  </Typography>
                </Paper>
              )}
              {messages.map(message => (
                <Box
                  key={message.id}
                  sx={{
                    display: 'flex',
                    justifyContent: message.role === 'user' ? 'flex-end' : 'flex-start',
                  }}
                >
                  <Paper
                    elevation={0}
                    sx={{
                      p: 1.5,
                      maxWidth: '80%',
                      bgcolor:
                        message.role === 'user'
                          ? 'rgba(15,139,141,0.14)'
                          : 'rgba(255,255,255,0.92)',
                      border: '1px solid rgba(18,22,33,0.08)',
                    }}
                  >
                    <Stack spacing={0.5}>
                      <Typography
                        variant="body2"
                        component="div"
                        dir="auto"
                        sx={{ whiteSpace: 'pre-wrap', textAlign: 'start' }}
                      >
                        {message.content}
                      </Typography>
                      {message.provider && message.role === 'assistant' && (
                        <Chip
                          label={`از ${message.provider}`}
                          size="small"
                          sx={{ alignSelf: 'flex-start' }}
                        />
                      )}
                      {message.created_at && (
                        <Typography variant="caption" color="text.secondary">
                          {formatTime(message.created_at)}
                        </Typography>
                      )}
                    </Stack>
                  </Paper>
                </Box>
              ))}
              <div ref={bottomRef} />
            </Box>
            {loading && <LinearProgress />}
            {error && (
              <Paper variant="outlined" sx={{ p: 1.5, borderColor: 'error.light' }}>
                <Typography variant="body2" color="error">
                  {error}
                </Typography>
              </Paper>
            )}
            {actionSuggestion && (
              <Paper variant="outlined" sx={{ p: 1.5, borderStyle: 'dashed' }}>
                <Stack spacing={1}>
                  <Typography variant="body2">
                    پیشنهاد اقدام: <strong>{actionSuggestion.action_type}</strong>
                  </Typography>
                  {actionSuggestion.summary && (
                    <Typography variant="caption" color="text.secondary">
                      {actionSuggestion.summary}
                    </Typography>
                  )}
                  <Button variant="contained" color="primary" onClick={queueAction} disabled={loading}>
                    در صف تایید بگذار
                  </Button>
                </Stack>
              </Paper>
            )}
            <Stack spacing={1}>
              <TextField
                value={input}
                onChange={event => setInput(event.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="پیام خود را بنویسید (Ctrl/Cmd + Enter برای ارسال)"
                multiline
                minRows={3}
                fullWidth
                sx={{
                  '& .MuiInputBase-input': {
                    direction: 'rtl',
                    textAlign: 'right',
                    lineHeight: 1.8,
                  },
                }}
              />
              <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1} justifyContent="space-between">
                <Button variant="text" color="secondary" onClick={startNewSession}>
                  گفتگوی جدید
                </Button>
                <Button
                  variant="contained"
                  color="primary"
                  onClick={sendMessage}
                  disabled={loading || !input.trim()}
                >
                  ارسال
                </Button>
              </Stack>
            </Stack>
          </Stack>
        </Paper>

        <Stack spacing={2}>
          <Paper sx={{ p: { xs: 2, md: 3 } }}>
            <Stack spacing={2}>
              <Typography variant="h6">جزئیات گفتگو</Typography>
              <TextField
                value={title}
                onChange={event => setTitle(event.target.value)}
                label="عنوان گفتگو"
                fullWidth
                sx={{
                  '& .MuiInputBase-input': {
                    direction: 'rtl',
                    textAlign: 'right',
                  },
                }}
              />
              <TextField
                value={context}
                onChange={event => setContext(event.target.value)}
                placeholder="اهداف، محدودیت‌ها یا تصمیم‌های اخیر."
                multiline
                minRows={4}
                fullWidth
                sx={{
                  '& .MuiInputBase-input': {
                    direction: 'rtl',
                    textAlign: 'right',
                    lineHeight: 1.8,
                  },
                }}
              />
              <FormControl fullWidth>
                <InputLabel id="assistant-mode-label">حالت هوش مصنوعی</InputLabel>
                <Select
                  labelId="assistant-mode-label"
                  label="حالت هوش مصنوعی"
                  value={mode}
                  onChange={event => setMode(event.target.value as AssistantMode)}
                >
                  <MenuItem value="hybrid">هیبرید</MenuItem>
                  <MenuItem value="openai">OpenAI</MenuItem>
                  <MenuItem value="deepseek">DeepSeek</MenuItem>
                </Select>
              </FormControl>
              <Button variant="outlined" onClick={saveConversation} disabled={loading || !activeConversationId}>
                ذخیره گفتگو
              </Button>
            </Stack>
          </Paper>

          <Paper sx={{ p: { xs: 2, md: 3 } }}>
            <Stack spacing={1.5}>
              <Stack direction="row" spacing={1} alignItems="center" justifyContent="space-between">
                <Typography variant="h6">گفتگوها</Typography>
                <Chip label={`${conversations.length}`} size="small" />
              </Stack>
              <List dense sx={{ maxHeight: 220, overflow: 'auto' }}>
                {conversations.map(conversation => (
                  <ListItemButton
                    key={conversation.id}
                    selected={conversation.id === activeConversationId}
                    onClick={() => setActiveConversationId(conversation.id)}
                  >
                    <ListItemText
                      primary={conversation.title || `Session #${conversation.id}`}
                      secondary={formatTime(conversation.last_message_at || conversation.updated_at)}
                    />
                  </ListItemButton>
                ))}
                {conversations.length === 0 && (
                  <Typography variant="body2" color="text.secondary">
                    هنوز گفتگویی ثبت نشده.
                  </Typography>
                )}
              </List>
            </Stack>
          </Paper>

          <Paper sx={{ p: { xs: 2, md: 3 } }}>
            <Stack spacing={1.5}>
              <Stack direction="row" spacing={1} alignItems="center" justifyContent="space-between">
                <Typography variant="h6">تاییدیه‌ها</Typography>
                <Chip label={`${pendingActions} در انتظار`} size="small" color="warning" />
              </Stack>
              <Typography variant="body2" color="text.secondary">
                تغییرات پیشنهادی دستیار را قبل از اعمال بررسی کنید.
              </Typography>
              <Button component={Link} to="/assistant/actions" variant="contained" color="primary">
                مشاهده تاییدیه‌ها
              </Button>
            </Stack>
          </Paper>

          <Paper sx={{ p: { xs: 2, md: 3 } }}>
            <Stack spacing={1.5}>
              <Typography variant="h6">پیشنهادهای سریع</Typography>
              <Typography variant="body2" color="text.secondary">
                با کلیک روی هر مورد، متن آن در کادر پیام قرار می‌گیرد.
              </Typography>
              <Stack spacing={1}>
                {quickPrompts.map(prompt => (
                  <Button
                    key={prompt}
                    variant="outlined"
                    color="primary"
                    onClick={() => setInput(prompt)}
                    sx={{ justifyContent: 'flex-start' }}
                  >
                    {prompt}
                  </Button>
                ))}
              </Stack>
            </Stack>
          </Paper>

          <Paper sx={{ p: { xs: 2, md: 3 } }}>
            <Stack spacing={1.5}>
              <Typography variant="h6">خروجی تاریخچه</Typography>
              <Typography variant="body2" color="text.secondary">
                تاریخچه دستیار را برای آموزش یا آرشیو دانلود کنید.
              </Typography>
              <Stack spacing={1}>
                <Button
                  variant="contained"
                  color="primary"
                  onClick={() => downloadExport('json', 'training', 'all')}
                  disabled={loading}
                >
                  دانلود JSON آموزشی
                </Button>
                <Button
                  variant="outlined"
                  color="primary"
                  onClick={() => downloadExport('json', 'messages', 'all')}
                  disabled={loading}
                >
                  دانلود همه (JSON)
                </Button>
                <Button
                  variant="outlined"
                  color="primary"
                  onClick={() => downloadExport('csv', 'messages', 'all')}
                  disabled={loading}
                >
                  دانلود همه (CSV)
                </Button>
                <Button
                  variant="outlined"
                  color="secondary"
                  onClick={() => downloadExport('json', 'messages', 'session')}
                  disabled={loading || !activeConversationId}
                >
                  دانلود همین گفتگو (JSON)
                </Button>
                <Button
                  variant="outlined"
                  color="secondary"
                  onClick={() => downloadExport('csv', 'messages', 'session')}
                  disabled={loading || !activeConversationId}
                >
                  دانلود همین گفتگو (CSV)
                </Button>
              </Stack>
            </Stack>
          </Paper>
        </Stack>
      </Box>
    </Box>
  );
};
